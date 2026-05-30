# Leonardo Execution Plan

Andrii-owned batch jobs use the same Python entry points as local validation.
Run live browser jobs only after the extension is built and the coach backend is reachable from the job environment.

## Environment

Copy `leonardo/env.example` and set site/backend/extension paths before submitting jobs.

Required variables:

- `EXTENSION_DIST`: absolute path to the built Chrome extension directory.
- `COACH_API_URL`: coach backend origin, for example `http://127.0.0.1:8787`.
- `UNIQA_CALCULATOR_URL`: live calculator URL, defaults to the public UNIQA page.
- `RUNNER_OUTPUT_DIR`: directory for JSON traces, screenshots, and reports.
- `PAGE_MAP_VERSION`, `EXTENSION_BUILD_ID`, `MODEL_VERSION_OR_POLICY`: metadata stamped onto every trace.

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

## Job Order

1. Run `scripts/slurm_browser_batch.sh` in validation mode for a few sessions.
2. Inspect traces with `scripts/slurm_replay.sh` or `python replay/replay_session.py <trace>`.
3. Run `scripts/slurm_evaluation_experiment.sh` for baseline versus rule-based folders and report.
4. Build the dataset with `training/build_dataset.py` after real decision-point traces exist.
5. Train with `scripts/slurm_train.sh` only after the dataset is non-empty and passes `training/quality_checks.py`.

Synthetic or mock traces are acceptable for unit tests and smoke checks only. They are not the primary evidence for demo metrics or model quality.
