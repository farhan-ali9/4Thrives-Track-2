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
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
fi
: "${ACTION_RANKING_DATASET:=artifacts/datasets/action-ranking.jsonl}"
python training/quality_checks.py "$ACTION_RANKING_DATASET" --fail-on-error
python training/train_ranker.py --dataset "$ACTION_RANKING_DATASET" --output artifacts/training/frequency-ranker.json
python training/evaluate_ranker.py --dataset "$ACTION_RANKING_DATASET" --model artifacts/training/frequency-ranker.json
