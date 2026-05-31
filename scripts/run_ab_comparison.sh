#!/usr/bin/env bash
# Run a baseline-vs-coach A/B comparison and emit a comparison report.
#
# Usage:
#   bash scripts/run_ab_comparison.sh [SESSIONS_PER_GROUP] [EXPERIMENT_PREFIX]
#
# Env overrides (all optional):
#   RUNNER_HEADLESS=1          run Chrome headless (default: 0 = visible)
#   COACH_API_URL              override coach API URL
#   FEATHERLESS_API_KEY        required for LLM persona decisions
#
# Output:
#   artifacts/browser-runs/<experiment>/  — raw session traces
#   artifacts/ab-reports/<experiment>/    — comparison report (JSON + Markdown)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/local_pipeline_env.sh"

SESSIONS="${1:-12}"
EXPERIMENT="${2:-ab-$(date +%Y%m%d-%H%M%S)}"
TRACES_DIR="$ROOT/artifacts/browser-runs/$EXPERIMENT"
REPORT_DIR="$ROOT/artifacts/ab-reports/$EXPERIMENT"
BASELINE_OUT="$TRACES_DIR/baseline"
COACH_OUT="$TRACES_DIR/coach"

load_local_pipeline_env
require_featherless_key

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  UNIQA Conversion Coach — A/B Comparison Experiment  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Experiment : $EXPERIMENT"
echo "║  Sessions   : $SESSIONS per group"
echo "║  Traces dir : $TRACES_DIR"
echo "║  Report dir : $REPORT_DIR"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Baseline (no coach) ──────────────────────────────────────────────
echo "▶ [1/3] Running BASELINE group ($SESSIONS sessions, no coach)..."
(cd "$ROOT" && RUNNER_OUTPUT_DIR="$BASELINE_OUT" python3 uniqa_pipeline.py validate-live \
  --execution-mode baseline \
  --sessions "$SESSIONS" \
  --experiment-id "$EXPERIMENT-baseline" \
  --output-dir "$BASELINE_OUT")
echo "✓ Baseline done."
echo ""

# ── Step 2: Coach (with extension) ───────────────────────────────────────────
echo "▶ [2/3] Running COACH group ($SESSIONS sessions, extension active)..."
ensure_extension_build
require_coach_api
(cd "$ROOT" && RUNNER_OUTPUT_DIR="$COACH_OUT" python3 uniqa_pipeline.py validate-live \
  --execution-mode coach \
  --sessions "$SESSIONS" \
  --experiment-id "$EXPERIMENT-coach" \
  --output-dir "$COACH_OUT")
echo "✓ Coach done."
echo ""

# ── Step 3: Compare ───────────────────────────────────────────────────────────
echo "▶ [3/3] Generating comparison report..."
mkdir -p "$REPORT_DIR"
python3 "$ROOT/evaluation/generate_ab_report.py" \
  --baseline "$BASELINE_OUT" \
  --treatment "$COACH_OUT" \
  --output-dir "$REPORT_DIR" \
  --experiment "$EXPERIMENT"
echo "✓ Report written to $REPORT_DIR"
echo ""

echo "══════════════════════════════════════════════════════"
echo "  Done. Open the report:"
echo "    cat $REPORT_DIR/comparison.md"
echo "    cat $REPORT_DIR/comparison.json"
echo "══════════════════════════════════════════════════════"
