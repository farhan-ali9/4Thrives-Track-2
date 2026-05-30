from __future__ import annotations

from typing import Any


def render_timeline(trace: dict[str, Any]) -> str:
    outcome = trace.get("terminal_outcome") or (trace.get("outcome") or {}).get("outcome") or "unknown"
    lines = [f"Session: {trace.get('session_id', 'unknown')}", f"Outcome: {outcome}", ""]
    for event in trace.get("events", []):
        decision = event.get("derived_context", {}).get("intervention_kind") or "none"
        action = event.get("raw_value", {}).get("action") or event.get("event_type")
        lines.append(f"{event.get('ts')} | {event.get('step_id')} | {event.get('element_key')} | action={action} | intervention={decision}")
    if trace.get("decisions"):
        lines.extend(["", "Decisions:"])
        for decision in trace["decisions"]:
            lines.append(
                f"{decision.get('decision_id')} | action={decision.get('chosen_action_id')} | "
                f"risk={decision.get('risk_score')} | latency_ms={decision.get('latency_ms')}"
            )
    if trace.get("exposures"):
        lines.extend(["", "Exposures:"])
        for exposure in trace["exposures"]:
            lines.append(
                f"{exposure.get('exposure_id')} | decision={exposure.get('decision_id')} | "
                f"action={exposure.get('action_id')} | render_success={exposure.get('render_success')}"
            )
    return "\n".join(lines)
