# Legacy Training Path

Optional frequency-ranker training on stored traces. Not used for the hackathon submission eval.

```bash
python training/build_dataset.py --traces artifacts/browser-runs --output artifacts/datasets/action-ranking.jsonl
python training/train_ranker.py --dataset artifacts/datasets/action-ranking.jsonl --output artifacts/training/frequency-ranker.json
```

See [`docs/evaluation/README.md`](../evaluation/README.md) for the older trainable-coach experiment layout.
