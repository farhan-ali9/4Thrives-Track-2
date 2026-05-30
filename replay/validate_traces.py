from __future__ import annotations

import argparse
import json
from pathlib import Path

from trace_store import load_traces, summarize_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate local or backend-exported session traces")
    parser.add_argument("traces", type=Path)
    parser.add_argument("--fail-on-invalid", action="store_true")
    args = parser.parse_args()
    summary = summarize_validation(load_traces(args.traces))
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.fail_on_invalid and summary["invalid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
