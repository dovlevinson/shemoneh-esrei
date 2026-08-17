# Nikud and automatic assessment

## What the current pilot evaluates

The current server compares an unpointed Hebrew transcript with the expected
words. It can estimate whether words were present and in the expected order.
It now treats vowel-mark-licensed defective and plene spellings as the same word,
so forms such as `אֱלֹהֵינוּ` and `אלוהינו` do not create a false reading error.

This is not nikud grading. Whisper does not preserve the vowel points in its
transcript, so word matching cannot distinguish readings such as `בָּרוּךְ` and
`בָּרַךְ` when their consonants are the same.

## Intended finished architecture

1. The pointed siddur text is converted into expected phoneme slots.
2. The word model locates omissions, additions, substitutions, and approximate
   time windows.
3. A separate acoustic model evaluates the expected consonant and vowel sounds
   inside those windows.
4. A calibrated decision layer routes attempts:
   - high-confidence acceptable attempts clear automatically;
   - high-confidence errors produce an automatic retry;
   - only ambiguous attempts go to selective teacher review.

A teacher reference recording may be useful as one calibration signal. It is
not intended to require a teacher to listen to every student attempt, and one
teacher's voice cannot by itself establish thresholds that are safe across
children, devices, rooms, and accepted pronunciation traditions.

## Evidence still required

The supplied adult recordings can test whether a phoneme feature reacts to a
planted error. They cannot establish child-speech accuracy or a safe automatic
pass threshold. Before nikud evidence affects automatic progression, the
phoneme layer must be evaluated on speaker-disjoint, teacher-labeled recordings
using the release gates in `EVALUATION.md`.

Research likewise reports wider GOP score distributions for child speech and
lower error-discrimination performance than for adult speech:

- Cao, Fan, Svendsen, and Salvi (2023), [An Analysis of Goodness of
  Pronunciation for Child Speech](https://www.isca-archive.org/interspeech_2023/cao23_interspeech.pdf)
- El Kheir et al. (2023), [Automatic Pronunciation Assessment: A
  Review](https://aclanthology.org/2023.findings-emnlp.557.pdf)
