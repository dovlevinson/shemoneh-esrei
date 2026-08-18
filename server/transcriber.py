"""Lazy adapter for the Hebrew faster-whisper model."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass

DEFAULT_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"


@dataclass(frozen=True)
class TranscriptWord:
    word: str
    start: float
    end: float
    probability: float | None


@dataclass(frozen=True)
class Transcript:
    transcript: str
    words: list[TranscriptWord]
    language: str
    duration: float
    inference_seconds: float
    model: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["words"] = [asdict(word) for word in self.words]
        return data


class FasterWhisperTranscriber:
    def __init__(self) -> None:
        self.model_id = os.getenv("KRIAH_MODEL_ID", DEFAULT_MODEL)
        self.device = os.getenv("KRIAH_DEVICE", "cpu")
        self.compute_type = os.getenv(
            "KRIAH_COMPUTE_TYPE", "int8" if self.device == "cpu" else "float16"
        )
        self._model = None
        self._load_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _get_model(self):
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        self.model_id,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
        return self._model

    def load(self) -> None:
        """Download and load the model outside a user analysis request."""

        self._get_model()

    def transcribe(self, path: str, language: str = "he") -> Transcript:
        started = time.monotonic()
        segments, info = self._get_model().transcribe(
            path,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            # Grading never supplies the expected prayer as an initial prompt.
            initial_prompt=None,
        )
        text_parts: list[str] = []
        words: list[TranscriptWord] = []
        for segment in segments:
            text_parts.append(segment.text)
            for word in segment.words or []:
                probability = getattr(word, "probability", None)
                words.append(
                    TranscriptWord(
                        word=word.word.strip(),
                        start=round(float(word.start), 3),
                        end=round(float(word.end), 3),
                        probability=round(float(probability), 4)
                        if probability is not None
                        else None,
                    )
                )
        return Transcript(
            transcript="".join(text_parts).strip(),
            words=words,
            language=getattr(info, "language", language),
            duration=round(float(info.duration), 3),
            inference_seconds=round(time.monotonic() - started, 3),
            model=self.model_id,
        )
