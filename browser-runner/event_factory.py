from __future__ import annotations

import time
import uuid
from typing import Any

from persona_policy import canonicalize_step_id

JsonDict = dict[str, Any]


def now_ms() -> int:
    return int(time.time() * 1000)


def make_runner_event(
    *,
    session_id: str,
    event_type: str,
    step_id: str | None,
    element_key: str | None = None,
    raw_value: JsonDict | None = None,
    derived_context: JsonDict | None = None,
    runner_metadata: JsonDict | None = None,
    event_id: str | None = None,
    ts: int | None = None,
    source: str = "browser-runner",
) -> JsonDict:
    value = raw_value or {}
    context = derived_context or {}
    return {
        "schema_version": "v1",
        "event_id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "session_id": session_id,
        "ts": ts if ts is not None else now_ms(),
        "source": source,
        "step_id": canonicalize_step_id(step_id),
        "event_type": event_type,
        "element_key": element_key,
        "raw_value": value,
        "derived_signals": derive_signal_flags(event_type=event_type, element_key=element_key, raw_value=value, derived_context=context),
        "derived_context": context,
        "runner_metadata": runner_metadata or {},
        "privacy_level": "anonymous",
    }


def make_step_event(*, session_id: str, step_id: str, event_type: str = "step_enter", runner_metadata: JsonDict | None = None) -> JsonDict:
    if event_type not in {"step_enter", "step_leave", "step_resolved"}:
        raise ValueError("step event_type must be step_enter, step_leave, or step_resolved")
    return make_runner_event(session_id=session_id, event_type=event_type, step_id=step_id, element_key=canonicalize_step_id(step_id), runner_metadata=runner_metadata)


def make_coach_event(
    *,
    session_id: str,
    step_id: str | None,
    event_type: str,
    decision_id: str,
    action_id: str,
    runner_metadata: JsonDict | None = None,
) -> JsonDict:
    if event_type not in {"coach_impression", "coach_cta", "coach_dismiss"}:
        raise ValueError("coach event_type must be coach_impression, coach_cta, or coach_dismiss")
    return make_runner_event(
        session_id=session_id,
        event_type=event_type,
        step_id=step_id,
        element_key=action_id,
        raw_value={"decision_id": decision_id, "action_id": action_id},
        derived_context={"decision_id": decision_id, "action_id": action_id},
        runner_metadata=runner_metadata,
    )


def derive_signal_flags(*, event_type: str, element_key: str | None, raw_value: JsonDict, derived_context: JsonDict | None = None) -> JsonDict:
    signals: JsonDict = {}
    intent = raw_value.get("intent")
    option = str(raw_value.get("option", "")).lower()
    target = raw_value.get("target")

    if intent == "out_of_scope_tariff" or option in {"opt_plus", "premium"}:
        signals["tariff_click_oos"] = True
        signals["path_oos"] = True
    if intent == "out_of_scope_path" or option in {"krankenhaus", "andere_personen", "other_persons", "hospital"}:
        signals["path_oos"] = True
    if event_type == "inactivity" or "idleMs" in raw_value:
        signals["inactivity"] = True
    if event_type == "pointerenter" and target == "price":
        signals["price_hover"] = True
    if event_type == "pointerenter" and target == "cancel":
        signals["cancel_hover"] = True
    if event_type == "scroll":
        signals["scroll"] = True
    if event_type == "coach_dismiss":
        signals["coach_dismissed"] = True
    if event_type == "coach_cta":
        signals["coach_cta_clicked"] = True
    if derived_context and derived_context.get("priceDelta") not in (None, 0):
        signals["price_changed"] = True
    if element_key in {"consultationContact", "berateranfrage", "advisor_cta"}:
        signals["advisor_terminal"] = True
    return signals
