import unittest

import numpy as np

from server.pronunciation import PronunciationUnavailable, _ctc_viterbi


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


if __name__ == "__main__":
    unittest.main()
