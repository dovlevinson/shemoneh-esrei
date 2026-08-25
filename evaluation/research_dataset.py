"""Aggregate versioned, human-reviewed Kriah research samples.

This report is descriptive.  It deliberately does not retrain a model, select a
threshold, or turn acoustic evidence into a student grade.  Its purpose is to
show whether the growing collection contains the speaker, passage, label, and
model-version coverage needed for a later controlled calibration experiment.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable


SAMPLE_SCHEMA = "kriah-research-sample-v1"
MANIFEST_SCHEMA = "kriah-research-manifest-v1"
HUMAN_VOWEL_LABELS = {
    "human_correct",
    "human_wrong_vowel",
    "human_uncertain",
}


def load_packages(paths: Iterable[str | Path]) -> list[dict]:
    samples = []
    seen = set()
    for path in paths:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        if data.get("schema_version") == SAMPLE_SCHEMA:
            incoming = [data]
        elif data.get("schema_version") == MANIFEST_SCHEMA:
            incoming = data.get("samples") or []
        else:
            raise ValueError(f"{source}: unsupported research package")
        for sample in incoming:
            if sample.get("schema_version") != SAMPLE_SCHEMA:
                raise ValueError(f"{source}: manifest contains an invalid sample")
            sample_id = str(sample.get("sample_id") or "")
            if not sample_id:
                raise ValueError(f"{source}: sample is missing sample_id")
            if sample_id in seen:
                continue
            if not isinstance(sample.get("analysis"), dict):
                raise ValueError(f"{source}: {sample_id} is missing analysis")
            if not sample.get("speaker", {}).get("code"):
                raise ValueError(f"{source}: {sample_id} is missing speaker code")
            seen.add(sample_id)
            samples.append(sample)
    return samples


def _measured_vowels(sample: dict) -> dict[str, dict]:
    measured = {}
    pronunciation = sample.get("analysis", {}).get("pronunciation") or {}
    for word in pronunciation.get("words") or []:
        if word.get("status") != "measured_uncalibrated":
            continue
        for slot_index, slot in enumerate(word.get("slots") or []):
            if slot.get("kind") != "vowel":
                continue
            key = f"{word.get('expected_index')}:{slot_index}"
            measured[key] = {
                "word": word.get("word"),
                "source": slot.get("source"),
                "margin": float(slot.get("peak_competitor_margin") or 0),
                "expected_probability": float(
                    slot.get("peak_expected_probability") or 0
                ),
            }
    return measured


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None, "minimum": None, "maximum": None}
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def aggregate(samples: Iterable[dict]) -> dict:
    material = list(samples)
    speakers = set()
    passages = set()
    passages_by_speaker: dict[str, set[str]] = defaultdict(set)
    speakers_by_passage: dict[str, set[str]] = defaultdict(set)
    complete_speakers_by_passage: dict[str, set[str]] = defaultdict(set)
    model_versions = Counter()
    reading_truth = Counter()
    passage_coverage = Counter()
    word_labels = Counter()
    vowel_labels = Counter()
    vowel_sources = Counter()
    margins: dict[str, list[float]] = defaultdict(list)
    expected_probabilities: dict[str, list[float]] = defaultdict(list)
    measured_total = 0
    labeled_measured = 0
    labels_without_evidence = 0

    for sample in material:
        speaker = str(sample["speaker"]["code"])
        passage = str(sample.get("passage", {}).get("id") or "unknown")
        speakers.add(speaker)
        passages.add(passage)
        passages_by_speaker[speaker].add(passage)
        speakers_by_passage[passage].add(speaker)
        reading_truth[str(sample.get("reading_truth") or "unknown")] += 1
        coverage = str(
            sample.get("recording_context", {}).get("passage_coverage") or "unknown"
        )
        passage_coverage[coverage] += 1
        if coverage == "full":
            complete_speakers_by_passage[passage].add(speaker)
        signature = sample.get("model_signature") or {}
        model_versions[
            " | ".join(
                [
                    str(signature.get("speech") or "unknown-speech"),
                    str(signature.get("pronunciation") or "unknown-pronunciation"),
                    str(signature.get("pronunciation_revision") or "unknown-revision"),
                ]
            )
        ] += 1

        review = sample.get("human_review") or {}
        word_labels.update(
            str(item.get("label") or "unknown")
            for item in (review.get("word_labels") or {}).values()
        )
        evidence = _measured_vowels(sample)
        measured_total += len(evidence)
        labels = review.get("vowel_labels") or {}
        for key, item in labels.items():
            label = str(item.get("label") or "unknown")
            vowel_labels[label] += 1
            slot = evidence.get(key)
            if slot is None:
                labels_without_evidence += 1
                continue
            labeled_measured += 1
            vowel_sources[str(slot.get("source") or "unknown")] += 1
            if label in HUMAN_VOWEL_LABELS:
                margins[label].append(slot["margin"])
                expected_probabilities[label].append(slot["expected_probability"])

    shared_passages = sorted(
        passage for passage, passage_speakers in speakers_by_passage.items()
        if len(passage_speakers) >= 2
    )
    shared_complete_passages = sorted(
        passage
        for passage, passage_speakers in complete_speakers_by_passage.items()
        if len(passage_speakers) >= 2
    )
    missing_brachot = [str(number) for number in range(1, 20) if str(number) not in passages]
    complete_passages = set(complete_speakers_by_passage)
    missing_complete_brachot = [
        str(number) for number in range(1, 20) if str(number) not in complete_passages
    ]
    correct_count = vowel_labels["human_correct"]
    wrong_count = vowel_labels["human_wrong_vowel"]
    return {
        "schema_version": "kriah-research-summary-v1",
        "recordings": len(material),
        "speakers": len(speakers),
        "brachot_represented": len(passages.intersection({str(i) for i in range(1, 20)})),
        "missing_brachot": missing_brachot,
        "complete_brachot_represented": len(
            complete_passages.intersection({str(i) for i in range(1, 20)})
        ),
        "missing_complete_brachot": missing_complete_brachot,
        "shared_passages_across_speakers": shared_passages,
        "shared_complete_passages_across_speakers": shared_complete_passages,
        "recordings_per_speaker": dict(sorted((k, len(v)) for k, v in passages_by_speaker.items())),
        "speakers_per_passage": dict(sorted((k, len(v)) for k, v in speakers_by_passage.items())),
        "reading_truth": dict(reading_truth),
        "passage_coverage": dict(passage_coverage),
        "word_labels": dict(word_labels),
        "vowel_labels": dict(vowel_labels),
        "measured_vowel_slots": measured_total,
        "human_labeled_measured_vowel_slots": labeled_measured,
        "labels_without_model_evidence": labels_without_evidence,
        "labeled_vowel_sources": dict(sorted(vowel_sources.items())),
        "model_versions": dict(model_versions),
        "evidence_by_human_label": {
            label: {
                "competitor_margin": _distribution(margins[label]),
                "expected_probability": _distribution(expected_probabilities[label]),
            }
            for label in sorted(HUMAN_VOWEL_LABELS)
        },
        "evaluation_readiness": {
            "has_correct_vowel_labels": correct_count > 0,
            "has_wrong_vowel_labels": wrong_count > 0,
            "has_cross_speaker_passage_overlap": bool(shared_passages),
            "has_cross_speaker_complete_passage_overlap": bool(
                shared_complete_passages
            ),
            "single_model_version": len(model_versions) == 1,
            "can_describe_label_separation": correct_count > 0 and wrong_count > 0,
            "validated_threshold_available": False,
        },
        "limitations": [
            "This report is descriptive and does not retrain either model.",
            "Human labels must be checked before they are calibration evidence.",
            "Threshold selection requires a predefined calibration split and a speaker-disjoint held-out test split.",
            "Adult recordings do not establish performance on children.",
            "Partial readings support only the manually verified, measured words and do not count as complete-bracha coverage.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("packages", nargs="+")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = aggregate(load_packages(args.packages))
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
