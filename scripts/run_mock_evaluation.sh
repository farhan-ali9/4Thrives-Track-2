#!/usr/bin/env bash
set -euo pipefail
python browser-runner/run_batch.py --mode mock --sessions "${RUNNER_SESSIONS:-6}" --experiment-id "mock-$(date +%Y%m%d-%H%M%S)"
