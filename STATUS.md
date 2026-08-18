# Project status

Updated 2026-08-18.

## Completed on the rebuild branch

- Replaced the prompt-biased `/transcribe` grading path with structured
  `/analyze-reading` requests.
- Added a conservative, tested server-side word aligner.
- Removed the nonexistent `/grade` vowel endpoint and all automatic nikud claims.
- Removed “accurate grader” and “mastery” language from the student experience.
- Prevented a configured but unavailable server from silently completing a
  practice checkpoint through browser fallback.
- Added upload limits, Hebrew-only input, restricted CORS, temporary-file
  deletion, best-effort rate limiting, generic error responses, and optional
  HMAC result tokens.
- Added pilot metrics with a check for speaker leakage between calibration and
  test sets.
- Kept all supplied audio outside the public repository.
- Fixed false penalties caused by pointed defective spelling versus Whisper's
  unpointed plene spelling, using only variants licensed by the target's vowel
  marks rather than globally deleting vav and yod.
- Fixed WPM so it measures recognized words over recording duration instead of
  counting only exact string matches.
- Made selective review the explicit product target and exposed that nikud,
  vowel, and phoneme evidence are not evaluated by the current server.
- Added a tested pointed-Hebrew pronunciation map with configurable mixed,
  Sephardi, and Ashkenazi alternatives.
- Added optional word-windowed CTC Viterbi measurements as shadow evidence.
  The evidence is explicitly uncalibrated and cannot affect routing.
- Added an offline JSON research-report command and kept the large phoneme model
  dependencies out of the default Codespaces installation.
- Added a single-page fast pilot that supports live recording or file upload,
  same-origin analysis, a human calibration label, and an optional self-contained
  sample download without automatic audio storage.
- Added a default Codespaces nikud evidence lab with automatic pronunciation-model
  setup, model-readiness status, per-vowel evidence, exact slot labels, paired
  recording comparison, and downloadable labeled packages.
- Moved long analysis into in-memory background jobs so Codespaces forwarding does
  not need to hold one request open for the full CPU inference run.
- Added three controlled, fully pointed master readings covering every supported
  written vowel source, all five core vowel sounds, and major consonant contrasts.
- Added browser recording for Reading B, exact Reading B vowel labels, bulk
  correct labeling, and export of both readings' labels.
- Added a conservative, non-authoritative reference-comparison endpoint that
  reports vowel-only means, strong candidate changes, context-sensitive sheva,
  and labeled catches, misses, and false alarms.

## Verified locally

- Pure scoring, signing, and evaluation unit tests pass.
- The inline browser JavaScript parses in Node.
- Python sources compile.
- The optional CTC and Whisper models completed a real-audio shadow run on the
  supplied adult `Atah Kadosh` recording. Thirteen of fourteen expected words
  produced acoustic evidence; one ASR word mismatch was left unmeasured.
- On the supplied paired bracha-4 recordings, the overall mean expected-phone
  probability was slightly higher for the recording labeled as containing
  mistakes (0.776509) than for the recording labeled correct (0.762565). This
  confirms that an absolute overall threshold would be unsafe.
- The three deliberately altered tzeirei slots produced paired competitor-margin
  deltas of -7.1108, -8.4812, and -6.5449. Other slots also moved substantially,
  so these adult paired results support further calibration research, not an
  automatic grading threshold.
- The initial conservative paired rule independently flags those same three
  tzeirei changes in the supplied user-exported comparison. Its vowel-only means
  are 0.755751 for the correct reading and 0.701499 for the mistake reading.
  This does not establish performance on the fourth reported planted error,
  different speakers, or child recordings.

The API integration tests are included but require the development dependencies.
Actual ASR accuracy, model startup, container behavior, and microphone behavior
still need verification in the target environment.

## Not complete, by design

- No production backend has been deployed.
- No child-speech validation set has been collected or teacher-labeled.
- No nikud or phoneme measurement is permitted to make a student decision.
- The Codespaces lab now installs and runs the shadow model, but its displayed
  measurements remain uncalibrated and cannot make a student decision.
- No school privacy, retention, or vendor review has been approved.
- No student authentication, roster sync, durable result storage, or teacher
  dashboard exists.
- Existing client result codes remain easy to alter. Server responses can carry
  a signed sub-token, but a real dashboard must verify it server-side.

## Current release classification

Developer pilot only. The static practice mode can be explored, but the project
must not be represented as a validated assessment system.
