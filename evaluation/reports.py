from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from compare_modes import load_traces
from metrics import compare_dropoff_reduction, compute_metrics


def metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = ["# Evaluation Report", "", f"Sessions: {metrics.get('sessions', 0)}", ""]
    for key in sorted(k for k in metrics if k != "sessions"):
        lines.append(f"- {key}: {metrics[key]}")
    return "\n".join(lines) + "\n"


def comparison_markdown(*, baseline: dict[str, Any], treatment: dict[str, Any], delta: dict[str, Any]) -> str:
    lines = ["# Evaluation Comparison", "", "## Baseline", "", metrics_markdown(baseline), "## Treatment", "", metrics_markdown(treatment), "## Delta", ""]
    for key in sorted(delta):
        lines.append(f"- {key}: {delta[key]}")
    return "\n".join(lines) + "\n"


def write_report(*, baseline_path: Path, treatment_path: Path, output: Path) -> dict[str, Any]:
    baseline = compute_metrics(load_traces(baseline_path))
    treatment = compute_metrics(load_traces(treatment_path))
    delta = compare_dropoff_reduction(baseline, treatment)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(comparison_markdown(baseline=baseline, treatment=treatment, delta=delta))
    return {"output": str(output), "baseline_sessions": baseline["sessions"], "treatment_sessions": treatment["sessions"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a markdown evaluation report")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_report(baseline_path=args.baseline, treatment_path=args.treatment, output=args.output), indent=2))


if __name__ == "__main__":
    main()
