"""Expose the existing pointed Amidah text as a research passage catalog.

The student coach already contains the project's reviewed, condition-tagged
prayer text.  This module reads that embedded JSON instead of maintaining a
second copy that could silently diverge.  The parser is intentionally strict so
an index-format change fails tests rather than changing research targets.
"""

from __future__ import annotations

import json
from pathlib import Path


DATA_PREFIX = "const DATA = "
SUPPORTED_CONDITIONS = frozenset(
    {
        "always",
        "ayt",
        "notayt",
        "winter",
        "notwinter",
        "rc",
        "nissim",
        "chanukah",
        "purim",
    }
)


def _embedded_data(index_path: str | Path) -> dict:
    with Path(index_path).open(encoding="utf-8") as handle:
        line = next((line for line in handle if line.startswith(DATA_PREFIX)), None)
    if line is None:
        raise ValueError("coach does not contain the embedded prayer catalog")
    payload = line[len(DATA_PREFIX) :].strip()
    if not payload.endswith(";"):
        raise ValueError("embedded prayer catalog is not terminated")
    data = json.loads(payload[:-1])
    if not isinstance(data.get("brachot"), list) or len(data["brachot"]) < 19:
        raise ValueError("embedded prayer catalog does not contain all 19 brachot")
    return data


def passage_catalog(index_path: str | Path) -> dict:
    """Return the 19 weekday blessings and their optional text segments."""

    source = _embedded_data(index_path)
    passages = []
    for number, bracha in enumerate(source["brachot"][:19], start=1):
        segments = []
        for segment in bracha.get("segs", []):
            condition = str(segment.get("c") or "always")
            if condition not in SUPPORTED_CONDITIONS:
                raise ValueError(f"unsupported prayer condition: {condition}")
            text = str(segment.get("t") or "").strip()
            if not text:
                raise ValueError(f"bracha {number} contains an empty segment")
            segments.append({"condition": condition, "text": text})
        if not segments:
            raise ValueError(f"bracha {number} contains no reading text")
        passages.append(
            {
                "id": str(number),
                "number": number,
                "english": str(bracha.get("en") or f"Bracha {number}"),
                "hebrew": str(bracha.get("he") or ""),
                "segments": segments,
            }
        )
    return {
        "schema_version": "kriah-passage-catalog-v1",
        "source": "existing-coach-pointed-text",
        "nusach": "project Ashkenaz text; verify against the reader's siddur",
        "passages": passages,
        "conditions": sorted(SUPPORTED_CONDITIONS),
    }
