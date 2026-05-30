from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from action_ranker import DEFAULT_CANDIDATES, load_ranker, predict_action

from backend_client import CoachApiClient, CoachApiError
from errors import BackendFailure, PageLoadFailure, SelectorFailure
from event_factory import make_runner_event, make_step_event
from live_page import (
    choose_no_for_question_group,
    derive_context,
    detect_step,
    dismiss_cookie_banner,
    generate_sv,
    install_runner_shim,
    read_runner_shim,
)
from llm_persona import LLMPersonaDriver, PersonaDecision
from persona_policy import ONLINE_STEPS, classify_outcome, load_personas
from playwright_config import BrowserRunConfig, RunnerSafetyConfig


def _now_ms() -> int:
    return int(time.time() * 1000)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class SessionProfile:
    first_name: str
    last_name: str
    gender_label: str
    birth_date: str
    social_provider: str
    social_insurance_number: str
    email: str
    phone: str
    height_cm: int
    weight_kg: int


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
        "run_mode": config.execution_mode,
        "instrumentation_mode": "extension" if config.execution_mode == "coach" else "runner_shim",
        "llm_model": config.llm_model,
        "site_timestamp": _now_ms(),
        "leonardo_job_id": None,
    }


def _ranker_model_path() -> Path:
    return Path(os.getenv("TRAINABLE_RANKER_MODEL", "artifacts/training/frequency-ranker.json"))


def _intervention_for_step(step_id: str, config: BrowserRunConfig) -> str | None:
    if config.model_version_or_policy == "baseline-no-coach":
        return None
    if config.model_version_or_policy == "trainable-ranker":
        model_path = _ranker_model_path()
        if not model_path.exists():
            raise RuntimeError(f"TRAINABLE_RANKER_MODEL does not exist: {model_path}")
        model = load_ranker(model_path)
        return predict_action(model, step_id=step_id, candidates=DEFAULT_CANDIDATES)
    return "price_transparency" if step_id in {"s4_initial_price", "s7_final_price"} else None


def _generate_profile(persona_id: str, seed: int) -> SessionProfile:
    persona_names = {
        "franz": ("Franz", "Muster", "männlich"),
        "judith": ("Judith", "Muster", "weiblich"),
        "peter": ("Peter", "Muster", "männlich"),
    }
    first_name, last_name, gender = persona_names.get(persona_id, ("Alex", "Muster", "männlich"))
    day = (seed % 27) + 1
    month = (seed % 12) + 1
    year = 1984 + (seed % 16)
    birth_date = f"{day:02d}.{month:02d}.{year}"
    email_name = f"{first_name.lower()}.{last_name.lower()}{seed}"
    return SessionProfile(
        first_name=first_name,
        last_name=last_name,
        gender_label=gender,
        birth_date=birth_date,
        social_provider="ÖGK",
        social_insurance_number=generate_sv(day, month, year),
        email=f"{email_name}@example.com",
        phone=f"+43664{seed:07d}"[:12],
        height_cm=168 + (seed % 17),
        weight_kg=63 + (seed % 19),
    )


