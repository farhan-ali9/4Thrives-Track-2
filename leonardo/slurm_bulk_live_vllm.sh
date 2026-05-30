#!/usr/bin/env bash
#SBATCH --job-name=uniqa-bulk-vllm
#SBATCH --output=artifacts/logs/bulk-vllm-%j.out
#SBATCH --error=artifacts/logs/bulk-vllm-%j.err
#SBATCH --partition=boost_usr_prod
#SBATCH --reservation=s_tra_ncc
#SBATCH --account=EUHPC_D30_031
#SBATCH --time=08:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G

set -euo pipefail
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
source "$PROJECT_ROOT/leonardo/slurm_common.sh"
mkdir -p artifacts/logs
leonardo_load_env
leonardo_prepare_pixi_cache

: "${PIXI_BIN:=$HOME/.pixi/bin/pixi}"
: "${RUNNER_MANIFEST:=leonardo/pixi.toml}"
: "${VLLM_MANIFEST:=leonardo-vllm/pixi.toml}"
: "${LLM_MODEL:=meta-llama/Meta-Llama-3.1-8B-Instruct}"
: "${LLM_API_URL:=http://127.0.0.1:8000/v1/chat/completions}"
: "${VLLM_BOOT_WAIT_S:=30}"

if [[ -z "${VLLM_SERVE_CMD:-}" ]]; then
  export VLLM_SERVE_CMD="$PIXI_BIN run --manifest-path $VLLM_MANIFEST python -m vllm.entrypoints.openai.api_server --model ${LLM_MODEL} --host 127.0.0.1 --port 8000"
fi

eval "$VLLM_SERVE_CMD" > "artifacts/logs/vllm-${SLURM_JOB_ID:-local}.out" 2>&1 &
export VLLM_PID=$!
trap 'kill ${VLLM_PID:-0} >/dev/null 2>&1 || true' EXIT
sleep "$VLLM_BOOT_WAIT_S"

CMD=("$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline run-live
  --execution-mode "${RUNNER_EXECUTION_MODE:-coach}"
  --sessions "${RUNNER_SESSIONS:-300}"
  --experiment-id "${EXPERIMENT_ID:-leonardo-bulk-vllm-${SLURM_JOB_ID:-local}}")
if [[ -n "${RUNNER_OUTPUT_DIR:-}" ]]; then
  CMD+=(--output-dir "$RUNNER_OUTPUT_DIR")
fi
"${CMD[@]}"
