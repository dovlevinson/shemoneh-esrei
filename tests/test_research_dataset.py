import json
from pathlib import Path
import tempfile
import unittest

from evaluation.research_dataset import aggregate, load_packages


def sample(sample_id="S01-3", speaker="S01", passage="3", label="human_correct", margin=2.0):
    return {
        "schema_version": "kriah-research-sample-v1",
        "sample_id": sample_id,
        "speaker": {"code": speaker},
        "passage": {"id": passage},
        "reading_truth": "known_acceptable",
        "model_signature": {
            "speech": "whisper-test",
            "pronunciation": "ctc-test",
            "pronunciation_revision": "abc",
        },
        "human_review": {
            "complete": True,
            "word_labels": {"0": {"label": "human_correct"}},
            "vowel_labels": {"0:0": {"label": label}},
        },
        "analysis": {
            "pronunciation": {
                "words": [
                    {
                        "expected_index": 0,
                        "word": "אַתָּה",
                        "status": "measured_uncalibrated",
                        "slots": [
                            {
                                "kind": "vowel",
                                "source": "פתח",
                                "peak_competitor_margin": margin,
                                "peak_expected_probability": 0.8,
                            }
                        ],
                    }
                ]
            }
        },
    }


class ResearchDatasetTests(unittest.TestCase):
    def test_aggregate_reports_overlap_and_label_distributions(self):
        report = aggregate(
            [
                sample(),
                sample("S02-3", "S02", "3", "human_wrong_vowel", -4.0),
            ]
        )
        self.assertEqual(report["recordings"], 2)
        self.assertEqual(report["speakers"], 2)
        self.assertEqual(report["shared_passages_across_speakers"], ["3"])
        self.assertEqual(report["vowel_labels"]["human_correct"], 1)
        self.assertEqual(report["vowel_labels"]["human_wrong_vowel"], 1)
        self.assertTrue(report["evaluation_readiness"]["can_describe_label_separation"])
        self.assertFalse(report["evaluation_readiness"]["validated_threshold_available"])

    def test_loads_samples_and_deduplicates_manifest_entries(self):
        item = sample()
        manifest = {
            "schema_version": "kriah-research-manifest-v1",
            "samples": [item, item],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_packages([path])
        self.assertEqual(len(loaded), 1)


if __name__ == "__main__":
    unittest.main()
