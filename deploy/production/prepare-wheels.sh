#!/usr/bin/env bash
# Run inside the selected Linux Python base image, with source mounted at /app.
set -euo pipefail
service=${1:?Specify backend or predictor}
test "$service" = backend || test "$service" = predictor
python -m pip install --upgrade pip==26.3 --index-url https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_CACHE_DIR=/app/production-wheels/cache
mkdir -p "$PIP_CACHE_DIR" "/app/production-wheels/$service"
chown "$(id -u):$(id -g)" "$PIP_CACHE_DIR"
if [ "$service" = backend ]; then
  python -m pip download --only-binary=:all: --no-deps --resume-retries 10 --retries 10 \
    --timeout 60 --dest /app/production-wheels/backend torch==2.13.0 \
    --index-url https://download.pytorch.org/whl/cpu
  python - <<'PY'
from pathlib import Path
lines = Path('/app/backend/requirements.lock').read_text().splitlines()
Path('/tmp/backend.lock').write_text('\n'.join(
    'mootdx @ file:///app/backend/vendor/mootdx' if line.startswith('mootdx @ ') else line
    for line in lines
) + '\n')
PY
  for attempt in 1 2 3 4 5; do
    python -m pip wheel --retries 10 --timeout 60 --wheel-dir /app/production-wheels/backend \
      --find-links /app/production-wheels/backend -r /tmp/backend.lock && exit 0
  done
else
  for attempt in 1 2 3 4 5; do
    python -m pip download --resume-retries 10 --retries 10 --timeout 60 \
      --dest /app/production-wheels/predictor -r /app/deploy/kronos/requirements.lock && exit 0
  done
fi
exit 1
