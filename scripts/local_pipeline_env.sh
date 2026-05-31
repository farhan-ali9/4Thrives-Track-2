#!/usr/bin/env bash
set -euo pipefail

PIPELINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_local_pipeline_env() {
  local env_file="${LOCAL_PIPELINE_ENV_FILE:-$PIPELINE_ROOT/.env}"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi

  export EXTENSION_DIST="${EXTENSION_DIST:-$PIPELINE_ROOT/extension/dist}"
  export COACH_API_URL="${COACH_API_URL:-http://127.0.0.1:8787}"
  export RUNNER_OUTPUT_DIR="${RUNNER_OUTPUT_DIR:-$PIPELINE_ROOT/artifacts/browser-runs}"
  export LLM_API_URL="${LLM_API_URL:-${LLM_GATEWAY_URL:-https://api.featherless.ai/v1/chat/completions}}"
  export LLM_MODEL="${LLM_MODEL:-${LLM_DEFAULT_MODEL:-${VITE_FEATHERLESS_MODEL:-Qwen/Qwen2.5-7B-Instruct}}}"
  export LLM_HTTP_REFERER="${LLM_HTTP_REFERER:-http://localhost}"
  export LLM_APP_TITLE="${LLM_APP_TITLE:-UNIQA Conversion Coach Runner}"
}

_is_local_llm() {
  if [[ "${LLM_PROVIDER:-}" == "local" ]]; then
    return 0
  fi
  case "${LLM_API_URL:-}" in
    *localhost*|*127.0.0.1*) return 0 ;;
    *) return 1 ;;
  esac
}

require_featherless_key() {
  if [[ -z "${FEATHERLESS_API_KEY:-}" ]]; then
    echo "FEATHERLESS_API_KEY is not set. Copy .env.example to .env and add your Featherless key." >&2
    exit 1
  fi
}

require_llm_provider() {
  if _is_local_llm; then
    local models_url="${LLM_API_URL%/chat/completions}/models"
    if ! curl -fsS "$models_url" >/dev/null; then
      echo "Ollama is not reachable at $models_url." >&2
      echo "Start it with 'ollama serve' and pull your model with 'ollama pull ${LLM_MODEL:-qwen2.5:3b-instruct}'." >&2
      exit 1
    fi
    local models_json
    if models_json="$(curl -fsS "$models_url")" && ! grep -q "\"${LLM_MODEL}\"" <<<"$models_json"; then
      echo "Warning: LLM_MODEL='${LLM_MODEL}' may not be pulled yet. Run: ollama pull ${LLM_MODEL}" >&2
    fi
    return 0
  fi
  require_featherless_key
}

ensure_extension_build() {
  (cd "$PIPELINE_ROOT" && npm run build:extension)
}

require_coach_api() {
  local healthz_url="${COACH_API_URL%/}/healthz"
  if ! curl -fsS "$healthz_url" >/dev/null; then
    echo "Coach API is not healthy at $healthz_url. Start it first with 'npm run dev:coach-api'." >&2
    exit 1
  fi
}
