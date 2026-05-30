from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = ["price_transparency", "trust_reassurance", "simplify_next_step", "advisor_handoff"]


def load_ranker(path: Path) -> dict[str, Any]:
    model = json.loads(path.read_text())
    if model.get("model_type") != "frequency_action_ranker":
        raise ValueError(f"Unsupported ranker model type: {model.get('model_type')}")
    if not isinstance(model.get("ranking_by_step"), dict):
        raise ValueError("Ranker model is missing ranking_by_step")
    return model


def rank_candidates(model: dict[str, Any], *, step_id: str | None, candidates: list[str] | None = None) -> list[str]:
    allowed = candidates or DEFAULT_CANDIDATES
    allowed_set = set(allowed)
    ranking = model.get("ranking_by_step", {}).get(step_id or "", [])
    if not ranking:
        return []
    ordered = [candidate for candidate, _count in ranking if candidate in allowed_set]
    ordered.extend(candidate for candidate in allowed if candidate not in ordered)
    return ordered


def predict_action(model: dict[str, Any], *, step_id: str | None, candidates: list[str] | None = None) -> str | None:
    ranking = rank_candidates(model, step_id=step_id, candidates=candidates)
    return ranking[0] if ranking else None
