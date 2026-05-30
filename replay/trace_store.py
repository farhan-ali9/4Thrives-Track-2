from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "session_id",
    "ts",
    "source",
    "step_id",
    "event_type",
    "element_key",
    "raw_value",
    "derived_signals",
    "derived_context",
    "privacy_level",
}
TERMINAL_OUTCOMES = {"converted_online", "abandoned", "advisor_handoff"}


def normalize_trace(data: dict[str, Any]) -> dict[str, Any]:
    if "session_id" in data and "terminal_outcome" in data:
        trace = dict(data)
    elif "sessionId" in data:
        trace = _normalize_repository_trace(data)
    elif "session_id" in data and {"decisions", "exposures", "outcome"}.intersection(data):
        trace = _normalize_v2_export_trace(data)
    else:
        trace = dict(data)
    trace.setdefault("events", [])
    trace.setdefault("decisions", [])
    trace.setdefault("exposures", [])
    return trace


def _normalize_repository_trace(data: dict[str, Any]) -> dict[str, Any]:
    snake = {
        "session_id": data.get("sessionId"),
        "events": data.get("events", []),
        "decisions": data.get("decisions", []),
        "exposures": data.get("exposures", []),
        "outcome": data.get("outcome"),
    }
    return _normalize_v2_export_trace(snake)


def _normalize_v2_export_trace(data: dict[str, Any]) -> dict[str, Any]:
    session_id = data.get("session_id")
    outcome = data.get("outcome") if isinstance(data.get("outcome"), dict) else None
    terminal = outcome.get("outcome") if outcome else data.get("terminal_outcome")
    decisions = data.get("decisions", []) if isinstance(data.get("decisions", []), list) else []
    exposures = data.get("exposures", []) if isinstance(data.get("exposures", []), list) else []
    events = [_normalize_event(event, session_id=session_id) for event in data.get("events", [])]
    return {
        "session_id": session_id,
        "terminal_outcome": terminal,
        "events": events,
        "decisions": decisions,
        "exposures": exposures,
        "outcome": outcome,
    }


def _normalize_event(event: dict[str, Any], *, session_id: str | None) -> dict[str, Any]:
    normalized = dict(event)
    normalized.setdefault("schema_version", event.get("schemaVersion", "v1"))
    normalized.setdefault("event_id", event.get("eventId"))
    normalized.setdefault("session_id", event.get("sessionId", session_id))
    normalized.setdefault("source", event.get("source", "backend_export"))
    normalized.setdefault("step_id", event.get("stepId"))
    normalized.setdefault("event_type", event.get("eventType"))
    normalized.setdefault("element_key", event.get("elementKey"))
    normalized.setdefault("raw_value", event.get("rawValue", {}))
    normalized.setdefault("derived_signals", event.get("derivedSignals", {}))
    normalized.setdefault("derived_context", event.get("derivedContext", {}))
    normalized.setdefault("runner_metadata", event.get("runnerMetadata", {}))
    normalized.setdefault("privacy_level", event.get("privacyLevel", "anonymous"))
    if isinstance(normalized.get("ts"), float) and normalized["ts"].is_integer():
        normalized["ts"] = int(normalized["ts"])
    return normalized


def load_trace_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "events" in data:
        return normalize_trace(data)
    if isinstance(data, dict) and "session" in data and "events" in data["session"]:
        return normalize_trace(data["session"])
    raise ValueError(f"{path} is not a supported session trace file")


def load_traces(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        return [load_trace_file(item) for item in sorted(path.glob("*.json"))]
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return [normalize_trace(item) for item in data]
    if isinstance(data, dict) and "sessions" in data and isinstance(data["sessions"], list):
        return [normalize_trace(item) for item in data["sessions"]]
    return [load_trace_file(path)]


def validate_trace(trace: dict[str, Any]) -> list[str]:
    trace = normalize_trace(trace)
    errors: list[str] = []
    session_id = trace.get("session_id")
    if not session_id:
        errors.append("missing session_id")
    events = trace.get("events")
    if not isinstance(events, list) or not events:
        errors.append("missing events")
        return errors
    outcome = trace.get("terminal_outcome") or trace.get("outcome")
    if outcome not in TERMINAL_OUTCOMES:
        errors.append("missing or invalid terminal_outcome")
    previous_ts = None
    for index, event in enumerate(events):
        missing = sorted(REQUIRED_EVENT_FIELDS - set(event))
        if missing:
            errors.append(f"event[{index}] missing fields: {', '.join(missing)}")
        if session_id and event.get("session_id") != session_id:
            errors.append(f"event[{index}] session_id mismatch")
        if event.get("privacy_level") != "anonymous":
            errors.append(f"event[{index}] privacy_level must be anonymous")
        ts = event.get("ts")
        if not isinstance(ts, int):
            errors.append(f"event[{index}] ts must be integer ms")
        elif previous_ts is not None and ts < previous_ts:
            errors.append(f"event[{index}] timestamp moved backwards")
        if isinstance(ts, int):
            previous_ts = ts
        metadata = event.get("runner_metadata") or trace.get("metadata", {})
        if metadata:
            for key in ["runner_id", "experiment_id", "persona_id", "intention", "seed", "backend_url", "model_version_or_policy"]:
                if key not in metadata:
                    errors.append(f"event[{index}] metadata missing {key}")
    return errors


def summarize_validation(traces: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = []
    for trace in traces:
        normalized = normalize_trace(trace)
        errors = validate_trace(normalized)
        if errors:
            invalid.append({"session_id": normalized.get("session_id"), "errors": errors})
    return {"traces": len(traces), "valid": len(traces) - len(invalid), "invalid": invalid}
