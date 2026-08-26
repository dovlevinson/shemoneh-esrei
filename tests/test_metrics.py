import unittest

from evaluation.metrics import assert_speaker_disjoint, evaluate


class EvaluationTests(unittest.TestCase):
    def test_false_pass_and_false_flag_rates(self):
        rows = [
            {"speaker_id": "a", "split": "test", "human_pass": True, "model_score": 95, "review_required": False},
            {"speaker_id": "b", "split": "test", "human_pass": True, "model_score": 70, "review_required": True},
            {"speaker_id": "c", "split": "test", "human_pass": False, "model_score": 92, "review_required": False},
            {"speaker_id": "d", "split": "test", "human_pass": False, "model_score": 40, "review_required": True},
        ]
        report = evaluate(rows, threshold=90)
        self.assertEqual(report["false_pass_rate"], 0.5)
        self.assertEqual(report["false_flag_rate"], 0.5)

    def test_rejects_speaker_leakage(self):
        rows = [
            {"speaker_id": "same", "split": "calibration"},
            {"speaker_id": "same", "split": "test"},
        ]
        with self.assertRaises(ValueError):
            assert_speaker_disjoint(rows)


if __name__ == "__main__":
    unittest.main()
