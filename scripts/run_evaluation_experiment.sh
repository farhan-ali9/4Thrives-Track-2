#!/usr/bin/env bash
set -euo pipefail
python evaluation/run_experiment.py \
  --runner-mode "${RUNNER_MODE:-mock}" \
  --sessions-per-mode "${RUNNER_SESSIONS_PER_MODE:-6}" \
  --experiment-id "${EXPERIMENT_ID:-eval-$(date +%Y%m%d-%H%M%S)}" \
  --output-root "${EVALUATION_OUTPUT_ROOT:-artifacts/evaluation-experiments/latest}" \
  --evaluation-modes "${EVALUATION_MODES:-baseline,rule_based}"
