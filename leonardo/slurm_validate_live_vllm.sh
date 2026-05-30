#!/usr/bin/env bash
#SBATCH --job-name=uniqa-validate-vllm
#SBATCH --output=artifacts/logs/validate-vllm-%j.out
#SBATCH --error=artifacts/logs/validate-vllm-%j.err
#SBATCH --partition=boost_usr_prod
#SBATCH --reservation=s_tra_ncc
#SBATCH --account=EUHPC_D30_031
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G

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

: "${LLM_MODEL:=meta-llama/Meta-Llama-3.1-8B-Instruct}"
: "${LLM_API_URL:=http://127.0.0.1:8000/v1/chat/completions}"
: "${VLLM_BOOT_WAIT_S:=30}"

if [[ -z "${VLLM_SERVE_CMD:-}" ]]; then
  export VLLM_SERVE_CMD="$HOME/.pixi/bin/pixi run --manifest-path leonardo-vllm/pixi.toml python -m vllm.entrypoints.openai.api_server --model ${LLM_MODEL} --host 127.0.0.1 --port 8000"
fi

eval "$VLLM_SERVE_CMD" > "artifacts/logs/vllm-${SLURM_JOB_ID:-local}.out" 2>&1 &
export VLLM_PID=$!
trap 'kill ${VLLM_PID:-0} >/dev/null 2>&1 || true' EXIT
sleep "$VLLM_BOOT_WAIT_S"

CMD=(./uniqa-pipeline validate-live
  --execution-mode "${RUNNER_EXECUTION_MODE:-coach}"
  --sessions "${RUNNER_SESSIONS:-12}"
  --experiment-id "${EXPERIMENT_ID:-leonardo-validation-vllm}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
