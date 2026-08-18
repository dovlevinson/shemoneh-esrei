import copy
import unittest

from server.calibration import (
    REQUIRED_VOWEL_SOURCES,
    calibration_suite,
    compare_vowel_evidence,
)


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


if __name__ == "__main__":
    unittest.main()
