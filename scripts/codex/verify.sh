#!/usr/bin/env bash
set -euo pipefail

python -m pytest projects/cot-radar/pipeline/tests -q
python -m ruff check projects/cot-radar/pipeline/src projects/cot-radar/pipeline/tests
python -m mypy projects/cot-radar/pipeline/src

if [[ -d projects/credit-radar/pipeline/tests ]]; then
  python -m pytest projects/credit-radar/pipeline/tests -q
  python -m ruff check projects/credit-radar/pipeline/src projects/credit-radar/pipeline/tests
  python -m mypy projects/credit-radar/pipeline/src
fi

python -m pytest tests/control_plane -q

if [[ -f projects/cot-radar/web/package.json ]]; then
  (
    cd projects/cot-radar/web
    npm test -- --run
    npm run build
  )
fi

if [[ -f projects/credit-radar/web/package.json ]]; then
  (
    cd projects/credit-radar/web
    npm test -- --run
    npm run build
  )
fi

git diff --check
