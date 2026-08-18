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

1. The pointed siddur text is converted into expected phoneme slots, including
   explicit accepted alternatives for the configured pronunciation profile.
2. The word model locates omissions, additions, substitutions, and approximate
   time windows.
3. A separate multilingual CTC model aligns the expected consonant and vowel
   slots inside those windows and reports posterior evidence.
4. The measurements are returned as uncalibrated shadow evidence with
   `affects_routing: false`.

The default Codespaces page now exposes this layer as a nikud evidence lab. It
shows expected-vowel evidence and the strongest competing modeled phone for each
measured vowel slot, accepts a human label at the same slot, and can compare two
recordings of the same text. Long analyses run as polled background jobs to avoid
forwarded-request timeouts. The lab intentionally does not turn those values
into correct, incorrect, pass, or fail decisions.

The source text uses U+0592 immediately after selected shevas as a source-specific
sheva-na marker. The mapper also handles shuruk, holam malei, furtive patah,
beged-kefet, soft tav alternatives, and separate Hashem/Adonai whole-word
variants. These are tested engineering rules, not yet a school-approved
pronunciation policy.

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
