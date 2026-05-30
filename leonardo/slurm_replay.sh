#!/usr/bin/env bash
#SBATCH --job-name=uniqa-replay
#SBATCH --output=artifacts/logs/replay-%j.out
#SBATCH --error=artifacts/logs/replay-%j.err
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G

set -euo pipefail
mkdir -p artifacts/logs artifacts/datasets
./uniqa-pipeline build-datasets \
  --traces "${RUNNER_OUTPUT_DIR:-artifacts/browser-runs}" \
  --user-output "${USER_POLICY_DATASET:-artifacts/datasets/user-policy.jsonl}" \
  --coach-output "${ACTION_RANKING_DATASET:-artifacts/datasets/coach-ranking.jsonl}"
