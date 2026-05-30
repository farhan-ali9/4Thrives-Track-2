from __future__ import annotations

import argparse
import json
from pathlib import Path

from user_policy import save_user_policy_model, train_frequency_user_policy


def train_user_policy(dataset: Path, output: Path) -> dict[str, object]:
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    model = train_frequency_user_policy(rows)
    save_user_policy_model(model, output)
    return {"examples": len(rows), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a simple frequency-based user policy model from live persona decisions")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/training/user-policy.json"))
    args = parser.parse_args()
    print(json.dumps(train_user_policy(args.dataset, args.output), indent=2))


if __name__ == "__main__":
    main()
