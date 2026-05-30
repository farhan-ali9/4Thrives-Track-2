from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _feature_keys(row: dict[str, Any]) -> list[str]:
    step_id = row.get("current_step_id") or ""
    persona_id = row.get("persona_id") or ""
    intention = row.get("intention") or ""
    run_mode = row.get("run_mode") or ""
    return [
        f"{step_id}|{persona_id}|{intention}|{run_mode}",
        f"{step_id}|{persona_id}|{intention}|*",
        f"{step_id}|{persona_id}|*|*",
        f"{step_id}|*|{intention}|*",
        f"{step_id}|*|*|*",
    ]


def train_frequency_user_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("No user-policy rows were provided")
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        chosen_action = row["chosen_action"]
        for key in _feature_keys(row):
            counters[key][chosen_action] += 1
    return {
        "model_type": "frequency_user_policy",
        "ranking_by_key": {key: counter.most_common() for key, counter in counters.items()},
    }


def save_user_policy_model(model: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, indent=2, sort_keys=True))
    return output


def load_user_policy_model(path: Path) -> dict[str, Any]:
    model = json.loads(path.read_text())
    if model.get("model_type") != "frequency_user_policy":
        raise ValueError(f"Unsupported user policy model type: {model.get('model_type')}")
    if not isinstance(model.get("ranking_by_key"), dict):
        raise ValueError("User policy model is missing ranking_by_key")
    return model


def predict_user_action(model: dict[str, Any], row: dict[str, Any]) -> str | None:
    rankings = model.get("ranking_by_key", {})
    allowed = set(row.get("candidate_actions", []))
    for key in _feature_keys(row):
        ranking = rankings.get(key, [])
        for candidate, _count in ranking:
            if not allowed or candidate in allowed:
                return candidate
    return None
