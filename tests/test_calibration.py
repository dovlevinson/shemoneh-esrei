import copy
import unittest

from server.calibration import (
    CALIBRATION_READINGS,
    REQUIRED_VOWEL_SOURCES,
    calibration_suite,
    compare_vowel_evidence,
)
from server.hebrew_g2p import pronunciation_variants


def reading(*, margin=2.0, probability=0.8, source="צירי", profile="mixed"):
    return {
        "bracha": "cal-core",
        "requested_pronunciation_profile": profile,
        "pronunciation": {
            "status": "evidence_available",
            "words": [
                {
                    "expected_index": 0,
                    "word": "חוֹנֵן",
                    "heard": "חונן",
                    "status": "measured_uncalibrated",
                    "slots": [
                        {
                            "kind": "consonant",
                            "source": "ח",
                            "peak_expected_probability": 1.0,
                            "peak_competitor_margin": 12.0,
                        },
                        {
                            "kind": "vowel",
                            "source": source,
                            "allowed": ["e"],
                            "peak_expected_probability": probability,
                            "peak_competitor_margin": margin,
                            "strongest_competing_phone": "a",
                        },
                    ],
                }
            ],
        },
    }


def complete_reading(passage_id="cal-core", profile="mixed"):
    passage = next(item for item in CALIBRATION_READINGS if item.identifier == passage_id)
    words = []
    for word_index, word in enumerate(passage.words):
        slots = []
        for slot in pronunciation_variants(word, profile=profile)[0].slots:
            slots.append(
                {
                    **slot.to_dict(),
                    "peak_expected_probability": 0.8,
                    "peak_competitor_margin": 2.0,
                    "strongest_competing_phone": "a",
                }
            )
        words.append(
            {
                "expected_index": word_index,
                "word": word,
                "heard": word,
                "word_alignment": "ok",
                "status": "measured_uncalibrated",
                "slots": slots,
            }
        )
    return {
        "bracha": passage_id,
        "requested_pronunciation_profile": profile,
        "pronunciation": {"status": "evidence_available", "words": words},
    }


class CalibrationSuiteTests(unittest.TestCase):
    def test_master_suite_covers_every_supported_written_vowel_type(self):
        suite = calibration_suite()
        self.assertEqual(len(suite["readings"]), 3)
        self.assertTrue(suite["coverage"]["all_required_vowel_sources_covered"])
        self.assertEqual(suite["coverage"]["missing_vowel_sources"], [])
        self.assertTrue(
            REQUIRED_VOWEL_SOURCES.issubset(suite["coverage"]["vowel_sources"])
        )
        self.assertTrue(
            all(10 <= item["word_count"] <= 30 for item in suite["readings"])
        )

    def test_master_suite_covers_core_vowels_and_consonant_contrasts(self):
        suite = calibration_suite("sephardi")
        vowels = set().union(
            *(set(item["coverage"]["vowel_sounds"]) for item in suite["readings"])
        )
        consonants = set(suite["coverage"]["consonant_sounds"])
        self.assertTrue({"a", "e", "i", "o", "u"}.issubset(vowels))
        self.assertTrue(
            {"b", "v", "k", "x", "p", "f", "sh", "s", "ts"}.issubset(
                consonants
            )
        )

    def test_master_suite_accepts_each_pronunciation_tradition(self):
        for profile in ("mixed", "sephardi", "ashkenazi"):
            with self.subTest(profile=profile):
                suite = calibration_suite(profile)
                self.assertEqual(suite["pronunciation_profile"], profile)
                self.assertTrue(
                    suite["coverage"]["all_required_vowel_sources_covered"]
                )

    def test_master_suite_rejects_unknown_pronunciation_tradition(self):
        with self.assertRaisesRegex(ValueError, "pronunciation profile"):
            calibration_suite("unknown")

    def test_guided_core_scenario_resolves_exact_vowel_positions(self):
        reading_data = calibration_suite()["readings"][0]
        scenario = reading_data["scenarios"][1]
        self.assertEqual(scenario["id"], "cal-core-guided-mistakes")
        self.assertEqual(len(scenario["targets"]), 7)
        self.assertEqual(
            {target["key"] for target in scenario["targets"]},
            {"2:1", "6:1", "10:1", "14:4", "17:1", "18:3", "22:1"},
        )
        self.assertIn("שֶׁבָּת", scenario["prompt_text"])
        self.assertIn("סַכָּה", scenario["prompt_text"])

    def test_guided_special_scenario_marks_the_initial_vowel(self):
        reading_data = calibration_suite()["readings"][1]
        targets = {item["word_index"]: item for item in reading_data["scenarios"][1]["targets"]}
        self.assertEqual(targets[3]["key"], "3:0")
        self.assertEqual(targets[3]["source"], "חטף פתח")
        self.assertEqual(targets[6]["key"], "6:1")
        self.assertEqual(targets[6]["source"], "חטף קמץ")

    def test_atah_chonen_has_four_guided_changes(self):
        scenarios = calibration_suite("sephardi")["additional_passage_scenarios"]["4"]
        self.assertEqual(len(scenarios[1]["targets"]), 4)
        self.assertEqual(
            [item["source"] for item in scenarios[1]["targets"]],
            ["צירי", "צירי", "צירי", "שורוק"],
        )


