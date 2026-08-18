import os
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.app import create_app
from server.pronunciation import PronunciationUnavailable
from server.transcriber import Transcript, TranscriptWord


class FakeTranscriber:
    model_id = "fake-hebrew-model"
    loaded = True

    def __init__(self, transcript="אתה קדוש", duration=2.5):
        self.text = transcript
        self.duration = duration
        self.saw_existing_file = False
        self.last_path = None

    def transcribe(self, path, language="he"):
        self.last_path = path
        self.saw_existing_file = os.path.exists(path)
        timestamped = [
            TranscriptWord(word, index * 0.5, (index + 1) * 0.5, 0.9)
            for index, word in enumerate(self.text.split())
        ]
        return Transcript(
            transcript=self.text,
            words=timestamped,
            language=language,
            duration=self.duration,
            inference_seconds=0.01,
            model=self.model_id,
        )


class AppTests(unittest.TestCase):
    def test_root_serves_the_nikud_lab(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kriah Nikud Evidence Lab", response.text)
        self.assertIn('href="/coach"', response.text)

    def test_nikud_alias_serves_the_lab(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/nikud")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/analysis-jobs", response.text)

    def test_coach_serves_the_full_browser_app(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/coach")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Shemoneh Esrei", response.text)
        self.assertIn('href="/"', response.text)

    def test_pilot_serves_the_streamlined_test(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/pilot")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fast Kriah Pilot", response.text)
        self.assertIn("/analyze-reading", response.text)

    def test_health_describes_limitations(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("does not yet grade nikud", response.json()["limitations"])

    def test_calibration_suite_exposes_all_master_readings(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/calibration-suite?pronunciation_profile=sephardi")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pronunciation_profile"], "sephardi")
        self.assertEqual(len(body["readings"]), 3)
        self.assertTrue(body["coverage"]["all_required_vowel_sources_covered"])

    def test_calibration_suite_rejects_unknown_profile(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/calibration-suite?pronunciation_profile=unknown")
        self.assertEqual(response.status_code, 422)

    def test_comparison_rejects_readings_without_vowel_evidence(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.post(
            "/compare-readings",
            json={"reference": {"bracha": "4"}, "candidate": {"bracha": "4"}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("pronunciation evidence", response.json()["detail"])

    def test_comparison_returns_non_authoritative_vowel_candidates(self):
        def evidence(probability, margin):
            return {
                "bracha": "cal-core",
                "requested_pronunciation_profile": "mixed",
                "pronunciation": {
                    "status": "evidence_available",
                    "words": [
                        {
                            "expected_index": 0,
                            "word": "חוֹנֵן",
                            "status": "measured_uncalibrated",
                            "slots": [
                                {
                                    "kind": "vowel",
                                    "source": "צירי",
                                    "allowed": ["e"],
                                    "peak_expected_probability": probability,
                                    "peak_competitor_margin": margin,
                                }
                            ],
                        }
                    ],
                },
            }

        client = TestClient(create_app(FakeTranscriber()))
        response = client.post(
            "/compare-readings",
            json={"reference": evidence(0.8, 3), "candidate": evidence(0.03, -4)},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["authoritative"])
        self.assertEqual(body["summary"]["strong_candidates"], 1)

    def test_exact_recorded_reading(self):
        fake = FakeTranscriber()
        with patch.dict(os.environ, {"KRIAH_RESULT_SECRET": "test-secret"}):
            client = TestClient(create_app(fake))
            response = client.post(
                "/analyze-reading",
                files={"audio": ("reading.webm", b"not-real-audio", "audio/webm")},
                data={
                    "expected_words": '["אַתָּה", "קָדוֹשׁ"]',
                    "language": "he",
                    "bracha": "3",
                    "attempt_id": "attempt-1",
                },
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["estimated_accuracy"], 100)
        self.assertEqual(body["status"], "advisory_pass")
        self.assertEqual(body["routing"], "automatic_word_clear")
        self.assertEqual(body["assessment_scope"]["nikud_and_vowels"], "not_evaluated")
        self.assertEqual(body["pronunciation"]["status"], "disabled")
        self.assertTrue(body["result_token"].startswith("SET2."))
        self.assertTrue(fake.saw_existing_file)
        self.assertFalse(os.path.exists(fake.last_path))

    def test_shadow_evidence_is_returned_but_cannot_change_routing(self):
        class FakePronunciationAssessor:
            mode = "shadow"
            model_id = "fake-phoneme-model"
            loaded = True

            def __init__(self):
                self.saw_existing_file = False
                self.last_path = None
                self.last_profile = None

            def assess(self, **kwargs):
                self.last_path = kwargs["path"]
                self.saw_existing_file = os.path.exists(kwargs["path"])
                self.last_profile = kwargs.get("profile")
                return {
                    "mode": "shadow",
                    "status": "evidence_available",
                    "affects_routing": False,
                    "calibration_state": "uncalibrated",
                    "summary": {"words_measured": 2},
                    "words": [],
                }

        assessor = FakePronunciationAssessor()
        client = TestClient(create_app(FakeTranscriber(), assessor))
        health = client.get("/health").json()
        self.assertIn("shadow-pronunciation-evidence", health["capabilities"])
        self.assertFalse(health["pronunciation"]["affects_routing"])
        response = client.post(
            "/analyze-reading",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={
                "expected_words": '["אַתָּה", "קָדוֹשׁ"]',
                "pronunciation_profile": "ashkenazi",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "advisory_pass")
        self.assertEqual(body["routing"], "automatic_word_clear")
        self.assertFalse(body["pronunciation"]["affects_routing"])
        self.assertEqual(
            body["assessment_scope"]["nikud_and_vowels"],
            "experimental_shadow_evidence",
        )
        self.assertTrue(assessor.saw_existing_file)
        self.assertEqual(assessor.last_profile, "ashkenazi")
        self.assertFalse(os.path.exists(assessor.last_path))

    def test_background_job_returns_completed_analysis(self):
        class FakePronunciationAssessor:
            mode = "shadow"
            model_id = "fake-phoneme-model"
            loaded = True

            def assess(self, **kwargs):
                return {
                    "mode": "shadow",
                    "status": "evidence_available",
                    "affects_routing": False,
                    "calibration_state": "uncalibrated",
                    "pronunciation_profile": kwargs["profile"],
                    "summary": {"words_measured": 2},
                    "words": [],
                }

        client = TestClient(create_app(FakeTranscriber(), FakePronunciationAssessor()))
        created = client.post(
            "/analysis-jobs",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={
                "expected_words": '["אַתָּה", "קָדוֹשׁ"]',
                "pronunciation_profile": "sephardi",
            },
        )
        self.assertEqual(created.status_code, 202)
        job_id = created.json()["job_id"]
        body = None
        for _ in range(50):
            body = client.get(f"/analysis-jobs/{job_id}").json()
            if body["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(
            body["result"]["pronunciation"]["pronunciation_profile"],
            "sephardi",
        )

    def test_rejects_unknown_pronunciation_profile(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.post(
            "/analysis-jobs",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={
                "expected_words": '["אַתָּה", "קָדוֹשׁ"]',
                "pronunciation_profile": "unknown",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_shadow_failure_does_not_fail_word_analysis(self):
        class FailingPronunciationAssessor:
            mode = "shadow"
            model_id = "missing-model"
            loaded = False

            def assess(self, **_kwargs):
                raise PronunciationUnavailable("not installed")

        client = TestClient(create_app(FakeTranscriber(), FailingPronunciationAssessor()))
        response = client.post(
            "/analyze-reading",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={"expected_words": '["אַתָּה", "קָדוֹשׁ"]'},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "advisory_pass")
        self.assertEqual(body["pronunciation"]["status"], "unavailable")
        self.assertEqual(body["assessment_scope"]["nikud_and_vowels"], "not_evaluated")

    def test_expected_words_are_required_json(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.post(
            "/analyze-reading",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={"expected_words": "not json"},
        )
        self.assertEqual(response.status_code, 422)

    def test_non_hebrew_language_is_rejected(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.post(
            "/transcribe",
            files={"audio": ("reading.webm", b"audio", "audio/webm")},
            data={"language": "en"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
