import unittest

from research.pronunciation_report import expected_words_for_bracha


class PronunciationReportTests(unittest.TestCase):
    def test_extracts_pointed_words_from_the_browser_data(self):
        bracha, words = expected_words_for_bracha(4)
        self.assertTrue(bracha["he"])
        self.assertGreater(len(words), 10)
        self.assertTrue(any("\u05b8" in word for word in words))


if __name__ == "__main__":
    unittest.main()
