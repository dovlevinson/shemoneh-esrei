# Research boundary

The earlier phoneme and peak-scoring scripts are not part of the production
service. They were useful experiments, but the supplied evidence is not enough
to validate vowel or pronunciation grading for children.

The specific reasons are:

- the phone model was not demonstrated to be a Hebrew child-speech assessor;
- the peak picker did not compute a calibrated, reference-normalized GOP score;
- results came from a tiny number of adult recordings, including paired takes
  from one speaker;
- a single teacher template cannot represent ordinary timing, pitch, microphone,
  age, and pronunciation variation;
- no speaker-disjoint holdout set or blinded teacher labels were used.

The original experiment files and recordings remain outside this branch. Do not
copy student or teacher audio into this public repository. A future acoustic
scorer belongs behind a versioned interface and must pass the gates in
`EVALUATION.md` before it can affect student progression.
