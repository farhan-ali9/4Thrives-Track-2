# Training Pipeline

Training starts only after trace files contain real decision points from the extension/backend loop.

Fetch a stored backend session trace from Farhan's v2 API:

```bash
python replay/fetch_session.py \
  --backend-url http://127.0.0.1:8787 \
  --session-id sess_123 \
  --output artifacts/backend-traces/sess_123.json \
  --fail-on-invalid
```

`training/build_dataset.py` accepts both local runner traces and Farhan v2 session exports shaped as `{ session_id, events, decisions, exposures, outcome }`.

The first workflow builds behavioral-imitation examples and trains a simple frequency ranker as a sanity check before richer outcome-aware ranking.

```bash
python training/build_dataset.py --traces artifacts/browser-runs --output artifacts/datasets/action-ranking.jsonl
python training/quality_checks.py artifacts/datasets/action-ranking.jsonl --fail-on-error
python training/train_ranker.py --dataset artifacts/datasets/action-ranking.jsonl --output artifacts/training/frequency-ranker.json
python training/evaluate_ranker.py --dataset artifacts/datasets/action-ranking.jsonl --model artifacts/training/frequency-ranker.json
TRAINABLE_RANKER_MODEL=artifacts/training/frequency-ranker.json bash scripts/run_evaluation_experiment.sh
```

`training/action_ranker.py` is the shared prediction helper used by offline ranker evaluation and by browser-runner trainable mode. Unknown steps produce no intervention rather than falling back to a rule-based action.

Dataset rows include:

- `session_id`
- `decision_id`
- `trace_prefix`
- `current_step_id`
- `page_map_version`
- `extension_version`
- `model_version_or_baseline`
- `candidate_set`
- `guardrail_filtered_candidates`
- `chosen_candidate`
- `exposure_result`
- `future_outcome_summary`
- `runner_metadata`
- `dataset_phase`

Mock traces are acceptable for unit tests only. Demo metrics and model-quality claims require real traces from the extension/backend loop.
