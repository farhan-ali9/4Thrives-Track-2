from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

ONLINE_CONVERSION = "converted_online"
ADVISOR_LEAD = "submitted_advisor_lead"
ADVISOR_HANDOFF = "advisor_handoff"
ABANDONED = "abandoned"
DROP_STEPS = ["s4_initial_price", "s5_add_ons", "s7_final_price"]
STEP_ALIASES = {"s5_addons": "s5_add_ons", "s6_personal_details": "s6_personal_medical_data", "s3_tariff_choice": "s3_quote_basics"}
OUT_OF_SCOPE_ELEMENTS = {"hospital", "other_persons", "opt_plus", "premium"}
EXPECTED_STEPS_PER_SESSION = 8


def _outcome(trace: dict[str, Any]) -> str:
    outcome = trace.get("terminal_outcome") or trace.get("outcome") or "abandoned"
    if outcome == ADVISOR_HANDOFF:
        return ADVISOR_LEAD
    return outcome


def _metadata(trace: dict[str, Any], event: dict[str, Any] | None = None) -> dict[str, Any]:
    if event and event.get("runner_metadata"):
        return event["runner_metadata"]
    return trace.get("metadata", {})


def _step_id(step: str | None) -> str | None:
    if step is None:
        return None
    return STEP_ALIASES.get(step, step)


def _is_out_of_scope_event(event: dict[str, Any]) -> bool:
    element_key = event.get("element_key")
    return element_key in OUT_OF_SCOPE_ELEMENTS or event.get("event_type") == "out_of_scope_selected"


