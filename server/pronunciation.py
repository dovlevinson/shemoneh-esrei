"""Experimental acoustic pronunciation evidence.

This module is deliberately non-authoritative.  It aligns the expected sound
slots for each ASR-located word to a multilingual CTC model's posterior frames
and returns measurements.  It does not label a pronunciation correct or wrong,
and the API never uses these measurements for routing or progression.
"""

from __future__ import annotations

import math
import os
import time
from typing import Sequence

from .hebrew_g2p import collapse_model_phone, pronunciation_variants


DEFAULT_MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
DEFAULT_MODEL_REVISION = "c43348bbaa5a77692c8e7bf3409d683474fdf2a4"


class PronunciationUnavailable(RuntimeError):
    """Raised when optional model dependencies or usable evidence are absent."""


def _ctc_viterbi(slot_scores, blank_scores, repeat_keys: Sequence[tuple[str, ...]]):
    """Return frame indexes assigned to each expected slot by CTC Viterbi.

    ``slot_scores`` has shape ``[frames, slots]`` and contains log posterior
    mass for each slot's accepted phone set.  The extended path alternates
    blank and slot states.  Direct slot-to-slot transitions are blocked for
    adjacent identical phone sets, matching the CTC repeat rule.
    """

    import numpy as np

    frames, slot_count = slot_scores.shape
    if slot_count == 0:
        return []
    if frames < slot_count:
        raise PronunciationUnavailable("word window has fewer frames than expected sounds")

    state_count = 2 * slot_count + 1
    emissions = np.empty((frames, state_count), dtype=np.float32)
    emissions[:, 0::2] = blank_scores[:, None]
    emissions[:, 1::2] = slot_scores

    negative = -np.inf
    previous = np.full(state_count, negative, dtype=np.float64)
    back = np.full((frames, state_count), -1, dtype=np.int32)
    previous[0] = emissions[0, 0]
    previous[1] = emissions[0, 1]

    for frame in range(1, frames):
        current = np.full(state_count, negative, dtype=np.float64)
        for state in range(state_count):
            candidates = [(previous[state], state)]
            if state:
                candidates.append((previous[state - 1], state - 1))
            if state >= 2 and state % 2 == 1:
                slot_index = state // 2
                if repeat_keys[slot_index] != repeat_keys[slot_index - 1]:
                    candidates.append((previous[state - 2], state - 2))
            score, source = max(candidates, key=lambda item: item[0])
            if math.isfinite(score):
                current[state] = score + emissions[frame, state]
                back[frame, state] = source
        previous = current

    final_candidates = [(previous[state_count - 1], state_count - 1)]
    final_candidates.append((previous[state_count - 2], state_count - 2))
    _score, state = max(final_candidates, key=lambda item: item[0])
    if not math.isfinite(_score):
        raise PronunciationUnavailable("no valid CTC path for the expected sounds")

    states = [0] * frames
    for frame in range(frames - 1, -1, -1):
        states[frame] = state
        if frame:
            state = int(back[frame, state])
            if state < 0:
                raise PronunciationUnavailable("incomplete CTC alignment path")

    assigned = [[] for _ in range(slot_count)]
    for frame, state in enumerate(states):
        if state % 2 == 1:
            assigned[state // 2].append(frame)
    if any(not frames_for_slot for frames_for_slot in assigned):
        raise PronunciationUnavailable("CTC alignment skipped an expected sound")
    return assigned


def _logsumexp_columns(matrix, columns):
    import numpy as np

    selected = matrix[:, columns]
    maximum = selected.max(axis=1)
    return maximum + np.log(np.exp(selected - maximum[:, None]).sum(axis=1))


class CtcPronunciationAssessor:
    mode = "shadow"

    def __init__(self) -> None:
        self.model_id = os.getenv("KRIAH_PRONUNCIATION_MODEL", DEFAULT_MODEL)
        self.revision = os.getenv(
            "KRIAH_PRONUNCIATION_MODEL_REVISION", DEFAULT_MODEL_REVISION
        )
        self.device = os.getenv("KRIAH_PRONUNCIATION_DEVICE", "cpu")
        self.profile = os.getenv("KRIAH_PRONUNCIATION_PROFILE", "mixed")
        self.divine_policy = os.getenv("KRIAH_DIVINE_NAME_POLICY", "both")
        self.padding_seconds = float(os.getenv("KRIAH_PRONUNCIATION_WORD_PADDING", "0.20"))
        self._resources = None

    @property
    def loaded(self) -> bool:
        return self._resources is not None

    def _load(self):
        if self._resources is not None:
            return self._resources
        try:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForCTC, AutoTokenizer
        except ModuleNotFoundError as exc:
            raise PronunciationUnavailable(
                "optional pronunciation dependencies are not installed"
            ) from exc

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.revision,
            do_phonemize=False,
        )
        feature_extractor = AutoFeatureExtractor.from_pretrained(
            self.model_id,
            revision=self.revision,
        )
        model = AutoModelForCTC.from_pretrained(
            self.model_id,
            revision=self.revision,
        ).to(self.device)
        model.eval()

        special_ids = set(getattr(tokenizer, "all_special_ids", []))
        blank_id = getattr(model.config, "pad_token_id", None)
        if blank_id is None:
            blank_id = tokenizer.pad_token_id
        if blank_id is None:
            raise PronunciationUnavailable("CTC model does not declare a blank token")

        buckets: dict[str, list[int]] = {}
        for symbol, token_id in tokenizer.get_vocab().items():
            if token_id in special_ids or token_id == blank_id:
                continue
            collapsed = collapse_model_phone(symbol)
            if collapsed:
                buckets.setdefault(collapsed, []).append(token_id)
        if not buckets:
            raise PronunciationUnavailable("CTC vocabulary produced no supported phone buckets")

        phone_ids = sorted({token_id for ids in buckets.values() for token_id in ids})
        self._resources = {
            "torch": torch,
            "tokenizer": tokenizer,
            "feature_extractor": feature_extractor,
            "model": model,
            "blank_id": int(blank_id),
            "buckets": buckets,
            "phone_ids": phone_ids,
        }
        return self._resources

    @staticmethod
    def _load_audio(path: str, sampling_rate: int):
        try:
            import av
            import numpy as np
        except ModuleNotFoundError as exc:
            raise PronunciationUnavailable("audio decoding dependencies are not installed") from exc

        chunks = []
        with av.open(path) as container:
            if not container.streams.audio:
                raise PronunciationUnavailable("upload contains no audio stream")
            resampler = av.audio.resampler.AudioResampler(
                format="fltp", layout="mono", rate=sampling_rate
            )
            for frame in container.decode(container.streams.audio[0]):
                for resampled in resampler.resample(frame):
                    chunks.append(resampled.to_ndarray().reshape(-1))
            for resampled in resampler.resample(None):
                chunks.append(resampled.to_ndarray().reshape(-1))
        if not chunks:
            raise PronunciationUnavailable("audio decoder returned no samples")
        return np.concatenate(chunks).astype(np.float32, copy=False)

    def _posteriors(self, path: str):
        resources = self._load()
        torch = resources["torch"]
        extractor = resources["feature_extractor"]
        sampling_rate = int(extractor.sampling_rate)
        audio = self._load_audio(path, sampling_rate)
        inputs = extractor(audio, sampling_rate=sampling_rate, return_tensors="pt")
        input_values = inputs.input_values.to(self.device)
        attention_mask = getattr(inputs, "attention_mask", None)
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)
        with torch.inference_mode():
            logits = resources["model"](
                input_values,
                attention_mask=attention_mask,
            ).logits[0]
        return (
            torch.log_softmax(logits, dim=-1).cpu().numpy(),
            len(audio) / sampling_rate,
        )

    def _variant_evidence(self, logpost, frame_offset: int, frame_seconds: float, variant):
        import numpy as np

        resources = self._load()
        slots = list(variant.slots)
        slot_scores = np.empty((logpost.shape[0], len(slots)), dtype=np.float32)
        allowed_ids: list[list[int]] = []
        repeat_keys: list[tuple[str, ...]] = []
        for index, slot in enumerate(slots):
            ids = sorted(
                {
                    token_id
                    for phone in slot.allowed
                    for token_id in resources["buckets"].get(phone, [])
                }
            )
            if not ids:
                raise PronunciationUnavailable(
                    f"model vocabulary has no token for expected phone set {sorted(slot.allowed)}"
                )
            allowed_ids.append(ids)
            repeat_keys.append(tuple(sorted(slot.allowed)))
            slot_scores[:, index] = _logsumexp_columns(logpost, ids)

        blank_scores = logpost[:, resources["blank_id"]]
        assignments = _ctc_viterbi(slot_scores, blank_scores, repeat_keys)
        phone_ids = set(resources["phone_ids"])

        evidence = []
        for index, (slot, assigned_frames) in enumerate(zip(slots, assignments)):
            peak = max(assigned_frames, key=lambda frame: float(slot_scores[frame, index]))
            expected_log = float(slot_scores[peak, index])
            competitor_ids = sorted(phone_ids.difference(allowed_ids[index]))
            competitor_log = (
                float(logpost[peak, competitor_ids].max()) if competitor_ids else expected_log
            )
            absolute_start = frame_offset + min(assigned_frames)
            absolute_end = frame_offset + max(assigned_frames) + 1
            evidence.append(
                {
                    **slot.to_dict(),
                    "start": round(absolute_start * frame_seconds, 3),
                    "end": round(absolute_end * frame_seconds, 3),
                    "peak_expected_probability": round(math.exp(expected_log), 6),
                    "mean_assigned_log_probability": round(
                        float(np.mean(slot_scores[assigned_frames, index])), 4
                    ),
                    "peak_competitor_margin": round(expected_log - competitor_log, 4),
                }
            )

        margins = [slot["peak_competitor_margin"] for slot in evidence]
        probabilities = [slot["peak_expected_probability"] for slot in evidence]
        return {
            "variant": variant.name,
            "slots": evidence,
            "mean_peak_expected_probability": round(float(np.mean(probabilities)), 6),
            "weakest_peak_expected_probability": round(float(np.min(probabilities)), 6),
            "mean_peak_competitor_margin": round(float(np.mean(margins)), 4),
        }

    def assess(
        self,
        *,
        path: str,
        expected_words: Sequence[str],
        alignment_rows: Sequence[dict],
        transcript_words: Sequence,
        transcript_duration: float,
    ) -> dict:
        import numpy as np

        started = time.monotonic()
        logpost, decoded_duration = self._posteriors(path)
        duration = decoded_duration or transcript_duration
        if not duration or not len(logpost):
            raise PronunciationUnavailable("model returned no timed acoustic frames")
        frame_seconds = duration / len(logpost)

        results = []
        all_probabilities: list[float] = []
        for row in alignment_rows:
            expected_index = row.get("expected_index")
            if expected_index is None:
                continue
            item = {
                "expected_index": expected_index,
                "word": expected_words[expected_index],
                "heard": row.get("heard"),
                "word_alignment": row.get("operation"),
            }
            heard_index = row.get("heard_index")
            if row.get("operation") not in {"ok", "almost"} or heard_index is None:
                item["status"] = "not_measured_word_mismatch"
                results.append(item)
                continue
            if heard_index >= len(transcript_words):
                item["status"] = "not_measured_missing_timestamp"
                results.append(item)
                continue

            heard_word = transcript_words[heard_index]
            start = max(0.0, float(heard_word.start) - self.padding_seconds)
            end = min(duration, float(heard_word.end) + self.padding_seconds)
            first_frame = max(0, int(math.floor(start / frame_seconds)))
            last_frame = min(len(logpost), int(math.ceil(end / frame_seconds)))
            variants = pronunciation_variants(
                expected_words[expected_index],
                profile=self.profile,
                divine_policy=self.divine_policy,
            )
            if not variants or not variants[0].slots:
                item["status"] = "not_measured_no_pronunciation_map"
                results.append(item)
                continue

            candidates = []
            for variant in variants:
                try:
                    candidates.append(
                        self._variant_evidence(
                            logpost[first_frame:last_frame],
                            first_frame,
                            frame_seconds,
                            variant,
                        )
                    )
                except PronunciationUnavailable:
                    continue
            if not candidates:
                item["status"] = "not_measured_alignment_unavailable"
                results.append(item)
                continue
            chosen = max(
                candidates,
                key=lambda candidate: candidate["mean_peak_competitor_margin"],
            )
            item.update(
                {
                    "status": "measured_uncalibrated",
                    "word_window": {"start": round(start, 3), "end": round(end, 3)},
                    **chosen,
                }
            )
            all_probabilities.extend(
                slot["peak_expected_probability"] for slot in chosen["slots"]
            )
            results.append(item)

        measured = [item for item in results if item["status"] == "measured_uncalibrated"]
        return {
            "mode": "shadow",
            "status": "evidence_available" if measured else "no_measurable_words",
            "affects_routing": False,
            "calibration_state": "uncalibrated",
            "method": "word-windowed-ctc-viterbi-posterior",
            "model": self.model_id,
            "model_revision": self.revision,
            "pronunciation_profile": self.profile,
            "divine_name_policy": self.divine_policy,
            "inference_seconds": round(time.monotonic() - started, 3),
            "summary": {
                "words_measured": len(measured),
                "expected_words": len(expected_words),
                "mean_peak_expected_probability": (
                    round(float(np.mean(all_probabilities)), 6)
                    if all_probabilities
                    else None
                ),
            },
            "words": results,
            "limitations": [
                "uncalibrated research evidence only",
                "uses ASR word windows rather than validated Hebrew forced alignment",
                "does not determine pass, retry, or teacher review",
            ],
        }


def configured_pronunciation_assessor():
    mode = os.getenv("KRIAH_PRONUNCIATION_MODE", "off").strip().lower()
    if mode == "off":
        return None
    if mode != "shadow":
        raise ValueError("KRIAH_PRONUNCIATION_MODE must be 'off' or 'shadow'")
    return CtcPronunciationAssessor()


def disabled_pronunciation_result() -> dict:
    return {
        "mode": "off",
        "status": "disabled",
        "affects_routing": False,
        "calibration_state": "not_started",
    }
