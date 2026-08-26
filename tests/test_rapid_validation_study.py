import json
from pathlib import Path
import tempfile
import unittest

from evaluation.rapid_validation_study import aggregate, load_package


def analysis(passage, targets, error):
    words = []
    for word_index in range(2):
        slots = []
        for slot_index in range(2):
            key = f"{word_index}:{slot_index}"
            is_target = key in targets
            slots.append(
                {
                    "kind": "vowel",
                    "source": "פתח",
                    "peak_expected_probability": 0.05 if error and is_target else 0.9,
                    "peak_competitor_margin": -3.0 if error and is_target else 2.0,
                }
            )
        words.append(
            {
                "expected_index": word_index,
                "word": f"word-{word_index}",
                "word_alignment": "ok",
                "word_window_reliability": "matched_transcript",
                "status": "measured_uncalibrated",
                "slots": slots,
            }
        )
    return {"pronunciation": {"status": "evidence_available", "words": words}}


def speaker(code, assignment):
    target = {"key": "0:0", "source": "פתח"}
    recordings = []
    for passage in ("9", "10"):
        error = (assignment == "A" and passage == "10") or (assignment == "B" and passage == "9")
        recordings.append(
            {
                "passage_id": passage,
                "role": "guided_mistakes" if error else "correct",
                "targets": [target] if error else [],
                "analysis": analysis(passage, {"0:0"}, error),
            }
        )
    return {
        "speaker_code": code,
        "assignment": assignment,
        "reading_level": "strong",
        "tradition": "ashkenazi",
        "device": "Mac",
        "room": "quiet",
        "recordings": recordings,
    }


class RapidValidationTests(unittest.TestCase):
    def test_loader_accepts_only_the_brachot_9_and_10_v2_package(self):
        prepared = speaker("A01", "A")
        package = {
            "schema_version": "kriah-rapid-validation-analyzed-v2",
            "complete": True,
            "speaker": {"speakerCode": "A01", "assignment": "A"},
            "recordings": prepared["recordings"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "study.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            loaded = load_package(path)
            self.assertEqual(loaded["speaker_code"], "A01")
            self.assertEqual(
                {item["passage_id"] for item in loaded["recordings"]},
                {"9", "10"},
            )
            package["schema_version"] = "kriah-rapid-validation-analyzed-v1"
            path.write_text(json.dumps(package), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "analyzed-v2"):
                load_package(path)

    def test_balanced_four_speaker_study_can_pass_exploratory_gate(self):
        report = aggregate(
            [speaker("A01", "A"), speaker("A02", "B"), speaker("A03", "A"), speaker("A04", "B")],
            [-2.0],
        )
        result = report["thresholds"][0]
        self.assertEqual(result["targets_planned"], 4)
        self.assertEqual(result["targets_detected"], 4)
        self.assertEqual(result["false_alarms"], 0)
        self.assertTrue(result["exploratory_gate_passed"])
        self.assertEqual(len(report["matched_target_positions"]), 2)

    def test_duplicate_speaker_codes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate speaker"):
            aggregate([speaker("A01", "A"), speaker("A01", "B")])

    def test_unbalanced_study_cannot_pass_gate(self):
        report = aggregate([speaker("A01", "A"), speaker("A02", "A")], [-2.0])
        self.assertFalse(report["thresholds"][0]["exploratory_gate_passed"])
        self.assertEqual(report["interpretation"]["production_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
