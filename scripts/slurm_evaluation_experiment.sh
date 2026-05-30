#!/usr/bin/env bash
#SBATCH --job-name=uniqa-eval-experiment
#SBATCH --output=artifacts/logs/eval-experiment-%j.out
#SBATCH --error=artifacts/logs/eval-experiment-%j.err
#SBATCH --time=00:45:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

set -euo pipefail
mkdir -p artifacts/logs
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$LEONARDO_ENV_FILE"
  set +a
fi
python evaluation/run_experiment.py \
  --runner-mode "${RUNNER_MODE:-validation}" \
  --sessions-per-mode "${RUNNER_SESSIONS_PER_MODE:-6}" \
  --experiment-id "${EXPERIMENT_ID:-leonardo-${SLURM_JOB_ID:-local}}" \
  --output-root "${EVALUATION_OUTPUT_ROOT:-artifacts/evaluation-experiments/latest}" \
  --evaluation-modes "${EVALUATION_MODES:-baseline,rule_based,trainable}" \
  --trainable-model "${TRAINABLE_RANKER_MODEL:-artifacts/training/frequency-ranker.json}"
