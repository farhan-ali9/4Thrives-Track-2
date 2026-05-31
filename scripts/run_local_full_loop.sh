#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

load_local_pipeline_env
require_llm_provider
ensure_extension_build
require_coach_api

EXPERIMENT_PREFIX="${EXPERIMENT_PREFIX:-local-$(date +%Y%m%d-%H%M%S)}"

(cd "$ROOT" && ./uniqa-pipeline local-full-loop \
  --validate-sessions "${LOCAL_VALIDATE_SESSIONS:-12}" \
  --bulk-sessions "${LOCAL_BULK_SESSIONS:-300}" \
  --experiment-prefix "$EXPERIMENT_PREFIX" \
  "$@")
