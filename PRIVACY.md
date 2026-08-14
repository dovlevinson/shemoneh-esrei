# Privacy and data handling

This project processes voice recordings, names, and class labels associated with
children. Treat them as sensitive school data even when a particular law or
policy has not yet been determined to apply.

## Current data flow

| Data | Location | Persistence |
|---|---|---|
| Name, class, progress | Browser local storage | Until browser data is cleared |
| Teacher reference clips | Browser IndexedDB | Until deleted or browser data is cleared |
| Recorded Check audio | Browser memory | Until the page/session is replaced; user can download it |
| Server upload | Temporary server file | Deleted immediately after transcription attempt |
| Transcript and analysis | Returned to browser | May enter local result code and browser state |

The analysis API does not request student name or class. It has no database and
does not intentionally retain audio. This does not prove that a cloud provider,
reverse proxy, browser, school network, or application log retains nothing.

## Required decisions before classroom use

- School owner and accountable administrator
- Approved hosting account and region
- Whether recordings may leave the school-managed device or network
- Consent and notice language
- Retention period and deletion procedure
- Who can view recordings, transcripts, and results
- Incident response contact
- Vendor and legal review, including a determination of which student-privacy
  requirements apply

The US Department of Education publishes the governing FERPA regulations and
student privacy resources at [studentprivacy.ed.gov](https://studentprivacy.ed.gov/ferpa).
That link is not a determination that FERPA does or does not apply here.

## Repository rules

- Never commit recordings, rosters, names, class exports, manifests, or consent
  records.
- Store evaluation data in a school-approved private system.
- Use pseudonymous speaker IDs in model-evaluation files.
- Do not put secrets in `index.html`, GitHub Pages, result codes, or repository
  settings visible to students.
- Rotate `KRIAH_RESULT_SECRET` if it is exposed.
