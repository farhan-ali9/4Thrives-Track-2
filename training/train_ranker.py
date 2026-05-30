from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_ranker import DEFAULT_CANDIDATES


def train_frequency_ranker(dataset: Path, output: Path) -> dict:
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("No training examples found. Generate real traces and run build_dataset.py first.")
    counts = defaultdict(Counter)
    for row in rows:
        counts[row["current_step_id"]][row["chosen_candidate"]] += 1
    model = {step: counter.most_common() for step, counter in counts.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"model_type": "frequency_action_ranker", "candidate_set": DEFAULT_CANDIDATES, "ranking_by_step": model}, indent=2, sort_keys=True))
    return {"examples": len(rows), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the first simple action ranker after real decision traces exist")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/training/frequency-ranker.json"))
    args = parser.parse_args()
    print(json.dumps(train_frequency_ranker(args.dataset, args.output), indent=2))


if __name__ == "__main__":
    main()
