import unittest

from server.hebrew_g2p import (
    collapse_model_phone,
    pronunciation_map,
    pronunciation_variants,
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

    def test_source_marker_makes_the_sheva_audible(self):
        variants = pronunciation_variants("נוֹפְ֒לִים")
        sources = [slot.source for slot in variants[0].slots]
        self.assertIn("שווא נע", sources)

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

    def test_model_phone_collapse_is_conservative(self):
        self.assertEqual(collapse_model_phone("ʃ"), "sh")
        self.assertEqual(collapse_model_phone("t͡s"), "ts")
        self.assertEqual(collapse_model_phone("aʊ"), "o")
        self.assertIsNone(collapse_model_phone("<pad>"))
        self.assertIsNone(collapse_model_phone("θ"))


if __name__ == "__main__":
    unittest.main()