def run_mock_session(*, persona_id: str, intention: str, experiment_id: str, seed: int, config: BrowserRunConfig) -> dict[str, Any]:
    personas = load_personas()
    policy = personas[persona_id]
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    metadata = _metadata(config, experiment_id=experiment_id, persona_id=persona_id, intention=intention, seed=seed)
    events: list[dict[str, Any]] = []
    llm_decisions: list[dict[str, Any]] = []
    for index, step_id in enumerate(ONLINE_STEPS):
        intervention = _intervention_for_step(step_id, config)
        action = policy.action_for_step(step_id=step_id, intention=intention, intervention_kind=intervention, seed=seed)
        events.append(
            make_runner_event(
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
        )
        llm_decisions.append(
            {
                "decision_id": f"lld_{uuid.uuid4().hex[:12]}",
                "step_id": step_id,
                "action": action["action"],
                "reasoning": "Mock persona policy",
                "dwell_ms": action["dwell_ms"],
                "llm_model": "mock-persona-policy",
                "latency_ms": 0,
                "fallback_used": True,
                "prompt_hash": "mock",
                "candidate_set": [],
                "overlay": {},
                "step_context": {},
                "history": [],
            }
        )
        if action["action"] in {"abandon", "request_advisor"}:
            break
    outcome = classify_outcome([{**event, "action": event["raw_value"].get("action")} for event in events])
    if events:
        events[-1]["terminal_outcome"] = outcome
    return {
        "session_id": session_id,
        "metadata": metadata,
        "events": events,
        "llm_decisions": llm_decisions,
        "run_mode": config.execution_mode,
        "instrumentation_mode": metadata["instrumentation_mode"],
        "terminal_outcome": outcome,
    }


def _wait_for_step(page: Any, *, timeout_ms: int = 25_000) -> dict[str, Any]:
    started = time.time()
    while (time.time() - started) * 1000 < timeout_ms:
        step = detect_step(page)
        if step:
            return step
        page.wait_for_timeout(250)
    raise SelectorFailure("Unable to detect a supported UNIQA step before timeout")


def _append_baseline_event(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    step_id: str | None,
    event_type: str,
    element_key: str | None,
    raw_value: dict[str, Any] | None,
    derived_context: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    events.append(
        make_runner_event(
            session_id=session_id,
            event_type=event_type,
            step_id=step_id,
            element_key=element_key,
            raw_value=raw_value,
            derived_context=derived_context,
            runner_metadata=metadata,
            source="browser-runner-live",
        )
    )


def _step_artifacts(page: Any, *, session_dir: Path, step_id: str, index: int, context: dict[str, Any]) -> dict[str, Any]:
    step_dir = session_dir / "artifacts"
    step_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = step_dir / f"{index:02d}-{step_id}.png"
    dom_path = step_dir / f"{index:02d}-{step_id}.html"
    page.screenshot(path=str(screenshot_path), full_page=True)
    dom_path.write_text(page.content(), encoding="utf-8")
    return {
        "step_id": step_id,
        "screenshot": str(screenshot_path),
        "dom_snapshot": str(dom_path),
        "visible_price": context.get("visiblePrice"),
    }


def _fill_quote_basics(page: Any, profile: SessionProfile) -> None:
    page.get_by_role("textbox", name="Geburtsdatum").fill(profile.birth_date)
    page.locator("[data-cy='ur-select-field-button']").click()
    page.get_by_text(profile.social_provider).click()
    page.get_by_role("button", name="Weiter").click()


def _fill_personal_medical_data(page: Any, profile: SessionProfile) -> None:
    page.get_by_text(profile.gender_label).click()
    text_inputs = page.locator("input[type='text']")
    if text_inputs.count() < 7:
        raise SelectorFailure("Live personal data fields did not match the expected shape")
    text_inputs.nth(0).fill(profile.first_name)
    text_inputs.nth(1).fill(profile.last_name)
    text_inputs.nth(2).fill(profile.social_insurance_number)
    text_inputs.nth(3).fill(profile.email)
    text_inputs.nth(4).fill(profile.phone)
    text_inputs.nth(5).fill(str(profile.height_cm))
    text_inputs.nth(6).fill(str(profile.weight_kg))
    page.get_by_text("nein").click()
    page.get_by_text("kein behandelnder Arzt").click()
    page.get_by_role("button", name="Weiter").click()


def _complete_questionnaire_to_boundary(page: Any) -> None:
    pages = [
        ["insuranceInPast7Years", "rejectedApplication"],
        ["diagnoses", "musculoskeletalSystem"],
        ["rehabilitationPlanned", "therapiesPlanned"],
    ]
    for groups in pages:
        found = False
        for group in groups:
            if page.locator(f"[data-cy='{group}']").count() > 0:
                choose_no_for_question_group(page, group)
                found = True
        if not found:
            continue
        page.get_by_role("button", name="Weiter").click()
        page.wait_for_timeout(350)
        next_step = detect_step(page)
        if next_step and next_step["pageStepId"] == "s8_confirm":
            return


def _click_tariff(page: Any, action: str) -> None:
    button_name = {
        "select_start": "Wählen Start",
        "select_optimal": "Wählen Optimal",
        "select_opt_plus": "Wählen Opt. Plus",
        "select_premium": "Wählen Premium",
    }.get(action)
    if not button_name:
        raise SelectorFailure(f"Unsupported tariff action: {action}")
    page.get_by_role("button", name=button_name).click()
    page.wait_for_timeout(300)
    if action in {"select_start", "select_optimal"} and page.get_by_role("button", name="Weiter").is_visible():
        page.get_by_role("button", name="Weiter").click()


def _safe_check(locator: Any) -> None:
    try:
        locator.check(force=True)
        return
    except Exception:
        handle = locator.element_handle()
        if handle is None:
            raise
        handle.evaluate(
            """
            (element) => {
              if (element instanceof HTMLInputElement) {
                element.checked = true;
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.dispatchEvent(new Event("change", { bubbles: true }));
                return;
              }
              if (element instanceof HTMLElement) {
                element.click();
              }
            }
            """
        )


def _try_coach_interaction(page: Any, decision: PersonaDecision) -> str | None:
    try:
        text = page.evaluate(
            """
            () => {
              const shadow = document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
              return shadow?.textContent?.trim() || "";
            }
            """
        )
    except Exception:
        return None
    if not text:
        return None
    mode = "cta" if decision.overlay.coach_receptiveness >= 1.0 and decision.action != "abandon" else "dismiss"
    page.evaluate(
        """
        (mode) => {
          const shadow = document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
          const target = mode === "cta" ? shadow?.querySelector(".cta") : shadow?.querySelector(".dismiss");
          if (target instanceof HTMLButtonElement) {
            target.click();
          }
        }
        """,
        mode,
    )
    return mode


def _execute_step_action(page: Any, *, step_id: str, action: str, profile: SessionProfile) -> dict[str, Any]:
    if action == "abandon":
        return {"terminal": True, "outcome": "abandoned", "element_key": "close_or_back"}

    if step_id == "s1_coverage_scope":
        if action == "at_doctor":
            page.get_by_role("checkbox", name="Bei Arztbesuchen").click()
            element_key = "at_doctor"
        elif action == "hospital":
            page.get_by_role("checkbox", name="Im Krankenhaus").click()
            element_key = "hospital"
        else:
            page.get_by_role("checkbox", name="Bei Arztbesuchen").click()
            page.get_by_role("checkbox", name="Im Krankenhaus").click()
            element_key = "both"
        page.get_by_role("button", name="Weiter").click()
        return {"terminal": False, "element_key": element_key}

    if step_id == "s2_for_whom":
        if action == "myself":
            page.get_by_role("radio", name="Ich selbst").click()
            element_key = "myself"
        else:
            page.get_by_role("radio", name="Andere Personen").click()
            element_key = "other_persons"
        page.get_by_role("button", name="Weiter").click()
        return {"terminal": False, "element_key": element_key}

    if step_id == "s3_quote_basics":
        _fill_quote_basics(page, profile)
        return {"terminal": False, "element_key": "submit_quote_basics"}

    if step_id == "s4_initial_price":
        if action == "back":
            page.get_by_role("button", name="Zurück").click()
            return {"terminal": False, "element_key": "backButton"}
        _click_tariff(page, action)
        element_key = {
            "select_start": "start",
            "select_optimal": "optimal",
            "select_opt_plus": "opt_plus",
            "select_premium": "premium",
        }.get(action, action)
        return {"terminal": False, "element_key": element_key}

    if step_id == "s5_add_ons":
        if action == "continue_with_first_addon":
            checkboxes = page.locator("input[type='checkbox']")
            count = checkboxes.count()
            for index in range(count):
                if not checkboxes.nth(index).is_checked():
                    _safe_check(checkboxes.nth(index))
                    break
        page.get_by_role("button", name="Weiter").click()
        return {"terminal": False, "element_key": "primary_continue"}

    if step_id == "s6_personal_medical_data":
        _fill_personal_medical_data(page, profile)
        return {"terminal": False, "element_key": "submit_personal_data"}

    if step_id == "s7_final_price":
        _complete_questionnaire_to_boundary(page)
        return {"terminal": False, "element_key": "questionnaire_continue"}

    if step_id == "s8_confirm":
        return {"terminal": True, "outcome": "advisor_handoff", "element_key": "consultationContact"}

    raise SelectorFailure(f"Unsupported step action execution for {step_id}")


def _build_baseline_trace(
    *,
    session_id: str,
    metadata: dict[str, Any],
    events: list[dict[str, Any]],
    llm_decisions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    shim_events: list[dict[str, Any]],
    profile: SessionProfile,
    terminal_outcome: str,
) -> dict[str, Any]:
    if events:
        events[-1]["terminal_outcome"] = terminal_outcome
    return {
        "session_id": session_id,
        "metadata": metadata,
        "events": events,
        "decisions": [],
        "exposures": [],
        "run_mode": metadata["run_mode"],
        "instrumentation_mode": metadata["instrumentation_mode"],
        "llm_decisions": llm_decisions,
        "artifacts": artifacts,
        "shim_events": shim_events,
        "profile": asdict(profile),
        "terminal_outcome": terminal_outcome,
    }


def run_live_session(*, persona_id: str, intention: str, experiment_id: str, seed: int, config: BrowserRunConfig, safety: RunnerSafetyConfig) -> dict[str, Any]:
    if safety.allow_purchase_submit:
        raise RuntimeError("Live purchase submission is disabled unless a separate approved test path is implemented")
    if config.execution_mode == "coach" and (not config.extension_path or not config.extension_path.exists()):
        raise RuntimeError("EXTENSION_DIST must point to a built extension directory for coach-mode live runs")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for live browser sessions") from exc

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    metadata = _metadata(config, experiment_id=experiment_id, persona_id=persona_id, intention=intention, seed=seed)
    profile = _generate_profile(persona_id, seed)
    llm_driver = LLMPersonaDriver(
        model=config.llm_model,
        api_url=config.llm_api_url,
        temperature=config.llm_temperature,
        timeout_s=config.llm_timeout_s,
    )
    llm_decisions: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    baseline_events: list[dict[str, Any]] = []
    coach_interaction_seen = False
    current_context: dict[str, Any] = {}
    session_dir = config.output_dir / session_id
    user_data_dir = session_dir / "chrome-profile"
    session_dir.mkdir(parents=True, exist_ok=True)
    client = CoachApiClient(config.backend_url)

    with sync_playwright() as p:
        launch_args: list[str] = []
        if config.execution_mode == "coach":
            launch_args.extend([
                f"--disable-extensions-except={config.extension_path}",
                f"--load-extension={config.extension_path}",
            ])
        context = p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=config.headless,
            args=launch_args,
        )
        page = context.pages[0] if context.pages else context.new_page()
        install_runner_shim(page, preferred_session_id=session_id if config.execution_mode == "coach" else None)
        try:
            try:
                page.goto(config.site_url, wait_until="domcontentloaded", timeout=45_000)
            except Exception as exc:
                raise PageLoadFailure(str(exc)) from exc
            dismiss_cookie_banner(page)

            visited_step_count = 0
            terminal_outcome: str | None = None
            while visited_step_count < 12 and terminal_outcome is None:
                step = _wait_for_step(page)
                step_id = step["pageStepId"]
                current_context = derive_context(page, step, current_context)
                artifacts.append(_step_artifacts(page, session_dir=session_dir, step_id=step_id, index=visited_step_count, context=current_context))
                if config.execution_mode == "baseline":
                    baseline_events.append(make_step_event(session_id=session_id, step_id=step_id, event_type="step_enter", runner_metadata=metadata))

                decision = llm_driver.decide(
                    persona_id=persona_id,
                    intention=intention,
                    step_id=step_id,
                    seed=seed,
                    step_context=current_context,
                    history=llm_decisions,
                    coach_interaction_seen=coach_interaction_seen,
                )
                llm_decisions.append(decision.to_trace_row(decision_id=f"lld_{uuid.uuid4().hex[:12]}", history=[{"step_id": row["step_id"], "action": row["action"]} for row in llm_decisions[-4:]]))
                page.wait_for_timeout(_clamp(decision.dwell_ms, safety.min_think_ms, safety.max_think_ms))
                if config.execution_mode == "coach":
                    interaction = _try_coach_interaction(page, decision)
                    coach_interaction_seen = coach_interaction_seen or interaction is not None
                execution = _execute_step_action(page, step_id=step_id, action=decision.action, profile=profile)
                if config.execution_mode == "baseline":
                    _append_baseline_event(
                        baseline_events,
                        session_id=session_id,
                        step_id=step_id,
                        event_type="persona_action",
                        element_key=execution.get("element_key"),
                        raw_value={"action": decision.action, "reasoning": decision.reasoning, "dwell_ms": decision.dwell_ms},
                        derived_context=current_context,
                        metadata=metadata,
                    )
                    if execution.get("element_key") in {"hospital", "other_persons", "opt_plus", "premium"}:
                        _append_baseline_event(
                            baseline_events,
                            session_id=session_id,
                            step_id=step_id,
                            event_type="out_of_scope_selected",
                            element_key=execution.get("element_key"),
                            raw_value={"action": decision.action},
                            derived_context=current_context,
                            metadata=metadata,
                        )
                terminal_outcome = execution.get("outcome")
                if terminal_outcome is None and step_id == "s8_confirm":
                    terminal_outcome = "advisor_handoff"
                visited_step_count += 1

            if terminal_outcome is None:
                terminal_outcome = "advisor_handoff" if detect_step(page) and detect_step(page)["pageStepId"] == "s8_confirm" else "abandoned"

            page.wait_for_timeout(1_000)
            if config.execution_mode == "coach":
                try:
                    client.post_outcome({
                        "session_id": session_id,
                        "outcome": terminal_outcome,
                        "terminal_step_id": detect_step(page)["pageStepId"] if detect_step(page) else None,
                        "ended_at": _now_ms(),
                        "final_visible_price": current_context.get("visiblePrice"),
                        "price_delta": current_context.get("priceDelta"),
                    })
                    trace = client.fetch_session(session_id)
                except (CoachApiError, ValueError) as exc:
                    raise BackendFailure(str(exc)) from exc
                trace["metadata"] = metadata
                trace["run_mode"] = metadata["run_mode"]
                trace["instrumentation_mode"] = metadata["instrumentation_mode"]
                trace["llm_decisions"] = llm_decisions
                trace["artifacts"] = artifacts
                trace["shim_events"] = read_runner_shim(page)
                trace["profile"] = asdict(profile)
                trace["terminal_outcome"] = terminal_outcome
                return trace
            return _build_baseline_trace(
                session_id=session_id,
                metadata=metadata,
                events=baseline_events,
                llm_decisions=llm_decisions,
                artifacts=artifacts,
                shim_events=read_runner_shim(page),
                profile=profile,
                terminal_outcome=terminal_outcome,
            )
        finally:
            context.close()


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
