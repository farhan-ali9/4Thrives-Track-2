#!/usr/bin/env bash
#SBATCH --job-name=uniqa-bulk-live
#SBATCH --output=artifacts/logs/bulk-live-%j.out
#SBATCH --error=artifacts/logs/bulk-live-%j.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G

set -euo pipefail
mkdir -p artifacts/logs
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
  set +a
fi

if [[ -n "${VLLM_SERVE_CMD:-}" ]]; then
  eval "$VLLM_SERVE_CMD" > "artifacts/logs/vllm-${SLURM_JOB_ID:-local}.out" 2>&1 &
  export VLLM_PID=$!
  trap 'kill ${VLLM_PID:-0} >/dev/null 2>&1 || true' EXIT
  sleep "${VLLM_BOOT_WAIT_S:-20}"
fi

CMD=(./uniqa-pipeline run-live
  --execution-mode "${RUNNER_EXECUTION_MODE:-coach}"
  --sessions "${RUNNER_SESSIONS:-300}"
  --experiment-id "${EXPERIMENT_ID:-leonardo-bulk-${SLURM_JOB_ID:-local}}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
