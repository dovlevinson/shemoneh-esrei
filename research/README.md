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
copy student or teacher audio into this public repository.

The service now has a replacement research path behind
`KRIAH_PRONUNCIATION_MODE=shadow`. It uses a pointed-Hebrew pronunciation map,
ASR word windows, and a blank-aware CTC Viterbi path. Unlike the old peak script,
it retains ordered blank/phone states and returns evidence without inventing a
correct/incorrect threshold. It is still not validated and cannot affect student
progression.

Run a consented adult recording without writing a report to disk:

```bash
pip install -r server/requirements-pronunciation.txt
KRIAH_PRONUNCIATION_MODE=shadow \
  python -m research.pronunciation_report --bracha 4 /private/reading.webm
```

The output is evidence for model development, not a grade. It must be compared
with blinded human labels and pass `EVALUATION.md` before any threshold is added.

To compare two reports slot by slot without assigning a verdict:

```bash
python -m research.compare_pronunciation_reports \
  /private/baseline.json /private/comparison.json
```
