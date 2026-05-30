from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from persona_policy import PersonaPolicy, load_personas

DEFAULT_HTTP_REFERER = "http://localhost"
DEFAULT_APP_TITLE = "UNIQA Conversion Coach Runner"

ALLOWED_ACTIONS_BY_STEP: dict[str, list[str]] = {
    "s1_coverage_scope": ["at_doctor", "hospital", "both", "abandon"],
    "s2_for_whom": ["myself", "other_persons", "abandon"],
    "s3_quote_basics": ["submit", "abandon"],
    "s4_initial_price": ["select_start", "select_optimal", "select_opt_plus", "select_premium", "back", "abandon"],
    "s5_add_ons": ["continue", "continue_with_first_addon", "abandon"],
    "s6_personal_medical_data": ["continue", "abandon"],
    "s7_final_price": ["answer_no_continue", "abandon"],
    "s8_confirm": ["stop_advisor"],
}

STEP_GUIDANCE: dict[str, str] = {
    "s1_coverage_scope": "Choose the doctor-visit path unless you genuinely want an advisor-only path right now.",
    "s2_for_whom": "Choose yourself unless you intentionally want the advisor-only path for other persons.",
    "s3_quote_basics": "Submit only if the required date-of-birth and insurer info feel acceptable for this persona.",
    "s4_initial_price": "Start and Optimal stay online. Opt. Plus and Premium route to advisor handling.",
    "s5_add_ons": "Add-ons are optional. Continue is the default unless curiosity is high.",
    "s6_personal_medical_data": "Continue only if privacy friction is manageable for this persona.",
    "s7_final_price": "Answer the live questionnaire conservatively with 'no' selections if continuing.",
    "s8_confirm": "This is the current advisor-request observation boundary. Do not submit anything irreversible.",
}

PERSONA_BRIEF_FILES = {
    "franz": "persona_franz_segment_2.md",
    "judith": "persona_judith_segment_1.md",
    "peter": "persona_peter_segment_3.md",
}


@dataclass(frozen=True)
class PersonaOverlay:
    price_sensitivity: float
    trust_friction: float
    privacy_friction: float
    impatience: float
    tariff_curiosity: float
    coach_receptiveness: float


@dataclass(frozen=True)
class PersonaDecision:
    step_id: str
    action: str
    reasoning: str
    dwell_ms: int
    llm_model: str
    latency_ms: int
    fallback_used: bool
    prompt_hash: str
    candidate_set: list[str]
    overlay: PersonaOverlay
    step_context: dict[str, Any]

    def to_trace_row(self, *, decision_id: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "decision_id": decision_id,
            "step_id": self.step_id,
            "action": self.action,
            "reasoning": self.reasoning,
            "dwell_ms": self.dwell_ms,
            "llm_model": self.llm_model,
            "latency_ms": self.latency_ms,
            "fallback_used": self.fallback_used,
            "prompt_hash": self.prompt_hash,
            "candidate_set": list(self.candidate_set),
            "overlay": asdict(self.overlay),
            "step_context": self.step_context,
            "history": history,
        }


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 3)


