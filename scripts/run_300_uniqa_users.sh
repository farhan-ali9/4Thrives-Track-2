#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export EXTENSION_DIST="${EXTENSION_DIST:-$PWD/extension/dist}"
export UNIQA_CALCULATOR_URL="${UNIQA_CALCULATOR_URL:-https://www.uniqa.at/rechner/krankenversicherung/}"

export LLM_API_URL="${LLM_API_URL:-https://api.featherless.ai/v1/chat/completions}"
export LLM_MODEL="${LLM_MODEL:-${VITE_FEATHERLESS_MODEL:-Qwen/Qwen2.5-7B-Instruct}}"

export RUNNER_MODE="${RUNNER_MODE:-bulk}"
export BASELINE_SESSIONS="${BASELINE_SESSIONS:-150}"
export COACH_SESSIONS="${COACH_SESSIONS:-150}"

export RUNNER_DWELL_MULTIPLIER="${RUNNER_DWELL_MULTIPLIER:-2.5}"
export RUNNER_MIN_THINK_MS="${RUNNER_MIN_THINK_MS:-2200}"
export RUNNER_MAX_THINK_MS="${RUNNER_MAX_THINK_MS:-11000}"

export PIPELINE_OUTPUT_ROOT="${PIPELINE_OUTPUT_ROOT:-artifacts/uniqa-300-users/$(date +%Y%m%d-%H%M%S)}"
export EVALUATION_RUNNER_MODE="${EVALUATION_RUNNER_MODE:-mock}"
export EVALUATION_SESSIONS_PER_MODE="${EVALUATION_SESSIONS_PER_MODE:-6}"

npm run build:extension

npm run pipeline:local
