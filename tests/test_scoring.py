import unittest

from server.scoring import (
    align_words,
    expected_spelling_variants,
    normalize_word,
    score_transcript,
    word_similarity,
)


class NormalizationTests(unittest.TestCase):
    def test_removes_points_and_folds_final_letters(self):
        self.assertEqual(normalize_word("מֶלֶךְ:"), "מלכ")

    def test_divine_name_variants(self):
        self.assertEqual(word_similarity("השם", "יְהֹוָה"), 1.0)
        self.assertEqual(word_similarity("אדוני", "יְהֹוָה"), 1.0)
        self.assertEqual(word_similarity("ה׳", "יְהֹוָה"), 1.0)

    def test_pointed_target_licenses_plene_spelling(self):
        examples = [
            ("תהילתך", "תְּהִלָּתֶךָ"),
            ("אלוהינו", "אֱלֹהֵינוּ"),
            ("ואלוהי", "וֵאלֹהֵי"),
            ("הגיבור", "הַגִּבּוֹר"),
        ]
        for heard, expected in examples:
            with self.subTest(heard=heard, expected=expected):
                self.assertIn(normalize_word(heard), expected_spelling_variants(expected))
                self.assertEqual(word_similarity(heard, expected), 1.0)

    def test_unlicensed_mater_does_not_become_exact(self):
        self.assertLess(word_similarity("ביהווה", "בְּאַהֲבָה"), 1.0)

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

    def test_teacher_avot_transcript_is_not_penalized_for_plene_spelling(self):
        expected = [
            "אֲדֹנָי", "שְׂפָתַי", "תִּפְתָּח", "וּפִי", "יַגִּיד", "תְּהִלָּתֶךָ",
            "בָּרוּךְ", "אַתָּה", "יְהֹוָה", "אֱלֹהֵינוּ", "וֵאלֹהֵי", "אֲבוֹתֵינוּ",
            "אֱלֹהֵי", "אַבְרָהָם", "אֱלֹהֵי", "יִצְחָק", "וֵאלֹהֵי", "יַעֲקֹב",
            "הָאֵל", "הַגָּדוֹל", "הַגִּבּוֹר", "וְהַנּוֹרָא", "אֵל", "עֶלְיוֹן",
            "גּוֹמֵל", "חֲסָדִים", "טוֹבִים", "וְקוֹנֵה", "הַכֹּל", "וְזוֹכֵר",
            "חַסְדֵי", "אָבוֹת", "וּמֵבִיא", "גוֹאֵל", "לִבְנֵי", "בְנֵיהֶם",
            "לְמַעַן", "שְׁמוֹ", "בְּאַהֲבָה", "מֶלֶךְ", "עוֹזֵר", "וּמוֹשִׁיעַ",
            "וּמָגֵן", "בָּרוּךְ", "אַתָּה", "יְהֹוָה", "מָגֵן", "אַבְרָהָם",
        ]
        transcript = (
            "אדוני ספסי תבטח ופי יגיד תהילתך ברוך אתה אדוני אלוהינו ואלוהי "
            "אבותינו אלוהי אברהם אלוהי יצחק ואלוהי יעקב האל הגדול הגיבור "
            "והנורא אל עליון גומל חסדים טובים וקונה הכל וזוכר חסדי אבות ומביא "
            "גואל לבני בניהם למען שמו ביהווה מלך עוזר ומושיע ומגן ברוך אתה ה׳ "
            "מגן אברהם"
        )
        result = score_transcript(expected, transcript)
        self.assertEqual(result["counts"]["ok"], 45)
        self.assertEqual(result["counts"]["almost"], 0)
        self.assertEqual(result["counts"]["wrong"], 3)
        self.assertEqual(result["estimated_accuracy"], 94)


if __name__ == "__main__":
    unittest.main()
