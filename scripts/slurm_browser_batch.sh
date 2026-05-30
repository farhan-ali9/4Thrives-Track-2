#!/usr/bin/env bash
#SBATCH --job-name=uniqa-browser-batch
#SBATCH --output=artifacts/logs/browser-batch-%j.out
#SBATCH --error=artifacts/logs/browser-batch-%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

set -euo pipefail
mkdir -p artifacts/logs
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$LEONARDO_ENV_FILE"
  set +a
fi
: "${RUNNER_EXECUTION_MODE:=baseline}"
: "${RUNNER_SESSIONS:=12}"
CMD=(./uniqa-pipeline validate-live
  --execution-mode "$RUNNER_EXECUTION_MODE"
  --sessions "$RUNNER_SESSIONS"
  --experiment-id "leonardo-${SLURM_JOB_ID:-local}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
