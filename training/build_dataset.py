from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "replay"))
from trace_store import load_traces, normalize_trace

DEFAULT_CANDIDATES = ["price_transparency", "trust_reassurance", "simplify_next_step", "advisor_handoff"]


def build_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    trace = normalize_trace(trace)
    event_examples = _build_event_decision_examples(trace, dataset_phase)
    backend_examples = _build_backend_decision_examples(trace, dataset_phase)
    return event_examples + backend_examples


def _build_event_decision_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    examples = []
    prefix = []
    for event in trace.get("events", []):
        intervention = event.get("derived_context", {}).get("intervention_kind")
        prefix.append(event)
        if not intervention:
            continue
        metadata = event.get("runner_metadata") or trace.get("metadata", {})
        examples.append({
            "session_id": trace.get("session_id"),
            "decision_id": event.get("event_id"),
            "trace_prefix": prefix[:-1],
            "current_step_id": event.get("step_id"),
            "page_map_version": metadata.get("page_map_version"),
            "extension_version": metadata.get("extension_build_id"),
            "model_version_or_baseline": metadata.get("model_version_or_policy"),
            "candidate_set": DEFAULT_CANDIDATES,
            "guardrail_filtered_candidates": [intervention],
            "chosen_candidate": intervention,
            "exposure_result": "shown" if event.get("event_type") != "render_failed" else "failed",
            "future_outcome_summary": trace.get("terminal_outcome"),
            "runner_metadata": metadata,
            "dataset_phase": dataset_phase,
        })
    return examples


def _build_backend_decision_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    examples = []
    events = trace.get("events", [])
    exposures_by_decision = {exposure.get("decision_id"): exposure for exposure in trace.get("exposures", [])}
    metadata = trace.get("metadata", {})
    for decision in trace.get("decisions", []):
        decision_id = decision.get("decision_id")
        chosen = decision.get("chosen_action_id")
        if not decision_id or not chosen:
            continue
        created_at_ts = _decision_created_ts(decision)
        prefix = [event for event in events if created_at_ts is None or event.get("ts", 0) <= created_at_ts]
        current_step_id = prefix[-1].get("step_id") if prefix else None
        guardrail_candidates = _guardrail_candidates(decision) or [chosen]
        exposure = exposures_by_decision.get(decision_id)
        examples.append({
            "session_id": trace.get("session_id"),
            "decision_id": decision_id,
            "trace_prefix": prefix,
            "current_step_id": current_step_id,
            "page_map_version": metadata.get("page_map_version"),
            "extension_version": metadata.get("extension_build_id"),
            "model_version_or_baseline": decision.get("model_version") or metadata.get("model_version_or_policy"),
            "candidate_set": sorted(set(DEFAULT_CANDIDATES + guardrail_candidates + [chosen])),
            "guardrail_filtered_candidates": guardrail_candidates,
            "chosen_candidate": chosen,
            "exposure_result": _exposure_result(exposure),
            "future_outcome_summary": trace.get("terminal_outcome"),
            "runner_metadata": metadata,
            "dataset_phase": dataset_phase,
        })
    return examples


def _decision_created_ts(decision: dict[str, Any]) -> int | None:
    created = decision.get("created_at")
    if isinstance(created, (int, float)):
        return int(created)
    return None


def _guardrail_candidates(decision: dict[str, Any]) -> list[str]:
    candidates = []
    for guardrail in decision.get("guardrail_decisions", []) or []:
        outcome = guardrail.get("outcome") if isinstance(guardrail, dict) else None
        if outcome:
            candidates.append(str(outcome))
    return candidates


def _exposure_result(exposure: dict[str, Any] | None) -> str:
    if not exposure:
        return "not_recorded"
    if exposure.get("render_success") is False:
        return "failed"
    if exposure.get("cta_ts") is not None:
        return "cta"
    if exposure.get("dismiss_ts") is not None:
        return "dismissed"
    if exposure.get("impression_ts") is not None:
        return "shown"
    return "recorded"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build action-ranking examples from real trace decision points")
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-phase", default="behavioral_imitation_bootstrap")
    args = parser.parse_args()
    examples = [example for trace in load_traces(args.traces) for example in build_examples(trace, args.dataset_phase)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(example, sort_keys=True) for example in examples) + ("\n" if examples else ""))
    print(json.dumps({"examples": len(examples), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
