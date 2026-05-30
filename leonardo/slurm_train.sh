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
python training/train_ranker.py --dataset artifacts/datasets/action-ranking.jsonl --output artifacts/training/frequency-ranker.json
python training/evaluate_ranker.py --dataset artifacts/datasets/action-ranking.jsonl --model artifacts/training/frequency-ranker.json
