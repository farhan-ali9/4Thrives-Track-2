# Leonardo Execution Plan

Leonardo jobs now go through the same `./uniqa-pipeline` CLI as local runs.
Run live browser jobs only after the extension is built and the coach backend is reachable from the job environment.

## Environment

Copy `leonardo/env.example` and set site/backend/extension paths before submitting jobs.

Required variables:

- `EXTENSION_DIST`: absolute path to the built Chrome extension directory.
- `COACH_API_URL`: coach backend origin, for example `http://127.0.0.1:8787`.
- `UNIQA_CALCULATOR_URL`: live calculator URL, defaults to the public UNIQA page.
- `RUNNER_OUTPUT_DIR`: directory for JSON traces, screenshots, and reports.
- `RUNNER_EXECUTION_MODE`: `baseline` or `coach`.
- `PAGE_MAP_VERSION`, `EXTENSION_BUILD_ID`, `MODEL_VERSION_OR_POLICY`: metadata stamped onto every trace.
- `LLM_API_URL`, `LLM_MODEL`: OpenAI-compatible persona endpoint details.
- `VLLM_SERVE_CMD`: optional command that starts `vLLM` inside the same Slurm job before the runner starts.

## Output Layout

```text
artifacts/
  browser-runs/<session_id>.json
  datasets/action-ranking.jsonl
  training/frequency-ranker.json
  evaluation-experiments/latest/
    baseline/*.json
    rule_based/*.json
    experiment_manifest.json
    baseline_vs_rule_based.md
```

## Apptainer/Singularity

Build the container on a system with Apptainer or Singularity:

```bash
apptainer build artifacts/containers/uniqa-runner.sif leonardo/apptainer.def
```

Run a smoke command inside it:

```bash
apptainer exec --bind "$PWD:$PWD" artifacts/containers/uniqa-runner.sif \
  python browser-runner/run_batch.py --mode mock --sessions 1
```

Chrome extension live mode requires a non-headless persistent Chromium context. On shared clusters, use an allocated node with browser sandbox support or an approved virtual display setup.

## CLI

Common entrypoints:

- `./uniqa-pipeline validate-live --execution-mode baseline`
- `./uniqa-pipeline validate-live --execution-mode coach`
- `./uniqa-pipeline run-live --execution-mode coach --sessions 300`
- `./uniqa-pipeline build-datasets --traces artifacts/browser-runs`
- `./uniqa-pipeline train-user-policy`
- `./uniqa-pipeline train-coach-ranker`
- `./uniqa-pipeline evaluate --runner-mode validation`

## Job Order

1. Run `leonardo/slurm_validate_live.sh` in `baseline` and `coach` mode for a few sessions.
2. Inspect traces with `scripts/slurm_replay.sh` or `python replay/replay_session.py <trace>`.
3. Run `scripts/slurm_evaluation_experiment.sh` for baseline versus rule-based folders and report.
4. Build both datasets with `./uniqa-pipeline build-datasets` after real traces exist.
5. Train with `scripts/slurm_train.sh` only after `user-policy.jsonl` and `coach-ranking.jsonl` pass their checks.

Synthetic or mock traces are acceptable for unit tests and smoke checks only. They are not the primary evidence for demo metrics or model quality.
