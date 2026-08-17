import os
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
    def test_root_serves_the_streamlined_pilot(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fast Kriah Pilot", response.text)
        self.assertIn('href="/coach"', response.text)

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

            def assess(self, **kwargs):
                self.last_path = kwargs["path"]
                self.saw_existing_file = os.path.exists(kwargs["path"])
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
            data={"expected_words": '["אַתָּה", "קָדוֹשׁ"]'},
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
        self.assertFalse(os.path.exists(assessor.last_path))

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
