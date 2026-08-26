import unittest

import numpy as np

from server.hebrew_g2p import pronunciation_variants
from server.pronunciation import (
    CtcPronunciationAssessor,
    PronunciationUnavailable,
    _ctc_viterbi,
)
from server.transcriber import TranscriptWord


class CtcAlignmentTests(unittest.TestCase):
    def test_aligns_ordered_slots_through_blank_states(self):
        slot_scores = np.full((5, 2), -10.0, dtype=np.float32)
        slot_scores[1, 0] = -0.01
        slot_scores[3, 1] = -0.02
        blank_scores = np.array([-0.01, -5.0, -0.01, -5.0, -0.01])
        assigned = _ctc_viterbi(slot_scores, blank_scores, [("b",), ("a",)])
        self.assertEqual(assigned, [[1], [3]])

    def test_repeated_phone_requires_an_intervening_blank(self):
        slot_scores = np.full((5, 2), -10.0, dtype=np.float32)
        slot_scores[1, 0] = -0.01
        slot_scores[3, 1] = -0.01
        blank_scores = np.array([-0.01, -5.0, -0.01, -5.0, -0.01])
        assigned = _ctc_viterbi(slot_scores, blank_scores, [("a",), ("a",)])
        self.assertEqual(assigned, [[1], [3]])

    def test_rejects_a_window_too_short_for_the_expected_sequence(self):
        with self.assertRaises(PronunciationUnavailable):
            _ctc_viterbi(
                np.full((1, 2), -1.0, dtype=np.float32),
                np.array([-0.1]),
                [("b",), ("a",)],
            )


class VowelEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assessor = CtcPronunciationAssessor()
        self.posterior = np.full((7, 5), -8.0, dtype=np.float32)
        self.posterior[:, 0] = -0.2
        self.posterior[1, 1] = -0.01  # /b/
        self.posterior[3, 3] = -0.01  # spoken /e/, although /a/ is expected
        self.posterior[5, 4] = -0.01  # /t/
        self.assessor._resources = {
            "blank_id": 0,
            "buckets": {"b": [1], "a": [2], "e": [3], "t": [4]},
            "phone_ids": [1, 2, 3, 4],
            "phone_by_id": {1: "b", 2: "a", 3: "e", 4: "t"},
        }

    def test_wrong_vowel_stays_in_its_own_acoustic_position(self):
        variant = pronunciation_variants("בַּתּ")[0]
        result = self.assessor._variant_evidence(self.posterior, 0, 0.1, variant)
        vowel = next(slot for slot in result["slots"] if slot["kind"] == "vowel")
        self.assertEqual(vowel["strongest_competing_phone"], "e")
        self.assertLess(vowel["peak_competitor_margin"], 0)
        self.assertEqual(vowel["start"], 0.3)

    def test_vowel_competitor_never_reports_a_consonant(self):
        self.posterior[3, 1] = -0.005
        variant = pronunciation_variants("בַּתּ")[0]
        result = self.assessor._variant_evidence(self.posterior, 0, 0.1, variant)
        vowel = next(slot for slot in result["slots"] if slot["kind"] == "vowel")
        self.assertEqual(vowel["strongest_competing_phone"], "e")

    def test_timestamped_mismatched_word_is_still_measured(self):
        self.assessor._posteriors = lambda _path: (self.posterior, 0.7)
        result = self.assessor.assess(
            path="unused.webm",
            expected_words=["בַּתּ"],
            alignment_rows=[
                {
                    "expected_index": 0,
                    "heard_index": 0,
                    "heard": "בית",
                    "operation": "wrong",
                }
            ],
            transcript_words=[TranscriptWord("בית", 0.0, 0.7, 0.9)],
            transcript_duration=0.7,
        )
        self.assertEqual(result["words"][0]["status"], "measured_uncalibrated")
        self.assertEqual(
            result["words"][0]["word_window_reliability"], "mismatched_transcript"
        )
        self.assertEqual(result["summary"]["mismatched_words_measured"], 1)

    def test_missing_word_without_audio_window_is_not_invented(self):
        self.assessor._posteriors = lambda _path: (self.posterior, 0.7)
        result = self.assessor.assess(
            path="unused.webm",
            expected_words=["בַּתּ"],
            alignment_rows=[
                {
                    "expected_index": 0,
                    "heard_index": None,
                    "heard": None,
                    "operation": "missing",
                }
            ],
            transcript_words=[],
            transcript_duration=0.7,
        )
        self.assertEqual(result["words"][0]["status"], "not_measured_word_mismatch")


if __name__ == "__main__":
    unittest.main()
