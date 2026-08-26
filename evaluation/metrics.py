"""Compute pilot gates from teacher labels and model estimates.

Input is JSON Lines. Each row must include speaker_id, split, human_pass,
model_score, and review_required. Threshold selection belongs only on the
calibration split. Final reporting belongs only on the speaker-disjoint test
split.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Iterable


REQUIRED = {"attempt_id", "speaker_id", "split", "human_pass", "model_score", "review_required"}


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = REQUIRED - row.keys()
            if missing:
                raise ValueError(f"line {line_number} is missing: {', '.join(sorted(missing))}")
            if row["split"] not in {"calibration", "test"}:
                raise ValueError(f"line {line_number} has an invalid split")
            rows.append(row)
    return rows


def assert_speaker_disjoint(rows: Iterable[dict]) -> None:
    speakers = {name: set() for name in ("calibration", "test")}
    for row in rows:
        speakers[row["split"]].add(str(row["speaker_id"]))
    overlap = speakers["calibration"] & speakers["test"]
    if overlap:
        raise ValueError(f"speaker leakage across splits: {', '.join(sorted(overlap))}")


def wilson_upper(errors: int, total: int, z: float = 1.96) -> float | None:
    if total == 0:
        return None
    proportion = errors / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    spread = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return (centre + spread) / denominator


def evaluate(rows: Iterable[dict], threshold: float = 90, split: str = "test") -> dict:
    selected = [row for row in rows if row["split"] == split]
    counts = Counter()
    speakers = set()
    for row in selected:
        speakers.add(str(row["speaker_id"]))
        human_pass = bool(row["human_pass"])
        model_pass = float(row["model_score"]) >= threshold and not bool(row["review_required"])
        if human_pass and model_pass:
            counts["true_pass"] += 1
        elif human_pass and not model_pass:
            counts["false_flag"] += 1
        elif not human_pass and model_pass:
            counts["false_pass"] += 1
        else:
            counts["true_flag"] += 1

    human_passes = counts["true_pass"] + counts["false_flag"]
    human_fails = counts["false_pass"] + counts["true_flag"]
    total = human_passes + human_fails
    false_pass_rate = counts["false_pass"] / human_fails if human_fails else None
    false_flag_rate = counts["false_flag"] / human_passes if human_passes else None
    return {
        "split": split,
        "threshold": threshold,
        "attempts": total,
        "speakers": len(speakers),
        "counts": dict(counts),
        "false_pass_rate": false_pass_rate,
        "false_pass_wilson_95_upper": wilson_upper(counts["false_pass"], human_fails),
        "false_flag_rate": false_flag_rate,
        "agreement": (counts["true_pass"] + counts["true_flag"]) / total if total else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--threshold", type=float, default=90)
    parser.add_argument("--split", choices=["calibration", "test"], default="test")
    args = parser.parse_args()
    rows = load_jsonl(args.manifest)
    assert_speaker_disjoint(rows)
    print(json.dumps(evaluate(rows, args.threshold, args.split), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
