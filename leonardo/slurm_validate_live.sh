#!/usr/bin/env bash
#SBATCH --job-name=uniqa-validate-live
#SBATCH --output=artifacts/logs/validate-live-%j.out
#SBATCH --error=artifacts/logs/validate-live-%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G

set -euo pipefail
mkdir -p artifacts/logs
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
  set +a
fi

if [[ -z "${PIXI_CACHE_DIR:-}" ]]; then
  if [[ -w /scratch_local || ! -e /scratch_local ]]; then
    export PIXI_CACHE_DIR="/scratch_local/pixi-cache-${USER}"
  else
    export PIXI_CACHE_DIR="/tmp/pixi-cache-${USER}"
  fi
fi
mkdir -p "$PIXI_CACHE_DIR"

: "${PIXI_BIN:=$HOME/.pixi/bin/pixi}"
: "${RUNNER_MANIFEST:=leonardo/pixi.toml}"

if [[ -n "${VLLM_SERVE_CMD:-}" ]]; then
  eval "$VLLM_SERVE_CMD" > "artifacts/logs/vllm-${SLURM_JOB_ID:-local}.out" 2>&1 &
  export VLLM_PID=$!
  trap 'kill ${VLLM_PID:-0} >/dev/null 2>&1 || true' EXIT
  sleep "${VLLM_BOOT_WAIT_S:-20}"
fi

CMD=("$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline validate-live
  --execution-mode "${RUNNER_EXECUTION_MODE:-baseline}"
  --sessions "${RUNNER_SESSIONS:-12}"
  --experiment-id "${EXPERIMENT_ID:-leonardo-validate-${SLURM_JOB_ID:-local}}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
