from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from errors import BackendFailure, PageLoadFailure, SelectorFailure
from playwright_config import BrowserRunConfig, RunnerSafetyConfig
from run_session import run_live_session, run_mock_session, write_trace

PERSONA_MATRIX = [
    ("franz", "purchase"),
    ("franz", "orientation"),
    ("franz", "comparison"),
    ("franz", "price_check"),
    ("judith", "purchase"),
    ("judith", "orientation"),
    ("judith", "comparison"),
    ("judith", "price_check"),
    ("peter", "purchase"),
    ("peter", "orientation"),
    ("peter", "comparison"),
    ("peter", "price_check"),
]
FailureCounts = dict[str, int]
RunnerFn = Callable[[str, str, str, int, BrowserRunConfig, RunnerSafetyConfig], dict[str, Any]]


def _circuit_breaker_reason(failures: FailureCounts, safety: RunnerSafetyConfig) -> str | None:
    if failures["selector"] >= safety.selector_failure_limit:
        return "selector_failure_limit"
    if failures["backend"] >= safety.backend_failure_limit:
        return "backend_failure_limit"
    if failures["page"] >= safety.page_failure_limit:
        return "page_failure_limit"
    return None


def _classify_failure(exc: Exception) -> str:
    if isinstance(exc, (SelectorFailure, TimeoutError)):
        return "selector"
    if isinstance(exc, (BackendFailure, ConnectionError)):
        return "backend"
    if isinstance(exc, PageLoadFailure):
        return "page"
    return "page"


def _default_runner(persona_id: str, intention: str, experiment_id: str, seed: int, config: BrowserRunConfig, safety: RunnerSafetyConfig) -> dict[str, Any]:
    if safety.mode == "mock":
        return run_mock_session(persona_id=persona_id, intention=intention, experiment_id=experiment_id, seed=seed, config=config)
    return run_live_session(persona_id=persona_id, intention=intention, experiment_id=experiment_id, seed=seed, config=config, safety=safety)


def run_batch(
    *,
    mode: str,
    experiment_id: str,
    sessions: int,
    output_dir: Path | None = None,
    runner: RunnerFn | None = None,
) -> dict[str, Any]:
    config = BrowserRunConfig.from_env()
    if output_dir:
        config = BrowserRunConfig(**{**config.__dict__, "output_dir": output_dir})
    safety = _safety_from_env(RunnerSafetyConfig.for_mode(mode))
    failures: FailureCounts = {"selector": 0, "backend": 0, "page": 0}
    traces = []
    failure_log = []
    selected_runner = runner or _default_runner

    for index in range(min(sessions, safety.max_sessions)):
        persona_id, intention = PERSONA_MATRIX[index % len(PERSONA_MATRIX)]
        seed = index // len(PERSONA_MATRIX) + 1
        try:
            trace = selected_runner(persona_id, intention, experiment_id, seed, config, safety)
            traces.append(str(write_trace(trace, config.output_dir)))
        except Exception as exc:  # classified below and summarized for evaluation hygiene
            bucket = _classify_failure(exc)
            failures[bucket] += 1
            failure_log.append({"session_index": index, "persona_id": persona_id, "intention": intention, "seed": seed, "failure_type": bucket, "message": str(exc)})
        breaker = _circuit_breaker_reason(failures, safety)
        if breaker:
            return {"experiment_id": experiment_id, "mode": mode, "traces": traces, "failures": failures, "failure_log": failure_log, "circuit_breaker": breaker}
        time.sleep(0.05 if mode == "mock" else safety.min_think_ms / 1000)
    return {"experiment_id": experiment_id, "mode": mode, "traces": traces, "failures": failures, "failure_log": failure_log, "circuit_breaker": None}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _safety_from_env(safety: RunnerSafetyConfig) -> RunnerSafetyConfig:
    multiplier = _env_float("RUNNER_DWELL_MULTIPLIER", 1.0)
    min_think = _env_int("RUNNER_MIN_THINK_MS", int(safety.min_think_ms * multiplier))
    max_think = _env_int("RUNNER_MAX_THINK_MS", int(safety.max_think_ms * multiplier))
    return replace(
        safety,
        min_think_ms=max(0, min_think),
        max_think_ms=max(min_think, max_think),
        selector_failure_limit=_env_int("RUNNER_SELECTOR_FAILURE_LIMIT", safety.selector_failure_limit),
        backend_failure_limit=_env_int("RUNNER_BACKEND_FAILURE_LIMIT", safety.backend_failure_limit),
        page_failure_limit=_env_int("RUNNER_PAGE_FAILURE_LIMIT", safety.page_failure_limit),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a capped batch of UNIQA persona sessions")
    parser.add_argument("--mode", choices=["mock", "validation", "bulk"], default="mock")
    parser.add_argument("--experiment-id", default=f"exp_{int(time.time())}")
    parser.add_argument("--sessions", type=int, default=6)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_batch(mode=args.mode, experiment_id=args.experiment_id, sessions=args.sessions, output_dir=args.output_dir), indent=2))


if __name__ == "__main__":
    main()
