"""Controlled reading material and non-authoritative vowel comparisons.

The calibration suite checks coverage of the pronunciation mapper.  Its paired
comparison is a research aid, not a validated student grade or routing rule.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean

from .hebrew_g2p import VALID_PROFILES, pronunciation_variants


@dataclass(frozen=True)
class CalibrationReading:
    identifier: str
    title: str
    purpose: str
    text: str

    @property
    def words(self) -> list[str]:
        return self.text.split()


@dataclass(frozen=True)
class PlannedVowelChange:
    word_index: int
    spoken_word: str
    source: str
    occurrence: int = 0


CALIBRATION_READINGS = (
    CalibrationReading(
        identifier="cal-core",
        title="Master 1: everyday vowels",
        purpose=(
            "Repeated familiar words for patach, kamatz, segol, tzeirei, "
            "chirik, cholam, shuruk, and kubutz."
        ),
        text=(
            "אַתָּה דַּעַת שַׁבָּת אָדָם חָכָם בָּנָה "
            "מֶלֶךְ סֵפֶר אֶרֶץ חוֹנֵן דֵּעָה לֵב "
            "בִּינָה צַדִּיק תַּלְמִיד קָדוֹשׁ עוֹלָם טוֹב "
            "בָּרוּךְ תְּשׁוּבָה גְּבוּרָה שֻׁלְחָן סֻכָּה קֻדְשָׁה"
        ),
    ),
    CalibrationReading(
        identifier="cal-special",
        title="Master 2: special vowel cases",
        purpose=(
            "Reduced vowels, kamatz katan, sounded and silent sheva, and "
            "furtive patach in real words."
        ),
        text=(
            "אֱמֶת אֱנוֹשׁ אֱמוּנָה אֲנַחְנוּ אֲדָמָה חֲכָמָה "
            "חֳדָשִׁים אֳנִיָּה צָהֳרַיִם כׇּל חׇכְמָה "
            "בְּרָכָה תְּפִלָּה מְלַמֵּד מַלְכָּה מִשְׁפָּט "
            "יִכְתֹּב רוּחַ שׁוֹמֵעַ גָּבוֹהַּ"
        ),
    ),
    CalibrationReading(
        identifier="cal-sounds",
        title="Master 3: letters and sound contrasts",
        purpose=(
            "Common Hebrew letters, hard and soft beged-kefet sounds, "
            "shin versus sin, and representative prayer vocabulary."
        ),
        text=(
            "אָבִיב בַּיִת גָּדוֹל דֶּלֶת הַיּוֹם וְזֶה "
            "חָכָם טוֹב יֶלֶד כֹּחַ לֵב מֶלֶךְ נֵר "
            "סֵפֶר עוֹלָם פֶּה צַדִּיק קוֹל רוּחַ "
            "שָׁלוֹם שִׂמְחָה תּוֹרָה"
        ),
    ),
)

ATAH_CHONEN_TEXT = (
    "אַתָּה חוֹנֵן לְאָדָם דַּֽעַת וּמְלַמֵּד לֶאֱנוֹשׁ בִּינָה: "
    "חָנֵּֽנוּ מֵאִתְּ֒ךָ דֵּעָה בִּינָה וְהַשְׂכֵּל: "
    "בָּרוּךְ אַתָּה יְהֹוָה חוֹנֵן הַדָּֽעַת:"
)

GUIDED_CHANGES = {
    "cal-core": (
        PlannedVowelChange(2, "שֶׁבָּת", "פתח"),
        PlannedVowelChange(6, "מַלֶךְ", "סגול"),
        PlannedVowelChange(10, "דִּעָה", "צירי"),
        PlannedVowelChange(14, "תַּלְמֵיד", "חיריק"),
        PlannedVowelChange(17, "טוּב", "חולם מלא"),
        PlannedVowelChange(18, "בָּרוֹךְ", "שורוק"),
        PlannedVowelChange(22, "סַכָּה", "קובוץ"),
    ),
    "cal-special": (
        PlannedVowelChange(0, "אֲמֶת", "חטף סגול"),
        PlannedVowelChange(3, "אֱנַחְנוּ", "חטף פתח"),
        PlannedVowelChange(6, "חֲדָשִׁים", "חטף קמץ"),
        PlannedVowelChange(9, "כַּל", "קמץ קטן"),
        PlannedVowelChange(10, "חַכְמָה", "קמץ קטן"),
    ),
    "4": (
        PlannedVowelChange(4, "וּמְלַמִּד", "צירי"),
        PlannedVowelChange(9, "דִּעָה", "צירי"),
        PlannedVowelChange(11, "וְהַשְׂכִּל:", "צירי"),
        PlannedVowelChange(12, "בָּרוֹךְ", "שורוק"),
    ),
}

REQUIRED_VOWEL_SOURCES = frozenset(
    {
        "פתח",
        "קמץ",
        "קמץ קטן",
        "סגול",
        "צירי",
        "חיריק",
        "חולם",
        "חולם מלא",
        "קובוץ",
        "שורוק",
        "חטף סגול",
        "חטף פתח",
        "חטף קמץ",
        "שווא נע",
    }
)

STRONG_MARGIN_DROP = -5.0
POSSIBLE_MARGIN_DROP = -3.0
MAX_STRONG_EXPECTED_PROBABILITY = 0.20
CONTEXT_SENSITIVE_VOWELS = frozenset({"שווא נע"})
WEAK_REFERENCE_PROBABILITY = 0.12


def _scenario_targets(words: list[str], changes: tuple, profile: str) -> list[dict]:
    targets = []
    for change in changes:
        expected_word = words[change.word_index]
        matching_slots = [
            (index, slot)
            for index, slot in enumerate(
                pronunciation_variants(expected_word, profile=profile)[0].slots
            )
            if slot.kind == "vowel" and slot.source == change.source
        ]
        if change.occurrence >= len(matching_slots):
            raise ValueError(
                f"guided target {change.source} is missing from {expected_word}"
            )
        slot_index, slot = matching_slots[change.occurrence]
        targets.append(
            {
                "key": f"{change.word_index}:{slot_index}",
                "word_index": change.word_index,
                "slot_index": slot_index,
                "expected_word": expected_word,
                "spoken_word": change.spoken_word,
                "source": change.source,
                "allowed": sorted(slot.allowed),
            }
        )
    return targets


def guided_scenarios(passage_id: str, words: list[str], profile: str) -> list[dict]:
    scenarios = [
        {
            "id": "clean-repeat",
            "name": "Read every word correctly again",
            "kind": "known_acceptable",
            "prompt_text": " ".join(words),
            "targets": [],
        }
    ]
    changes = GUIDED_CHANGES.get(passage_id)
    if not changes:
        return scenarios

    targets = _scenario_targets(words, changes, profile)
    prompt_words = list(words)
    for target in targets:
        prompt_words[target["word_index"]] = target["spoken_word"]
    scenarios.append(
        {
            "id": f"{passage_id}-guided-mistakes",
            "name": f"Read the {len(targets)} highlighted vowel changes",
            "kind": "known_nikud_errors",
            "prompt_text": " ".join(prompt_words),
            "targets": targets,
        }
    )
    return scenarios


def _reading_coverage(reading: CalibrationReading, profile: str) -> dict:
    vowel_sources: Counter[str] = Counter()
    vowel_sounds: Counter[str] = Counter()
    consonant_sounds: Counter[str] = Counter()
    for word in reading.words:
        for slot in pronunciation_variants(word, profile=profile)[0].slots:
            if slot.kind == "vowel":
                vowel_sources[slot.source] += 1
                for sound in slot.allowed:
                    vowel_sounds[sound] += 1
            elif slot.kind == "consonant":
                for sound in slot.allowed:
                    consonant_sounds[sound] += 1
    return {
        "vowel_sources": dict(sorted(vowel_sources.items())),
        "vowel_sounds": dict(sorted(vowel_sounds.items())),
        "consonant_sounds": dict(sorted(consonant_sounds.items())),
    }


def calibration_suite(profile: str = "mixed") -> dict:
    if profile not in VALID_PROFILES:
        raise ValueError("pronunciation profile must be mixed, ashkenazi, or sephardi")

    readings = []
    combined_vowels: Counter[str] = Counter()
    combined_consonants: Counter[str] = Counter()
    for reading in CALIBRATION_READINGS:
        coverage = _reading_coverage(reading, profile)
        combined_vowels.update(coverage["vowel_sources"])
        combined_consonants.update(coverage["consonant_sounds"])
        readings.append(
            {
                "id": reading.identifier,
                "name": reading.title,
                "purpose": reading.purpose,
                "text": reading.text,
                "words": reading.words,
                "word_count": len(reading.words),
                "coverage": coverage,
                "scenarios": guided_scenarios(reading.identifier, reading.words, profile),
            }
        )

    missing_sources = sorted(REQUIRED_VOWEL_SOURCES.difference(combined_vowels))
    return {
        "version": 2,
        "pronunciation_profile": profile,
        "readings": readings,
        "coverage": {
            "vowel_sources": dict(sorted(combined_vowels.items())),
            "consonant_sounds": dict(sorted(combined_consonants.items())),
            "required_vowel_sources": sorted(REQUIRED_VOWEL_SOURCES),
            "missing_vowel_sources": missing_sources,
            "all_required_vowel_sources_covered": not missing_sources,
        },
        "recording_plan": [
            "Record each section correctly twice to measure natural variation.",
            "Choose the guided mistakes and read the highlighted substitutions.",
            "The exact target vowels are scored automatically without manual labels.",
            "Repeat with other adult and child speakers before choosing thresholds.",
        ],
        "additional_passage_scenarios": {
            "4": guided_scenarios("4", ATAH_CHONEN_TEXT.split(), profile)
        },
        "limitations": [
            "A master suite checks sound coverage but cannot replace references for actual brachot.",
            "Silent sheva has no expected audible vowel slot and cannot be directly scored as a vowel.",
            "Results are uncalibrated and cannot determine student pass or fail.",
        ],
    }


def _vowel_slots(result: dict) -> dict[str, dict]:
    pronunciation = result.get("pronunciation")
    if not isinstance(pronunciation, dict):
        raise TypeError("reading is missing pronunciation evidence")
    if pronunciation.get("status") != "evidence_available":
        raise ValueError("reading does not contain available pronunciation evidence")

    slots = {}
    for word in pronunciation.get("words", []):
        if word.get("status") != "measured_uncalibrated":
            continue
        for slot_index, slot in enumerate(word.get("slots", [])):
            if slot.get("kind") != "vowel":
                continue
            expected_index = word.get("expected_index")
            if expected_index is None:
                continue
            key = f"{expected_index}:{slot_index}"
            slots[key] = {
                "key": key,
                "word_index": expected_index,
                "slot_index": slot_index,
                "word": word.get("word"),
                "heard": word.get("heard"),
                "source": slot.get("source"),
                "allowed": slot.get("allowed", []),
                "peak_expected_probability": slot.get("peak_expected_probability"),
                "peak_competitor_margin": slot.get("peak_competitor_margin"),
                "strongest_competing_phone": slot.get("strongest_competing_phone"),
            }
    return slots


def _candidate_tier(reference: dict, candidate: dict) -> tuple[str, float]:
    delta = round(
        float(candidate["peak_competitor_margin"])
        - float(reference["peak_competitor_margin"]),
        4,
    )
    if reference.get("source") in CONTEXT_SENSITIVE_VOWELS:
        return "context_sensitive", delta
    if (
        delta <= STRONG_MARGIN_DROP
        and float(candidate["peak_competitor_margin"]) < 0
        and float(candidate["peak_expected_probability"])
        <= MAX_STRONG_EXPECTED_PROBABILITY
    ):
        return "strong_candidate", delta
    if delta <= POSSIBLE_MARGIN_DROP and float(candidate["peak_competitor_margin"]) < 0:
        return "possible_candidate", delta
    return "stable", delta


def _target_evaluation(
    *,
    reference_result: dict,
    candidate_result: dict,
    comparisons: list[dict],
    scenario_id: str,
    profile: str,
) -> dict:
    passage_id = reference_result.get("bracha")
    if passage_id == "4":
        expected_words = ATAH_CHONEN_TEXT.split()
    else:
        reading = next(
            (item for item in CALIBRATION_READINGS if item.identifier == passage_id),
            None,
        )
        if reading is None:
            raise ValueError("guided scenarios are unavailable for this passage")
        expected_words = reading.words

    scenario = next(
        (
            item
            for item in guided_scenarios(passage_id, expected_words, profile)
            if item["id"] == scenario_id
        ),
        None,
    )
    if scenario is None:
        raise ValueError("guided scenario does not match this passage")

    comparisons_by_key = {item["key"]: item for item in comparisons}
    reference_words = {
        word.get("expected_index"): word
        for word in reference_result["pronunciation"].get("words", [])
    }
    candidate_words = {
        word.get("expected_index"): word
        for word in candidate_result["pronunciation"].get("words", [])
    }
    targeted_keys = {target["key"] for target in scenario["targets"]}
    target_words = {target["word_index"] for target in scenario["targets"]}
    target_results = []
    for target in scenario["targets"]:
        comparison = comparisons_by_key.get(target["key"])
        reference_word = reference_words.get(target["word_index"], {})
        candidate_word = candidate_words.get(target["word_index"], {})
        if reference_word.get("status") != "measured_uncalibrated":
            outcome = "unmeasured_reference"
        elif candidate_word.get("status") != "measured_uncalibrated":
            outcome = "unmeasured_candidate"
        elif comparison is None:
            outcome = "not_comparable"
        elif comparison["tier"] == "strong_candidate":
            outcome = "detected"
        elif comparison["tier"] == "possible_candidate":
            outcome = "possible"
        else:
            outcome = "missed"

        reference_quality = None
        if comparison is not None:
            probability = float(comparison["reference"]["peak_expected_probability"])
            reference_quality = (
                "weak" if probability < WEAK_REFERENCE_PROBABILITY else "usable"
            )
        target_results.append(
            {
                **target,
                "outcome": outcome,
                "reference_quality": reference_quality,
                "reference_word_alignment": reference_word.get("word_alignment"),
                "candidate_word_alignment": candidate_word.get("word_alignment"),
                "margin_delta": comparison.get("margin_delta") if comparison else None,
                "strongest_competing_phone": (
                    comparison["candidate"].get("strongest_competing_phone")
                    if comparison
                    else None
                ),
            }
        )

    false_alarms = [
        item
        for item in comparisons
        if item["tier"] == "strong_candidate" and item["key"] not in targeted_keys
    ]
    mislocalized = [item for item in false_alarms if item["word_index"] in target_words]
    outcomes = Counter(item["outcome"] for item in target_results)
    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "truth_source": "predefined_reading_script",
        "manual_labels_used": False,
        "planned_vowels": len(target_results),
        "detected": outcomes["detected"],
        "possible": outcomes["possible"],
        "missed": outcomes["missed"],
        "unmeasured": (
            outcomes["unmeasured_reference"]
            + outcomes["unmeasured_candidate"]
            + outcomes["not_comparable"]
        ),
        "false_alarms": len(false_alarms),
        "mislocalized": len(mislocalized),
        "weak_reference_targets": sum(
            item["reference_quality"] == "weak" for item in target_results
        ),
        "target_results": target_results,
        "validated": False,
    }


def compare_vowel_evidence(
    reference_result: dict,
    candidate_result: dict,
    scenario_id: str | None = None,
) -> dict:
    reference_profile = reference_result.get("requested_pronunciation_profile", "mixed")
    candidate_profile = candidate_result.get("requested_pronunciation_profile", "mixed")
    if reference_profile != candidate_profile:
        raise ValueError("readings must use the same pronunciation profile")
    if reference_result.get("bracha") != candidate_result.get("bracha"):
        raise ValueError("readings must use the same passage")

    reference_slots = _vowel_slots(reference_result)
    candidate_slots = _vowel_slots(candidate_result)
    comparisons = []
    for key, reference in reference_slots.items():
        candidate = candidate_slots.get(key)
        if candidate is None:
            continue
        if reference["word"] != candidate["word"] or reference["source"] != candidate["source"]:
            continue
        tier, delta = _candidate_tier(reference, candidate)
        comparisons.append(
            {
                "key": key,
                "word_index": reference["word_index"],
                "word": reference["word"],
                "source": reference["source"],
                "allowed": reference["allowed"],
                "reference": reference,
                "candidate": candidate,
                "margin_delta": delta,
                "tier": tier,
            }
        )
    comparisons.sort(key=lambda item: item["margin_delta"])

    reference_probabilities = [
        float(item["reference"]["peak_expected_probability"]) for item in comparisons
    ]
    candidate_probabilities = [
        float(item["candidate"]["peak_expected_probability"]) for item in comparisons
    ]
    tiers = Counter(item["tier"] for item in comparisons)
    report = {
        "version": 2,
        "authoritative": False,
        "calibration_state": "uncalibrated",
        "pronunciation_profile": reference_profile,
        "summary": {
            "shared_vowel_slots": len(comparisons),
            "reference_only_vowel_slots": len(reference_slots.keys() - candidate_slots.keys()),
            "candidate_only_vowel_slots": len(candidate_slots.keys() - reference_slots.keys()),
            "reference_vowel_mean": (
                round(mean(reference_probabilities), 6) if reference_probabilities else None
            ),
            "candidate_vowel_mean": (
                round(mean(candidate_probabilities), 6) if candidate_probabilities else None
            ),
            "strong_candidates": tiers["strong_candidate"],
            "possible_candidates": tiers["possible_candidate"],
            "context_sensitive_slots": tiers["context_sensitive"],
        },
        "rule": {
            "strong_margin_drop": STRONG_MARGIN_DROP,
            "possible_margin_drop": POSSIBLE_MARGIN_DROP,
            "maximum_strong_expected_probability": MAX_STRONG_EXPECTED_PROBABILITY,
            "context_sensitive_vowels": sorted(CONTEXT_SENSITIVE_VOWELS),
            "validated": False,
        },
        "comparisons": comparisons,
        "limitations": [
            "Candidate flags are an unvalidated research heuristic.",
            "Natural variation must be measured using separate clean reference takes.",
            "Teacher-labeled child readings are required before any automatic grade.",
        ],
    }
    if scenario_id is not None:
        report["target_evaluation"] = _target_evaluation(
            reference_result=reference_result,
            candidate_result=candidate_result,
            comparisons=comparisons,
            scenario_id=scenario_id,
            profile=reference_profile,
        )
    return report
