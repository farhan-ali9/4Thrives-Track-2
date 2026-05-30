#!/usr/bin/env bash
#SBATCH --job-name=uniqa-build-datasets
#SBATCH --output=artifacts/logs/build-datasets-%j.out
#SBATCH --error=artifacts/logs/build-datasets-%j.err
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G

set -euo pipefail
mkdir -p artifacts/logs artifacts/datasets
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
  set +a
fi

: "${PIXI_BIN:=$HOME/.pixi/bin/pixi}"
: "${RUNNER_MANIFEST:=leonardo/pixi.toml}"

"$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline build-datasets \
  --traces "${RUNNER_OUTPUT_DIR:-artifacts/browser-runs}" \
  --user-output "${USER_POLICY_DATASET:-artifacts/datasets/user-policy.jsonl}" \
  --coach-output "${ACTION_RANKING_DATASET:-artifacts/datasets/coach-ranking.jsonl}"
