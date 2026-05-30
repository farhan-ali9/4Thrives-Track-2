from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_INTENTIONS = {"purchase", "orientation", "comparison", "price_check"}
TERMINAL_OUTCOMES = {"converted_online", "abandoned", "advisor_handoff"}
LIVE_UNIQA_STEPS = [
    "s1_coverage_scope",
    "s2_for_whom",
    "s3_quote_basics",
    "s4_initial_price",
    "s5_add_ons",
    "s6_personal_medical_data",
    "s7_final_price",
    "s8_confirm",
]
STEP_ALIASES = {
    "s1_entry": "s1_coverage_scope",
    "s2_needs": "s2_for_whom",
    "s3_tariff_choice": "s3_quote_basics",
    "s5_addons": "s5_add_ons",
    "s6_personal_details": "s6_personal_medical_data",
}
ONLINE_STEPS = LIVE_UNIQA_STEPS
OUT_OF_SCOPE_ELEMENTS = {"hospital", "other_persons", "opt_plus", "premium"}
ADVISOR_TERMINAL_ELEMENTS = {"consultationContact", "advisor_cta", "berateranfrage"}


@dataclass(frozen=True)
class PersonaPolicy:
    persona_id: str
    display_name: str
    segment: str
    traits: tuple[str, ...]
    responds_to: tuple[str, ...]
    base_dwell_ms: int
    intentions: dict[str, dict[str, float]]
    key_cases: tuple[str, ...]
    coach_affinity: dict[str, float]

    @classmethod
    def from_file(cls, path: Path) -> "PersonaPolicy":
        data = json.loads(path.read_text())
        missing = VALID_INTENTIONS - set(data["intentions"])
        if missing:
            raise ValueError(f"{path} is missing intentions: {sorted(missing)}")
        return cls(
            persona_id=data["persona_id"],
            display_name=data["display_name"],
            segment=data["segment"],
            traits=tuple(data.get("traits", [])),
            responds_to=tuple(data.get("responds_to", [])),
            base_dwell_ms=int(data["base_dwell_ms"]),
            intentions=data["intentions"],
            key_cases=tuple(data.get("key_cases", [])),
            coach_affinity={k: float(v) for k, v in data.get("coach_affinity", {}).items()},
        )

    def action_for_step(
        self,
        *,
        step_id: str,
        intention: str,
        intervention_kind: str | None = None,
        seed: int = 0,
    ) -> dict[str, Any]:
        if intention not in VALID_INTENTIONS:
            raise ValueError(f"Unsupported intention: {intention}")

        rng = random.Random(f"{self.persona_id}:{intention}:{step_id}:{intervention_kind}:{seed}")
        weights = self.intentions[intention]
        dwell = int(self.base_dwell_ms * float(weights["dwell_multiplier"]) * rng.uniform(0.75, 1.35))
        continue_bias = float(weights["continue_bias"])
        abandon_bias = float(weights["abandon_bias"])
        advisor_bias = float(weights["advisor_bias"])

        if intervention_kind:
            affinity = self.coach_affinity.get(intervention_kind, 0.5)
            continue_bias += max(0.0, affinity - 0.5) * 0.25
            abandon_bias -= max(0.0, affinity - 0.5) * 0.18
            if intervention_kind == "advisor_handoff":
                advisor_bias += affinity * 0.20

        canonical_step = canonicalize_step_id(step_id)
        if canonical_step == "s4_initial_price" and self.persona_id == "judith":
            dwell = int(dwell * 1.35)
        if canonical_step == "s7_final_price":
            abandon_bias += 0.15 if self.persona_id in {"franz", "judith"} else 0.08
        if canonical_step in {"s2_for_whom", "s3_quote_basics"} and self.persona_id == "peter":
            abandon_bias += 0.12
            advisor_bias += 0.08

        total = max(0.01, continue_bias) + max(0.01, abandon_bias) + max(0.01, advisor_bias)
        roll = rng.random() * total
        if roll < max(0.01, advisor_bias):
            action = "request_advisor"
        elif roll < max(0.01, advisor_bias) + max(0.01, abandon_bias):
            action = "abandon"
        else:
            action = "continue"

        if "click_premium_once" in self.key_cases and canonical_step == "s3_quote_basics" and rng.random() < 0.35:
            action = "explore_out_of_scope_then_back"
            element_key = "premium"
        elif action == "request_advisor":
            element_key = "advisor_cta"
        elif action == "abandon":
            element_key = "close_or_back"
        else:
            element_key = "primary_continue"

        return {
            "persona_id": self.persona_id,
            "intention": intention,
            "step_id": canonical_step,
            "action": action,
            "element_key": element_key,
            "dwell_ms": max(250, dwell),
        }


def canonicalize_step_id(step_id: str | None) -> str | None:
    if step_id is None:
        return None
    return STEP_ALIASES.get(step_id, step_id)


def load_personas(persona_dir: Path | None = None) -> dict[str, PersonaPolicy]:
    root = persona_dir or Path(__file__).resolve().parents[1] / "personas"
    personas = {}
    for path in sorted(root.glob("*.json")):
        if path.name == "variants.json" or path.name.startswith("._"):
            continue
        policy = PersonaPolicy.from_file(path)
        personas[policy.persona_id] = policy
    return personas


def classify_outcome(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        outcome = event.get("terminal_outcome") or event.get("outcome")
        if outcome in TERMINAL_OUTCOMES:
            return outcome
        element_key = event.get("element_key")
        derived_context = event.get("derived_context", {}) if isinstance(event.get("derived_context", {}), dict) else {}
        if element_key in OUT_OF_SCOPE_ELEMENTS or event.get("action") == "request_advisor":
            return "advisor_handoff"
        if canonicalize_step_id(event.get("step_id")) == "s8_confirm" and (
            element_key in ADVISOR_TERMINAL_ELEMENTS
            or derived_context.get("terminalScreen") == "advisor_handoff"
            or derived_context.get("screenTitle") == "Berateranfrage"
        ):
            return "advisor_handoff"
        if event.get("event_type") == "purchase_submitted":
            return "converted_online"
        if event.get("action") == "abandon" or event.get("event_type") in {"abandon", "page_close"}:
            return "abandoned"
    last_step = events[-1].get("step_id") if events else None
    return "converted_online" if last_step == "s8_confirm" else "abandoned"
