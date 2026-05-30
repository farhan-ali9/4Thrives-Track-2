"""LLM-backed PersonaBot.

Drop-in replacement for `PersonaBot` that delegates `decide()` to an
OpenAI-compatible gateway. Same return shape, same persona parameters used as
system-prompt grounding. Falls back to the rule-based parent on any
API / parse error so a single bad request never breaks a journey.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests

from .journey import Step, StepContext
from .personas import Decision, Persona, PersonaBot
from .signals import Signal, SignalKind

# Default to Featherless AI (OpenAI-compatible). Override via env:
#   LLM_GATEWAY_URL, LLM_DEFAULT_MODEL
# API key is read from FEATHERLESS_API_KEY, then GROQ_API_KEY, then LOVABLE_API_KEY.
GATEWAY_URL = os.environ.get(
    "LLM_GATEWAY_URL",
    "https://api.featherless.ai/v1/chat/completions",
)
DEFAULT_MODEL = os.environ.get(
    "LLM_DEFAULT_MODEL",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
)


ALLOWED_ACTIONS: dict[Step, list[str]] = {
    Step.S1_COVERAGE_SCOPE: ["at_doctor", "hospital", "both"],
    Step.S2_FOR_WHOM: ["myself", "other_persons"],
    Step.S3_PERSONAL_DATA: ["submit", "abandon"],
    Step.S4_INITIAL_PRICE: [
        "select_optimal", "select_start", "select_opt_plus",
        "select_premium", "back", "abandon",
    ],
    Step.S5_ADD_ONS: ["continue", "abandon"],
    Step.S6_HEALTH_QUESTIONS: ["continue", "abandon"],
    Step.S7_FINAL_PRICE: ["confirm", "abandon"],
    Step.S8_CONFIRM: ["confirm", "abandon"],
}

BLURBS = {
    "judith": ("Segment 1 - Rising Hybrid. 32, researches online but seeks "
               "reassurance before paying. Trusts UNIQA brand. Cautious "
               "with personal data. Highly coachable when transparency is "
               "offered."),
    "franz":  ("Segment 2 - Online Affine. 45, self-directed, price-aware, "
               "tech-comfortable. Curious about premium tariffs and will "
               "click them, then bounce when they require an advisor. "
               "Low patience for hand-holding."),
    "peter":  ("Segment 3 - Service Affine. 58, prefers talking to an "
               "advisor. High trust threshold for online forms, slow to "
               "submit personal data, easily annoyed by long flows."),
}

# Locate the UNIQA case-material briefings. They are bundled at
# `<repo>/case_materials/persona_<id>_segment_<n>.md` (mirroring the
# hackathon zip). If present, the full briefing is injected into the
# LLM system prompt verbatim — this is what the case README asks for:
# "Full persona briefings (use as system prompts for persona bots)".
_CASE_DIR = Path(__file__).resolve().parent.parent / "case_materials"
_PERSONA_FILES = {
    "judith": "persona_judith_segment_1.md",
    "franz":  "persona_franz_segment_2.md",
    "peter":  "persona_peter_segment_3.md",
}


@lru_cache(maxsize=8)
def load_persona_briefing(persona_id: str) -> str:
    """Return the full markdown briefing for a persona, or empty string
    if the case-materials folder is not bundled with this checkout."""
    fname = _PERSONA_FILES.get(persona_id)
    if not fname:
        return ""
    path = _CASE_DIR / fname
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


@dataclass
class LLMDecisionTrace:
    step: str
    action: str
    reasoning: str
    dwell_seconds: float


class LLMPersonaBot(PersonaBot):
    """PersonaBot whose `decide()` is driven by an LLM."""

    def __init__(self, persona: Persona, rng: random.Random,
                 wants_purchase: Optional[bool] = None,
                 *, model: str = DEFAULT_MODEL,
                 api_key: Optional[str] = None,
                 temperature: float = 0.7,
                 fallback_on_error: bool = True):
        super().__init__(persona, rng, wants_purchase=wants_purchase)
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("FEATHERLESS_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or os.environ.get("LOVABLE_API_KEY")
        )
        self.temperature = temperature
        self.fallback_on_error = fallback_on_error
        self.history: list[LLMDecisionTrace] = []
        self.last_error: Optional[str] = None

    def _system_prompt(self) -> str:
        p = self.persona
        blurb = BLURBS.get(p.id, "")
        briefing = load_persona_briefing(p.id)
        intent = ("You are genuinely considering buying online today."
                  if self.wants_purchase
                  else "You are mostly comparison-shopping and unlikely to "
                       "complete a purchase today.")
        prompt = (
            f"You are roleplaying {p.name}, a UNIQA private health insurance "
            f"prospect.\n{blurb}\n\n"
            f"Internal traits (0..1): price_sensitivity={p.price_sensitivity:.2f}, "
            f"coachability={p.coachability:.2f}, trust_threshold={p.trust_threshold:.2f}, "
            f"explores_advisor_only_tariffs={p.explore_oos_pct:.2f}.\n"
            f"{intent}\n\n"
            "You are walking through UNIQA's online health-insurance "
            "calculator. At each step you will be told what the screen "
            "shows and which actions are available. Respond ONLY with a "
            "single JSON object matching this schema:\n"
            '{"action": "<one of the allowed actions>", '
            '"reasoning": "<one short sentence, first-person>", '
            '"dwell_seconds": <number between 3 and 90>}\n'
            "Stay in character. Do not invent actions. Do not add prose outside the JSON."
        )
        if briefing:
            prompt += (
                "\n\n---\n\nFULL CHARACTER BRIEFING (from UNIQA persona "
                "briefings, May 2026). Stay consistent with this:\n\n"
                f"{briefing}"
            )
        return prompt

    # Per-step coaching for the LLM: what an in-scope, realistic prospect
    # would actually do at this stage. Without this, small models pick OOS
    # branches ('both', 'other_persons', 'select_premium') almost every run
    # and the funnel exits to an advisor before any coaching can be shown.
    _STEP_GUIDANCE: dict[Step, str] = {
        Step.S1_COVERAGE_SCOPE: (
            "You came here for help with everyday doctor visits. "
            "Prefer 'at_doctor'. Only pick 'hospital' or 'both' if you "
            "genuinely want a Sonderklasse hospital plan today — that "
            "branch hands you off to a human advisor and ends the online "
            "flow."
        ),
        Step.S2_FOR_WHOM: (
            "You are shopping for yourself. Pick 'myself' unless you are "
            "explicitly buying a policy for another person, which ends "
            "the online flow."
        ),
        Step.S3_PERSONAL_DATA: (
            "Date of birth and social insurance number are needed for an "
            "accurate quote. Picking 'abandon' here means you walk away. "
            "If you trust UNIQA enough, 'submit'. If a coach has just "
            "reassured you about why this data is needed, you should "
            "'submit'."
        ),
        Step.S4_INITIAL_PRICE: (
            "Start (EUR 38.74) and Optimal (EUR 68.14) can be purchased "
            "fully online. Opt.Plus and Premium require an advisor call "
            "and will end this online flow. If price feels high, you may "
            "'back' or 'abandon'; if a coach reframed the price, lean "
            "'select_optimal'."
        ),
        Step.S5_ADD_ONS: (
            "Add-ons are optional. 'continue' is the normal choice; only "
            "'abandon' if the form feels overwhelming."
        ),
        Step.S6_HEALTH_QUESTIONS: (
            "Standard yes/no questions. 'continue' unless the questions "
            "feel invasive."
        ),
        Step.S7_FINAL_PRICE: (
            "The final premium may be a few euros higher than the "
            "initial estimate because of your health profile. If a coach "
            "just explained the gap, you should 'confirm'. Otherwise "
            "price shock can make you 'abandon'."
        ),
        Step.S8_CONFIRM: (
            "Last screen. 'confirm' completes the purchase."
        ),
    }

    def _user_prompt(self, ctx: StepContext) -> str:
        allowed = ALLOWED_ACTIONS.get(ctx.step, ctx.options)
        bits = [
            f"Step: {ctx.step.value}",
            f"Screen title: {ctx.title}",
            f"What you see: {ctx.description}",
            f"Allowed actions: {allowed}",
        ]
        if ctx.shows_price_eur:
            bits.append(f"Initial estimated premium: EUR {ctx.shows_price_eur:.2f}")
        if ctx.shows_final_price_eur:
            bits.append(
                f"Final premium after health profile: EUR {ctx.shows_final_price_eur:.2f} "
                "(may be higher than the initial estimate)."
            )
        if ctx.is_critical_dropoff:
            bits.append("This is a known hesitation point in the funnel.")
        if self.state.coach_uplift > 0:
            bits.append(
                "A coach has just reassured you with transparent, "
                "trustworthy info — this materially lowers your urge to "
                "abandon on this step."
            )
        guidance = self._STEP_GUIDANCE.get(ctx.step)
        if guidance:
            bits.append(f"Guidance: {guidance}")
        return "\n".join(bits)

    def _call_llm(self, ctx: StepContext) -> Optional[dict]:
        if not self.api_key:
            self.last_error = "FEATHERLESS_API_KEY (or GROQ_API_KEY / LOVABLE_API_KEY) not set"
            return None
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(ctx)},
            ],
        }
        try:
            r = requests.post(
                GATEWAY_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            if r.status_code != 200:
                self.last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                return None
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return None

    def decide(self, ctx: StepContext) -> Decision:
        allowed = ALLOWED_ACTIONS.get(ctx.step)
        parsed = self._call_llm(ctx) if allowed else None
        if parsed is None or parsed.get("action") not in (allowed or []):
            if self.fallback_on_error:
                return super().decide(ctx)
            raise RuntimeError(self.last_error or "LLM persona failed")

        action = parsed["action"]
        reasoning = str(parsed.get("reasoning", ""))[:240]
        try:
            dwell = float(parsed.get("dwell_seconds", self.persona.dwell_mean))
        except (TypeError, ValueError):
            dwell = self.persona.dwell_mean
        dwell = max(2.0, min(120.0, dwell))

        self.history.append(LLMDecisionTrace(
            step=ctx.step.value, action=action,
            reasoning=reasoning, dwell_seconds=dwell,
        ))

        signals: list[Signal] = [Signal(SignalKind.DWELL, dwell)]
        if ctx.step == Step.S1_COVERAGE_SCOPE and action in {"hospital", "both"}:
            signals.append(Signal(SignalKind.PATH_OOS, note=action))
        if ctx.step == Step.S2_FOR_WHOM and action == "other_persons":
            signals.append(Signal(SignalKind.PATH_OOS, note="other_persons"))
        if ctx.step == Step.S3_PERSONAL_DATA and action == "abandon":
            signals.append(Signal(SignalKind.INACTIVITY, 45.0))
        if ctx.step == Step.S4_INITIAL_PRICE:
            signals.append(Signal(SignalKind.PRICE_HOVER))
            if action in {"select_opt_plus", "select_premium"}:
                signals.append(Signal(SignalKind.TARIFF_CLICK_OOS, note=action))
            if action == "back":
                signals.append(Signal(SignalKind.BACK_NAV))
            if action == "abandon":
                signals.append(Signal(SignalKind.CANCEL_HOVER))
        if ctx.step == Step.S7_FINAL_PRICE:
            signals.append(Signal(SignalKind.PRICE_HOVER))
            if action == "abandon":
                signals.append(Signal(SignalKind.CANCEL_HOVER, 3))
                signals.append(Signal(SignalKind.INACTIVITY, 25))
        return Decision(action, dwell, signals)


__all__ = ["LLMPersonaBot", "BLURBS", "ALLOWED_ACTIONS"]
