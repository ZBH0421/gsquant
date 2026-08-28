#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if [[ -f projects/cot-radar/web/package.json ]]; then
  (
    cd projects/cot-radar/web
    npm install
  )
fi

if [[ -f projects/credit-radar/web/package.json ]]; then
  (
    cd projects/credit-radar/web
    npm install
  )
fi
