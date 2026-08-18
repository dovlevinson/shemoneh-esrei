"""Conservative pointed-Hebrew to pronunciation-slot conversion.

The output is an *expected pronunciation specification*, not a grade.  Every
slot contains the sounds accepted by the selected pronunciation profile.  The
acoustic layer may collect evidence for these slots in shadow mode, but these
rules must still be reviewed against the school's siddur and pronunciation
policy before they can affect a student result.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


SHVA = "\u05b0"
HATAF_SEGOL = "\u05b1"
HATAF_PATAH = "\u05b2"
HATAF_QAMATS = "\u05b3"
HIRIQ = "\u05b4"
TSERE = "\u05b5"
SEGOL = "\u05b6"
PATAH = "\u05b7"
QAMATS = "\u05b8"
HOLAM = "\u05b9"
QUBUTS = "\u05bb"
DAGESH = "\u05bc"
METEG = "\u05bd"
SHIN_DOT = "\u05c1"
SIN_DOT = "\u05c2"
QAMATS_QATAN = "\u05c7"

# This source text places U+0592 immediately after selected shevas to mark
# pronounced sheva.  It is a source-specific convention, not a universal
# Unicode meaning, so the evidence output reports the rule explicitly.
SOURCE_SHVA_NA_MARKER = "\u0592"
MAQAF = "\u05be"

VOWEL_POINTS = {
    HIRIQ,
    TSERE,
    SEGOL,
    PATAH,
    QAMATS,
    QAMATS_QATAN,
    HOLAM,
    QUBUTS,
    HATAF_SEGOL,
    HATAF_PATAH,
    HATAF_QAMATS,
}
KEPT_MARKS = VOWEL_POINTS | {
    SHVA,
    DAGESH,
    METEG,
    SHIN_DOT,
    SIN_DOT,
    SOURCE_SHVA_NA_MARKER,
}

FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
VALID_PROFILES = {"mixed", "sephardi", "ashkenazi"}
VALID_DIVINE_POLICIES = {"both", "hashem", "adonai"}


@dataclass(frozen=True)
class Slot:
    allowed: frozenset[str]
    kind: str
    source: str
    symbol: str

    def to_dict(self) -> dict:
        return {
            "allowed": sorted(self.allowed),
            "kind": self.kind,
            "source": self.source,
            "symbol": self.symbol,
        }


@dataclass(frozen=True)
class PronunciationVariant:
    name: str
    slots: tuple[Slot, ...]


CONSONANTS = {
    "א": None,
    "ב": "v",
    "ג": "g",
    "ד": "d",
    "ה": "h",
    "ו": "v",
    "ז": "z",
    "ח": "x",
    "ט": "t",
    "י": "j",
    "כ": "x",
    "ל": "l",
    "מ": "m",
    "נ": "n",
    "ס": "s",
    "ע": None,
    "פ": "f",
    "צ": "ts",
    "ק": "k",
    "ר": "r",
    "ש": "sh",
    "ת": "t",
}
BEGEDKEFET_HARD = {"ב": "b", "כ": "k", "פ": "p"}
BEGEDKEFET_SOFT = {"ב": "v", "כ": "x", "פ": "f"}

VOWEL_NAMES = {
    HIRIQ: "חיריק",
    TSERE: "צירי",
    SEGOL: "סגול",
    PATAH: "פתח",
    QAMATS: "קמץ",
    QAMATS_QATAN: "קמץ קטן",
    HOLAM: "חולם",
    QUBUTS: "קובוץ",
    HATAF_SEGOL: "חטף סגול",
    HATAF_PATAH: "חטף פתח",
    HATAF_QAMATS: "חטף קמץ",
}


def _vowel_sound(mark: str, profile: str) -> frozenset[str]:
    fixed = {
        HIRIQ: {"i"},
        TSERE: {"e"},
        SEGOL: {"e"},
        PATAH: {"a"},
        QAMATS_QATAN: {"o"},
        HOLAM: {"o"},
        QUBUTS: {"u"},
        HATAF_SEGOL: {"e"},
        HATAF_PATAH: {"a"},
        HATAF_QAMATS: {"o"},
    }
    if mark == QAMATS:
        return frozenset(
            {"a", "o"}
            if profile == "mixed"
            else ({"o"} if profile == "ashkenazi" else {"a"})
        )
    return frozenset(fixed[mark])


def _soft_tav(profile: str) -> frozenset[str]:
    if profile == "mixed":
        return frozenset({"s", "t"})
    return frozenset({"s" if profile == "ashkenazi" else "t"})


def _bare(word: str) -> str:
    return "".join(FINALS.get(char, char) for char in word if "א" <= char <= "ת")


def is_divine_name(word: str) -> bool:
    return _bare(word) in {"יהוה", "אדני", "אדוני"}


def _divine_variants(policy: str) -> list[PronunciationVariant]:
    variants = {
        "hashem": PronunciationVariant(
            "hashem",
            (
                Slot(frozenset({"h"}), "consonant", "שם ה׳", "ה"),
                Slot(frozenset({"a"}), "vowel", "פתח", PATAH),
                Slot(frozenset({"sh"}), "consonant", "שם ה׳", "ש"),
                Slot(frozenset({"e"}), "vowel", "סגול", SEGOL),
                Slot(frozenset({"m"}), "consonant", "שם ה׳", "ם"),
            ),
        ),
        "adonai": PronunciationVariant(
            "adonai",
            (
                Slot(frozenset({"a"}), "vowel", "חטף פתח", HATAF_PATAH),
                Slot(frozenset({"d"}), "consonant", "ד", "ד"),
                Slot(frozenset({"o"}), "vowel", "חולם", HOLAM),
                Slot(frozenset({"n"}), "consonant", "נ", "נ"),
                Slot(frozenset({"a"}), "vowel", "קמץ", QAMATS),
                Slot(frozenset({"j"}), "consonant", "י", "י"),
            ),
        ),
    }
    return [variants[name] for name in ("hashem", "adonai") if policy in {"both", name}]


def _units(word: str) -> list[tuple[str, list[str]]]:
    cleaned = "".join(
        char
        for char in unicodedata.normalize("NFC", word)
        if ("א" <= char <= "ת") or char in KEPT_MARKS
    )
    units: list[list] = []
    for char in cleaned:
        if "א" <= char <= "ת":
            units.append([char, []])
        elif units:
            units[-1][1].append(char)
    return [(letter, marks) for letter, marks in units]


def _is_shva_na(units: list[tuple[str, list[str]]], index: int, marks: set[str]) -> bool:
    if SOURCE_SHVA_NA_MARKER in marks:
        return True
    if index == 0:
        return True
    previous_marks = set(units[index - 1][1])
    if SHVA in previous_marks and index == len(units) - 1:
        return False
    if SHVA in previous_marks:
        return True
    if DAGESH in marks and FINALS.get(units[index][0], units[index][0]) not in BEGEDKEFET_HARD:
        return True
    return False


def _ordinary_slots(word: str, profile: str) -> tuple[Slot, ...]:
    units = _units(word)
    slots: list[Slot] = []
    for index, (letter, raw_marks) in enumerate(units):
        base = FINALS.get(letter, letter)
        marks = set(raw_marks)
        vowels = [mark for mark in raw_marks if mark in VOWEL_POINTS]
        vowel = vowels[0] if vowels else None
        previous_marks = set(units[index - 1][1]) if index else set()
        is_last = index == len(units) - 1
        has_dagesh = DAGESH in marks

        # Matres lectionis and shuruk contribute a vowel, not a /v/ consonant.
        if base == "ו" and has_dagesh and not vowel and SHVA not in marks:
            slots.append(Slot(frozenset({"u"}), "vowel", "שורוק", "וּ"))
            continue
        if base == "ו" and vowel == HOLAM and not has_dagesh:
            slots.append(Slot(frozenset({"o"}), "vowel", "חולם מלא", "וֹ"))
            continue
        if base == "ו" and not vowel and HOLAM in previous_marks:
            continue
        if base == "י" and not vowel and SHVA not in marks and index:
            if previous_marks & {HIRIQ, TSERE}:
                continue

        # Modern school pronunciations normally leave final he and quiescent
        # alef silent.  Mapiq he remains audible because it carries dagesh.
        if base == "ה" and is_last and not vowel and not has_dagesh:
            continue
        consonant: Slot | None
        if base == "א" and not vowel:
            consonant = None
        elif base == "ש":
            consonant = Slot(
                frozenset({"s" if SIN_DOT in marks else "sh"}),
                "consonant",
                "שׂ" if SIN_DOT in marks else "שׁ",
                letter,
            )
        elif base in BEGEDKEFET_HARD:
            sound = BEGEDKEFET_HARD[base] if has_dagesh else BEGEDKEFET_SOFT[base]
            consonant = Slot(frozenset({sound}), "consonant", letter, letter)
        elif base == "ת" and not has_dagesh:
            consonant = Slot(_soft_tav(profile), "consonant", "ת רפה", letter)
        else:
            sound = CONSONANTS.get(base)
            consonant = (
                Slot(frozenset({sound}), "consonant", letter, letter) if sound else None
            )

        vowel_slot = (
            Slot(_vowel_sound(vowel, profile), "vowel", VOWEL_NAMES[vowel], vowel)
            if vowel
            else None
        )

        # A final furtive patah is pronounced before the final guttural.
        if is_last and base in {"ח", "ה", "ע"} and vowel == PATAH:
            if vowel_slot:
                slots.append(vowel_slot)
            if consonant:
                slots.append(consonant)
        else:
            if consonant:
                slots.append(consonant)
            if vowel_slot:
                slots.append(vowel_slot)

        if not vowel and SHVA in marks and _is_shva_na(units, index, marks):
            slots.append(Slot(frozenset({"e"}), "vowel", "שווא נע", SHVA))

    return tuple(slots)


def pronunciation_variants(
    word: str,
    profile: str = "mixed",
    divine_policy: str = "both",
) -> list[PronunciationVariant]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"unsupported pronunciation profile: {profile}")
    if divine_policy not in VALID_DIVINE_POLICIES:
        raise ValueError(f"unsupported Divine-Name policy: {divine_policy}")
    if is_divine_name(word):
        return _divine_variants(divine_policy)
    return [PronunciationVariant(profile, _ordinary_slots(word, profile))]


def pronunciation_map(
    words: list[str],
    profile: str = "mixed",
    divine_policy: str = "both",
) -> list[dict]:
    return [
        {
            "word": word,
            "variants": [
                {"name": variant.name, "slots": [slot.to_dict() for slot in variant.slots]}
                for variant in pronunciation_variants(word, profile, divine_policy)
            ],
        }
        for word in words
    ]


_DIRECT_PHONES = {
    "a",
    "b",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "r",
    "s",
    "t",
    "ts",
    "u",
    "v",
    "x",
    "z",
}
_PHONE_MAP = {
    "ɑ": "a",
    "æ": "a",
    "ʌ": "a",
    "ɐ": "a",
    "ɛ": "e",
    "ə": "e",
    "ɜ": "e",
    "ɪ": "i",
    "ɨ": "i",
    "ɔ": "o",
    "ɒ": "o",
    "ø": "o",
    "ʊ": "u",
    "ʉ": "u",
    "ɹ": "r",
    "ʁ": "r",
    "ɾ": "r",
    "ʀ": "r",
    "ʃ": "sh",
    "ʒ": "sh",
    "χ": "x",
    "ħ": "x",
    "ɡ": "g",
    "ɢ": "g",
    "w": "v",
    "t͡s": "ts",
    "ʦ": "ts",
    "ʔ": None,
    "ʕ": None,
}


def collapse_model_phone(symbol: str | None) -> str | None:
    """Map an IPA/eSpeak vocabulary token to the project's small phone set."""

    value = (symbol or "").strip()
    if not value or value.startswith("<") or value in {"|", "_"}:
        return None
    value = "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
        and char not in {"ˈ", "ˌ", "ː", ":", ".", "ʰ", "ʲ"}
        and not char.isdigit()
    )
    if value in _DIRECT_PHONES:
        return value
    if value in _PHONE_MAP:
        return _PHONE_MAP[value]
    if len(value) > 1:
        first = _PHONE_MAP.get(value[0], value[0])
        second = _PHONE_MAP.get(value[1], value[1])
        if first == "t" and second == "s":
            return "ts"
        if first == "a" and second == "u":
            return "o"
        if first in {"a", "e", "i", "o", "u"}:
            return first
        if first in _DIRECT_PHONES:
            return first
    return None
