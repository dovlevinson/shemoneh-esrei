# Evaluation plan and release gates

The supplied paired adult recordings can demonstrate a hypothesis. They cannot
estimate classroom accuracy, child-speech transfer, or a safe pass threshold.

## Labeling protocol

1. Obtain school approval and parent/guardian consent where required.
2. Assign pseudonymous speaker IDs. Keep the identity map outside this project.
3. Ask each student for normal reads and controlled error reads across several
   brachot, devices, rooms, and speaking rates.
4. Have two qualified teachers independently label each recording without seeing
   the model output. Resolve disagreements and keep both original labels.
5. Label whole-read pass/fail plus word-level missing, extra, substitution, and
   pronunciation or nikud issues.
6. Split by speaker before choosing thresholds. A student's recordings may
   appear in calibration or test, never both.

## Minimum pilot shape

- At least 30 child speakers across the intended age range
- At least 300 labeled recordings total
- At least 100 recordings containing teacher-confirmed errors
- At least 10 speakers and 100 recordings reserved for the untouched test split
- Results reported by age band, pronunciation tradition, microphone/device type,
  room condition, and bracha when sample sizes permit

These are minimum engineering gates, not a claim of statistical or pedagogical
validation.

## Proposed automatic-progression gates

Do not allow a model result to affect progression unless all are true on the
untouched, speaker-disjoint test split:

- false-pass rate is at most 5%;
- the 95% Wilson upper bound for false-pass rate is at most 10%;
- false-flag rate is at most 15%;
- no reviewed subgroup has a false-pass rate more than 5 percentage points above
  the overall rate;
- p95 end-to-end response time is at most 20 seconds on target school devices;
- upload or analysis failures are below 2%;
- every automated result remains reviewable from its original recording.

Until these gates pass, stars are practice progression only and teacher review
is the final decision.

## Run the report

Copy `evaluation/manifest.example.jsonl` to a private data workspace, populate
it with teacher labels and model outputs, then run:

```bash
PYTHONPATH=. python -m evaluation.metrics private/manifest.jsonl --threshold 90 --split test
```

Never tune the threshold against the test split. Record the selected threshold,
model ID, code commit, and dataset version before the final run.
