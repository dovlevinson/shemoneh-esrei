import unittest

from research.compare_pronunciation_reports import compare_reports


def report(audio, margin, probability):
    return {
        "audio_file": audio,
        "pronunciation": {
            "words": [
                {
                    "expected_index": 0,
                    "word": "חוֹנֵן",
                    "slots": [
                        {
                            "source": "צירי",
                            "allowed": ["e"],
                            "peak_competitor_margin": margin,
                            "peak_expected_probability": probability,
                        }
                    ],
                }
            ]
        },
    }


class ComparePronunciationReportsTests(unittest.TestCase):
    def test_reports_directional_slot_delta_without_a_verdict(self):
        result = compare_reports(report("a.webm", 3.0, 0.8), report("b.webm", -2.0, 0.1))
        self.assertEqual(result["shared_slots"], 1)
        self.assertEqual(result["slots"][0]["margin_delta"], -5.0)
        self.assertNotIn("correct", result["slots"][0])


if __name__ == "__main__":
    unittest.main()
