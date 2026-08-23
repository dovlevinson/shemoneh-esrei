"""Aggregate the multi-speaker Kriah vowel validation study.

The input is one or more analyzed packages downloaded from ``/study``.  Older
``kriah-nikud-pair-v3`` exports can be supplied with ``--legacy-pair`` as a
baseline.  Audio is ignored and never copied into the report.

This is an exploratory threshold analysis.  It cannot promote the shadow model
to an automatic student decision layer.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Iterable

from .metrics import wilson_upper


DEFAULT_THRESHOLDS = (-5.0, -4.5, -4.0, -3.0)
MAX_EXPECTED_PROBABILITY = 0.20
WEAK_REFERENCE_PROBABILITY = 0.12


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _is_alert(row: dict, threshold: float) -> bool:
    candidate = row.get("candidate") or {}
    margin_delta = _number(row.get("margin_delta"))
    margin = _number(candidate.get("peak_competitor_margin"))
    probability = _number(candidate.get("peak_expected_probability"))
    return bool(
        row.get("tier") != "context_sensitive"
        and margin_delta is not None
        and margin is not None
        and probability is not None
        and margin_delta <= threshold
        and margin < 0
        and probability <= MAX_EXPECTED_PROBABILITY
    )


def _reference_usable(row: dict) -> bool:
    if row.get("tier") == "context_sensitive":
        return False
    probability = _number((row.get("reference") or {}).get("peak_expected_probability"))
    return probability is not None and probability >= WEAK_REFERENCE_PROBABILITY


def _target_keys(comparison: dict) -> tuple[set[str], list[dict]]:
    target_evaluation = comparison.get("target_evaluation") or {}
    targets = target_evaluation.get("target_results") or []
    return {str(item.get("key")) for item in targets}, targets


def _score_comparison(comparison: dict, threshold: float, has_targets: bool) -> dict:
    rows = {
        str(row.get("key")): row
        for row in comparison.get("comparisons") or []
        if row.get("key") is not None
    }
    target_keys, targets = _target_keys(comparison) if has_targets else (set(), [])
    counts = Counter()
    sources = defaultdict(Counter)

    for target in targets:
        key = str(target.get("key"))
        row = rows.get(key)
        source = str(target.get("source") or "unknown")
        counts["targets_planned"] += 1
        sources[source]["planned"] += 1
        if target.get("reference_quality") == "weak" or not row or not _reference_usable(row):
            counts["targets_weak_or_unmeasured"] += 1
            sources[source]["weak_or_unmeasured"] += 1
        else:
            counts["targets_evaluable"] += 1
            sources[source]["evaluable"] += 1
            if _is_alert(row, threshold):
                counts["targets_detected"] += 1
                sources[source]["detected"] += 1

    for key, row in rows.items():
        if key in target_keys or not _reference_usable(row):
            continue
        counts["negative_slots"] += 1
        if _is_alert(row, threshold):
            counts["false_alarms"] += 1

    return {
        **dict(counts),
        "per_source": {name: dict(values) for name, values in sorted(sources.items())},
    }


def _empty_threshold_counts() -> Counter:
    return Counter(
        targets_planned=0,
        targets_evaluable=0,
        targets_detected=0,
        targets_weak_or_unmeasured=0,
        negative_slots=0,
        false_alarms=0,
        clean_negative_slots=0,
        clean_false_alarms=0,
    )


def _finalize_counts(counts: Counter) -> dict:
    result = dict(counts)
    result["target_evaluable_rate"] = _rate(
        counts["targets_evaluable"], counts["targets_planned"]
    )
    result["sensitivity"] = _rate(
        counts["targets_detected"], counts["targets_evaluable"]
    )
    result["false_alarm_rate"] = _rate(
        counts["false_alarms"], counts["negative_slots"]
    )
    result["false_alarm_wilson_95_upper"] = (
        round(wilson_upper(counts["false_alarms"], counts["negative_slots"]), 6)
        if counts["negative_slots"]
        else None
    )
    result["clean_false_alarm_rate"] = _rate(
        counts["clean_false_alarms"], counts["clean_negative_slots"]
    )
    return result


def load_study_package(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "kriah-validation-analyzed-v1":
        raise ValueError(f"{path}: expected kriah-validation-analyzed-v1")
    if not data.get("complete"):
        raise ValueError(f"{path}: package is not complete and confirmed")
    if not isinstance(data.get("comparisons"), dict):
        raise ValueError(f"{path}: analyzed comparisons are missing")
    speaker = data.get("speaker") or {}
    code = speaker.get("speakerCode")
    if not code:
        raise ValueError(f"{path}: speaker code is missing")
    return {
        "speaker_code": str(code),
        "age_group": str(speaker.get("ageGroup") or "unknown"),
        "tradition": str(speaker.get("tradition") or "unknown"),
        "reading_level": str(speaker.get("readingLevel") or "unknown"),
        "device": str(speaker.get("device") or "unknown"),
        "room": str(speaker.get("room") or "unknown"),
        "source": "multi-speaker-study",
        "comparisons": data["comparisons"],
    }


def load_legacy_pairs(paths: Iterable[str | Path]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != "kriah-nikud-pair-v3":
            raise ValueError(f"{path}: expected kriah-nikud-pair-v3")
        reading = data.get("reading_a") or {}
        code = str(reading.get("speaker_id") or "legacy-speaker")
        passage = str((reading.get("passage") or {}).get("id") or "unknown")
        entry = grouped.setdefault(
            code,
            {
                "speaker_code": code,
                "age_group": "adult",
                "tradition": str(reading.get("pronunciation_tradition") or "unknown"),
                "reading_level": "unknown",
                "device": "unknown",
                "room": "unknown",
                "source": "legacy-pair-v3",
                "comparisons": {},
            },
        )
        entry["comparisons"][passage] = {"mistakes": data["comparison"]}
    return list(grouped.values())


def _speaker_counts(speaker: dict, threshold: float) -> tuple[Counter, dict[str, Counter]]:
    total = _empty_threshold_counts()
    per_source: dict[str, Counter] = defaultdict(Counter)
    for pair in speaker["comparisons"].values():
        clean = pair.get("clean")
        if clean:
            scored = _score_comparison(clean, threshold, has_targets=False)
            total["negative_slots"] += scored.get("negative_slots", 0)
            total["false_alarms"] += scored.get("false_alarms", 0)
            total["clean_negative_slots"] += scored.get("negative_slots", 0)
            total["clean_false_alarms"] += scored.get("false_alarms", 0)
        mistakes = pair.get("mistakes")
        if mistakes:
            scored = _score_comparison(mistakes, threshold, has_targets=True)
            for key in (
                "targets_planned",
                "targets_evaluable",
                "targets_detected",
                "targets_weak_or_unmeasured",
                "negative_slots",
                "false_alarms",
            ):
                total[key] += scored.get(key, 0)
            for source, values in scored.get("per_source", {}).items():
                per_source[source].update(values)
    return total, per_source


def aggregate(speakers: list[dict], thresholds: Iterable[float] = DEFAULT_THRESHOLDS) -> dict:
    codes = [speaker["speaker_code"] for speaker in speakers]
    duplicates = sorted(code for code, count in Counter(codes).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate speaker codes: {', '.join(duplicates)}")

    child_groups = {"elementary", "middle-school", "high-school"}
    new_speakers = [s for s in speakers if s["source"] == "multi-speaker-study"]
    strata = {
        "age_groups": dict(Counter(s["age_group"] for s in speakers)),
        "traditions": dict(Counter(s["tradition"] for s in speakers)),
        "devices": dict(Counter(s["device"] for s in speakers)),
        "rooms": dict(Counter(s["room"] for s in speakers)),
    }
    threshold_results = []
    for threshold in thresholds:
        total = _empty_threshold_counts()
        total_per_source: dict[str, Counter] = defaultdict(Counter)
        per_speaker = []
        speaker_count_rows = []
        for speaker in speakers:
            counts, per_source = _speaker_counts(speaker, float(threshold))
            total.update(counts)
            speaker_count_rows.append((speaker, counts))
            for source, values in per_source.items():
                total_per_source[source].update(values)
            per_speaker.append(
                {
                    "speaker_code": speaker["speaker_code"],
                    "age_group": speaker["age_group"],
                    "tradition": speaker["tradition"],
                    "source": speaker["source"],
                    **_finalize_counts(counts),
                }
            )
        metrics = _finalize_counts(total)
        by_group = {}
        for field in ("age_group", "tradition"):
            grouped: dict[str, Counter] = defaultdict(_empty_threshold_counts)
            for speaker, counts in speaker_count_rows:
                grouped[speaker[field]].update(counts)
            by_group[field] = {
                name: _finalize_counts(counts) for name, counts in sorted(grouped.items())
            }
        exploratory_gate = bool(
            len(new_speakers) >= 3
            and any(s["age_group"] in child_groups for s in new_speakers)
            and metrics["target_evaluable_rate"] is not None
            and metrics["target_evaluable_rate"] >= 0.90
            and metrics["sensitivity"] is not None
            and metrics["sensitivity"] >= 0.80
            and metrics["false_alarm_rate"] is not None
            and metrics["false_alarm_rate"] <= 0.02
        )
        threshold_results.append(
            {
                "threshold": float(threshold),
                **metrics,
                "per_source": {
                    source: {
                        **dict(values),
                        "sensitivity": _rate(values["detected"], values["evaluable"]),
                    }
                    for source, values in sorted(total_per_source.items())
                },
                "by_group": by_group,
                "exploratory_gate_passed": exploratory_gate,
                "per_speaker": per_speaker,
            }
        )

    return {
        "schema_version": "kriah-validation-summary-v1",
        "speaker_count": len(speakers),
        "new_speaker_count": len(new_speakers),
        "child_speaker_count": sum(s["age_group"] in child_groups for s in new_speakers),
        "strata": strata,
        "thresholds": threshold_results,
        "interpretation": {
            "exploratory_gate": (
                "At least three new speakers including one child, at least 90% evaluable targets, "
                "at least 80% sensitivity, and at most 2% observed false alarms."
            ),
            "production_status": "blocked",
            "reason": (
                "This convenience study may nominate a threshold for a larger speaker-disjoint "
                "child evaluation; it cannot validate automatic student decisions."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="*", help="analyzed packages from /study")
    parser.add_argument("--legacy-pair", action="append", default=[], help="old pair-v3 baseline")
    parser.add_argument(
        "--thresholds",
        default=",".join(str(value) for value in DEFAULT_THRESHOLDS),
        help="comma-separated margin-drop thresholds; use --thresholds=-5,-4",
    )
    parser.add_argument("--output", help="optional private JSON report path")
    args = parser.parse_args()
    thresholds = [float(value) for value in args.thresholds.split(",") if value.strip()]
    speakers = [load_study_package(path) for path in args.packages]
    speakers.extend(load_legacy_pairs(args.legacy_pair))
    if not speakers:
        parser.error("provide at least one analyzed package or --legacy-pair")
    report = aggregate(speakers, thresholds)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
