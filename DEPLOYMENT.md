# Deployment runbook

This branch is deployable as a static frontend plus a containerized analysis API.
Deployment is intentionally separate from merging so the school can approve the
account, region, privacy terms, budget, and rollback owner first.

## Backend configuration

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `KRIAH_ALLOWED_ORIGINS` | Yes in production | GitHub Pages plus local origins | Comma-separated exact browser origins |
| `KRIAH_RESULT_SECRET` | Recommended | unset | HMAC key for tamper-evident server result tokens |
| `KRIAH_MODEL_ID` | No | `ivrit-ai/whisper-large-v3-turbo-ct2` | Speech model |
| `KRIAH_DEVICE` | No | `cpu` | `cpu` or `cuda` |
| `KRIAH_COMPUTE_TYPE` | No | `int8` on CPU, `float16` on GPU | Faster-whisper compute mode |
| `KRIAH_MAX_UPLOAD_BYTES` | No | 15728640 | Per-upload byte limit |
| `KRIAH_MAX_AUDIO_SECONDS` | No | 180 | Model-reported duration limit |
| `KRIAH_RATE_LIMIT_PER_MINUTE` | No | 10 | Single-process safety limit |

Generate a secret with a password manager or platform secret generator. Do not
place it in git or the static frontend.

## Container smoke test

From the project root:

```bash
docker build -f server/Dockerfile -t kriah-analysis .
docker run --rm -p 8000:8000 \
  -e KRIAH_ALLOWED_ORIGINS=http://127.0.0.1:8080 \
  -e KRIAH_RESULT_SECRET=replace-with-a-secret \
  kriah-analysis
curl http://127.0.0.1:8000/health
```

Then submit a short, consented test recording to `/analyze-reading`. The health
check does not load the model and is not an end-to-end ASR test.

## Production controls

- Put TLS, request-size enforcement, and distributed rate limiting at the edge.
- Use one worker per loaded model unless memory measurements support more.
- Disable request-body logging and confirm provider log retention.
- Add uptime, latency, 4xx/5xx, cold-start, and memory alerts without recording
  audio or transcript contents.
- Pin a container digest after the first verified build.
- Keep the prior frontend and backend image available for rollback.
- Set the Teacher tab endpoint to the production
  `https://.../analyze-reading` URL on managed devices.

Scale-to-zero platforms can reduce idle cost, but the model's cold-start time and
memory must be measured before choosing one. Modal documents that HTTP endpoints
can scale to zero in its [web endpoint guide](https://modal.com/docs/guide/endpoints).
This project does not assume a provider or cost until a real load test exists.

## Release order

1. Deploy the backend to a non-production environment.
2. Run API tests, a real-audio smoke test, and a deletion/logging check.
3. Point a private copy of the frontend at staging.
4. Run the evaluation plan and privacy review.
5. Merge and deploy only after the designated school owner approves.
