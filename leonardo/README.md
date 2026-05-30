# Leonardo Execution Plan

Leonardo jobs go through the checked-in `./uniqa-pipeline` CLI, wrapped by Pixi inside the Slurm scripts so the cluster does not depend on the system Python.

## Start Here

- Read [FULL_LOOP_COMMANDS.md](/Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2/leonardo/FULL_LOOP_COMMANDS.md) for the copy-paste command sequence.
- Copy `leonardo/env.example` to `leonardo/.env` and set the paths for your checkout.
- Build the extension locally before syncing to Leonardo; the live coach flow depends on `extension/dist`.

## Environment

Important variables:

- `EXTENSION_DIST`: absolute path to the built Chrome extension directory on Leonardo.
- `COACH_API_URL`: coach backend origin, for example `http://127.0.0.1:8787`.
- `RUNNER_OUTPUT_DIR`: directory for JSON traces, screenshots, and reports.
- `LLM_API_URL`, `LLM_MODEL`: OpenAI-compatible persona endpoint details.
- `PIXI_BIN`, `RUNNER_MANIFEST`, `VLLM_MANIFEST`: explicit runtime locations used by the Slurm wrappers.
- `VLLM_SERVE_CMD`: optional override if you want a custom `vLLM` launch command.

## Key Scripts

- `leonardo/slurm_validate_live.sh`: serial validation, good for baseline or coach with a remote LLM endpoint.
- `leonardo/slurm_validate_live_vllm.sh`: GPU validation with local `vLLM`.
- `leonardo/slurm_bulk_live.sh`: serial bulk run, only appropriate when the LLM endpoint is external.
- `leonardo/slurm_bulk_live_vllm.sh`: GPU bulk run with local `vLLM`.
- `leonardo/slurm_build_datasets.sh`: builds `user-policy.jsonl` and `coach-ranking.jsonl`.
- `leonardo/slurm_train.sh`: trains the user-policy model and coach ranker.
- `leonardo/slurm_evaluation_experiment.sh`: evaluation experiment over baseline, rule-based, and trainable modes.

## Output Layout

```text
artifacts/
  browser-runs/<session_id>.json
  datasets/user-policy.jsonl
  datasets/coach-ranking.jsonl
  training/user-policy.json
  training/frequency-ranker.json
  evaluation-experiments/latest/
```

## Notes

- Chrome extension live mode requires a persistent Chromium context.
- `s8_confirm` remains an observation boundary; purchase submission is not part of the loop.
- Synthetic or mock traces are fine for smoke tests, not for the real training set.
