from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate_ranker(dataset: Path, model_path: Path) -> dict:
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    model = json.loads(model_path.read_text())["ranking_by_step"]
    correct = 0
    for row in rows:
        ranking = model.get(row["current_step_id"], [])
        top = ranking[0][0] if ranking else None
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