class VowelComparisonTests(unittest.TestCase):
    def test_strong_margin_drop_with_weak_expected_vowel_is_flagged(self):
        report = compare_vowel_evidence(
            reading(margin=3.2, probability=0.82),
            reading(margin=-3.4, probability=0.03),
        )
        self.assertFalse(report["authoritative"])
        self.assertEqual(report["calibration_state"], "uncalibrated")
        self.assertEqual(report["summary"]["shared_vowel_slots"], 1)
        self.assertEqual(report["summary"]["strong_candidates"], 1)
        self.assertEqual(report["comparisons"][0]["margin_delta"], -6.6)
        self.assertEqual(report["comparisons"][0]["tier"], "strong_candidate")

    def test_vowel_mean_does_not_include_consonant_evidence(self):
        report = compare_vowel_evidence(
            reading(probability=0.74),
            reading(margin=-1.0, probability=0.21),
        )
        self.assertEqual(report["summary"]["reference_vowel_mean"], 0.74)
        self.assertEqual(report["summary"]["candidate_vowel_mean"], 0.21)

    def test_smaller_drop_is_possible_but_not_a_strong_flag(self):
        report = compare_vowel_evidence(
            reading(margin=2.0),
            reading(margin=-1.2, probability=0.05),
        )
        self.assertEqual(report["summary"]["strong_candidates"], 0)
        self.assertEqual(report["summary"]["possible_candidates"], 1)

    def test_sounded_sheva_remains_context_sensitive(self):
        report = compare_vowel_evidence(
            reading(margin=4.0, source="שווא נע"),
            reading(margin=-4.0, probability=0.01, source="שווא נע"),
        )
        self.assertEqual(report["summary"]["strong_candidates"], 0)
        self.assertEqual(report["summary"]["context_sensitive_slots"], 1)
        self.assertEqual(report["comparisons"][0]["tier"], "context_sensitive")

    def test_ordinary_reference_variation_is_not_flagged(self):
        report = compare_vowel_evidence(
            reading(margin=2.0),
            reading(margin=1.0, probability=0.7),
        )
        self.assertEqual(report["summary"]["strong_candidates"], 0)
        self.assertEqual(report["comparisons"][0]["tier"], "stable")

    def test_mismatched_profiles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "same pronunciation profile"):
            compare_vowel_evidence(reading(), reading(profile="ashkenazi"))

    def test_mismatched_passages_are_rejected(self):
        candidate = reading()
        candidate["bracha"] = "cal-special"
        with self.assertRaisesRegex(ValueError, "same passage"):
            compare_vowel_evidence(reading(), candidate)

    def test_missing_evidence_is_rejected(self):
        candidate = copy.deepcopy(reading())
        candidate["pronunciation"]["status"] = "disabled"
        with self.assertRaisesRegex(ValueError, "available pronunciation evidence"):
            compare_vowel_evidence(reading(), candidate)

    def test_guided_comparison_does_not_depend_on_manual_labels(self):
        reference = complete_reading()
        candidate = copy.deepcopy(reference)
        slot = candidate["pronunciation"]["words"][10]["slots"][1]
        slot.update(peak_expected_probability=0.02, peak_competitor_margin=-5.0)
        report = compare_vowel_evidence(reference, candidate, "cal-core-guided-mistakes")
        evaluation = report["target_evaluation"]
        self.assertFalse(evaluation["manual_labels_used"])
        self.assertEqual(evaluation["planned_vowels"], 7)
        self.assertEqual(evaluation["detected"], 1)
        self.assertEqual(evaluation["missed"], 6)
        self.assertEqual(evaluation["false_alarms"], 0)

    def test_wrong_vowel_in_same_word_is_not_counted_as_a_catch(self):
        reference = complete_reading("cal-special")
        candidate = copy.deepcopy(reference)
        wrong_slot = candidate["pronunciation"]["words"][3]["slots"][5]
        wrong_slot.update(peak_expected_probability=0.01, peak_competitor_margin=-5.1)
        report = compare_vowel_evidence(
            reference, candidate, "cal-special-guided-mistakes"
        )
        evaluation = report["target_evaluation"]
        self.assertEqual(evaluation["detected"], 0)
        self.assertEqual(evaluation["false_alarms"], 1)
        self.assertEqual(evaluation["mislocalized"], 1)

    def test_guided_target_that_cannot_be_measured_is_reported(self):
        reference = complete_reading()
        candidate = copy.deepcopy(reference)
        candidate["pronunciation"]["words"][22] = {
            "expected_index": 22,
            "word": "סֻכָּה",
            "heard": "סעקה",
            "word_alignment": "wrong",
            "status": "not_measured_word_mismatch",
        }
        report = compare_vowel_evidence(reference, candidate, "cal-core-guided-mistakes")
        target = next(
            item
            for item in report["target_evaluation"]["target_results"]
            if item["word_index"] == 22
        )
        self.assertEqual(target["outcome"], "unmeasured_candidate")
        self.assertEqual(report["target_evaluation"]["unmeasured"], 1)
        self.assertGreater(report["summary"]["reference_only_vowel_slots"], 0)

    def test_weak_correct_reference_is_explicitly_identified(self):
        reference = complete_reading("cal-special")
        reference["pronunciation"]["words"][0]["slots"][0][
            "peak_expected_probability"
        ] = 0.04
        report = compare_vowel_evidence(
            reference, copy.deepcopy(reference), "cal-special-guided-mistakes"
        )
        target = report["target_evaluation"]["target_results"][0]
        self.assertEqual(target["reference_quality"], "weak")
        self.assertEqual(report["target_evaluation"]["weak_reference_targets"], 1)

    def test_clean_repeat_counts_all_strong_candidates_as_false_alarms(self):
        reference = complete_reading()
        candidate = copy.deepcopy(reference)
        slot = candidate["pronunciation"]["words"][10]["slots"][1]
        slot.update(peak_expected_probability=0.02, peak_competitor_margin=-5.0)
        report = compare_vowel_evidence(reference, candidate, "clean-repeat")
        self.assertEqual(report["target_evaluation"]["planned_vowels"], 0)
        self.assertEqual(report["target_evaluation"]["false_alarms"], 1)

    def test_wrong_guided_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "guided scenario"):
            compare_vowel_evidence(
                complete_reading(),
                complete_reading(),
                "cal-special-guided-mistakes",
            )


if __name__ == "__main__":
    unittest.main()
