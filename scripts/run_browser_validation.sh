#!/usr/bin/env bash
set -euo pipefail
python browser-runner/run_batch.py --mode validation --sessions "${RUNNER_SESSIONS:-3}" --experiment-id "validation-$(date +%Y%m%d-%H%M%S)"
