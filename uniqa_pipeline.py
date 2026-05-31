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
FEATHERLESS_CHAT_COMPLETIONS_URL = "https://api.featherless.ai/v1/chat/completions"
DEFAULT_FEATHERLESS_MODEL = "Qwen/Qwen2.5-7B-Instruct"
PERSONA_MATRIX = (
    ("franz", "purchase"),
    ("franz", "research"),
    ("franz", "price_sensitive"),
    ("franz", "advisor_route"),
    ("judith", "purchase"),
    ("judith", "research"),
    ("judith", "price_sensitive"),
    ("judith", "advisor_route"),
    ("peter", "purchase"),
    ("peter", "research"),
    ("peter", "price_sensitive"),
    ("peter", "advisor_route"),
)

sys.path.insert(0, str(ROOT / "browser-runner"))
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT / "replay"))

from report_bulk_runs import write_bulk_report
from run_batch import run_batch


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_env_file(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        _apply_local_llm_defaults()
        return {}
    loaded: dict[str, str] = {}
    for line in path.read_text().splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        loaded[key] = value
        os.environ.setdefault(key, value)
    _apply_local_llm_defaults()
    return loaded


def _apply_local_llm_defaults() -> None:
    os.environ.setdefault("LLM_API_URL", os.getenv("LLM_GATEWAY_URL", FEATHERLESS_CHAT_COMPLETIONS_URL))
    os.environ.setdefault(
        "LLM_MODEL",
        os.getenv("LLM_DEFAULT_MODEL", os.getenv("VITE_FEATHERLESS_MODEL", DEFAULT_FEATHERLESS_MODEL)),
    )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _session_count(*, explicit_sessions: int | None, persona_runs: int) -> int:
    if explicit_sessions is not None:
        return explicit_sessions
    return len(PERSONA_MATRIX) * persona_runs


def _comparison_markdown(*, baseline: dict[str, object], coach: dict[str, object], delta: dict[str, object]) -> str:
    lines = [
        "# Local Training Pipeline Overview",
        "",
        "| Metric | Baseline | Coach | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    metric_pairs = [
        ("sessions", "Sessions"),
        ("abandonment_rate", "Drop-off rate"),
        ("online_conversion_rate", "Online conversion rate"),
        ("advisor_handoff_count", "Advisor handoffs"),
        ("s4_initial_price_dropoff", "S4 initial-price drop-offs"),
        ("s5_addon_dropoff", "S5 add-on drop-offs"),
        ("s7_final_price_dropoff", "S7 final-price drop-offs"),
        ("intervention_count", "Coach interventions"),
        ("trace_completeness_rate", "Trace completeness"),
        ("step_detection_success_rate", "Step detection success"),
    ]
    delta_by_metric = {
        "online_conversion_rate": delta.get("conversion_rate_uplift", 0.0),
        "s4_initial_price_dropoff": delta.get("s4_dropoff_reduction", 0),
        "s5_addon_dropoff": delta.get("s5_dropoff_reduction", 0),
        "s7_final_price_dropoff": delta.get("s7_dropoff_reduction", 0),
    }
    for key, label in metric_pairs:
        lines.append(f"| {label} | {_format_metric(baseline.get(key))} | {_format_metric(coach.get(key))} | {_format_metric(delta_by_metric.get(key, ''))} |")
    lines.extend([
        "",
        "## Persona Conversion",
        "",
        f"- Baseline: `{baseline.get('conversion_by_persona', {})}`",
        f"- Coach: `{coach.get('conversion_by_persona', {})}`",
        "",
        "## Notes",
        "",
        "- Drop-off rate is `abandoned / sessions`.",
        "- Positive conversion-rate delta means coach improved online conversion.",
        "- Positive S4/S5/S7 drop-off reduction means the coach had fewer drop-offs than baseline at that step.",
    ])
    return "\n".join(lines) + "\n"


def _format_metric(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if value is None:
        return ""
    return str(value)


def _write_local_overview(*, traces_dir: Path, output_root: Path) -> dict[str, object]:
    traces = load_traces(traces_dir)
    baseline_traces = [trace for trace in traces if trace.get("run_mode") == "baseline" or trace.get("metadata", {}).get("run_mode") == "baseline"]
    coach_traces = [trace for trace in traces if trace.get("run_mode") == "coach" or trace.get("metadata", {}).get("run_mode") == "coach"]
    baseline = compute_metrics(baseline_traces)
    coach = compute_metrics(coach_traces)
    delta = compare_dropoff_reduction(baseline, coach)
    overview = {
        "baseline": baseline,
        "coach": coach,
        "delta": delta,
        "baseline_trace_count": len(baseline_traces),
        "coach_trace_count": len(coach_traces),
    }
    (output_root / "overview.json").write_text(json.dumps(overview, indent=2, sort_keys=True, default=str))
    (output_root / "overview.md").write_text(_comparison_markdown(baseline=baseline, coach=coach, delta=delta))
    return overview


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
    parser = argparse.ArgumentParser(
        description="Run UNIQA Conversion Coach browser experiments and local reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_live = subparsers.add_parser(
        "validate-live",
        help="Run a small live-browser validation batch.",
    )
    validate_live.add_argument("--execution-mode", choices=["baseline", "coach"], default="baseline")
    validate_live.add_argument("--sessions", type=int, default=12)
    validate_live.add_argument("--experiment-id", default="validation")
    validate_live.add_argument("--output-dir", type=Path, default=None)
    validate_live.set_defaults(func=cmd_validate_live)

    run_live = subparsers.add_parser(
        "run-live",
        help="Run a larger live-browser batch.",
    )
    run_live.add_argument("--execution-mode", choices=["baseline", "coach"], default="coach")
    run_live.add_argument("--sessions", type=int, default=300)
    run_live.add_argument("--experiment-id", default="bulk")
    run_live.add_argument("--output-dir", type=Path, default=None)
    run_live.set_defaults(func=cmd_run_live)

    local_full_loop = subparsers.add_parser(
        "local-full-loop",
        help="Run baseline validation, coach validation, bulk runs, and report generation.",
    )
    local_full_loop.add_argument("--artifacts-root", type=Path, default=ROOT / "artifacts")
    local_full_loop.add_argument("--output-dir", type=Path, default=None)
    local_full_loop.add_argument("--report-output-dir", type=Path, default=None)
    local_full_loop.add_argument("--experiment-prefix", default="local-full-loop")
    local_full_loop.add_argument("--validate-sessions", type=int, default=12)
    local_full_loop.add_argument("--bulk-sessions", type=int, default=300)
    local_full_loop.set_defaults(func=cmd_local_full_loop)

    return parser


def main() -> None:
    load_env_file(ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
