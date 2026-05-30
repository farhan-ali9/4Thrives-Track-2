from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_ranker import load_ranker, predict_action


def evaluate_ranker(dataset: Path, model_path: Path) -> dict:
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    model = load_ranker(model_path)
    correct = 0
    for row in rows:
        top = predict_action(model, step_id=row["current_step_id"], candidates=row.get("candidate_set"))
        correct += int(top == row["chosen_candidate"])
    return {"examples": len(rows), "top1_accuracy": correct / len(rows) if rows else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the frequency action ranker")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_ranker(args.dataset, args.model), indent=2))


if __name__ == "__main__":
    main()
