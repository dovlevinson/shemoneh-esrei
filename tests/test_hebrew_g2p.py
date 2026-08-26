import unittest

from server.hebrew_g2p import (
    PRONUNCIATION_POLICY_VERSION,
    collapse_model_phone,
    pronunciation_policy,
    pronunciation_map,
    pronunciation_variants,
    written_vowels,
)


def phones(word, profile="mixed", divine_policy="both"):
    variant = pronunciation_variants(word, profile, divine_policy)[0]
    return [slot.allowed for slot in variant.slots]


class HebrewG2PTests(unittest.TestCase):
    def test_qamats_respects_pronunciation_profile(self):
        self.assertIn(frozenset({"a", "o"}), phones("בָּרוּךְ", "mixed"))
        self.assertIn(frozenset({"a"}), phones("בָּרוּךְ", "sephardi"))
        self.assertIn(frozenset({"o"}), phones("בָּרוּךְ", "ashkenazi"))

    def test_holam_malei_does_not_add_a_vav_consonant(self):
        allowed = phones("קָדוֹשׁ")
        self.assertIn(frozenset({"o"}), allowed)
        self.assertNotIn(frozenset({"v"}), allowed)

    def test_source_marker_records_sheva_without_forcing_an_acoustic_slot(self):
        variants = pronunciation_variants("נוֹפְ֒לִים")
        sources = [slot.source for slot in variants[0].slots]
        self.assertNotIn("שווא נע", sources)
        sheva = next(item for item in written_vowels("נוֹפְ֒לִים") if item["symbol"] == "ְ")
        self.assertEqual(sheva["shva_classification"], "na")
        self.assertEqual(sheva["evaluation_tier"], "research_only")
        self.assertFalse(sheva["counts_toward_primary"])

    def test_sheva_after_word_initial_shuruk_is_recorded_as_optional(self):
        for word in ("וּבְרָכָה", "וּקְדוֹשִׁים"):
            sheva = next(item for item in written_vowels(word) if item["symbol"] == "ְ")
            self.assertEqual(sheva["classification_rule"], "after_shuruk")
            self.assertEqual(sheva["accepted_realizations"], ["BRIEF_E", "NONE"])
            self.assertNotIn("שווא נע", [slot.source for slot in pronunciation_variants(word)[0].slots])

    def test_sheva_after_written_long_vowel_is_classified_but_not_forced(self):
        sheva = next(item for item in written_vowels("נוֹפְלִים") if item["symbol"] == "ְ")
        self.assertEqual(sheva["shva_classification"], "na")
        self.assertEqual(sheva["classification_rule"], "after_written_long_vowel")
        self.assertFalse(sheva["counts_toward_primary"])

    def test_consonantal_vav_with_holam_keeps_both_v_and_o(self):
        for word in ("וּבְמִצְוֹתֶיךָ", "מִצְוֺתֶיךָ"):
            sequence = [(slot.kind, slot.allowed) for slot in pronunciation_variants(word)[0].slots]
            self.assertIn(("consonant", frozenset({"v"})), sequence)
            self.assertIn(("vowel", frozenset({"o"})), sequence)

    def test_written_families_merge_chataf_and_shuruk_as_requested(self):
        chataf = next(item for item in written_vowels("אֲנַחְנוּ") if item["source"] == "חטף פתח")
        shuruk = next(item for item in written_vowels("רוּחַ") if item["source"] == "שורוק")
        kubutz = next(item for item in written_vowels("שֻׁלְחָן") if item["source"] == "קובוץ")
        self.assertEqual(chataf["sound_family"], "A")
        self.assertEqual(shuruk["sound_family"], "U")
        self.assertEqual(kubutz["sound_family"], "U")
        self.assertTrue(chataf["counts_toward_primary"])

    def test_furtive_patah_precedes_final_guttural(self):
        variant = pronunciation_variants("רוּחַ")[0]
        tail = [(slot.kind, slot.allowed) for slot in variant.slots[-2:]]
        self.assertEqual(
            tail,
            [("vowel", frozenset({"a"})), ("consonant", frozenset({"x"}))],
        )

    def test_divine_name_policy_builds_separate_whole_word_variants(self):
        both = pronunciation_variants("אֲדֹנָי", divine_policy="both")
        self.assertEqual([variant.name for variant in both], ["hashem", "adonai"])
        adonai = pronunciation_variants("יְהֹוָה", divine_policy="adonai")
        self.assertEqual([variant.name for variant in adonai], ["adonai"])

    def test_map_is_serializable_and_retains_accepted_alternatives(self):
        mapped = pronunciation_map(["בָּרוּךְ"])
        qamats = next(
            slot
            for slot in mapped[0]["variants"][0]["slots"]
            if slot["source"] == "קמץ"
        )
        self.assertEqual(qamats["allowed"], ["a", "o"])
        self.assertEqual(mapped[0]["policy_version"], PRONUNCIATION_POLICY_VERSION)

    def test_mixed_profile_documents_common_diphthong_realizations(self):
        tsere = next(item for item in written_vowels("סֵפֶר") if item["source"] == "צירי")
        holam = next(item for item in written_vowels("חוֹנֵן") if item["source"] == "חולם מלא")
        self.assertEqual(tsere["accepted_realizations"], ["E", "EI"])
        self.assertEqual(holam["accepted_realizations"], ["O", "OY"])

    def test_machine_readable_policy_has_five_classes_and_research_only_sheva(self):
        policy = pronunciation_policy("mixed")
        self.assertEqual(policy["version"], PRONUNCIATION_POLICY_VERSION)
        self.assertEqual(policy["acoustic_classes"], ["A", "E", "I", "O", "U"])
        sheva = next(item for item in policy["mappings"] if item["source"] == "שווא")
        self.assertFalse(sheva["counts_toward_primary"])
        self.assertFalse(policy["authoritative_grade"])

    def test_model_phone_collapse_is_conservative(self):
        self.assertEqual(collapse_model_phone("ʃ"), "sh")
        self.assertEqual(collapse_model_phone("t͡s"), "ts")
        self.assertEqual(collapse_model_phone("aʊ"), "o")
        self.assertIsNone(collapse_model_phone("<pad>"))
        self.assertIsNone(collapse_model_phone("θ"))


if __name__ == "__main__":
    unittest.main()
