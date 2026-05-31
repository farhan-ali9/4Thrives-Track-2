#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

load_local_pipeline_env
require_llm_provider

(cd "$ROOT" && ./uniqa-pipeline validate-live \
  --execution-mode "${RUNNER_EXECUTION_MODE:-baseline}" \
  --sessions "${RUNNER_SESSIONS:-3}" \
  --experiment-id "validation-$(date +%Y%m%d-%H%M%S)")