def _persona_briefing(persona_id: str) -> str:
    root = Path(__file__).resolve().parents[1] / "case_materials"
    filename = PERSONA_BRIEF_FILES.get(persona_id)
    if not filename:
        return ""
    path = root / filename
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def generate_overlay(persona_id: str, intention: str, seed: int) -> PersonaOverlay:
    rng = random.Random(f"overlay:{persona_id}:{intention}:{seed}")
    base = {
        "franz": (1.12, 0.84, 0.82, 1.08, 1.18, 0.72),
        "judith": (1.04, 1.14, 1.08, 0.92, 0.78, 1.16),
        "peter": (0.95, 1.2, 1.18, 1.05, 0.7, 1.08),
    }.get(persona_id, (1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    intention_adjustment = {
        "purchase": (0.0, -0.05, -0.04, -0.02, 0.0, 0.06),
        "orientation": (0.06, 0.06, 0.04, 0.03, 0.02, -0.03),
        "comparison": (0.08, 0.02, 0.01, 0.02, 0.08, -0.02),
        "price_check": (0.12, 0.04, 0.02, 0.08, 0.04, -0.05),
    }.get(intention, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))

    values = []
    for offset, adjustment in zip(base, intention_adjustment):
        values.append(_clamp(offset + adjustment + rng.uniform(-0.12, 0.12), 0.55, 1.45))
    return PersonaOverlay(*values)


def _prompt_hash(messages: list[dict[str, str]], model: str) -> str:
    payload = json.dumps({"messages": messages, "model": model}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _history_excerpt(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"step_id": row["step_id"], "action": row["action"], "fallback_used": row.get("fallback_used", False)} for row in history[-4:]]


def _system_prompt(persona: PersonaPolicy, intention: str, overlay: PersonaOverlay) -> str:
    briefing = _persona_briefing(persona.persona_id)
    prompt = (
        f"You are simulating {persona.display_name} on UNIQA's private health insurance calculator.\n"
        f"Segment: {persona.segment}\n"
        f"Traits: {', '.join(persona.traits)}\n"
        f"Responds to: {', '.join(persona.responds_to)}\n"
        f"Intention: {intention}\n"
        f"Overlay: price_sensitivity={overlay.price_sensitivity}, trust_friction={overlay.trust_friction}, "
        f"privacy_friction={overlay.privacy_friction}, impatience={overlay.impatience}, "
        f"tariff_curiosity={overlay.tariff_curiosity}, coach_receptiveness={overlay.coach_receptiveness}\n"
        "Return exactly one JSON object with keys action, reasoning, dwell_ms.\n"
        "Do not output markdown or commentary outside the JSON."
    )
    if briefing:
        prompt += f"\n\nPersona briefing:\n{briefing}"
    return prompt


def _user_prompt(*, step_id: str, candidate_set: list[str], step_context: dict[str, Any], history: list[dict[str, Any]]) -> str:
    context = {
        "step_id": step_id,
        "candidate_set": candidate_set,
        "guidance": STEP_GUIDANCE.get(step_id),
        "step_context": step_context,
        "recent_history": _history_excerpt(history),
    }
    return json.dumps(context, ensure_ascii=True, sort_keys=True)


def _fallback_action(
    persona: PersonaPolicy,
    *,
    step_id: str,
    intention: str,
    seed: int,
    coach_interaction_seen: bool,
) -> tuple[str, int, str]:
    intervention_kind = "trust_reassurance" if coach_interaction_seen else None
    base = persona.action_for_step(step_id=step_id, intention=intention, intervention_kind=intervention_kind, seed=seed)
    if step_id == "s1_coverage_scope":
        action = "hospital" if base["action"] in {"request_advisor", "explore_out_of_scope_then_back"} else "at_doctor"
    elif step_id == "s2_for_whom":
        action = "other_persons" if base["action"] == "request_advisor" else "myself"
    elif step_id == "s3_quote_basics":
        action = "submit" if base["action"] == "continue" else "abandon"
    elif step_id == "s4_initial_price":
        if base["action"] == "explore_out_of_scope_then_back":
            action = "select_premium"
        elif base["action"] == "request_advisor":
            action = "select_opt_plus"
        elif base["action"] == "abandon":
            action = "abandon"
        else:
            action = "select_start" if persona.persona_id == "peter" else "select_optimal"
    elif step_id == "s5_add_ons":
        action = "continue_with_first_addon" if persona.persona_id == "franz" and base["action"] == "continue" else ("abandon" if base["action"] == "abandon" else "continue")
    elif step_id == "s6_personal_medical_data":
        action = "abandon" if base["action"] == "abandon" else "continue"
    elif step_id == "s7_final_price":
        action = "abandon" if base["action"] == "abandon" else "answer_no_continue"
    else:
        action = "stop_advisor"
    return action, int(base["dwell_ms"]), f"Fallback from persona policy ({base['action']})"


class LLMPersonaDriver:
    def __init__(
        self,
        *,
        model: str,
        api_url: str,
        temperature: float = 0.2,
        timeout_s: float = 30.0,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.api_url = api_url
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.api_key = api_key or os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("VLLM_API_KEY")
        self.http_referer = os.getenv("LLM_HTTP_REFERER")
        self.app_title = os.getenv("LLM_APP_TITLE")
        self.personas = load_personas()

    def decide(
        self,
        *,
        persona_id: str,
        intention: str,
        step_id: str,
        seed: int,
        step_context: dict[str, Any],
        history: list[dict[str, Any]],
        coach_interaction_seen: bool,
    ) -> PersonaDecision:
        persona = self.personas[persona_id]
        candidate_set = ALLOWED_ACTIONS_BY_STEP[step_id]
        overlay = generate_overlay(persona_id, intention, seed)
        messages = [
            {"role": "system", "content": _system_prompt(persona, intention, overlay)},
            {"role": "user", "content": _user_prompt(step_id=step_id, candidate_set=candidate_set, step_context=step_context, history=history)},
        ]
        prompt_hash = _prompt_hash(messages, self.model)
        started = time.time()
        parsed = self._call_llm(messages)
        latency_ms = int((time.time() - started) * 1000)
        fallback_used = parsed is None or parsed.get("action") not in candidate_set
        if fallback_used:
            action, dwell_ms, reasoning = _fallback_action(
                persona,
                step_id=step_id,
                intention=intention,
                seed=seed,
                coach_interaction_seen=coach_interaction_seen,
            )
        else:
            action = str(parsed["action"])
            reasoning = str(parsed.get("reasoning", "")).strip()[:240] or "Chose the most plausible next action for this persona."
            try:
                dwell_ms = int(parsed.get("dwell_ms", parsed.get("dwellMilliseconds", persona.base_dwell_ms)))
            except (TypeError, ValueError):
                dwell_ms = persona.base_dwell_ms
            dwell_ms = max(300, min(45_000, dwell_ms))
        return PersonaDecision(
            step_id=step_id,
            action=action,
            reasoning=reasoning,
            dwell_ms=dwell_ms,
            llm_model=self.model,
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            prompt_hash=prompt_hash,
            candidate_set=candidate_set,
            overlay=overlay,
            step_context=step_context,
        )

    def _call_llm(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        body = json.dumps({
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "featherless.ai" in self.api_url:
            headers["HTTP-Referer"] = self.http_referer or DEFAULT_HTTP_REFERER
            headers["X-Title"] = self.app_title or DEFAULT_APP_TITLE
        req = request.Request(self.api_url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, ValueError, OSError):
            return None
        try:
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None
