import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.app import create_app
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
        return Transcript(
            transcript=self.text,
            words=[TranscriptWord("אתה", 0.0, 0.5, 0.9)],
            language=language,
            duration=self.duration,
            inference_seconds=0.01,
            model=self.model_id,
        )


class AppTests(unittest.TestCase):
    def test_health_describes_limitations(self):
        client = TestClient(create_app(FakeTranscriber()))
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("does not grade nikud", response.json()["limitations"])

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
        self.assertTrue(body["result_token"].startswith("SET2."))
        self.assertTrue(fake.saw_existing_file)
        self.assertFalse(os.path.exists(fake.last_path))

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
