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
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  # shellcheck disable=SC1090
  source "$LEONARDO_ENV_FILE"
fi
python replay/validate_traces.py "${RUNNER_OUTPUT_DIR:-artifacts/browser-runs}" --fail-on-invalid
./uniqa-pipeline build-datasets \
  --traces "${RUNNER_OUTPUT_DIR:-artifacts/browser-runs}" \
  --user-output "${USER_POLICY_DATASET:-artifacts/datasets/user-policy.jsonl}" \
  --coach-output "${ACTION_RANKING_DATASET:-artifacts/datasets/coach-ranking.jsonl}"
python training/check_user_policy_dataset.py "${USER_POLICY_DATASET:-artifacts/datasets/user-policy.jsonl}" --fail-on-error
python training/quality_checks.py "${ACTION_RANKING_DATASET:-artifacts/datasets/coach-ranking.jsonl}" --fail-on-error
