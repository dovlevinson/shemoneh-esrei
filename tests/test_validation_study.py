import unittest

from evaluation.validation_study import aggregate


def row(key, reference_probability, candidate_probability, candidate_margin, delta):
    return {
        "key": key,
        "tier": "no_change",
        "margin_delta": delta,
        "reference": {"peak_expected_probability": reference_probability},
        "candidate": {
            "peak_expected_probability": candidate_probability,
            "peak_competitor_margin": candidate_margin,
        },
    }


def comparison(target=False):
    result = {
        "comparisons": [
            row("0:1", 0.9, 0.05, -2.0, -4.2),
            row("1:1", 0.9, 0.8, 2.0, -0.2),
            row("2:1", 0.05, 0.01, -4.0, -8.0),
        ]
    }
    if target:
        result["target_evaluation"] = {
            "target_results": [
                {"key": "0:1", "source": "פתח", "reference_quality": "usable"},
                {"key": "2:1", "source": "צירי", "reference_quality": "weak"},
            ]
        }
    return result


def speaker(code="C01"):
    return {
        "speaker_code": code,
        "age_group": "middle-school",
        "tradition": "ashkenazi",
        "reading_level": "typical",
        "device": "Chromebook",
        "room": "quiet",
        "source": "multi-speaker-study",
        "comparisons": {"cal-core": {"clean": comparison(), "mistakes": comparison(True)}},
    }


class ValidationStudyTests(unittest.TestCase):
    def test_threshold_reclassification_and_weak_reference_exclusion(self):
        strict = aggregate([speaker()], [-5])["thresholds"][0]
        relaxed = aggregate([speaker()], [-4])["thresholds"][0]
        self.assertEqual(strict["targets_planned"], 2)
        self.assertEqual(strict["targets_evaluable"], 1)
        self.assertEqual(strict["targets_detected"], 0)
        self.assertEqual(relaxed["targets_detected"], 1)
        self.assertEqual(relaxed["false_alarms"], 1)
        self.assertEqual(relaxed["negative_slots"], 3)

    def test_duplicate_speaker_codes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate speaker"):
            aggregate([speaker(), speaker()])

    def test_exploratory_gate_requires_multiple_speakers(self):
        report = aggregate([speaker()], [-4])
        self.assertFalse(report["thresholds"][0]["exploratory_gate_passed"])
        self.assertEqual(report["interpretation"]["production_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
