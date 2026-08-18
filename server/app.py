"""HTTP API for advisory Hebrew reading analysis.

The service does not store uploaded audio.  Optional pronunciation measurements
run only in shadow mode and never affect routing or student progression.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, JSONResponse

from .hebrew_g2p import VALID_PROFILES
from .pronunciation import (
    PronunciationUnavailable,
    configured_pronunciation_assessor,
    disabled_pronunciation_result,
)
from .scoring import normalize_word, score_transcript
from .signing import sign_result, verify_result
from .transcriber import FasterWhisperTranscriber

LOGGER = logging.getLogger("kriah.server")
MAX_UPLOAD_BYTES = int(os.getenv("KRIAH_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_AUDIO_SECONDS = float(os.getenv("KRIAH_MAX_AUDIO_SECONDS", "180"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("KRIAH_RATE_LIMIT_PER_MINUTE", "10"))
ALLOWED_SUFFIXES = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg"}
FRONTEND_PATH = Path(__file__).resolve().parents[1] / "index.html"
PILOT_PATH = Path(__file__).resolve().parents[1] / "pilot.html"
NIKUD_PATH = Path(__file__).resolve().parents[1] / "nikud.html"
JOB_TTL_SECONDS = int(os.getenv("KRIAH_JOB_TTL_SECONDS", "1800"))
MAX_JOBS = int(os.getenv("KRIAH_MAX_JOBS", "25"))


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
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(raw)
        handle.flush()
        return handle.name, len(raw)


def create_app(transcriber=None, pronunciation_assessor=None) -> FastAPI:
    speech = transcriber or FasterWhisperTranscriber()
    pronunciation = (
        pronunciation_assessor
        if pronunciation_assessor is not None
        else configured_pronunciation_assessor()
    )
    limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MINUTE)
    analysis_lock = threading.Lock()
    jobs_lock = threading.Lock()
    jobs: dict[str, dict] = {}
    model_state = {
        "speech": "ready" if bool(getattr(speech, "loaded", False)) else "not_loaded",
        "pronunciation": (
            "off"
            if pronunciation is None
            else (
                "ready"
                if bool(getattr(pronunciation, "loaded", False))
                else "not_loaded"
            )
        ),
    }

    def load_model(name: str, model) -> None:
        loader = getattr(model, "load", None)
        if loader is None:
            model_state[name] = (
                "ready" if bool(getattr(model, "loaded", False)) else "unavailable"
            )
            return
        model_state[name] = "loading"
        try:
            loader()
            model_state[name] = "ready"
        except Exception:
            model_state[name] = "failed"
            LOGGER.exception("%s model preload failed", name)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if os.getenv("KRIAH_PRELOAD_MODELS", "0") == "1":
            threading.Thread(
                target=load_model,
                args=("speech", speech),
                name="kriah-speech-preload",
                daemon=True,
            ).start()
            if pronunciation is not None:
                threading.Thread(
                    target=load_model,
                    args=("pronunciation", pronunciation),
                    name="kriah-pronunciation-preload",
                    daemon=True,
                ).start()
        yield

    app = FastAPI(
        title="Kriah Trainer advisory analysis",
        version="0.2.0",
        lifespan=lifespan,
    )
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
        pronunciation_mode = getattr(pronunciation, "mode", "off")
        speech_loaded = bool(getattr(speech, "loaded", False))
        pronunciation_loaded = bool(getattr(pronunciation, "loaded", False))
        if speech_loaded:
            model_state["speech"] = "ready"
        if pronunciation_loaded:
            model_state["pronunciation"] = "ready"
        nikud_lab_ready = (
            speech_loaded
            and pronunciation_mode == "shadow"
            and pronunciation_loaded
        )
        capabilities = ["transcription", "word-order-analysis"]
        limitations = ["uncertain word results require selective review"]
        if pronunciation_mode == "shadow":
            capabilities.append("shadow-pronunciation-evidence")
            limitations.extend(
                [
                    "pronunciation evidence is uncalibrated",
                    "pronunciation evidence does not affect routing",
                ]
            )
        else:
            limitations.append("does not yet grade nikud")
        return {
            "status": "ok",
            "service": "kriah-advisory-analysis",
            "model": getattr(speech, "model_id", "injected-test-model"),
            "model_loaded": speech_loaded,
            "nikud_lab_ready": nikud_lab_ready,
            "model_preparation": dict(model_state),
            "signing_configured": bool(os.getenv("KRIAH_RESULT_SECRET")),
            "capabilities": capabilities,
            "limitations": limitations,
            "pronunciation": {
                "mode": pronunciation_mode,
                "model": getattr(pronunciation, "model_id", None),
                "model_loaded": pronunciation_loaded,
                "affects_routing": False,
            },
        }

    @app.get("/coach", include_in_schema=False)
    def frontend():
        if not FRONTEND_PATH.is_file():
            raise HTTPException(status_code=404, detail="frontend is unavailable")
        html = FRONTEND_PATH.read_text(encoding="utf-8")
        codespaces_bootstrap = """<script>
