#!/usr/bin/env bash
#SBATCH --job-name=uniqa-ranker-train
#SBATCH --output=artifacts/logs/train-%j.out
#SBATCH --error=artifacts/logs/train-%j.err
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G

set -euo pipefail
mkdir -p artifacts/logs artifacts/training
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
  set +a
fi

: "${PIXI_BIN:=$HOME/.pixi/bin/pixi}"
: "${RUNNER_MANIFEST:=leonardo/pixi.toml}"

"$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline train-user-policy \
  --dataset "${USER_POLICY_DATASET:-artifacts/datasets/user-policy.jsonl}" \
  --output "${USER_POLICY_MODEL:-artifacts/training/user-policy.json}"
"$PIXI_BIN" run --manifest-path "$RUNNER_MANIFEST" ./uniqa-pipeline train-coach-ranker \
  --dataset "${ACTION_RANKING_DATASET:-artifacts/datasets/coach-ranking.jsonl}" \
  --output "${TRAINABLE_RANKER_MODEL:-artifacts/training/frequency-ranker.json}"
