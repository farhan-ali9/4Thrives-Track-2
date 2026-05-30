from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "session_id",
    "decision_id",
    "trace_prefix",
    "current_step_id",
    "persona_id",
    "intention",
    "seed",
    "run_mode",
    "llm_model",
    "candidate_actions",
    "chosen_action",
    "future_outcome_summary",
    "runner_metadata",
    "dataset_phase",
}


def check_user_policy_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    by_persona = Counter()
    by_intention = Counter()
    by_run_mode = Counter()
    for index, row in enumerate(rows):
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            errors.append(f"row[{index}] missing fields: {', '.join(missing)}")
        if row.get("chosen_action") not in row.get("candidate_actions", []):
            errors.append(f"row[{index}] chosen_action not in candidate_actions")
        by_persona[row.get("persona_id", "unknown")] += 1
        by_intention[row.get("intention", "unknown")] += 1
        by_run_mode[row.get("run_mode", "unknown")] += 1
    return {
        "rows": len(rows),
        "valid": not errors,
        "errors": errors,
        "by_persona": dict(by_persona),
        "by_intention": dict(by_intention),
        "by_run_mode": dict(by_run_mode),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the live user-policy dataset")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    summary = check_user_policy_rows(rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.fail_on_error and not summary["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