if (location.hostname.endsWith('.app.github.dev')) {
  localStorage.setItem('se-grader-url', new URL('/analyze-reading', location.origin).href);
}
</script>
"""
        pilot_link = """<div style="max-width:860px;margin:12px auto 0;padding:0 14px">
  <a href="/" style="display:block;text-align:center;padding:12px 16px;border-radius:12px;background:#2456a6;color:white;text-decoration:none;font:600 16px/1.3 system-ui,sans-serif">Open the nikud evidence lab</a>
</div>
"""
        html = html.replace(
            '<div id="app"></div>',
            codespaces_bootstrap + pilot_link + '<div id="app"></div>',
            1,
        )
        return HTMLResponse(html)

    @app.get("/pilot", include_in_schema=False)
    @app.get("/word-pilot", include_in_schema=False)
    def pilot_frontend():
        if not PILOT_PATH.is_file():
            raise HTTPException(status_code=404, detail="pilot frontend is unavailable")
        return HTMLResponse(PILOT_PATH.read_text(encoding="utf-8"))

    @app.get("/", include_in_schema=False)
    @app.get("/nikud", include_in_schema=False)
    def nikud_frontend():
        if not NIKUD_PATH.is_file():
            raise HTTPException(status_code=404, detail="nikud lab is unavailable")
        return HTMLResponse(NIKUD_PATH.read_text(encoding="utf-8"))

    async def transcribe_path(path: str, language: str):
        if language != "he":
            raise HTTPException(status_code=422, detail="only Hebrew analysis is supported")
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

    async def run_transcription(audio: UploadFile, language: str):
        path, _size = await _save_upload(audio)
        try:
            return await transcribe_path(path, language)
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

    def validate_analysis_metadata(
        *,
        language: str,
        bracha: str | None,
        attempt_id: str | None,
        pronunciation_profile: str,
    ) -> None:
        if language != "he":
            raise HTTPException(status_code=422, detail="only Hebrew analysis is supported")
        if bracha is not None and len(bracha) > 20:
            raise HTTPException(status_code=422, detail="bracha is too long")
        if attempt_id is not None and len(attempt_id) > 100:
            raise HTTPException(status_code=422, detail="attempt_id is too long")
        if pronunciation_profile not in VALID_PROFILES:
            raise HTTPException(
                status_code=422,
                detail="pronunciation_profile must be mixed, ashkenazi, or sephardi",
            )

    def analyze_saved_path(
        *,
        path: str,
        expected: list[str],
        language: str,
        bracha: str | None,
        attempt_id: str | None,
        pronunciation_profile: str,
    ) -> dict:
        with analysis_lock:
            try:
                transcript = speech.transcribe(path, language)
            except Exception as exc:
                LOGGER.exception("speech transcription failed")
                raise HTTPException(
                    status_code=503,
                    detail="speech analysis is temporarily unavailable",
                ) from exc
            if transcript.duration > MAX_AUDIO_SECONDS:
                raise HTTPException(status_code=413, detail="audio recording is too long")
            analysis = score_transcript(expected, transcript.transcript)
            pronunciation_result = disabled_pronunciation_result()
            if pronunciation is not None:
                try:
                    pronunciation_result = pronunciation.assess(
                        path=path,
                        expected_words=expected,
                        alignment_rows=analysis["words"],
                        transcript_words=transcript.words,
                        transcript_duration=transcript.duration,
                        profile=pronunciation_profile,
                    )
                except PronunciationUnavailable:
                    LOGGER.warning("shadow pronunciation evidence is unavailable")
                    pronunciation_result = {
                        "mode": "shadow",
                        "status": "unavailable",
                        "affects_routing": False,
                        "calibration_state": "uncalibrated",
                    }
                except Exception:
                    LOGGER.exception("shadow pronunciation analysis failed")
                    pronunciation_result = {
                        "mode": "shadow",
                        "status": "failed",
                        "affects_routing": False,
                        "calibration_state": "uncalibrated",
                    }

        average_probability = None
        probabilities = [
            word.probability for word in transcript.words if word.probability is not None
        ]
        if probabilities:
            average_probability = round(sum(probabilities) / len(probabilities), 4)
            if average_probability < 0.55:
                analysis["review_required"] = True
                analysis["review_reasons"].append("speech-model confidence is low")

        pronunciation_evidence_available = (
            pronunciation_result.get("status") == "evidence_available"
        )
        result = {
            "version": 2,
            "attempt_id": attempt_id or str(uuid4()),
            "bracha": bracha,
            "requested_pronunciation_profile": pronunciation_profile,
            "status": "review_required" if analysis["review_required"] else "advisory_pass",
            "routing": (
                "selective_review"
                if analysis["review_required"]
                else "automatic_word_clear"
            ),
            "assessment_scope": {
                "word_identity_and_order": "evaluated",
                "nikud_and_vowels": (
                    "experimental_shadow_evidence"
                    if pronunciation_evidence_available
                    else "not_evaluated"
                ),
                "phoneme_pronunciation": (
                    "experimental_shadow_evidence"
                    if pronunciation_evidence_available
                    else "not_evaluated"
                ),
            },
            "transcript": transcript.transcript,
            "transcript_words": [asdict(word) for word in transcript.words],
            "duration": transcript.duration,
            "inference_seconds": transcript.inference_seconds,
            "model": transcript.model,
            "average_word_probability": average_probability,
            "pronunciation": pronunciation_result,
            "caveat": (
                "Routing evaluates word identity and order only. "
                "Any pronunciation measurements are uncalibrated shadow evidence "
                "and cannot change this result."
            ),
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

    @app.post("/analyze-reading")
    async def analyze_reading(
        audio: Annotated[UploadFile, File(...)],
        expected_words: Annotated[str, Form(...)],
        language: Annotated[str, Form()] = "he",
        bracha: Annotated[str | None, Form()] = None,
        attempt_id: Annotated[str | None, Form()] = None,
        pronunciation_profile: Annotated[str, Form()] = "mixed",
    ):
        validate_analysis_metadata(
            language=language,
            bracha=bracha,
            attempt_id=attempt_id,
            pronunciation_profile=pronunciation_profile,
        )
        expected = _expected_words(expected_words)
        path, _size = await _save_upload(audio)
        try:
            return await run_in_threadpool(
                analyze_saved_path,
                path=path,
                expected=expected,
                language=language,
                bracha=bracha,
                attempt_id=attempt_id,
                pronunciation_profile=pronunciation_profile,
            )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def cleanup_jobs() -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        expired = [
            job_id
            for job_id, job in jobs.items()
            if job.get("finished_at", float("inf")) < cutoff
        ]
        for job_id in expired:
            jobs.pop(job_id, None)

    def run_analysis_job(
        *,
        job_id: str,
        path: str,
        expected: list[str],
        language: str,
        bracha: str | None,
        attempt_id: str | None,
        pronunciation_profile: str,
    ) -> None:
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["status"] = "running"
        try:
            result = analyze_saved_path(
                path=path,
                expected=expected,
                language=language,
                bracha=bracha,
                attempt_id=attempt_id,
                pronunciation_profile=pronunciation_profile,
            )
            with jobs_lock:
                jobs[job_id].update(
                    status="completed",
                    result=result,
                    finished_at=time.time(),
                )
        except HTTPException as exc:
            with jobs_lock:
                jobs[job_id].update(
                    status="failed",
                    error=exc.detail,
                    finished_at=time.time(),
                )
        except Exception:
            LOGGER.exception("background reading analysis failed")
            with jobs_lock:
                jobs[job_id].update(
                    status="failed",
                    error="analysis failed; check the server log",
                    finished_at=time.time(),
                )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @app.post("/analysis-jobs", status_code=202)
    async def create_analysis_job(
        audio: Annotated[UploadFile, File(...)],
        expected_words: Annotated[str, Form(...)],
        language: Annotated[str, Form()] = "he",
        bracha: Annotated[str | None, Form()] = None,
        attempt_id: Annotated[str | None, Form()] = None,
        pronunciation_profile: Annotated[str, Form()] = "mixed",
    ):
        validate_analysis_metadata(
            language=language,
            bracha=bracha,
            attempt_id=attempt_id,
            pronunciation_profile=pronunciation_profile,
        )
        expected = _expected_words(expected_words)
        path, _size = await _save_upload(audio)
        job_id = str(uuid4())
        with jobs_lock:
            cleanup_jobs()
            if len(jobs) >= MAX_JOBS:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=503,
                    detail="too many analyses are already queued",
                )
            jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "created_at": time.time(),
            }
        threading.Thread(
            target=run_analysis_job,
            kwargs={
                "job_id": job_id,
                "path": path,
                "expected": expected,
                "language": language,
                "bracha": bracha,
                "attempt_id": attempt_id,
                "pronunciation_profile": pronunciation_profile,
            },
            name=f"kriah-analysis-{job_id[:8]}",
            daemon=True,
        ).start()
        return {"job_id": job_id, "status": "queued"}

    @app.get("/analysis-jobs/{job_id}")
    def analysis_job(job_id: str):
        with jobs_lock:
            cleanup_jobs()
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="analysis job was not found")
            return dict(job)

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
