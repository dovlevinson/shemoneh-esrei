"""Generate a non-authoritative shadow pronunciation report for local research.

No audio or report is written unless ``--output`` is supplied.  Reports contain
uncalibrated acoustic evidence and must not be used as student grades.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.pronunciation import CtcPronunciationAssessor
from server.scoring import score_transcript
from server.transcriber import FasterWhisperTranscriber


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_SEGMENT_CLASSES = {"ayt", "chanukah", "purim", "winter", "rc"}


def _browser_data(path: Path = ROOT / "index.html") -> dict:
    source = path.read_text(encoding="utf-8")
    marker = "const DATA = {"
    marker_index = source.find(marker)
    if marker_index < 0:
        raise ValueError("index.html does not contain the prayer data object")
    start = source.index("{", marker_index)
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(source[start : index + 1])
    raise ValueError("prayer data object is incomplete")


def expected_words_for_bracha(number: int) -> tuple[dict, list[str]]:
    data = _browser_data()
    try:
        bracha = data["brachot"][number - 1]
    except (IndexError, KeyError) as exc:
        raise ValueError(f"bracha {number} is unavailable") from exc
    words = []
    for segment in bracha["segs"]:
        if segment.get("c") in EXCLUDED_SEGMENT_CLASSES:
            continue
        words.extend(segment["t"].replace("־", " ").split())
    return bracha, words


def create_report(audio_path: Path, bracha_number: int) -> dict:
    bracha, expected = expected_words_for_bracha(bracha_number)
    transcript = FasterWhisperTranscriber().transcribe(str(audio_path), "he")
    alignment = score_transcript(expected, transcript.transcript)
    evidence = CtcPronunciationAssessor().assess(
        path=str(audio_path),
        expected_words=expected,
        alignment_rows=alignment["words"],
        transcript_words=transcript.words,
        transcript_duration=transcript.duration,
    )
    return {
        "report_version": 1,
        "audio_file": audio_path.name,
        "bracha": {
            "number": bracha_number,
            "hebrew": bracha.get("he"),
            "english": bracha.get("en"),
        },
        "word_alignment": alignment,
        "transcript": transcript.to_dict(),
        "pronunciation": evidence,
        "warning": "Uncalibrated shadow evidence. Not a student grade.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--bracha", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = create_report(args.audio, args.bracha)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
