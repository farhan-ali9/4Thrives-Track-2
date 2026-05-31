#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

SESSIONS="${SUBMISSION_SESSIONS:-12}"
PREFIX="${EXPERIMENT_PREFIX:-submission-mini-$(date +%Y%m%d-%H%M%S)}"
OUT="$ROOT/artifacts/browser-runs/$PREFIX"
REPORT_OUT="$ROOT/submissions/4Thrives/extras/results"

load_local_pipeline_env
require_llm_provider
ensure_extension_build
require_coach_api

mkdir -p "$OUT"

echo "Running baseline bulk ($SESSIONS sessions)..."
(cd "$ROOT" && ./uniqa-pipeline run-live \
  --execution-mode baseline \
  --sessions "$SESSIONS" \
  --experiment-id baseline-bulk \
  --output-dir "$OUT")

echo "Running coach bulk ($SESSIONS sessions)..."
(cd "$ROOT" && ./uniqa-pipeline run-live \
  --execution-mode coach \
  --sessions "$SESSIONS" \
  --experiment-id coach-bulk \
  --output-dir "$OUT")

echo "Building report..."
python3 "$ROOT/evaluation/report_bulk_runs.py" \
  --baseline "$OUT/baseline-bulk" \
  --coach "$OUT/coach-bulk" \
  --output-dir "$ROOT/artifacts/reports/$PREFIX"

mkdir -p "$REPORT_OUT"
cp -r "$ROOT/artifacts/reports/$PREFIX/"* "$REPORT_OUT/"

echo "Done. Experiment prefix: $PREFIX"
echo "Submission results: $REPORT_OUT"
echo "Update submissions/4Thrives/REPORT.md Results section from $REPORT_OUT/summary.md"
