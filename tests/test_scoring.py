import unittest

from server.scoring import align_words, normalize_word, score_transcript, word_similarity


class NormalizationTests(unittest.TestCase):
    def test_removes_points_and_folds_final_letters(self):
        self.assertEqual(normalize_word("מֶלֶךְ:"), "מלכ")

    def test_divine_name_variants(self):
        self.assertEqual(word_similarity("השם", "יְהֹוָה"), 1.0)
        self.assertEqual(word_similarity("אדוני", "יְהֹוָה"), 1.0)

    def test_short_words_are_strict(self):
        self.assertEqual(word_similarity("מי", "כי"), 0.0)

    def test_distinct_consonants_are_not_folded_to_exact(self):
        self.assertLess(word_similarity("חדוש", "קדוש"), 1.0)
        self.assertLess(word_similarity("ברכה", "ברוך"), 0.55)

    def test_one_changed_consonant_in_long_word_is_not_green(self):
        rows = align_words(["וכשאמרתנו"], ["וכשאמרכנו"])
        self.assertNotEqual(rows[0].operation, "ok")


class AlignmentTests(unittest.TestCase):
    def test_exact_read(self):
        result = score_transcript(["אַתָּה", "קָדוֹשׁ"], "אתה קדוש")
        self.assertEqual(result["estimated_accuracy"], 100)
        self.assertFalse(result["review_required"])

    def test_missing_word(self):
        result = score_transcript(["אתה", "חונן", "לאדם"], "אתה לאדם")
        self.assertEqual(result["counts"]["missing"], 1)
        self.assertTrue(result["review_required"])

    def test_extra_word_is_preserved_and_penalized(self):
        result = score_transcript(["אתה", "קדוש"], "אתה ממש קדוש")
        self.assertEqual(result["counts"]["extra"], 1)
        self.assertEqual(result["estimated_accuracy"], 75)

    def test_different_word_is_not_green(self):
        rows = align_words(["ברוך"], ["ברכה"])
        self.assertEqual(rows[0].operation, "wrong")


if __name__ == "__main__":
    unittest.main()
