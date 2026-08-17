"""HTTP API for advisory Hebrew reading analysis.

The service does not store uploaded audio and does not claim to grade nikud.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse

from .scoring import normalize_word, score_transcript
from .signing import sign_result, verify_result
from .transcriber import FasterWhisperTranscriber


LOGGER = logging.getLogger("kriah.server")
MAX_UPLOAD_BYTES = int(os.getenv("KRIAH_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_AUDIO_SECONDS = float(os.getenv("KRIAH_MAX_AUDIO_SECONDS", "180"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("KRIAH_RATE_LIMIT_PER_MINUTE", "10"))
ALLOWED_SUFFIXES = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg"}
FRONTEND_PATH = Path(__file__).resolve().parents[1] / "index.html"


class VerifyRequest(BaseModel):
    token: str


class SlidingWindowLimiter:
    """Best-effort single-process limiter; edge throttling is still required in production."""

    def __init__(self, limit: int, period_seconds: int = 60) -> None:
        self.limit = limit
        self.period_seconds = period_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        events = self.events[key]
        while events and events[0] <= now - self.period_seconds:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True


def _origins() -> list[str]:
    configured = os.getenv(
        "KRIAH_ALLOWED_ORIGINS",
        "https://dovlevinson.github.io,http://127.0.0.1:8080,http://localhost:8080",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _expected_words(value: str) -> list[str]:
    try:
        words = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="expected_words must be valid JSON") from exc
    if not isinstance(words, list) or not words or len(words) > 500:
        raise HTTPException(status_code=422, detail="expected_words must contain 1 to 500 words")
    if any(not isinstance(word, str) or not word.strip() or len(word) > 100 for word in words):
        raise HTTPException(status_code=422, detail="expected_words contains an invalid word")
    if any(not normalize_word(word) for word in words):
        raise HTTPException(status_code=422, detail="expected_words must contain Hebrew words")
    return words


async def _save_upload(audio: UploadFile) -> tuple[str, int]:
    suffix = Path(audio.filename or "reading.webm").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="unsupported audio file type")
    raw = await audio.read(MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio upload")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio upload is too large")
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(raw)
        handle.flush()
        return handle.name, len(raw)
    finally:
        handle.close()


def create_app(transcriber=None) -> FastAPI:
    speech = transcriber or FasterWhisperTranscriber()
    limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MINUTE)
    app = FastAPI(title="Kriah Trainer advisory analysis", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.method == "POST":
            client = request.client.host if request.client else "unknown"
            if not limiter.allow(client):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "too many requests; try again shortly"},
                )
        return await call_next(request)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "kriah-advisory-analysis",
            "model": getattr(speech, "model_id", "injected-test-model"),
            "model_loaded": bool(getattr(speech, "loaded", False)),
            "signing_configured": bool(os.getenv("KRIAH_RESULT_SECRET")),
            "capabilities": ["transcription", "word-order-analysis"],
            "limitations": ["does not grade nikud", "results require teacher review"],
        }

    @app.get("/", include_in_schema=False)
    def frontend():
        if not FRONTEND_PATH.is_file():
            raise HTTPException(status_code=404, detail="frontend is unavailable")
        return FileResponse(FRONTEND_PATH, media_type="text/html")

    async def run_transcription(audio: UploadFile, language: str):
        if language != "he":
            raise HTTPException(status_code=422, detail="only Hebrew analysis is supported")
        path, _size = await _save_upload(audio)
        try:
            result = await run_in_threadpool(speech.transcribe, path, language)
            if result.duration > MAX_AUDIO_SECONDS:
                raise HTTPException(status_code=413, detail="audio recording is too long")
            return result
        except HTTPException:
            raise
        except Exception:
            LOGGER.exception("speech transcription failed")
            raise HTTPException(status_code=503, detail="speech analysis is temporarily unavailable")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @app.post("/transcribe")
    async def transcribe(
        audio: Annotated[UploadFile, File(...)],
        language: Annotated[str, Form()] = "he",
    ):
        return (await run_transcription(audio, language)).to_dict()

    @app.post("/analyze-reading")
    async def analyze_reading(
        audio: Annotated[UploadFile, File(...)],
        expected_words: Annotated[str, Form(...)],
        language: Annotated[str, Form()] = "he",
        bracha: Annotated[str | None, Form()] = None,
        attempt_id: Annotated[str | None, Form()] = None,
    ):
        if bracha is not None and len(bracha) > 20:
            raise HTTPException(status_code=422, detail="bracha is too long")
        if attempt_id is not None and len(attempt_id) > 100:
            raise HTTPException(status_code=422, detail="attempt_id is too long")
        expected = _expected_words(expected_words)
        transcript = await run_transcription(audio, language)
        analysis = score_transcript(expected, transcript.transcript)
        average_probability = None
        probabilities = [
            word.probability for word in transcript.words if word.probability is not None
        ]
        if probabilities:
            average_probability = round(sum(probabilities) / len(probabilities), 4)
            if average_probability < 0.55:
                analysis["review_required"] = True
                analysis["review_reasons"].append("speech-model confidence is low")

        result = {
            "version": 2,
            "attempt_id": attempt_id or str(uuid4()),
            "bracha": bracha,
            "status": "review_required" if analysis["review_required"] else "advisory_pass",
            "transcript": transcript.transcript,
            "transcript_words": [asdict(word) for word in transcript.words],
            "duration": transcript.duration,
            "inference_seconds": transcript.inference_seconds,
            "model": transcript.model,
            "average_word_probability": average_probability,
            "caveat": "Advisory consonant/word analysis only. Nikud is not graded.",
            **analysis,
        }
        secret = os.getenv("KRIAH_RESULT_SECRET")
        result["result_token"] = (
            sign_result(
                {
                    "v": 2,
                    "attempt_id": result["attempt_id"],
                    "bracha": bracha,
                    "estimated_accuracy": result["estimated_accuracy"],
                    "counts": result["counts"],
                    "model": result["model"],
                },
                secret,
            )
            if secret
            else None
        )
        return result

    @app.post("/verify-result")
    def verify_signed_result(request: VerifyRequest):
        secret = os.getenv("KRIAH_RESULT_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="result verification is not configured")
        try:
            return {"valid": True, "payload": verify_result(request.token, secret)}
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid result token")

    return app


app = create_app()
