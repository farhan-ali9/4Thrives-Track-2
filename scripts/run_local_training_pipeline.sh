#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${LOCAL_PIPELINE_ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "${#value}" -ge 2 ]]; then
      first="${value:0:1}"
      last="${value: -1}"
      if [[ "$first" == "$last" && ( "$first" == "\"" || "$first" == "'" ) ]]; then
        value="${value:1:${#value}-2}"
      fi
    fi
    export "$key=$value"
  done < "$ENV_FILE"
fi

export LLM_API_URL="${LLM_API_URL:-${LLM_GATEWAY_URL:-https://api.featherless.ai/v1/chat/completions}}"
export LLM_MODEL="${LLM_MODEL:-${LLM_DEFAULT_MODEL:-${VITE_FEATHERLESS_MODEL:-MihaiPopa-1/Qwen-3-0.6B-Claude-4.7-Opus-Distilled}}}"
export COACH_API_URL="${COACH_API_URL:-${VITE_COACH_API_ORIGIN:-http://127.0.0.1:8787}}"
export EXTENSION_DIST="${EXTENSION_DIST:-$ROOT_DIR/extension/dist}"
export RUNNER_OUTPUT_DIR="${RUNNER_OUTPUT_DIR:-artifacts/browser-runs}"
export RUNNER_DWELL_MULTIPLIER="${RUNNER_DWELL_MULTIPLIER:-2.2}"
export RUNNER_MIN_THINK_MS="${RUNNER_MIN_THINK_MS:-1800}"
export RUNNER_MAX_THINK_MS="${RUNNER_MAX_THINK_MS:-9000}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

ARGS=(
  local-full
  --env-file "$ENV_FILE"
  --experiment-id "${EXPERIMENT_ID:-local-training}"
  --runner-mode "${RUNNER_MODE:-validation}"
  --persona-runs "${PERSONA_RUNS:-1}"
  --output-root "${PIPELINE_OUTPUT_ROOT:-artifacts/local-training-pipeline/latest}"
  --evaluation-runner-mode "${EVALUATION_RUNNER_MODE:-mock}"
  --evaluation-sessions-per-mode "${EVALUATION_SESSIONS_PER_MODE:-6}"
  --evaluation-modes "${EVALUATION_MODES:-baseline,rule_based,trainable}"
)

if [[ -z "${BASELINE_SESSIONS:-}" && -n "${RUNNER_SESSIONS:-}" ]]; then
  BASELINE_SESSIONS="$RUNNER_SESSIONS"
fi

if [[ -z "${COACH_SESSIONS:-}" && -n "${RUNNER_SESSIONS:-}" ]]; then
  COACH_SESSIONS="$RUNNER_SESSIONS"
fi

if [[ -n "${BASELINE_SESSIONS:-}" ]]; then
  ARGS+=(--baseline-sessions "$BASELINE_SESSIONS")
fi

if [[ -n "${COACH_SESSIONS:-}" ]]; then
  ARGS+=(--coach-sessions "$COACH_SESSIONS")
fi

if [[ "${SKIP_EVALUATE:-0}" == "1" ]]; then
  ARGS+=(--skip-evaluate)
fi

"$PYTHON_BIN" uniqa_pipeline.py "${ARGS[@]}"