def compute_metrics(traces: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(traces)
    outcomes = Counter(_outcome(trace) for trace in traces)
    dropoffs = Counter()
    persona_totals = Counter()
    persona_conversions = Counter()
    intention_totals = Counter()
    intention_conversions = Counter()
    persona_step_dropoffs: Counter[tuple[str, str]] = Counter()
    intervention_count = 0
    rendered = 0
    accepted = 0
    dismissed = 0
    annoyed = 0
    eligible_decisions = 0
    relevant_interventions = 0
    advisor_required = 0
    advisor_correct = 0
    step_events = 0
    complete_traces = 0
    selector_failures = 0
    backend_timeouts = 0
    latencies = []
    popup_steps = 0
    popup_rendered = 0
    popup_timeouts = 0
    popup_cta = 0
    popup_dismiss = 0

    for trace in traces:
        events = trace.get("events", [])
        coach_render_log = trace.get("coach_render_log", [])
        metadata = _metadata(trace, events[0] if events else None)
        persona = metadata.get("persona_id", "unknown")
        intention = metadata.get("intention", "unknown")
        outcome = _outcome(trace)
        persona_totals[persona] += 1
        intention_totals[intention] += 1
        if outcome == ONLINE_CONVERSION:
            persona_conversions[persona] += 1
            intention_conversions[intention] += 1
        if events:
            complete_traces += 1
        seen_steps = {_step_id(event.get("step_id")) for event in events if event.get("step_id")}
        step_events += len(seen_steps)

        out_of_scope_seen = any(_is_out_of_scope_event(event) for event in events)
        if out_of_scope_seen:
            advisor_required += 1
            if outcome == ADVISOR_LEAD:
                advisor_correct += 1

        if outcome == ABANDONED:
            for step in reversed([_step_id(event.get("step_id")) for event in events]):
                if step in DROP_STEPS:
                    dropoffs[step] += 1
                    persona_step_dropoffs[(persona, step)] += 1
                    break

        for event in events:
            event_type = event.get("event_type")
            if event_type in {"selector_missing", "selector_drift"}:
                selector_failures += 1
            if event_type in {"backend_timeout", "inference_timeout"}:
                backend_timeouts += 1
            if event_type == "coach_cta":
                popup_cta += 1
            if event_type == "coach_dismiss":
                popup_dismiss += 1
            latency = event.get("derived_context", {}).get("inference_latency_ms")
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))
            kind = event.get("derived_context", {}).get("intervention_kind")
            if kind:
                intervention_count += 1
                if event_type != "render_failed":
                    rendered += 1
                if event_type in {"cta_click", "intervention_accepted"} or event.get("raw_value", {}).get("action") == "accept_intervention":
                    accepted += 1
                if event_type in {"dismiss", "intervention_dismissed"} or event.get("raw_value", {}).get("action") == "dismiss_intervention":
                    dismissed += 1
                if event.get("derived_signals", {}).get("annoyed") or event_type == "annoyance_signal":
                    annoyed += 1
                if outcome in {ONLINE_CONVERSION, ADVISOR_HANDOFF}:
                    relevant_interventions += 1
            if event.get("derived_context", {}).get("eligible_for_intervention") or kind:
                eligible_decisions += 1

        for row in coach_render_log:
            popup_steps += 1
            if row.get("rendered"):
                popup_rendered += 1
            if row.get("decision_state") == "timeout":
                popup_timeouts += 1

    rate = lambda count: (count / total) if total else 0.0
    return {
        "sessions": total,
        "online_conversion_rate": rate(outcomes[ONLINE_CONVERSION]),
        "advisor_lead_submission_rate": rate(outcomes[ADVISOR_LEAD]),
        "advisor_lead_count": outcomes[ADVISOR_LEAD] + outcomes[ADVISOR_HANDOFF],
        "advisor_handoff_count": outcomes[ADVISOR_LEAD] + outcomes[ADVISOR_HANDOFF],
        "abandonment_rate": rate(outcomes[ABANDONED]),
        "s4_initial_price_dropoff": dropoffs["s4_initial_price"],
        "s5_addon_dropoff": dropoffs["s5_add_ons"],
        "s7_final_price_dropoff": dropoffs["s7_final_price"],
        "conversion_by_persona": {persona: persona_conversions[persona] / count for persona, count in persona_totals.items()},
        "conversion_by_intention": {intention: intention_conversions[intention] / count for intention, count in intention_totals.items()},
        "dropoff_by_persona_step": {f"{persona}:{step}": count for (persona, step), count in persona_step_dropoffs.items()},
        "advisor_routing_correctness": advisor_correct / advisor_required if advisor_required else 1.0,
        "intervention_count": intervention_count,
        "intervention_volume_per_session": intervention_count / total if total else 0.0,
        "impression_to_cta_rate": accepted / rendered if rendered else 0.0,
        "acceptance_rate": accepted / intervention_count if intervention_count else 0.0,
        "dismiss_rate": dismissed / intervention_count if intervention_count else 0.0,
        "annoyance_rate": annoyed / intervention_count if intervention_count else 0.0,
        "intervention_precision": relevant_interventions / intervention_count if intervention_count else 1.0,
        "intervention_recall": intervention_count / eligible_decisions if eligible_decisions else 1.0,
        "extension_render_success_rate": rendered / intervention_count if intervention_count else 1.0,
        "step_detection_success_rate": step_events / (total * EXPECTED_STEPS_PER_SESSION) if total else 0.0,
        "selector_drift_rate": selector_failures / total if total else 0.0,
        "backend_timeout_rate": backend_timeouts / total if total else 0.0,
        "inference_latency_ms_avg": mean(latencies) if latencies else 0.0,
        "trace_completeness_rate": complete_traces / total if total else 0.0,
        "popup_render_rate": popup_rendered / popup_steps if popup_steps else 0.0,
        "popup_rendered_steps": popup_rendered,
        "popup_steps": popup_steps,
        "popup_timeout_count": popup_timeouts,
        "popup_cta_count": popup_cta,
        "popup_dismiss_count": popup_dismiss,
    }


def compare_dropoff_reduction(baseline: dict[str, Any], treatment: dict[str, Any]) -> dict[str, float]:
    return {
        "s4_dropoff_reduction": baseline.get("s4_initial_price_dropoff", 0) - treatment.get("s4_initial_price_dropoff", 0),
        "s5_dropoff_reduction": baseline.get("s5_addon_dropoff", 0) - treatment.get("s5_addon_dropoff", 0),
        "s7_dropoff_reduction": baseline.get("s7_final_price_dropoff", 0) - treatment.get("s7_final_price_dropoff", 0),
        "conversion_rate_uplift": treatment.get("online_conversion_rate", 0.0) - baseline.get("online_conversion_rate", 0.0),
    }
