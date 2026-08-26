# Nikud and automatic assessment

## What the current result evaluates

The current server compares an unpointed Hebrew transcript with the expected
words. It can estimate whether words were present and in the expected order.
It now treats vowel-mark-licensed defective and plene spellings as the same word,
so forms such as `אֱלֹהֵינוּ` and `אלוהינו` do not create a false reading error.

This is not nikud grading. Whisper does not preserve the vowel points in its
transcript, so word matching cannot distinguish readings such as `בָּרוּךְ` and
`בָּרַךְ` when their consonants are the same.

## Shadow layer now implemented

1. The pointed siddur text is preserved as exact written-vowel metadata, then
   mapped to accepted sound families under `kriah-pronunciation-v2`.
2. The word model locates omissions, additions, substitutions, and approximate
   time windows.
3. A separate multilingual CTC model anchors consonants but aligns vowel slots
   against any vowel sound, allowing an incorrect vowel to stay in its proper
   position rather than forcing the expected vowel into a neighboring syllable.
   Vowel evidence is compared against competing vowel sounds only.
4. The measurements are returned as uncalibrated shadow evidence with
   `affects_routing: false`.

## Pronunciation policy v2

The written mark remains exact in every result. Acoustic evidence is evaluated
against a sound family rather than treating every Tiberian sign as a separate
modern vowel quality.

| Written mark | Accepted family or realization | Evidence tier |
| --- | --- | --- |
| Patach | A | primary |
| Kamatz gadol | A or rounded A/O | primary |
| Kamatz katan | O | primary |
| Segol | E | primary |
| Tzeirei | E or EI in mixed/Ashkenazi mode; E in Sephardi mode | multi-realization family |
| Chirik | I | primary |
| Cholam | O or OY in mixed/Ashkenazi mode; O in Sephardi mode | multi-realization family |
| Kubutz and shuruk | U | primary |
| Chataf patach | A | reduced-family |
| Chataf segol | E | reduced-family |
| Chataf kamatz | O | reduced-family |
| Sheva | brief E or no separately audible vowel | research-only, not independently scored |

Chataf duration is not graded. Kubutz and shuruk retain different written
labels but share U acoustically. Tzeirei and cholam preserve their permitted
realizations in metadata while the current five-family model collects the
base-family evidence. Soft tav remains token-level T or S in mixed mode.

Sheva is deliberately outside the primary CTC sequence. The result stores its
traditional classification, the rule used, and both `BRIEF_E` and `NONE` as
possible modern realizations. This prevents a missing or extremely brief sheva
from shifting every later vowel alignment in the word.

The default Codespaces page now exposes this layer as a nikud evidence lab. It
shows expected-vowel evidence and the strongest competing modeled phone for each
measured vowel slot, accepts a human label at the same slot, and can compare two
recordings of the same text. Long analyses run as polled background jobs to avoid
forwarded-request timeouts. The lab intentionally does not turn those values
into correct, incorrect, pass, or fail decisions.

## Controlled master-reading calibration

The lab also supplies three short, pointed master readings with ordinary Hebrew
words. Together they cover the target vowel sources in the controlled suite,
the five core vowel sounds, and representative consonant contrasts. The
special-cases section includes sheva classifications, kamatz katan, reduced
vowels, and furtive patach. No sheva has a forced audible vowel slot in policy
v2.

The recommended sequence is:

1. Record a correct reference take for one master section.
2. Record a second correct take and check for false alarms from natural variation.
3. Select a guided mistake scenario and read the highlighted substitute words.
4. Inspect automatic per-target catches, misses, unmeasured words, misplaced
   vowel alerts, and false alarms. No manual vowel labels are needed.
5. Repeat across other speakers, traditions, recording conditions, and actual brachot.

The comparison endpoint uses only aligned vowel slots, not consonant evidence.
If Whisper calls a timestamped word incorrect, its audio window is still checked
against the expected pronunciation and explicitly marked lower confidence.
Its initial strong-candidate research rule requires a competitor-margin drop of
at least five points, a negative candidate margin, and expected-vowel evidence
at or below 20%. Sheva is excluded from policy-v2 comparison. These numbers
were selected from an adult example and are not validated decision thresholds.
They cannot change a student's routing or grade.

The source text uses U+0592 immediately after selected shevas as a source-specific
sheva-na marker even though Unicode names U+0592 "HEBREW ACCENT SEGOL." Policy
v2 reports that source-specific rule instead of treating the character as a
universal sheva sign. It also recognizes U+05BA and preserves consonantal V plus
O in forms such as `מִצְוֺתֶיךָ`; a regression rule handles the current source
spelling `מִצְוֹתֶיךָ` as V plus O as well. The mapper also handles shuruk,
holam malei, furtive patah, beged-kefet, soft tav alternatives, and separate
Hashem/Adonai whole-word variants. These remain tested engineering rules, not a
validated student assessment.

Every saved sample carries its pronunciation-policy version. The research page
can load the audio and exact text from an older full sample and rerun it under
the current policy. Reports keep the new result linked to its source sample and
do not pool different policy versions for threshold claims.
The same table is available to clients at `/pronunciation-policy`.

The model is pinned to a specific revision of Meta's multilingual
[`wav2vec2-lv-60-espeak-cv-ft`](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft).
Its model card supports its use as a phoneme recognizer. It does not claim that
the model grades Hebrew, children, tefillah, or nikud.

## Still required before automatic decisions

A calibrated decision layer would eventually route attempts:

   - high-confidence acceptable attempts clear automatically;
   - high-confidence errors produce an automatic retry;
   - only ambiguous attempts go to selective teacher review.

A teacher reference recording may be useful as one calibration signal. It is
not intended to require a teacher to listen to every student attempt, and one
teacher's voice cannot by itself establish thresholds that are safe across
children, devices, rooms, and accepted pronunciation traditions.

## Evidence still required

The supplied adult recordings can test whether a phoneme measurement reacts to
a planted error. They cannot establish child-speech accuracy or a safe automatic
pass threshold. Before nikud evidence affects automatic progression, the shadow
layer must be evaluated on speaker-disjoint, teacher-labeled recordings using
the release gates in `EVALUATION.md`.

Recent CTC pronunciation research supports alignment-independent and
insertion/deletion-aware approaches, but does not validate this specific Hebrew
implementation: [Cao et al., Interspeech 2024](https://www.isca-archive.org/interspeech_2024/cao24b_interspeech.pdf).

Research likewise reports wider GOP score distributions for child speech and
lower error-discrimination performance than for adult speech:

- Cao, Fan, Svendsen, and Salvi (2023), [An Analysis of Goodness of
  Pronunciation for Child Speech](https://www.isca-archive.org/interspeech_2023/cao23_interspeech.pdf)
- El Kheir et al. (2023), [Automatic Pronunciation Assessment: A
  Review](https://aclanthology.org/2023.findings-emnlp.557.pdf)
