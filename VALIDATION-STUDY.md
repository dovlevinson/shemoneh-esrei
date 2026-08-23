# Twelve-hour multi-speaker validation study

## Purpose

This study asks whether the current vowel evidence reacts consistently to known
vowel changes across voices, ages, traditions, rooms, and devices. It is a
threshold-selection pilot, not a student grading study. It cannot authorize an
automatic pass, retry, or mastery decision.

The browser collector is at `/study`. It records nine short takes, saves a
private package for one speaker, and can run the slow analysis after the speaker
leaves.

## Who to recruit

Aim for four speakers in this order:

1. One strong adult Ashkenazi reader.
2. One strong adult Sephardi or Israeli reader.
3. One middle-school or elementary reader who resembles the intended user.
4. A second child, preferably with a different reading level, device, or room.

If only three people are available, prioritize one child and two adults from
different pronunciation traditions. If only adults are available, the data can
improve the engineering and nominate a threshold for later testing, but it
cannot support child use.

Use only speakers who have agreed to internal product research. For a minor,
obtain the parent or school permission required by the organization running the
study. Do not enter names. Use codes such as `A01`, `A02`, `C01`, and `C02`.

## What every person records

Each person makes the same nine recordings. The page supplies the full pointed
text and highlights the intentional changes.

| Recording | Passage | Instruction | Planned changes |
|---|---|---|---:|
| 1 | Master 1 | Correct reference | 0 |
| 2 | Master 1 | Second correct reading | 0 |
| 3 | Master 1 | Read every highlighted change | 7 |
| 4 | Master 2 | Correct reference | 0 |
| 5 | Master 2 | Second correct reading | 0 |
| 6 | Master 2 | Read every highlighted change | 5 |
| 7 | Atah Chonen | Correct reference | 0 |
| 8 | Atah Chonen | Second correct reading | 0 |
| 9 | Atah Chonen | Read every highlighted change | 4 |

The 16 intentional changes are fixed in advance:

| Passage | Correct form | Form to say in the intentional-change take |
|---|---|---|
| Master 1 | שַׁבָּת | שֶׁבָּת |
| Master 1 | מֶלֶךְ | מַלֶךְ |
| Master 1 | דֵּעָה | דִּעָה |
| Master 1 | תַּלְמִיד | תַּלְמֵיד |
| Master 1 | טוֹב | טוּב |
| Master 1 | בָּרוּךְ | בָּרוֹךְ |
| Master 1 | סֻכָּה | סַכָּה |
| Master 2 | אֱמֶת | אֲמֶת |
| Master 2 | אֲנַחְנוּ | אֱנַחְנוּ |
| Master 2 | חֳדָשִׁים | חֲדָשִׁים |
| Master 2 | כׇּל | כַּל |
| Master 2 | חׇכְמָה | חַכְמָה |
| Atah Chonen | וּמְלַמֵּד | וּמְלַמִּד |
| Atah Chonen | דֵּעָה | דִּעָה |
| Atah Chonen | וְהַשְׂכֵּל | וְהַשְׂכִּל |
| Atah Chonen | בָּרוּךְ | בָּרוֹךְ |

## Recording procedure

1. Open `/study` in current Chrome or Edge on the recording device.
2. Enter the pseudonymous code and all requested conditions.
3. Keep the same device and microphone for all nine takes from that speaker.
4. Place the microphone roughly 15 to 30 cm from the speaker. Do not use a
   Bluetooth headset. Avoid a television, music, or another voice in the room.
5. Let the speaker practice the displayed substitutions before recording. Do
   not coach or speak during a take.
6. Record only the displayed text. Do not say the recording number, introduce
   the passage, or add words after it.
7. Play back every take immediately. Confirm it only if the displayed script was
   actually followed. If a word is uncertain, discard and redo the take. A note
   documents an unusual condition; it does not turn an uncertain take into
   known ground truth.
8. After the ninth take, select **Download recordings**. Verify that the package
   says it is complete before starting the next speaker.

Budget 10 to 15 minutes per person. Natural reading is more useful than slow,
over-enunciated speech. The correct repeat should be independent, not an attempt
to imitate the first waveform.

## File handling

The downloaded raw and analyzed JSON packages contain base64-encoded audio.
Treat them as private recordings. Keep them in an approved private folder and
do not add them to this public repository. Do not rename two different people
to the same speaker code.

If analysis is not ready or is slow, keep collecting. The raw package is the
important deliverable while the speaker is present.

## Analysis after collection

For each speaker:

1. Return to `/study` on a machine where the health message says analysis is
   ready.
2. Import that speaker's raw JSON package.
3. Select **Analyze all recordings** and keep the tab open.
4. Download the analyzed study when all nine analyses and six comparisons are
   complete.
5. Keep both raw and analyzed packages private.

All recordings are analyzed with the same `mixed` evidence profile so their
reference comparisons are technically compatible. The speaker's real
pronunciation tradition remains metadata for stratified review.

To produce an audio-free aggregate report:

```bash
python -m evaluation.validation_study \
  /private/kriah-validation-analyzed-A01.json \
  /private/kriah-validation-analyzed-C01.json \
  --output /private/kriah-validation-summary.json
```

The evaluator recomputes the candidate classifications at margin-drop
thresholds `-5`, `-4.5`, `-4`, and `-3`. It excludes context-sensitive slots and
weak or unmeasured references from the sensitivity denominator. It reports
false alarms from both clean repeats and untouched vowels in intentional-change
takes.

## Baseline from the first speaker

A manual audit of the three supplied pair exports found 16 planned targets. The
current display classified 10 as strong, 3 as possible, and 3 as missed, with no
displayed false alarms. Three targets had weak reference evidence and should not
be used to tune a decision threshold. On the remaining 13 evaluable targets:

| Margin-drop threshold | Detected | Sensitivity | False alarms among 105 eligible untouched slots |
|---:|---:|---:|---:|
| -5.0 | 9 of 13 | 69.2% | 0 |
| -4.5 | 11 of 13 | 84.6% | 0 |
| -4.0 | 11 of 13 | 84.6% | 0 |
| -3.0 | 11 of 13 | 84.6% | 0 |

This corrects the raw 16-target count by separating weak references. The first
speaker did not provide the new clean-repeat controls, so the zero false alarms
above is not a clean-speech false-alarm estimate.

## Tonight's decision rules

The aggregate evaluator marks an exploratory threshold as passing only when all
of these are true:

- at least three new speakers were collected;
- at least one new speaker is a child;
- at least 90% of planned targets are evaluable;
- sensitivity is at least 80%;
- the observed false-alarm rate is at most 2%.

Passing means only that a threshold is worth carrying into a larger,
speaker-disjoint child evaluation. It does not mean the product can grade
students. A failure should identify whether the problem is low sensitivity,
weak references, false alarms, a specific vowel class, a speaker group, or
recording conditions before the model or platform is changed.

Child speech can produce wider pronunciation-score distributions than adult
speech, and the selected phoneme model is a general multilingual recognizer,
not a validated Hebrew child assessment model. See [Cao et al., Interspeech
2023](https://www.isca-archive.org/interspeech_2023/cao23_interspeech.pdf) and
the [model card](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft).
