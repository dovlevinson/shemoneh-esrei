"""Compare two shadow reports without turning their deltas into a grade."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _slots(report: dict) -> dict[tuple[int, int], dict]:
    flattened = {}
    for word in report["pronunciation"]["words"]:
        for slot_index, slot in enumerate(word.get("slots", [])):
            flattened[(word["expected_index"], slot_index)] = {
                "word": word["word"],
                "slot_index": slot_index,
                **slot,
            }
    return flattened


def compare_reports(baseline: dict, comparison: dict) -> dict:
    left = _slots(baseline)
    right = _slots(comparison)
    rows = []
    for key in sorted(left.keys() & right.keys()):
        baseline_slot = left[key]
        comparison_slot = right[key]
        baseline_margin = baseline_slot["peak_competitor_margin"]
        comparison_margin = comparison_slot["peak_competitor_margin"]
        baseline_probability = baseline_slot["peak_expected_probability"]
        comparison_probability = comparison_slot["peak_expected_probability"]
        rows.append(
            {
                "expected_index": key[0],
                "word": baseline_slot["word"],
                "slot_index": key[1],
                "source": baseline_slot["source"],
                "allowed": baseline_slot["allowed"],
                "baseline_margin": baseline_margin,
                "comparison_margin": comparison_margin,
                "margin_delta": round(comparison_margin - baseline_margin, 4),
                "baseline_probability": baseline_probability,
                "comparison_probability": comparison_probability,
                "probability_delta": round(
                    comparison_probability - baseline_probability, 6
                ),
            }
        )
    rows.sort(key=lambda row: row["margin_delta"])
    return {
        "comparison_version": 1,
        "baseline_audio": baseline.get("audio_file"),
        "comparison_audio": comparison.get("audio_file"),
        "shared_slots": len(rows),
        "slots": rows,
        "warning": (
            "Uncalibrated paired-recording deltas. Natural speaker and timing "
            "variation are not pronunciation labels or student grades."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_reports(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.comparison.read_text(encoding="utf-8")),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
