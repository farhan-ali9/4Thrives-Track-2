from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "replay"))
from trace_store import load_traces, normalize_trace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dataset import DEFAULT_CANDIDATES, build_examples


RULE_BASED_INTERVENTIONS_BY_STEP = {
    "s4_initial_price": "price_transparency",
    "s7_final_price": "price_transparency",
}


def build_user_policy_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    normalized = normalize_trace(trace)
    metadata = normalized.get("metadata", {})
    decisions = normalized.get("llm_decisions", [])
    examples = []
    for decision in decisions:
        history = decision.get("history", [])
        step_context = decision.get("step_context", {})
        examples.append({
            "session_id": normalized.get("session_id"),
            "decision_id": decision.get("decision_id"),
            "trace_prefix": history,
            "current_step_id": decision.get("step_id"),
            "persona_id": metadata.get("persona_id"),
            "intention": metadata.get("intention"),
            "seed": metadata.get("seed"),
            "run_mode": normalized.get("run_mode") or metadata.get("run_mode"),
            "llm_model": decision.get("llm_model") or metadata.get("llm_model"),
            "candidate_actions": decision.get("candidate_set", []),
            "chosen_action": decision.get("action"),
            "future_outcome_summary": normalized.get("terminal_outcome"),
            "fallback_used": decision.get("fallback_used", False),
            "prompt_hash": decision.get("prompt_hash"),
            "step_context": step_context,
            "runner_metadata": metadata,
            "dataset_phase": dataset_phase,
        })
    return examples


def build_coach_ranking_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    normalized = normalize_trace(trace)
    metadata = normalized.get("metadata", {})
    run_mode = normalized.get("run_mode") or metadata.get("run_mode")
    if run_mode != "coach" and not normalized.get("decisions"):
        return []
    examples = build_examples(normalized, dataset_phase)
    if examples:
        return examples
    return _build_rule_based_bootstrap_examples(normalized, dataset_phase)


def _build_rule_based_bootstrap_examples(trace: dict[str, Any], dataset_phase: str) -> list[dict[str, Any]]:
    metadata = trace.get("metadata", {})
    if (trace.get("run_mode") or metadata.get("run_mode")) != "coach":
        return []
    if metadata.get("model_version_or_policy") != "rule-based":
        return []

    examples = []
    prefix = []
    for decision in trace.get("llm_decisions", []):
        step_id = decision.get("step_id")
        chosen = RULE_BASED_INTERVENTIONS_BY_STEP.get(step_id)
        if chosen:
            examples.append({
                "session_id": trace.get("session_id"),
                "decision_id": decision.get("decision_id"),
                "trace_prefix": list(prefix),
                "current_step_id": step_id,
                "page_map_version": metadata.get("page_map_version"),
                "extension_version": metadata.get("extension_build_id"),
                "model_version_or_baseline": metadata.get("model_version_or_policy"),
                "candidate_set": DEFAULT_CANDIDATES,
                "guardrail_filtered_candidates": [chosen],
                "chosen_candidate": chosen,
                "exposure_result": "not_recorded",
                "future_outcome_summary": trace.get("terminal_outcome"),
                "runner_metadata": metadata,
                "dataset_phase": dataset_phase,
            })
        prefix.append({
            "decision_id": decision.get("decision_id"),
            "step_id": step_id,
            "action": decision.get("action"),
            "step_context": decision.get("step_context", {}),
        })
    return examples


def build_live_datasets(*, traces_path: Path, user_output: Path, coach_output: Path, user_dataset_phase: str, coach_dataset_phase: str) -> dict[str, Any]:
    traces = load_traces(traces_path)
    user_examples = [row for trace in traces for row in build_user_policy_examples(trace, user_dataset_phase)]
    coach_examples = [row for trace in traces for row in build_coach_ranking_examples(trace, coach_dataset_phase)]
    user_output.parent.mkdir(parents=True, exist_ok=True)
    coach_output.parent.mkdir(parents=True, exist_ok=True)
    user_output.write_text("\n".join(json.dumps(row, sort_keys=True) for row in user_examples) + ("\n" if user_examples else ""))
    coach_output.write_text("\n".join(json.dumps(row, sort_keys=True) for row in coach_examples) + ("\n" if coach_examples else ""))
    return {
        "traces": len(traces),
        "user_policy_examples": len(user_examples),
        "coach_ranking_examples": len(coach_examples),
        "user_output": str(user_output),
        "coach_output": str(coach_output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build user-policy and coach-ranking datasets from live browser traces")
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--user-output", type=Path, default=Path("artifacts/datasets/user-policy.jsonl"))
    parser.add_argument("--coach-output", type=Path, default=Path("artifacts/datasets/coach-ranking.jsonl"))
    parser.add_argument("--user-dataset-phase", default="behavioral_imitation_live")
    parser.add_argument("--coach-dataset-phase", default="coach_ranking_live")
    args = parser.parse_args()
    print(json.dumps(
        build_live_datasets(
            traces_path=args.traces,
            user_output=args.user_output,
            coach_output=args.coach_output,
            user_dataset_phase=args.user_dataset_phase,
            coach_dataset_phase=args.coach_dataset_phase,
        ),
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
