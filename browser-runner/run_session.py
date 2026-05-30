from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

from event_factory import make_runner_event
from persona_policy import ONLINE_STEPS, classify_outcome, load_personas
from playwright_config import BrowserRunConfig, RunnerSafetyConfig


def _now_ms() -> int:
    return int(time.time() * 1000)


def _metadata(config: BrowserRunConfig, *, experiment_id: str, persona_id: str, intention: str, seed: int) -> dict[str, Any]:
    return {
        "runner_id": "andrii-browser-runner",
        "experiment_id": experiment_id,
        "persona_id": persona_id,
        "persona_variant_id": f"{persona_id}_{intention}_{seed}",
        "intention": intention,
        "seed": seed,
        "extension_build_id": config.extension_build_id,
        "page_map_version": config.page_map_version,
        "backend_url": config.backend_url,
        "model_version_or_policy": config.model_version_or_policy,
        "site_timestamp": _now_ms(),
        "leonardo_job_id": None,
    }


def run_mock_session(*, persona_id: str, intention: str, experiment_id: str, seed: int, config: BrowserRunConfig) -> dict[str, Any]:
    personas = load_personas()
    policy = personas[persona_id]
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    metadata = _metadata(config, experiment_id=experiment_id, persona_id=persona_id, intention=intention, seed=seed)
    events: list[dict[str, Any]] = []
    for index, step_id in enumerate(ONLINE_STEPS):
        intervention = "price_transparency" if step_id in {"s4_initial_price", "s7_final_price"} else None
        action = policy.action_for_step(step_id=step_id, intention=intention, intervention_kind=intervention, seed=seed)
        event = make_runner_event(
            session_id=session_id,
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            ts=_now_ms() + index,
            source="browser-runner-mock",
            step_id=step_id,
            event_type="persona_action",
            element_key=action["element_key"],
            raw_value={"action": action["action"], "dwell_ms": action["dwell_ms"]},
            derived_context={"intervention_kind": intervention} if intervention else {},
            runner_metadata=metadata,
        )
        event["derived_signals"]["intention"] = intention
        events.append(event)
        if action["action"] == "explore_out_of_scope_then_back":
            events.append({**event, "event_id": f"evt_{uuid.uuid4().hex[:12]}", "element_key": "premium", "event_type": "out_of_scope_selected"})
        if action["action"] in {"abandon", "request_advisor"}:
            break
    outcome = classify_outcome([{**event, "action": event["raw_value"].get("action")} for event in events])
    if events:
        events[-1]["terminal_outcome"] = outcome
    return {"session_id": session_id, "metadata": metadata, "events": events, "terminal_outcome": outcome}


def run_live_session(*, persona_id: str, intention: str, experiment_id: str, seed: int, config: BrowserRunConfig, safety: RunnerSafetyConfig) -> dict[str, Any]:
    if not config.extension_path or not config.extension_path.exists():
        raise RuntimeError("EXTENSION_DIST must point to a built extension directory for live runs")
    if safety.allow_purchase_submit:
        raise RuntimeError("Live purchase submission is disabled unless a separate approved test path is implemented")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for live browser sessions") from exc

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    metadata = _metadata(config, experiment_id=experiment_id, persona_id=persona_id, intention=intention, seed=seed)
    events: list[dict[str, Any]] = []
    user_data_dir = config.output_dir / session_id / "chrome-profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            args=[
                f"--disable-extensions-except={config.extension_path}",
                f"--load-extension={config.extension_path}",
            ],
        )
        page = context.new_page()
        try:
            page.goto(config.site_url, wait_until="domcontentloaded", timeout=45_000)
            events.append({
                "schema_version": "v1",
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "session_id": session_id,
                "ts": _now_ms(),
                "source": "browser-runner-live",
                "step_id": "s1_entry",
                "event_type": "page_loaded",
                "element_key": "calculator_entry",
                "raw_value": {"url": page.url},
                "derived_signals": {},
                "derived_context": {},
                "runner_metadata": metadata,
                "privacy_level": "anonymous",
            })
            if safety.screenshots:
                shot_dir = config.output_dir / session_id
                shot_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot_dir / "landing.png"), full_page=True)
        finally:
            context.close()
    outcome = classify_outcome(events)
    if events:
        events[-1]["terminal_outcome"] = outcome
    return {"session_id": session_id, "metadata": metadata, "events": events, "terminal_outcome": outcome}


def write_trace(trace: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{trace['session_id']}.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one UNIQA persona browser session")
    parser.add_argument("--persona", default="franz", choices=sorted(load_personas().keys()))
    parser.add_argument("--intention", default="purchase", choices=["purchase", "orientation", "comparison", "price_check"])
    parser.add_argument("--experiment-id", default=f"exp_{int(time.time())}")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--mode", choices=["mock", "validation", "bulk"], default="mock")
    args = parser.parse_args()

    config = BrowserRunConfig.from_env()
    safety = RunnerSafetyConfig.for_mode(args.mode)
    if args.mode == "mock":
        trace = run_mock_session(persona_id=args.persona, intention=args.intention, experiment_id=args.experiment_id, seed=args.seed, config=config)
    else:
        trace = run_live_session(persona_id=args.persona, intention=args.intention, experiment_id=args.experiment_id, seed=args.seed, config=config, safety=safety)
    path = write_trace(trace, config.output_dir)
    print(json.dumps({"trace": str(path), "terminal_outcome": trace["terminal_outcome"]}, indent=2))


if __name__ == "__main__":
    main()
