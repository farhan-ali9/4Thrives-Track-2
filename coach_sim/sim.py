"""Single-journey runner. Returns a structured trace + outcome."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .coach import Coach, Intervention
from .detector import Detector, Event
from .journey import IN_SCOPE_ORDER, STEP_META, Step, TERMINAL, context_for, next_step
from .personas import PersonaBot
from .signals import StepObservation


CURRENT_STEP_RESCUE_PROB = {
    Intervention.TRUST_SIGNAL: 0.22,
    Intervention.SIMPLIFIED_EXPLANATION: 0.18,
    Intervention.PRICE_REFRAME: 0.28,
    Intervention.MARKET_COMPARISON: 0.24,
    Intervention.PRICE_GAP_TRANSPARENCY: 0.34,
    Intervention.SAVE_PROGRESS: 0.14,
    Intervention.CALLBACK_REQUEST: 0.0,
}


@dataclass
class JourneyResult:
    persona_id: str
    converted: bool
    advisor_routed: bool
    abandoned: bool
    terminal_step: Step
    steps: list[StepObservation] = field(default_factory=list)
    coach_events: list[tuple[Step, list[Event], Intervention, bool | None]] = field(
        default_factory=list)
    interventions_shown: int = 0
    interventions_accepted: int = 0
    initial_price_eur: float = 0.0
    final_price_eur: float = 0.0
    price_delta_eur: float = 0.0
    outcome_reason: str = ""


def _initial_price() -> float:
    return 68.14   # Optimal estimated premium


def _final_price(initial: float, rng: random.Random) -> float:
    """Personal health profile bumps the price by 0–15%."""
    return round(initial * (1.0 + rng.uniform(0.0, 0.15)), 2)


def run_journey(bot: PersonaBot, *, coach: Coach | None = None,
                detector: Detector | None = None,
                max_steps: int = 30) -> JourneyResult:
    """Run one persona through the funnel. If `coach` is None, baseline."""
    detector = detector or Detector()
    if coach is not None:
        coach.reset()

    state = Step.START
    next_real = Step.S1_COVERAGE_SCOPE
    initial = _initial_price()
    final = _final_price(initial, bot.rng)

    result = JourneyResult(
        persona_id=bot.persona.id,
        converted=False,
        advisor_routed=False,
        abandoned=False,
        terminal_step=Step.START,
        initial_price_eur=initial,
        final_price_eur=final,
        price_delta_eur=round(final - initial, 2),
    )

    state = next_real
    for _ in range(max_steps):
        if state in TERMINAL:
            break
        ctx = context_for(state, initial_price=initial, final_price=final)
        decision = bot.decide(ctx)
        meta = STEP_META.get(state, {})
        obs = StepObservation(step_id=state.value, persona_id=bot.persona.id,
                              action=decision.action,
                              dwell_seconds=decision.dwell_seconds,
                              signals=decision.signals,
                              screen_title=ctx.title,
                              screen_description=ctx.description,
                              phase=meta.get("phase", ""))

        # Coach inspects the signals BEFORE the action commits a transition,
        # mirroring how a real coach would interrupt at the wobble point.
        if coach is not None:
            events = detector.detect(
                decision.signals,
                initial_price=initial if state == Step.S7_FINAL_PRICE else None,
                final_price=final if state == Step.S7_FINAL_PRICE else None,
            )
            obs.detected_events = [event.value for event in events]
            intervention = coach.choose(state, events)
            accepted: bool | None = None
            if intervention not in {Intervention.NONE,
                                    Intervention.ADVISOR_ROUTE,
                                    Intervention.TARIFF_ROUTE_EXPLAINER}:
                accepted = bot.receive_intervention(intervention.value)
                result.interventions_shown += 1
                if accepted:
                    result.interventions_accepted += 1
                    # Rescue an imminent abandonment: if the persona was
                    # about to drop off on this step and accepted the coach,
                    # some fraction continues immediately. The rest only gets
                    # a lower drop-off probability on future steps.
                    rescue_prob = CURRENT_STEP_RESCUE_PROB.get(intervention, 0.0)
                    if decision.action == "abandon" and bot.rng.random() < rescue_prob:
                        rescue = {
                            Step.S3_PERSONAL_DATA: "submit",
                            Step.S4_INITIAL_PRICE: "select_optimal",
                            Step.S5_ADD_ONS: "continue",
                            Step.S6_HEALTH_QUESTIONS: "continue",
                            Step.S7_FINAL_PRICE: "confirm",
                            Step.S8_CONFIRM: "confirm",
                        }.get(state)
                        if rescue:
                            decision.action = rescue
                            obs.action = rescue
            elif intervention == Intervention.TARIFF_ROUTE_EXPLAINER:
                # Steers the persona away from the OOS tariff: on the next
                # decide() the explore flag is already set, so they'll move
                # forward into the in-scope Optimal selection.
                accepted = bot.receive_intervention(intervention.value)
                if accepted:
                    # Convert the back-nav into a forward Optimal pick now,
                    # so we don't burn another loop iteration.
                    decision.action = "select_optimal"
                    obs.action = "select_optimal"
            coach.record(state, intervention)
            obs.intervention_shown = intervention.value
            obs.intervention_accepted = accepted
            result.coach_events.append((state, events, intervention, accepted))

        result.steps.append(obs)
        state = next_step(state, decision.action)

    result.terminal_step = state
    result.converted = state == Step.CONVERTED
    result.advisor_routed = state == Step.ADVISOR_ROUTED
    result.abandoned = state == Step.ABANDONED
    if result.converted:
        result.outcome_reason = "Online purchase completed for an in-scope Start/Optimal tariff."
    elif result.advisor_routed:
        result.outcome_reason = "Out-of-scope selection routed to advisor and excluded from conversion."
    elif result.abandoned:
        result.outcome_reason = "Persona abandoned before online purchase completion."
    else:
        result.outcome_reason = "Journey stopped before a terminal outcome."
    return result


__all__ = ["JourneyResult", "run_journey", "IN_SCOPE_ORDER"]
