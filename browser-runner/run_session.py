from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend_client import RuntimeApiClient, RuntimeApiError
from errors import BackendFailure, PageLoadFailure, SelectorFailure
from event_factory import make_runner_event, make_step_event
from live_page import (
    choose_no_for_question_group,
    derive_context,
    detect_step,
    dismiss_cookie_banner,
    generate_sv,
    install_runner_shim,
    read_extension_state,
    read_runner_shim,
    wait_for_coach_cycle,
    wait_for_extension_ready,
)
from llm_persona import LLMPersonaDriver, PersonaDecision
from persona_policy import ONLINE_STEPS, classify_outcome, load_personas
from playwright_config import BrowserRunConfig, RunnerSafetyConfig


ADVISOR_OUTCOME = "submitted_advisor_lead"


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
        "run_mode": config.execution_mode,
        "instrumentation_mode": "extension" if config.execution_mode == "coach" else "runner_shim",
        "llm_model": config.llm_model,
        "site_timestamp": _now_ms(),
    }


def _mock_play_for_step(step_id: str, execution_mode: str) -> str | None:
    if execution_mode != "coach":
        return None
    if step_id in {"s3_quote_basics", "s6_personal_medical_data"}:
        return "trust_builder"
    if step_id == "s4_initial_price":
        return "price_reframe"
    if step_id == "s7_final_price":
        return "price_change_explainer"
    return None


