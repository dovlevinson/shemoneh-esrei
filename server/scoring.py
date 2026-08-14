"""Pure word-level alignment for Hebrew reading attempts.

This module deliberately scores only evidence available in an unvocalized ASR
transcript.  It does not claim to grade nikud.  Keeping the alignment pure and
dependency-free makes it easy to test independently of the speech model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable, Sequence


FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
HEBREW_LETTERS = re.compile(r"[^א-ת]")
DIVINE_TARGETS = {"יהוה", "אדני"}
DIVINE_FORMS = {"יהוה", "אדני", "אדוני", "השמ", "אדושמ", "יי"}

OK_THRESHOLD = 1.0
ALMOST_THRESHOLD = 0.55
EXTRA_PENALTY = 0.5


def normalize_word(value: str | None) -> str:
    """Return a final-form-folded Hebrew consonant skeleton."""

    text = HEBREW_LETTERS.sub("", value or "").translate(FINALS)
    # Common religious spelling used by Hebrew ASR for Elohim-family words.
    return re.sub(r"אלו?ק", "אלה", text)


def tokenize_transcript(transcript: str | None) -> list[str]:
    return [token for token in (transcript or "").split() if normalize_word(token)]


def levenshtein(left: str, right: str) -> int:
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def word_similarity(heard: str | None, expected: str | None) -> float:
    """Conservative similarity supported by an unvocalized transcript.

    A green match must be exact after final-form and explicit Divine-Name
    normalization. Unlike the prior browser matcher, this does not collapse
    unrelated Hebrew consonants such as kuf, kaf, and chet.
    """

    heard_norm = normalize_word(heard)
    expected_norm = normalize_word(expected)
    if expected_norm in DIVINE_TARGETS:
        return 1.0 if heard_norm in DIVINE_FORMS else 0.0
    if not heard_norm or not expected_norm:
        return 0.0
    if heard_norm == expected_norm:
        return 1.0
    if min(len(heard_norm), len(expected_norm)) <= 2:
        return 0.0
    distance = levenshtein(heard_norm, expected_norm)
    return max(0.0, 1.0 - distance / max(len(heard_norm), len(expected_norm)))


@dataclass(frozen=True)
class AlignmentRow:
    operation: str
    expected_index: int | None
    expected: str | None
    heard: str | None
    similarity: float

    def to_dict(self) -> dict:
        return asdict(self)


def _operation(similarity: float) -> str:
    if similarity >= OK_THRESHOLD:
        return "ok"
    if similarity >= ALMOST_THRESHOLD:
        return "almost"
    return "wrong"


def align_words(expected_words: Sequence[str], heard_words: Sequence[str]) -> list[AlignmentRow]:
    """Globally align expected and heard words with explicit insertions/deletions."""

    expected = list(expected_words)
    heard = list(heard_words)
    rows, columns = len(expected), len(heard)
    costs = [[0.0] * (columns + 1) for _ in range(rows + 1)]
    back: list[list[tuple[str, int, int, float] | None]] = [
        [None] * (columns + 1) for _ in range(rows + 1)
    ]
    for row in range(1, rows + 1):
        costs[row][0] = float(row)
        back[row][0] = ("missing", row - 1, 0, 0.0)
    for column in range(1, columns + 1):
        costs[0][column] = float(column)
        back[0][column] = ("extra", 0, column - 1, 0.0)

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            similarity = word_similarity(heard[column - 1], expected[row - 1])
            choices = [
                (costs[row - 1][column - 1] + (1.0 - similarity), "pair", similarity),
                (costs[row - 1][column] + 1.0, "missing", 0.0),
                (costs[row][column - 1] + 1.0, "extra", 0.0),
            ]
            cost, action, score = min(choices, key=lambda item: item[0])
            costs[row][column] = cost
            if action == "pair":
                back[row][column] = (action, row - 1, column - 1, score)
            elif action == "missing":
                back[row][column] = (action, row - 1, column, score)
            else:
                back[row][column] = (action, row, column - 1, score)

    aligned: list[AlignmentRow] = []
    row, column = rows, columns
    while row or column:
        step = back[row][column]
        if step is None:
            raise RuntimeError("word alignment backtrace is incomplete")
        action, previous_row, previous_column, similarity = step
        if action == "pair":
            aligned.append(
                AlignmentRow(
                    operation=_operation(similarity),
                    expected_index=row - 1,
                    expected=expected[row - 1],
                    heard=heard[column - 1],
                    similarity=round(similarity, 4),
                )
            )
        elif action == "missing":
            aligned.append(
                AlignmentRow("missing", row - 1, expected[row - 1], None, 0.0)
            )
        else:
            aligned.append(AlignmentRow("extra", None, None, heard[column - 1], 0.0))
        row, column = previous_row, previous_column

    aligned.reverse()
    return aligned


def summarize_alignment(rows: Iterable[AlignmentRow]) -> dict:
    aligned = list(rows)
    counts = {name: 0 for name in ("ok", "almost", "wrong", "missing", "extra")}
    for row in aligned:
        counts[row.operation] += 1
    expected_count = sum(counts[name] for name in ("ok", "almost", "wrong", "missing"))
    points = counts["ok"] + 0.5 * counts["almost"] - EXTRA_PENALTY * counts["extra"]
    estimated_accuracy = round(100 * max(0.0, points) / expected_count) if expected_count else 0

    review_reasons: list[str] = []
    if counts["missing"]:
        review_reasons.append(f"{counts['missing']} expected word(s) missing")
    if counts["wrong"]:
        review_reasons.append(f"{counts['wrong']} different word(s) heard")
    if counts["extra"]:
        review_reasons.append(f"{counts['extra']} extra word(s) heard")
    if counts["almost"]:
        review_reasons.append(f"{counts['almost']} uncertain word match(es)")

    return {
        "estimated_accuracy": estimated_accuracy,
        "counts": counts,
        "expected_count": expected_count,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
    }


def score_transcript(expected_words: Sequence[str], transcript: str) -> dict:
    rows = align_words(expected_words, tokenize_transcript(transcript))
    return {
        "words": [row.to_dict() for row in rows],
        **summarize_alignment(rows),
    }
