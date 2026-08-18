#!/usr/bin/env bash
set -euo pipefail

log_file="${TMPDIR:-/tmp}/kriah-reading-coach.log"

health="$(curl --fail --silent http://127.0.0.1:8000/health 2>/dev/null || true)"
if [[ "${health}" == *'"mode":"shadow"'* ]]; then
  exit 0
fi
if [[ -n "${health}" ]]; then
  pkill -f "python -m uvicorn server.app:app" 2>/dev/null || true
fi

nohup python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 >"${log_file}" 2>&1 &

for _ in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
    exit 0
  fi
  sleep 1
done

echo "Kriah Reading Coach did not start. Log output follows:"
sed -n '1,160p' "${log_file}"
exit 1
