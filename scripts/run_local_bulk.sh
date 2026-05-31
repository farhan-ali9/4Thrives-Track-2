#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

MODE="${1:-coach}"
SESSIONS="${2:-300}"
EXPERIMENT_ID="${3:-local-bulk-${MODE}-$(date +%Y%m%d-%H%M%S)}"

load_local_pipeline_env
require_llm_provider

if [[ "$MODE" == "coach" ]]; then
  ensure_extension_build
  require_coach_api
fi

(cd "$ROOT" && ./uniqa-pipeline run-live --execution-mode "$MODE" --sessions "$SESSIONS" --experiment-id "$EXPERIMENT_ID")
