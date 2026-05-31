from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib import error, request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "browser-runner"))
sys.path.insert(0, str(ROOT / "evaluation"))

from report_bulk_runs import write_bulk_report
from run_batch import run_batch


@contextmanager
def _temporary_env(**updates: str) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_live_batch(*, execution_mode: str, runner_mode: str, experiment_id: str, output_dir: Path | None, sessions: int) -> dict[str, object]:
    with _temporary_env(RUNNER_EXECUTION_MODE=execution_mode):
        return run_batch(mode=runner_mode, experiment_id=experiment_id, sessions=sessions, output_dir=output_dir)


def _healthcheck(url: str, *, timeout_s: float = 5.0) -> bool:
    try:
        with request.urlopen(url, timeout=timeout_s) as response:
            return 200 <= getattr(response, "status", 500) < 300
    except (error.URLError, TimeoutError, OSError, ValueError):
        return False


def _total_failures(summary: dict[str, object]) -> int:
    failures = summary.get("failures", {})
    if not isinstance(failures, dict):
        return 0
    return sum(int(value) for value in failures.values())


def _assert_validation_gate(name: str, summary: dict[str, object], expected_sessions: int) -> None:
    traces = summary.get("traces", [])
    completed = len(traces) if isinstance(traces, list) else 0
    total_failures = _total_failures(summary)
    if summary.get("circuit_breaker") or total_failures or completed < expected_sessions:
        raise RuntimeError(
            json.dumps(
                {
                    "gate": name,
                    "expected_sessions": expected_sessions,
                    "completed_sessions": completed,
                    "failures": summary.get("failures", {}),
                    "failure_log": summary.get("failure_log", []),
                    "circuit_breaker": summary.get("circuit_breaker"),
                },
                indent=2,
                sort_keys=True,
            )
        )


def _ensure_live_prereqs() -> None:
    if not os.getenv("FEATHERLESS_API_KEY"):
        raise RuntimeError("FEATHERLESS_API_KEY must be set for live browser runs")


def _ensure_coach_prereqs() -> None:
    _ensure_live_prereqs()
    extension_dist = os.getenv("EXTENSION_DIST")
    if extension_dist and not Path(extension_dist).expanduser().exists():
        raise RuntimeError(f"EXTENSION_DIST does not exist: {extension_dist}")
    if not (ROOT / "extension" / "dist").exists() and not extension_dist:
        raise RuntimeError("Build the extension first with `npm run build:extension`, or set EXTENSION_DIST to an existing build")
    coach_api_url = os.getenv("COACH_API_URL", "http://127.0.0.1:8787").rstrip("/")
    if not _healthcheck(f"{coach_api_url}/healthz"):
        raise RuntimeError(f"Coach API health check failed at {coach_api_url}/healthz")


def cmd_validate_live(args: argparse.Namespace) -> dict[str, object]:
    return _run_live_batch(
        execution_mode=args.execution_mode,
        runner_mode="validation",
        experiment_id=args.experiment_id,
        output_dir=args.output_dir,
        sessions=args.sessions,
    )


def cmd_run_live(args: argparse.Namespace) -> dict[str, object]:
    return _run_live_batch(
        execution_mode=args.execution_mode,
        runner_mode="bulk",
        experiment_id=args.experiment_id,
        output_dir=args.output_dir,
        sessions=args.sessions,
    )


def cmd_local_full_loop(args: argparse.Namespace) -> dict[str, object]:
    _ensure_live_prereqs()
    artifacts_root = args.artifacts_root
    traces_root = args.output_dir or artifacts_root / "browser-runs" / args.experiment_prefix
    reports_root = args.report_output_dir or artifacts_root / "reports" / args.experiment_prefix

    baseline_validation = _run_live_batch(
        execution_mode="baseline",
        runner_mode="validation",
        experiment_id="baseline-validation",
        output_dir=traces_root,
        sessions=args.validate_sessions,
    )
    _assert_validation_gate("baseline_validation", baseline_validation, args.validate_sessions)

    _ensure_coach_prereqs()
    coach_validation = _run_live_batch(
        execution_mode="coach",
        runner_mode="validation",
        experiment_id="coach-validation",
        output_dir=traces_root,
        sessions=args.validate_sessions,
    )
    _assert_validation_gate("coach_validation", coach_validation, args.validate_sessions)

    baseline_bulk = _run_live_batch(
        execution_mode="baseline",
        runner_mode="bulk",
        experiment_id="baseline-bulk",
        output_dir=traces_root,
        sessions=args.bulk_sessions,
    )
    coach_bulk = _run_live_batch(
        execution_mode="coach",
        runner_mode="bulk",
        experiment_id="coach-bulk",
        output_dir=traces_root,
        sessions=args.bulk_sessions,
    )

    report = write_bulk_report(
        baseline_path=Path(str(baseline_bulk["trace_dir"])),
        coach_path=Path(str(coach_bulk["trace_dir"])),
        output_dir=reports_root,
    )

    return {
        "experiment_prefix": args.experiment_prefix,
        "paths": {
            "artifacts_root": str(artifacts_root),
            "reports_root": str(reports_root),
            "traces_root": str(traces_root),
        },
        "validation": {
            "baseline": baseline_validation,
            "coach": coach_validation,
        },
        "bulk": {
            "baseline": baseline_bulk,
            "coach": coach_bulk,
        },
        "report": report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI entrypoint for UNIQA live baseline/coach browser runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-live", help="Run a capped live validation batch")
    validate.add_argument("--execution-mode", choices=("baseline", "coach"), default="baseline")
    validate.add_argument("--sessions", type=int, default=12)
    validate.add_argument("--experiment-id", default="validate-live")
    validate.add_argument("--output-dir", type=Path)
    validate.set_defaults(func=cmd_validate_live)

    run_live = subparsers.add_parser("run-live", help="Run the bulk live generation batch")
    run_live.add_argument("--execution-mode", choices=("baseline", "coach"), default="coach")
    run_live.add_argument("--sessions", type=int, default=300)
    run_live.add_argument("--experiment-id", default="run-live")
    run_live.add_argument("--output-dir", type=Path)
    run_live.set_defaults(func=cmd_run_live)

    local_loop = subparsers.add_parser("local-full-loop", help="Run baseline validation, coach validation, both bulk runs, and bulk reporting")
    local_loop.add_argument("--validate-sessions", type=int, default=12)
    local_loop.add_argument("--bulk-sessions", type=int, default=300)
    local_loop.add_argument("--experiment-prefix", default="local-full-loop")
    local_loop.add_argument("--artifacts-root", type=Path, default=Path("artifacts"))
    local_loop.add_argument("--output-dir", type=Path)
    local_loop.add_argument("--report-output-dir", type=Path)
    local_loop.set_defaults(func=cmd_local_full_loop)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
