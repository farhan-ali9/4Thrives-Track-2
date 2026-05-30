from __future__ import annotations

import argparse
import json
from pathlib import Path

from metrics import compare_dropoff_reduction, compute_metrics


def load_traces(path: Path) -> list[dict]:
    if path.is_dir():
        return [json.loads(item.read_text()) for item in sorted(path.glob("*.json"))]
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else [data]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and coached trace directories")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    args = parser.parse_args()
    baseline = compute_metrics(load_traces(args.baseline))
    treatment = compute_metrics(load_traces(args.treatment))
    print(json.dumps({"baseline": baseline, "treatment": treatment, "delta": compare_dropoff_reduction(baseline, treatment)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
