import unittest
from pathlib import Path

from server.hebrew_g2p import PRONUNCIATION_POLICY_VERSION, pronunciation_map
from server.passage_catalog import passage_catalog


ROOT = Path(__file__).resolve().parents[1]


class PassageCatalogTests(unittest.TestCase):
    def test_catalog_exposes_exactly_nineteen_brachot(self):
        catalog = passage_catalog(ROOT / "index.html")
        self.assertEqual(catalog["schema_version"], "kriah-passage-catalog-v1")
        self.assertEqual([item["id"] for item in catalog["passages"]], [str(i) for i in range(1, 20)])
        self.assertIn("סְלַח לָֽנוּ", catalog["passages"][5]["segments"][0]["text"])
        self.assertIn("עַל־הַצַּדִּיקִים", catalog["passages"][12]["segments"][0]["text"])
        self.assertIn("אֶת־צֶֽמַח", catalog["passages"][14]["segments"][0]["text"])

    def test_catalog_preserves_seasonal_and_special_conditions(self):
        passages = passage_catalog(ROOT / "index.html")["passages"]
        conditions = {
            segment["condition"]
            for passage in passages
            for segment in passage["segments"]
        }
        for condition in ("winter", "notwinter", "ayt", "notayt", "rc", "nissim", "chanukah", "purim"):
            self.assertIn(condition, conditions)

    def test_every_catalog_word_builds_a_versioned_pronunciation_map(self):
        passages = passage_catalog(ROOT / "index.html")["passages"]
        words = [
            word
            for passage in passages
            for segment in passage["segments"]
            for token in segment["text"].split()
            for word in token.split("־")
            if any("א" <= char <= "ת" for char in word)
        ]
        mapped = pronunciation_map(words)
        self.assertEqual(len(mapped), len(words))
        self.assertTrue(all(item["policy_version"] == PRONUNCIATION_POLICY_VERSION for item in mapped))
        self.assertTrue(all(item["variants"] for item in mapped))
        self.assertGreater(sum(len(item["written_vowels"]) for item in mapped), 1000)

    def test_catalog_consonantal_vav_holam_does_not_lose_its_v(self):
        mapped = pronunciation_map(["וּבְמִצְוֹתֶֽיךָ"])[0]["variants"][0]["slots"]
        self.assertTrue(any(slot["kind"] == "consonant" and slot["allowed"] == ["v"] for slot in mapped))
        self.assertTrue(any(slot["kind"] == "vowel" and slot["allowed"] == ["o"] for slot in mapped))


if __name__ == "__main__":
    unittest.main()
