"""Persona bots: Judith (Segment 1), Franz (Segment 2), Peter (Segment 3).

Rule-based and seedable so baseline and coach runs are directly
comparable. Parameters are grounded in the persona briefings and
personas.json; tune via the `Persona` dataclass without changing the
decision code.

To swap in an LLM persona later, subclass `PersonaBot` and override
`decide()`. Keep the return shape identical.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .journey import Step, StepContext
from .signals import Signal, SignalKind


@dataclass
class Persona:
    id: str
    name: str
    segment: str
    # Probability the persona is actually a "completer" (other traffic
    # mix: comparison shoppers, price-checkers, oriented browsers).
    intent_purchase_pct: float
    # How price-sensitive (0..1). Drives initial-price drop probability.
    price_sensitivity: float
    # How easily reassured (0..1). Higher = coach interventions are
    # more likely to land.
    coachability: float
    # Trust threshold for handing over personal data (0..1). Higher =
    # more likely to bounce at S3 / S7.
    trust_threshold: float
    # Probability the persona explores the out-of-scope tariffs out of
    # curiosity (clicks Opt.Plus/Premium before settling).
    explore_oos_pct: float
    # Probability the persona ever considers the hospital branch.
    hospital_pct: float
    # Probability the persona is shopping "for other persons".
    other_persons_pct: float
    # Typical dwell time on a normal step (seconds, mean).
    dwell_mean: float = 12.0
    # Multiplier on dwell at critical-dropoff steps.
    critical_dwell_mult: float = 2.5


# Parameters distilled from the briefings + personas.json.
# - Segment 2 (Franz, Online Affine): high purchase intent, price-aware,
#   self-directed, low coachability (doesn't want hand-holding).
# - Segment 1 (Judith, Rising Hybrid): research-first but seeks trust at
#   decision time; medium price sensitivity, high coachability.
# - Segment 3 (Peter, Service Affine): wants an advisor; low intent to
#   complete online, high trust threshold.
PERSONAS: dict[str, Persona] = {
    "franz": Persona(
        id="franz", name="Franz", segment="segment_2",
        # Segment 2 — Online Affine (50% of funnel traffic, 69% online
        # purchase share). High intent, low advisor tolerance, fast.
        # Drop-off lives at S7 (final price > initial price), not at S3.
        intent_purchase_pct=0.90, price_sensitivity=0.65,
        coachability=0.52, trust_threshold=0.25,
        explore_oos_pct=0.08, hospital_pct=0.005, other_persons_pct=0.005,
        dwell_mean=8.0, critical_dwell_mult=1.8,
    ),
    "judith": Persona(
        id="judith", name="Judith", segment="segment_1",
        # Segment 1 — Rising Hybrids (30% of funnel, 19% online purchase).
        # Researches online, drops at S4 initial price ("better tariffs
        # require advisor"), highly coachable when transparency offered.
        intent_purchase_pct=0.70, price_sensitivity=0.55,
        coachability=0.75, trust_threshold=0.50,
        explore_oos_pct=0.12, hospital_pct=0.015, other_persons_pct=0.01,
        dwell_mean=15.0, critical_dwell_mult=3.0,
    ),
    "peter": Persona(
        id="peter", name="Peter", segment="segment_3",
        # Segment 3 - Service Affine (20% of funnel, 34% online purchase
        # but driven by circumstance). Overwhelmed early; drops before
        # tariff selection. High trust threshold for online forms.
        intent_purchase_pct=0.50, price_sensitivity=0.55,
        coachability=0.55, trust_threshold=0.80,
        explore_oos_pct=0.064, hospital_pct=0.03, other_persons_pct=0.02,
        dwell_mean=22.0, critical_dwell_mult=3.5,
    ),
}


# UNIQA internal estimate for online funnel traffic mix from the case brief.
FUNNEL_WEIGHTS: dict[str, float] = {
    "franz": 0.50,
    "judith": 0.30,
    "peter": 0.20,
}


@dataclass
class PersonaState:
    """Mutable per-journey state for a persona run."""
    coach_uplift: float = 0.0          # added on accepted interventions
    visited_oos_tariff: bool = False


@dataclass
class Decision:
    action: str
    dwell_seconds: float
    signals: list[Signal] = field(default_factory=list)


class PersonaBot:
    """Stateful, seedable persona simulator."""

    def __init__(self, persona: Persona, rng: random.Random,
                 wants_purchase: Optional[bool] = None):
        self.persona = persona
        self.rng = rng
        self.state = PersonaState()
        # Resolve up-front whether this run is a would-be completer.
        if wants_purchase is None:
            wants_purchase = rng.random() < persona.intent_purchase_pct
        self.wants_purchase = wants_purchase

    # ------------------------------------------------------------------
    # Public hook
    # ------------------------------------------------------------------
    def decide(self, ctx: StepContext) -> Decision:
        p = self.persona
        r = self.rng
        dwell = max(2.0, r.gauss(p.dwell_mean, p.dwell_mean * 0.35))
        if ctx.is_critical_dropoff:
            dwell *= p.critical_dwell_mult
        signals: list[Signal] = [Signal(SignalKind.DWELL, dwell)]

        # --- Step 1: coverage scope
        if ctx.step == Step.S1_COVERAGE_SCOPE:
            if r.random() < p.hospital_pct:
                signals.append(Signal(SignalKind.PATH_OOS, note="hospital"))
                return Decision("hospital", dwell, signals)
            return Decision("at_doctor", dwell, signals)

        # --- Step 2: for whom
        if ctx.step == Step.S2_FOR_WHOM:
            if r.random() < p.other_persons_pct:
                signals.append(Signal(SignalKind.PATH_OOS, note="other_persons"))
                return Decision("other_persons", dwell, signals)
            return Decision("myself", dwell, signals)

        # --- Step 3: personal data (trust barrier, no price yet)
        if ctx.step == Step.S3_PERSONAL_DATA:
            # Hesitation rises with trust threshold.
            if r.random() < p.trust_threshold * 0.12 and not self.wants_purchase:
                signals.append(Signal(SignalKind.INACTIVITY, 45.0))
                return Decision("abandon", dwell + 30, signals)
            return Decision("submit", dwell, signals)

        # --- Step 4: initial price (the 66% dropoff)
        if ctx.step == Step.S4_INITIAL_PRICE:
            signals.append(Signal(SignalKind.PRICE_HOVER))
            # Out-of-scope curiosity: click Opt.Plus / Premium first.
            if not self.state.visited_oos_tariff and r.random() < p.explore_oos_pct:
                self.state.visited_oos_tariff = True
                signals.append(Signal(SignalKind.TARIFF_CLICK_OOS,
                                      note="opt_plus_or_premium"))
                # On the unaided run this typically becomes a back-nav
                # followed by abandonment (see Franz example in the brief).
                signals.append(Signal(SignalKind.BACK_NAV))
                # Whether the user actually clicks the OOS tariff or just
                # bounces back is decided here; the coach gets the chance
                # to intervene before the next decide() call.
                return Decision("back", dwell, signals)

            base_drop = 0.66
            # Price sensitivity raises drop; coach uplift lowers it.
            drop_prob = base_drop * (0.6 + 0.6 * p.price_sensitivity)
            drop_prob = max(0.0, drop_prob - self.state.coach_uplift)
            if not self.wants_purchase:
                drop_prob = min(0.95, drop_prob + 0.15)
            if r.random() < drop_prob:
                signals.append(Signal(SignalKind.CANCEL_HOVER))
                return Decision("abandon", dwell + 10, signals)
            # Default to Optimal (the brief's intended convert target).
            return Decision("select_optimal", dwell, signals)

        # --- Step 5: add-ons (24% drop)
        if ctx.step == Step.S5_ADD_ONS:
            drop_prob = 0.22 - 0.5 * self.state.coach_uplift
            if r.random() < max(0.0, drop_prob):
                return Decision("abandon", dwell, signals)
            return Decision("continue", dwell, signals)

        # --- Step 6: health questions (trust barrier — personal health data)
        if ctx.step == Step.S6_HEALTH_QUESTIONS:
            drop_prob = p.trust_threshold * 0.10
            if r.random() < drop_prob:
                signals.append(Signal(SignalKind.INACTIVITY, 30.0))
                return Decision("abandon", dwell + 20, signals)
            return Decision("continue", dwell, signals)

        # --- Step 7: final price (78% drop), often higher than initial
        if ctx.step == Step.S7_FINAL_PRICE:
            signals.append(Signal(SignalKind.PRICE_HOVER))
            base_drop = 0.78
            drop_prob = base_drop * (0.65 + 0.55 * p.price_sensitivity)
            drop_prob = max(0.0, drop_prob - self.state.coach_uplift)
            if not self.wants_purchase:
                drop_prob = min(0.97, drop_prob + 0.10)
            if r.random() < drop_prob:
                signals.append(Signal(SignalKind.CANCEL_HOVER, 3))
                signals.append(Signal(SignalKind.INACTIVITY, 25))
                return Decision("abandon", dwell + 15, signals)
            return Decision("confirm", dwell, signals)

        # --- Step 8: confirm
        if ctx.step == Step.S8_CONFIRM:
            if r.random() < 0.01 - 0.01 * self.state.coach_uplift:
                return Decision("abandon", dwell, signals)
            return Decision("confirm", dwell, signals)

        return Decision("continue", dwell, signals)

    # Called by the runner after an intervention is shown.
    def receive_intervention(self, intervention: str) -> bool:
        """Persona decides whether the intervention lands.

        Returns True if the persona is reassured (raises coach_uplift),
        False if it annoys them.
        """
        p = self.persona
        # Some interventions are universally helpful, and some fit specific
        # segments better. This keeps the logic traceable while showing real
        # persona differentiation in evaluation.
        universal_bonus = {
            "price_gap_transparency": 0.16,
            "tariff_route_explainer": 0.20,
            "trust_signal": 0.10,
            "market_comparison": 0.08,
            "price_reframe": 0.06,
        }.get(intervention, 0.0)
        persona_bonus = {
            "franz": {
                "market_comparison": 0.22,
                "tariff_route_explainer": 0.18,
                "price_gap_transparency": 0.18,
                "price_reframe": 0.12,
            },
            "judith": {
                "trust_signal": 0.18,
                "price_gap_transparency": 0.18,
                "price_reframe": 0.10,
            },
            "peter": {
                "trust_signal": 0.24,
                "simplified_explanation": 0.22,
                "price_gap_transparency": 0.10,
            },
        }.get(p.id, {}).get(intervention, 0.0)
        accept_prob = min(0.95, p.coachability + universal_bonus + persona_bonus)
        if self.rng.random() < accept_prob:
            uplift = {
                "price_gap_transparency": 0.16,
                "tariff_route_explainer": 0.15,
                "trust_signal": 0.13,
                "market_comparison": 0.13,
                "price_reframe": 0.12,
                "simplified_explanation": 0.11,
                "save_progress": 0.06,
            }.get(intervention, 0.08)
            self.state.coach_uplift = min(0.45, self.state.coach_uplift + uplift)
            return True
        # Annoyance: a mis-timed intervention can slightly accelerate drop.
        self.state.coach_uplift = max(-0.15, self.state.coach_uplift - 0.05)
        return False
