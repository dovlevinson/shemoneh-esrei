"""Aggregate the two-bracha balanced adult Kriah study.

Inputs are analyzed packages downloaded from ``/study``. Audio is ignored and
is never copied into the summary. The resulting thresholds are exploratory and
cannot be used for automatic student decisions.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable

from .metrics import wilson_upper


DEFAULT_MARGIN_THRESHOLDS = (0.0, -1.0, -2.0, -3.0, -4.0)
MAX_EXPECTED_PROBABILITY = 0.20
CONTEXT_SENSITIVE_SOURCES = {"שווא נע"}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": round(mean(values), 6) if values else None,
        "median": round(median(values), 6) if values else None,
        "minimum": round(min(values), 6) if values else None,
        "maximum": round(max(values), 6) if values else None,
    }


def load_package(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "kriah-rapid-validation-analyzed-v1":
        raise ValueError(f"{path}: expected kriah-rapid-validation-analyzed-v1")
    if not data.get("complete"):
        raise ValueError(f"{path}: package is not complete and confirmed")
    speaker = data.get("speaker") or {}
    code = str(speaker.get("speakerCode") or "")
    assignment = str(speaker.get("assignment") or "")
    if not code or assignment not in {"A", "B"}:
        raise ValueError(f"{path}: valid speaker code and assignment are required")
    recordings = data.get("recordings") or []
    if len(recordings) != 2 or {str(item.get("passage_id")) for item in recordings} != {"3", "4"}:
        raise ValueError(f"{path}: expected exactly brachot 3 and 4")
    expected_roles = {"A": {"3": "correct", "4": "guided_mistakes"}, "B": {"3": "guided_mistakes", "4": "correct"}}
    for recording in recordings:
        passage = str(recording.get("passage_id"))
        if recording.get("role") != expected_roles[assignment][passage]:
            raise ValueError(f"{path}: recording roles do not match assignment {assignment}")
        analysis = recording.get("analysis") or {}
        if (analysis.get("pronunciation") or {}).get("status") != "evidence_available":
            raise ValueError(f"{path}: {passage} is missing pronunciation evidence")
    return {
        "speaker_code": code,
        "assignment": assignment,
        "reading_level": str(speaker.get("readingLevel") or "unknown"),
        "tradition": str(speaker.get("tradition") or "unknown"),
        "device": str(speaker.get("device") or "unknown"),
        "room": str(speaker.get("room") or "unknown"),
        "recordings": recordings,
    }


def _slots(recording: dict) -> dict[str, dict]:
    slots = {}
    pronunciation = recording["analysis"]["pronunciation"]
    for word in pronunciation.get("words") or []:
        if word.get("status") != "measured_uncalibrated":
            continue
        word_index = word.get("expected_index")
        if word_index is None:
            continue
        for slot_index, slot in enumerate(word.get("slots") or []):
            if slot.get("kind") != "vowel" or slot.get("source") in CONTEXT_SENSITIVE_SOURCES:
                continue
            probability = _number(slot.get("peak_expected_probability"))
            margin = _number(slot.get("peak_competitor_margin"))
            if probability is None or margin is None:
                continue
            key = f"{word_index}:{slot_index}"
            slots[key] = {
                "key": key,
                "word_index": word_index,
                "slot_index": slot_index,
                "word": word.get("word"),
                "source": slot.get("source"),
                "expected_probability": probability,
                "competitor_margin": margin,
                "word_alignment": word.get("word_alignment"),
                "word_window_reliability": word.get("word_window_reliability"),
            }
    return slots


def evidence_rows(speakers: list[dict]) -> tuple[list[dict], list[dict]]:
    target_definitions: dict[tuple[str, str], dict] = {}
    for speaker in speakers:
        for recording in speaker["recordings"]:
            for target in recording.get("targets") or []:
                target_definitions[(str(recording["passage_id"]), str(target["key"]))] = target

    rows = []
    missing_targets = []
    for speaker in speakers:
        for recording in speaker["recordings"]:
            passage = str(recording["passage_id"])
            measured = _slots(recording)
            recording_targets = {str(item["key"]): item for item in recording.get("targets") or []}
            for key, target in recording_targets.items():
                if key not in measured:
                    missing_targets.append(
                        {
                            "speaker_code": speaker["speaker_code"],
                            "passage_id": passage,
                            "key": key,
                            "source": target.get("source"),
                        }
                    )
            for key, slot in measured.items():
                definition = target_definitions.get((passage, key))
                if key in recording_targets:
                    truth = "planned_error"
                elif recording.get("role") == "correct" and definition:
                    truth = "matched_correct_control"
                else:
                    truth = "other_correct_vowel"
                rows.append(
                    {
                        **slot,
                        "speaker_code": speaker["speaker_code"],
                        "assignment": speaker["assignment"],
                        "reading_level": speaker["reading_level"],
                        "tradition": speaker["tradition"],
                        "device": speaker["device"],
                        "room": speaker["room"],
                        "passage_id": passage,
                        "role": recording.get("role"),
                        "truth": truth,
                        "target_source": definition.get("source") if definition else None,
                    }
                )
    return rows, missing_targets


def _is_alert(row: dict, threshold: float) -> bool:
    return bool(
        row["competitor_margin"] <= threshold
        and row["expected_probability"] <= MAX_EXPECTED_PROBABILITY
    )


def _metric_counts(rows: list[dict], missing_targets: list[dict], threshold: float) -> Counter:
    counts = Counter(
        targets_unmeasured=len(missing_targets),
        targets_evaluable=0,
        targets_detected=0,
        correct_vowels_evaluable=0,
        false_alarms=0,
        matched_controls_evaluable=0,
        matched_control_false_alarms=0,
    )
    for row in rows:
        if row["truth"] == "planned_error":
            counts["targets_evaluable"] += 1
            if _is_alert(row, threshold):
                counts["targets_detected"] += 1
        else:
            counts["correct_vowels_evaluable"] += 1
            if _is_alert(row, threshold):
                counts["false_alarms"] += 1
            if row["truth"] == "matched_correct_control":
                counts["matched_controls_evaluable"] += 1
                if _is_alert(row, threshold):
                    counts["matched_control_false_alarms"] += 1
    counts["targets_planned"] = counts["targets_evaluable"] + counts["targets_unmeasured"]
    return counts


def _finalize(counts: Counter) -> dict:
    negatives = counts["correct_vowels_evaluable"]
    return {
        **dict(counts),
        "target_evaluable_rate": _rate(counts["targets_evaluable"], counts["targets_planned"]),
        "sensitivity": _rate(counts["targets_detected"], counts["targets_evaluable"]),
        "false_alarm_rate": _rate(counts["false_alarms"], negatives),
        "false_alarm_wilson_95_upper": (
            round(wilson_upper(counts["false_alarms"], negatives), 6) if negatives else None
        ),
        "matched_control_false_alarm_rate": _rate(
            counts["matched_control_false_alarms"], counts["matched_controls_evaluable"]
        ),
    }


def aggregate(speakers: list[dict], thresholds: Iterable[float] = DEFAULT_MARGIN_THRESHOLDS) -> dict:
    codes = [speaker["speaker_code"] for speaker in speakers]
    duplicates = sorted(code for code, count in Counter(codes).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate speaker codes: {', '.join(duplicates)}")
    rows, missing_targets = evidence_rows(speakers)
    assignment_counts = Counter(speaker["assignment"] for speaker in speakers)

    position_groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["truth"] not in {"planned_error", "matched_correct_control"}:
            continue
        position = f"{row['passage_id']}:{row['key']}"
        position_groups[position][row["truth"]].append(row)
    positions = {}
    for position, truths in sorted(position_groups.items()):
        example = next(iter(next(iter(truths.values()))))
        positions[position] = {
            "passage_id": example["passage_id"],
            "key": example["key"],
            "word": example["word"],
            "source": example["target_source"] or example["source"],
            "error_expected_probability": _summary([row["expected_probability"] for row in truths["planned_error"]]),
            "correct_expected_probability": _summary([row["expected_probability"] for row in truths["matched_correct_control"]]),
            "error_competitor_margin": _summary([row["competitor_margin"] for row in truths["planned_error"]]),
            "correct_competitor_margin": _summary([row["competitor_margin"] for row in truths["matched_correct_control"]]),
        }

    threshold_results = []
    for threshold in thresholds:
        counts = _metric_counts(rows, missing_targets, float(threshold))
        metrics = _finalize(counts)
        exploratory_pass = bool(
            len(speakers) >= 4
            and assignment_counts["A"] >= 2
            and assignment_counts["B"] >= 2
            and metrics["target_evaluable_rate"] is not None
            and metrics["target_evaluable_rate"] >= 0.90
            and metrics["sensitivity"] is not None
            and metrics["sensitivity"] >= 0.80
            and metrics["false_alarm_rate"] is not None
            and metrics["false_alarm_rate"] <= 0.02
        )
        threshold_results.append(
            {"competitor_margin_threshold": float(threshold), **metrics, "exploratory_gate_passed": exploratory_pass}
        )

    return {
        "schema_version": "kriah-rapid-validation-summary-v1",
        "speaker_count": len(speakers),
        "assignments": dict(sorted(assignment_counts.items())),
        "strata": {
            "reading_levels": dict(Counter(s["reading_level"] for s in speakers)),
            "traditions": dict(Counter(s["tradition"] for s in speakers)),
            "devices": dict(Counter(s["device"] for s in speakers)),
            "rooms": dict(Counter(s["room"] for s in speakers)),
        },
        "thresholds": threshold_results,
        "matched_target_positions": positions,
        "missing_targets": missing_targets,
        "interpretation": {
            "design": "Unpaired balanced adult comparison of the same vowel positions under correct and guided-error conditions.",
            "production_status": "blocked",
            "reason": "A small adult convenience sample can select a candidate method for child testing, but cannot validate automatic student decisions.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+", help="analyzed rapid-study packages")
    parser.add_argument(
        "--thresholds",
        default=",".join(str(value) for value in DEFAULT_MARGIN_THRESHOLDS),
        help="comma-separated competitor-margin thresholds",
    )
    parser.add_argument("--output", help="optional private JSON report path")
    args = parser.parse_args()
    thresholds = [float(value) for value in args.thresholds.split(",") if value.strip()]
    report = aggregate([load_package(path) for path in args.packages], thresholds)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
