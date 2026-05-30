from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_DATASET_FIELDS = {
    "session_id",
    "decision_id",
    "trace_prefix",
    "current_step_id",
    "page_map_version",
    "extension_version",
    "model_version_or_baseline",
    "candidate_set",
    "guardrail_filtered_candidates",
    "chosen_candidate",
    "exposure_result",
    "future_outcome_summary",
    "runner_metadata",
    "dataset_phase",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = []
    phases = Counter()
    outcomes = Counter()
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_DATASET_FIELDS - set(row))
        if missing:
            errors.append(f"row[{index}] missing fields: {', '.join(missing)}")
        if row.get("chosen_candidate") not in row.get("candidate_set", []):
            errors.append(f"row[{index}] chosen_candidate not in candidate_set")
        if not row.get("guardrail_filtered_candidates"):
            errors.append(f"row[{index}] empty guardrail_filtered_candidates")
        if row.get("trace_prefix") and row["trace_prefix"][-1].get("event_id") == row.get("decision_id"):
            errors.append(f"row[{index}] trace_prefix includes current decision event")
        phases[row.get("dataset_phase", "unknown")] += 1
        outcomes[row.get("future_outcome_summary", "unknown")] += 1
    return {"rows": len(rows), "valid": not errors, "errors": errors, "phases": dict(phases), "outcomes": dict(outcomes)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check action-ranking dataset quality")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()
    summary = check_dataset(load_jsonl(args.dataset))
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.fail_on_error and not summary["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
