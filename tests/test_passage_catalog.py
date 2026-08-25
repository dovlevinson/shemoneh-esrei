import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
