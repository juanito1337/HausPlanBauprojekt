#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python --version
python tools/run_checks.py
# No network install and no NX run. Optional full suite: python tools/run_checks.py --full
