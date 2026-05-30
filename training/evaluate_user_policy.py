from __future__ import annotations

import argparse
import json
from pathlib import Path

from user_policy import load_user_policy_model, predict_user_action


def evaluate_user_policy(dataset: Path, model_path: Path) -> dict[str, float | int]:
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    model = load_user_policy_model(model_path)
    correct = 0
    for row in rows:
        predicted = predict_user_action(model, row)
        correct += int(predicted == row["chosen_action"])
    return {"examples": len(rows), "top1_accuracy": correct / len(rows) if rows else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the frequency-based user policy model")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_user_policy(args.dataset, args.model), indent=2))


if __name__ == "__main__":
    main()
