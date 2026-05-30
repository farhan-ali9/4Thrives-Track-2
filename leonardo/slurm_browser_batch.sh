#!/usr/bin/env bash
#SBATCH --job-name=uniqa-browser-batch
#SBATCH --output=artifacts/logs/browser-batch-%j.out
#SBATCH --error=artifacts/logs/browser-batch-%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

set -euo pipefail
mkdir -p artifacts/logs
: "${RUNNER_OUTPUT_DIR:=artifacts/browser-runs}"
: "${RUNNER_MODE:=validation}"
: "${RUNNER_SESSIONS:=3}"
python browser-runner/run_batch.py --mode "$RUNNER_MODE" --sessions "$RUNNER_SESSIONS" --experiment-id "leonardo-${SLURM_JOB_ID}"
