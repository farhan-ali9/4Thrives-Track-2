#!/usr/bin/env python3
"""Patch mislabeled s8_confirm outcomes in stored browser-runner traces."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "browser-runner" / "persona_policy.py"


def _load_policy():
    spec = importlib.util.spec_from_file_location("persona_policy", POLICY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules["persona_policy"] = module
    spec.loader.exec_module(module)
    return module


def patch_trace(path: Path, policy) -> str | None:
    trace = json.loads(path.read_text())
    events = trace.get("events", [])
    artifacts = trace.get("artifacts", [])
    corrected = policy.s8_boundary_outcome(events, artifacts=artifacts)
    if corrected is None or trace.get("terminal_outcome") == corrected:
        return None
    trace["terminal_outcome"] = corrected
    if events:
        events[-1]["terminal_outcome"] = corrected
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return corrected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_dirs", nargs="+", type=Path, help="Directories containing sess_*.json traces")
    args = parser.parse_args()
    policy = _load_policy()
    patched = 0
    for trace_dir in args.trace_dirs:
        for path in sorted(trace_dir.glob("sess_*.json")):
            outcome = patch_trace(path, policy)
            if outcome:
                patched += 1
                print(f"patched {path.name} -> {outcome}")
    print(f"patched {patched} trace(s)")


if __name__ == "__main__":
    main()
