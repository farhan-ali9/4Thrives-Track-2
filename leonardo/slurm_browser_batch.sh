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
  set -a
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
  set +a
fi

: "${PIXI_BIN:=$HOME/.pixi/bin/pixi}"
: "${RUNNER_MANIFEST:=leonardo/pixi.toml}"
: "${RUNNER_EXECUTION_MODE:=baseline}"
: "${RUNNER_SESSIONS:=12}"
CMD=("$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline validate-live
  --execution-mode "$RUNNER_EXECUTION_MODE"
  --sessions "$RUNNER_SESSIONS"
  --experiment-id "leonardo-${SLURM_JOB_ID:-local}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
