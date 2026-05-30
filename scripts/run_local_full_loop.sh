#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

load_local_pipeline_env
require_featherless_key
ensure_extension_build
require_coach_api

EXPERIMENT_PREFIX="${EXPERIMENT_PREFIX:-local-$(date +%Y%m%d-%H%M%S)}"

(cd "$ROOT" && "$PYTHON_BIN" uniqa_pipeline.py local-full-loop \
  --validate-sessions "${LOCAL_VALIDATE_SESSIONS:-12}" \
  --bulk-sessions "${LOCAL_BULK_SESSIONS:-300}" \
  --evaluation-sessions-per-mode "${LOCAL_EVAL_SESSIONS_PER_MODE:-6}" \
  --experiment-prefix "$EXPERIMENT_PREFIX" \
  "$@")