def _normalize_outcome(outcome: str | None) -> str:
    if outcome == "advisor_handoff":
        return ADVISOR_OUTCOME
    if outcome in {"converted_online", ADVISOR_OUTCOME, "abandoned"}:
        return outcome
    return "abandoned"


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
    coach_render_log: list[dict[str, Any]] = []
    for index, step_id in enumerate(ONLINE_STEPS):
        play_id = _mock_play_for_step(step_id, config.execution_mode)
        action = policy.action_for_step(step_id=step_id, intention=intention, intervention_kind=play_id, seed=seed)
        events.append(make_step_event(session_id=session_id, step_id=step_id, event_type="step_enter", runner_metadata=metadata))
        if play_id:
            coach_render_log.append({
                "decision_state": "rendered",
                "play_id": play_id,
                "rendered": True,
                "step_id": step_id,
                "waited_ms": 0,
            })
            events.append(
                make_runner_event(
                    session_id=session_id,
                    event_id=f"evt_{uuid.uuid4().hex[:12]}",
                    ts=_now_ms() + index,
                    source="browser-runner-mock",
                    step_id=step_id,
                    event_type="coach_impression",
                    element_key=play_id,
                    raw_value={"play_id": play_id},
                    derived_context={"intervention_kind": play_id},
                    runner_metadata=metadata,
                )
            )
        events.append(
            make_runner_event(
                session_id=session_id,
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                ts=_now_ms() + index + 1,
                source="browser-runner-mock",
                step_id=step_id,
                event_type="persona_action",
                element_key=action["element_key"],
                raw_value={"action": action["action"], "dwell_ms": action["dwell_ms"]},
                derived_context={"intervention_kind": play_id} if play_id else {},
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
    outcome = _normalize_outcome(classify_outcome([{**event, "action": event.get("raw_value", {}).get("action")} for event in events]))
    if events:
        events[-1]["terminal_outcome"] = outcome
    return {
        "session_id": session_id,
        "metadata": metadata,
        "events": events,
        "llm_decisions": llm_decisions,
        "run_mode": config.execution_mode,
        "instrumentation_mode": metadata["instrumentation_mode"],
        "artifacts": [],
        "runtime_trace": None,
        "coach_render_log": coach_render_log,
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


def _append_runner_event(
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


def _click_next(page: Any) -> None:
    button = page.locator("[data-cy='nextStepButton']")
    if button.count() > 0:
        button.first.click()
        return
    page.get_by_role("button", name="Weiter").click()


def _coach_overlay_text(page: Any) -> str:
    return page.evaluate(
        """
        () => {
          const shadow = document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
          const state = window.__UNIQA_COACH_STATE__;
          if (!state?.cardCount) return "";
          const target = shadow?.querySelector(".card");
          if (!target) return "";
          return target.textContent?.trim() || "";
        }
        """
    )


def _post_action_settle(page: Any, safety: RunnerSafetyConfig, *, coach_mode: bool) -> None:
    delay_ms = safety.post_action_settle_ms if coach_mode else min(350, safety.post_action_settle_ms)
    if delay_ms > 0:
        page.wait_for_timeout(delay_ms)


def _click_label_exact(page: Any, label_text: str) -> None:
    clicked = page.evaluate(
        """
        (labelText) => {
          const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
          const wanted = normalize(labelText);
          const labels = Array.from(document.querySelectorAll("label"));
          const target = labels.find((label) => normalize(label.textContent) === wanted);
          if (target instanceof HTMLElement) {
            target.click();
            return true;
          }
          return false;
        }
        """,
        label_text,
    )
    if not clicked:
        page.get_by_text(label_text, exact=True).first.click()


def _answer_visible_no_options(page: Any) -> None:
    clicked = page.evaluate(
        """
        () => {
          const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
          let clickedCount = 0;
          for (const label of Array.from(document.querySelectorAll("label[role='radio'], label"))) {
            if (normalize(label.textContent) !== "nein") continue;
            const visible = Boolean(label.offsetWidth || label.offsetHeight || label.getClientRects().length);
            if (!visible) continue;
            const input = label.querySelector("input");
            const checked = label.getAttribute("aria-checked") === "true" || Boolean(input?.checked);
            if (!checked && label instanceof HTMLElement) {
              label.click();
              clickedCount += 1;
            }
          }
          return clickedCount;
        }
        """
    )
    if clicked == 0:
        page.get_by_text("nein", exact=True).first.click()
    page.wait_for_timeout(150)


def _terminal_outcome_for_element(element_key: str | None) -> str | None:
    if element_key in {"hospital", "both", "other_persons"}:
        return ADVISOR_OUTCOME
    return None


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
    _click_next(page)


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
    _answer_visible_no_options(page)
    _click_label_exact(page, "kein behandelnder Arzt")
    _click_next(page)


def _complete_questionnaire_to_boundary(page: Any, safety: RunnerSafetyConfig, *, coach_mode: bool) -> None:
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
        _click_next(page)
        _post_action_settle(page, safety, coach_mode=coach_mode)
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
    if action in {"select_start", "select_optimal"} and page.locator("[data-cy='nextStepButton']").is_visible():
        _click_next(page)


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


def _coach_interaction_mode(decision: PersonaDecision) -> str:
    if decision.action == "abandon":
        return "dismiss"
    receptiveness = decision.overlay.coach_receptiveness
    if receptiveness >= 1.2:
        return "cta"
    if receptiveness <= 0.65:
        return "dismiss"
    probability = _clamp(int((receptiveness - 0.65) * 100), 15, 85) / 100
    digest = hashlib.sha256(f"{decision.prompt_hash}:{decision.step_id}:{decision.action}".encode("utf-8")).hexdigest()
    roll = int(digest[:8], 16) / 0xFFFFFFFF
    return "cta" if roll < probability else "dismiss"


def _try_coach_interaction(page: Any, decision: PersonaDecision, *, read_ms: int = 0) -> str | None:
    try:
        text = _coach_overlay_text(page)
    except Exception:
        return None
    if not text:
        return None
    if read_ms > 0:
        page.wait_for_timeout(read_ms)
    mode = _coach_interaction_mode(decision)
    page.evaluate(
        """
        (mode) => {
          const shadow = document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
          const target = mode === "cta" ? shadow?.querySelector(".card-cta") : shadow?.querySelector(".card-dismiss");
          if (target instanceof HTMLButtonElement) {
            target.click();
          }
        }
        """,
        mode,
    )
    return mode


def _execute_step_action(
    page: Any,
    *,
    step_id: str,
    action: str,
    profile: SessionProfile,
    safety: RunnerSafetyConfig,
    coach_mode: bool,
) -> dict[str, Any]:
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
        _click_next(page)
        return {"terminal": False, "element_key": element_key}

    if step_id == "s2_for_whom":
        if action == "myself":
            page.get_by_role("radio", name="Ich selbst").click()
            element_key = "myself"
        else:
            page.get_by_role("radio", name="Andere Personen").click()
            element_key = "other_persons"
        _click_next(page)
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
        _click_next(page)
        return {"terminal": False, "element_key": "primary_continue"}

    if step_id == "s6_personal_medical_data":
        _fill_personal_medical_data(page, profile)
        return {"terminal": False, "element_key": "submit_personal_data"}

    if step_id == "s7_final_price":
        _complete_questionnaire_to_boundary(page, safety, coach_mode=coach_mode)
        return {"terminal": False, "element_key": "questionnaire_continue"}

    if step_id == "s8_confirm":
        return {"terminal": True, "outcome": ADVISOR_OUTCOME, "element_key": "consultationContact"}

    raise SelectorFailure(f"Unsupported step action execution for {step_id}")


def _initial_journey_state() -> dict[str, Any]:
    return {
        "insured_person": None,
        "selected_coverage": [],
        "selected_tariff": None,
    }


def _update_journey_state(journey_state: dict[str, Any], *, step_id: str, element_key: str | None) -> None:
    if step_id == "s1_coverage_scope":
        if element_key == "at_doctor":
            journey_state["selected_coverage"] = ["doctor_visits"]
        elif element_key == "hospital":
            journey_state["selected_coverage"] = ["hospital"]
        elif element_key == "both":
            journey_state["selected_coverage"] = ["doctor_visits", "hospital"]
    elif step_id == "s2_for_whom":
        journey_state["insured_person"] = "other_persons" if element_key == "other_persons" else "myself"
    elif step_id == "s4_initial_price" and element_key in {"start", "optimal", "opt_plus", "premium"}:
        journey_state["selected_tariff"] = element_key


def _classify_route_family(journey_state: dict[str, Any]) -> str:
    coverage = set(journey_state.get("selected_coverage", []))
    tariff = journey_state.get("selected_tariff")
    if "hospital" in coverage:
        return "advisor_coverage"
    if journey_state.get("insured_person") == "other_persons":
        return "advisor_other_persons"
    if tariff in {"opt_plus", "premium"}:
        return "advisor_tariff"
    return "online_doctor"


def _step_to_terminal_stage(step: dict[str, Any] | None) -> str:
    if not step:
        return "done"
    return step.get("journeyStage") or "done"


def _build_trace(
    *,
    session_id: str,
    metadata: dict[str, Any],
    events: list[dict[str, Any]],
    llm_decisions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    shim_events: list[dict[str, Any]],
    profile: SessionProfile,
    terminal_outcome: str,
    runtime_trace: dict[str, Any] | None,
    coach_render_log: list[dict[str, Any]],
) -> dict[str, Any]:
    if events:
        events[-1]["terminal_outcome"] = terminal_outcome
    return {
        "session_id": session_id,
        "metadata": metadata,
        "events": events,
        "run_mode": metadata["run_mode"],
        "instrumentation_mode": metadata["instrumentation_mode"],
        "llm_decisions": llm_decisions,
        "artifacts": artifacts,
        "shim_events": shim_events,
        "profile": asdict(profile),
        "runtime_trace": runtime_trace,
        "coach_render_log": coach_render_log,
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
    events: list[dict[str, Any]] = []
    coach_render_log: list[dict[str, Any]] = []
    coach_interaction_seen = False
    current_context: dict[str, Any] = {}
    journey_state = _initial_journey_state()
    session_dir = config.output_dir / session_id
    user_data_dir = session_dir / "chrome-profile"
    session_dir.mkdir(parents=True, exist_ok=True)
    runtime_client = RuntimeApiClient(config.backend_url)

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
            if config.execution_mode == "coach":
                ready = wait_for_extension_ready(
                    page,
                    timeout_ms=max(5_000, safety.coach_overlay_timeout_ms * 3),
                    settle_ms=safety.coach_settle_ms,
                )
                if not ready:
                    state = read_extension_state(page)
                    raise PageLoadFailure(f"Coach extension did not become ready: {state}")

            visited_step_count = 0
            terminal_outcome: str | None = None
            while visited_step_count < 12 and terminal_outcome is None:
                step = _wait_for_step(page)
                step_id = step["pageStepId"]
                entered_at = _now_ms() - 1_000
                current_context = derive_context(page, step, current_context)
                artifacts.append(_step_artifacts(page, session_dir=session_dir, step_id=step_id, index=visited_step_count, context=current_context))
                events.append(make_step_event(session_id=session_id, step_id=step_id, event_type="step_enter", runner_metadata=metadata))

                coach_state: dict[str, Any] | None = None
                if config.execution_mode == "coach":
                    wait_started = _now_ms()
                    coach_state = wait_for_coach_cycle(
                        page,
                        step_id=step_id,
                        entered_at=entered_at,
                        timeout_ms=safety.coach_overlay_timeout_ms * 3,
                        settle_ms=safety.coach_settle_ms,
                    )
                    waited_ms = _now_ms() - wait_started
                    coach_render_log.append(
                        {
                            "step_id": step_id,
                            "decision_state": coach_state.get("decisionState") if coach_state else "timeout",
                            "play_id": coach_state.get("playId") if coach_state else None,
                            "waited_ms": waited_ms,
                            "rendered": bool(coach_state and coach_state.get("decisionState") == "rendered"),
                        }
                    )
                    if coach_state and coach_state.get("decisionState") == "rendered":
                        _append_runner_event(
                            events,
                            session_id=session_id,
                            step_id=step_id,
                            event_type="coach_impression",
                            element_key=coach_state.get("playId"),
                            raw_value={"play_id": coach_state.get("playId")},
                            derived_context={"intervention_kind": coach_state.get("playId")},
                            metadata=metadata,
                        )

                decision = llm_driver.decide(
                    persona_id=persona_id,
                    intention=intention,
                    step_id=step_id,
                    seed=seed,
                    step_context=current_context,
                    history=llm_decisions,
                    coach_interaction_seen=coach_interaction_seen,
                )
                llm_decisions.append(
                    decision.to_trace_row(
                        decision_id=f"lld_{uuid.uuid4().hex[:12]}",
                        history=[{"step_id": row["step_id"], "action": row["action"]} for row in llm_decisions[-4:]],
                    )
                )

                page.wait_for_timeout(_clamp(decision.dwell_ms, safety.min_think_ms, safety.max_think_ms))
                if coach_state and coach_state.get("decisionState") == "rendered":
                    interaction = _try_coach_interaction(page, decision, read_ms=safety.coach_read_ms)
                    coach_interaction_seen = coach_interaction_seen or interaction is not None
                    if interaction:
                        _append_runner_event(
                            events,
                            session_id=session_id,
                            step_id=step_id,
                            event_type="coach_cta" if interaction == "cta" else "coach_dismiss",
                            element_key=coach_state.get("playId"),
                            raw_value={"interaction_mode": interaction, "play_id": coach_state.get("playId")},
                            derived_context={"intervention_kind": coach_state.get("playId")},
                            metadata=metadata,
                        )
                        page.wait_for_timeout(safety.post_action_settle_ms)

                execution = _execute_step_action(
                    page,
                    step_id=step_id,
                    action=decision.action,
                    profile=profile,
                    safety=safety,
                    coach_mode=config.execution_mode == "coach",
                )
                _update_journey_state(journey_state, step_id=step_id, element_key=execution.get("element_key"))
                _post_action_settle(page, safety, coach_mode=config.execution_mode == "coach")
                _append_runner_event(
                    events,
                    session_id=session_id,
                    step_id=step_id,
                    event_type="persona_action",
                    element_key=execution.get("element_key"),
                    raw_value={"action": decision.action, "reasoning": decision.reasoning, "dwell_ms": decision.dwell_ms},
                    derived_context=current_context,
                    metadata=metadata,
                )
                if execution.get("element_key") in {"hospital", "other_persons", "opt_plus", "premium"}:
                    _append_runner_event(
                        events,
                        session_id=session_id,
                        step_id=step_id,
                        event_type="out_of_scope_selected",
                        element_key=execution.get("element_key"),
                        raw_value={"action": decision.action},
                        derived_context=current_context,
                        metadata=metadata,
                    )

                terminal_outcome = execution.get("outcome") or _terminal_outcome_for_element(execution.get("element_key"))
                if terminal_outcome is None and step_id == "s8_confirm":
                    terminal_outcome = ADVISOR_OUTCOME
                visited_step_count += 1

            final_step = detect_step(page)
            if terminal_outcome is None:
                terminal_outcome = ADVISOR_OUTCOME if final_step and final_step["pageStepId"] == "s8_confirm" else "abandoned"
            terminal_outcome = _normalize_outcome(terminal_outcome)

            runtime_trace: dict[str, Any] | None = None
            if config.execution_mode == "coach":
                try:
                    runtime_client.post_outcome(
                        {
                            "sessionId": session_id,
                            "routeFamily": _classify_route_family(journey_state),
                            "terminalStage": _step_to_terminal_stage(final_step),
                            "outcome": terminal_outcome,
                            "finalTariff": journey_state.get("selected_tariff"),
                            "finalPriceMonthly": current_context.get("visiblePrice"),
                            "decidedAt": _now_ms(),
                        }
                    )
                    runtime_trace = runtime_client.fetch_session(session_id)
                except (RuntimeApiError, ValueError) as exc:
                    raise BackendFailure(str(exc)) from exc

            return _build_trace(
                session_id=session_id,
                metadata=metadata,
                events=events,
                llm_decisions=llm_decisions,
                artifacts=artifacts,
                shim_events=read_runner_shim(page),
                profile=profile,
                terminal_outcome=terminal_outcome,
                runtime_trace=runtime_trace,
                coach_render_log=coach_render_log,
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
