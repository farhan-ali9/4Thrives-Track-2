# Leonardo Full Loop Commands

This is the shortest reliable path for a fresh Leonardo run using the local `vLLM` path for coach sessions.

## 1. Prepare Locally

Build the extension on your laptop:

```bash
cd /Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2
npm --prefix extension ci
npm --prefix extension run build:extension
```

Sync the repo to Leonardo from your laptop:

```bash
cd /Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2
rsync -av --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'artifacts' \
  ./ a08trc05@login01-ext.leonardo.cineca.it:~/4Thrives-Track-2/
```

## 2. Set Up Leonardo

SSH to Leonardo:

```bash
ssh a08trc05@login01-ext.leonardo.cineca.it
cd ~/4Thrives-Track-2
```

Install Pixi once if it is not already present:

```bash
curl -fsSL https://pixi.sh/install.sh | bash
export PATH="$HOME/.pixi/bin:$PATH"
```

Install the runner envs:

```bash
~/.pixi/bin/pixi install --manifest-path leonardo/pixi.toml
~/.pixi/bin/pixi install --manifest-path leonardo-vllm/pixi.toml
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml python -m playwright install chromium
```

Create the Leonardo env file:

```bash
cp leonardo/env.example leonardo/.env
```

Edit `leonardo/.env` and set at minimum:

```bash
EXTENSION_DIST=/leonardo/home/usertrain/a08trc05/4Thrives-Track-2/extension/dist
COACH_API_URL=http://127.0.0.1:8787
RUNNER_OUTPUT_DIR=artifacts/browser-runs
PIXI_BIN=$HOME/.pixi/bin/pixi
RUNNER_MANIFEST=leonardo/pixi.toml
VLLM_MANIFEST=leonardo-vllm/pixi.toml
LLM_API_URL=http://127.0.0.1:8000/v1/chat/completions
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
RUNNER_SESSIONS=12
RUNNER_SESSIONS_PER_MODE=6
EVALUATION_MODES=baseline,rule_based,trainable
```

Start from a clean run directory:

```bash
cd ~/4Thrives-Track-2
rm -rf artifacts/browser-runs artifacts/datasets artifacts/training artifacts/evaluation-experiments/latest
mkdir -p artifacts/logs
```

## 3. Validate First

Baseline validation:

```bash
cd ~/4Thrives-Track-2
RUNNER_EXECUTION_MODE=baseline \
EXPERIMENT_ID=baseline-validate \
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_validate_live.sh
```

Coach validation with local `vLLM`:

```bash
cd ~/4Thrives-Track-2
RUNNER_EXECUTION_MODE=coach \
EXPERIMENT_ID=coach-validate-vllm \
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_validate_live_vllm.sh
```

Check status and logs:

```bash
squeue --me
tail -f artifacts/logs/validate-live-<job_id>.out
tail -f artifacts/logs/validate-live-<job_id>.err
tail -f artifacts/logs/validate-vllm-<job_id>.out
tail -f artifacts/logs/validate-vllm-<job_id>.err
tail -f artifacts/logs/vllm-<job_id>.out
```

The validation gate is simple:

- baseline validation should complete without selector/page circuit breaking
- coach validation should produce traces with `run_mode=coach` and non-empty `llm_decisions`

## 4. Run The Real Bulk Generation

For the baseline bulk set:

```bash
cd ~/4Thrives-Track-2
RUNNER_EXECUTION_MODE=baseline \
RUNNER_SESSIONS=300 \
EXPERIMENT_ID=baseline-bulk \
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_bulk_live.sh
```

For the coached bulk set with local `vLLM`:

```bash
cd ~/4Thrives-Track-2
RUNNER_EXECUTION_MODE=coach \
RUNNER_SESSIONS=300 \
EXPERIMENT_ID=coach-bulk-vllm \
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_bulk_live_vllm.sh
```

## 5. Build Datasets

After both bulk jobs finish:

```bash
cd ~/4Thrives-Track-2
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_build_datasets.sh
```

Optional direct check:

```bash
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline build-datasets --traces artifacts/browser-runs
wc -l artifacts/datasets/user-policy.jsonl
wc -l artifacts/datasets/coach-ranking.jsonl
```

## 6. Train

```bash
cd ~/4Thrives-Track-2
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_train.sh
```

Expected outputs:

```bash
ls -lh artifacts/training/user-policy.json
ls -lh artifacts/training/frequency-ranker.json
```

## 7. Evaluate

```bash
cd ~/4Thrives-Track-2
RUNNER_MODE=validation \
RUNNER_SESSIONS_PER_MODE=6 \
EXPERIMENT_ID=eval-validation \
sbatch --export=ALL,LEONARDO_ENV_FILE=$PWD/leonardo/.env leonardo/slurm_evaluation_experiment.sh
```

Inspect the report:

```bash
ls artifacts/evaluation-experiments/latest
find artifacts/evaluation-experiments/latest -maxdepth 2 -type f | sort
```

## 8. One-Line CLI Submit Variants

If you prefer the checked-in CLI wrapper:

```bash
cd ~/4Thrives-Track-2
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job validate --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job validate-vllm --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job bulk --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job bulk-vllm --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job build-datasets --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job train --env-file leonardo/.env
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline leonardo-submit --job evaluate --env-file leonardo/.env
```

## 9. Failure Checks

Use these when a job exits early:

```bash
sacct -j <job_id> --format=JobID,State,Elapsed,ExitCode
tail -n 100 artifacts/logs/*<job_id>*
```

For a manual smoke run without Slurm:

```bash
cd ~/4Thrives-Track-2
set -a
source leonardo/.env
set +a
~/.pixi/bin/pixi run --manifest-path leonardo/pixi.toml ./uniqa-pipeline validate-live --execution-mode baseline --sessions 1 --experiment-id manual-smoke
```
