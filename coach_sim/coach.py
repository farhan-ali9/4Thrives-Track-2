"""Decision layer: pick an intervention from detected behavioral events.

The Coach is deliberately traceable. It is not a black-box recommender:
signals become events in `detector.py`, and this module maps those events to
explicit interventions with a small annoyance budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from .detector import Event
from .journey import Step


class Intervention(str, Enum):
    NONE = "none"
    SIMPLIFIED_EXPLANATION = "simplified_explanation"
    TRUST_SIGNAL = "trust_signal"
    PRICE_REFRAME = "price_reframe"
    MARKET_COMPARISON = "market_comparison"
    PRICE_GAP_TRANSPARENCY = "price_gap_transparency"
    TARIFF_ROUTE_EXPLAINER = "tariff_route_explainer"
    ADVISOR_ROUTE = "advisor_route"
    CALLBACK_REQUEST = "callback_request"
    SAVE_PROGRESS = "save_progress"


INTERVENTION_COPY: dict[Intervention, str] = {
    Intervention.SIMPLIFIED_EXPLANATION:
        "Two online tariffs cover most needs. Want a 30-second comparison?",
    Intervention.TRUST_SIGNAL:
        "We need your DOB and social insurance number only to estimate your "
        "premium accurately. No commitment yet.",
    Intervention.PRICE_REFRAME:
        "Optimal is EUR 2.25/day - less than a coffee. Covers therapies, "
        "medications, and medical aids.",
    Intervention.MARKET_COMPARISON:
        "At EUR 68/month, Optimal is in the lower third of the Austrian "
        "private-doctor tariff market for comparable coverage.",
    Intervention.PRICE_GAP_TRANSPARENCY:
        "Your final price includes your personal health profile. The increase "
        "is transparent, and you can still complete online right now.",
    Intervention.TARIFF_ROUTE_EXPLAINER:
        "Opt. Plus and Premium require a short advisory call. Optimal is fully "
        "online and can be completed now.",
    Intervention.ADVISOR_ROUTE:
        "This path requires personalised advice. Book a free 15-minute call.",
    Intervention.CALLBACK_REQUEST:
        "Would it be easier if someone called you to walk through this? Pick a "
        "time - no obligation.",
    Intervention.SAVE_PROGRESS:
        "Do not lose your progress. Email yourself a resume link and finish "
        "from your phone in 60 seconds.",
}


INTERVENTION_RATIONALE: dict[Intervention, str] = {
    Intervention.NONE:
        "No material hesitation detected or intervention budget exhausted.",
    Intervention.SIMPLIFIED_EXPLANATION:
        "Reduce cognitive load without removing required calculator steps.",
    Intervention.TRUST_SIGNAL:
        "Address trust friction before personal or health data entry.",
    Intervention.PRICE_REFRAME:
        "Turn monthly premium shock into an understandable daily value.",
    Intervention.MARKET_COMPARISON:
        "Prevent comparison-shopping abandonment by giving a benchmark in-flow.",
    Intervention.PRICE_GAP_TRANSPARENCY:
        "Explain why final price differs from the provisional estimate.",
    Intervention.TARIFF_ROUTE_EXPLAINER:
        "Recover users who clicked advisor-only tariffs by pointing back to Optimal.",
    Intervention.ADVISOR_ROUTE:
        "Cleanly exit out-of-scope paths without counting them as conversion.",
    Intervention.CALLBACK_REQUEST:
        "Reserved for explicit advisor-required exits.",
    Intervention.SAVE_PROGRESS:
        "Keep an online-affine user from losing progress when near abandonment.",
}


Policy = Literal["minimal", "balanced", "aggressive"]


@dataclass
class CoachConfig:
    policy: Policy = "balanced"
    max_interventions_per_journey: int = 3


@dataclass
class CoachState:
    interventions_shown: int = 0
    last_intervention: Intervention | None = None
    history: list[tuple[Step, Intervention]] = field(default_factory=list)
    shown_interventions: set[Intervention] = field(default_factory=set)


class Coach:
    """Transparent intervention policy for the in-scope conversion path."""

    def __init__(self, config: CoachConfig | None = None,
                 persona_id: str | None = None):
        self.cfg = config or CoachConfig()
        self.state = CoachState()
        self.persona_id = persona_id

    def reset(self) -> None:
        self.state = CoachState()

    def _pick_once(self, *candidates: Intervention) -> Intervention:
        """Return the first intervention not already shown this journey."""
        for candidate in candidates:
            if candidate not in self.state.shown_interventions:
                return candidate
        return Intervention.NONE

    def choose(self, step: Step, events: list[Event]) -> Intervention:
        event_set = set(events)

        # Scope boundary: out-of-scope selections are clean exits, not wins.
        if Event.OUT_OF_SCOPE_PATH in event_set:
            return Intervention.ADVISOR_ROUTE
        if Event.OUT_OF_SCOPE_TARIFF in event_set:
            return Intervention.TARIFF_ROUTE_EXPLAINER

        if self.state.interventions_shown >= self.cfg.max_interventions_per_journey:
            return Intervention.NONE

        if self.cfg.policy == "minimal":
            return self._minimal(step, event_set)
        if self.cfg.policy == "aggressive":
            return self._aggressive(step, event_set)
        return self._balanced(step, event_set)

    def _minimal(self, step: Step, events: set[Event]) -> Intervention:
        if Event.CANCEL_INTENT not in events:
            return Intervention.NONE
        if step == Step.S4_INITIAL_PRICE:
            return self._pick_once(Intervention.PRICE_REFRAME)
        if step == Step.S7_FINAL_PRICE:
            return self._pick_once(Intervention.PRICE_GAP_TRANSPARENCY)
        return Intervention.NONE

    def _aggressive(self, step: Step, events: set[Event]) -> Intervention:
        # Intentionally broad for A/B comparison; still avoids duplicate nudges.
        if step == Step.S3_PERSONAL_DATA and self._has_hesitation(events):
            return self._pick_once(Intervention.TRUST_SIGNAL)
        if step == Step.S4_INITIAL_PRICE:
            return self._pick_once(
                Intervention.PRICE_REFRAME,
                Intervention.MARKET_COMPARISON,
                Intervention.SIMPLIFIED_EXPLANATION,
            )
        if step == Step.S5_ADD_ONS:
            return self._pick_once(Intervention.SIMPLIFIED_EXPLANATION)
        if step == Step.S6_HEALTH_QUESTIONS:
            return self._pick_once(Intervention.TRUST_SIGNAL)
        if step == Step.S7_FINAL_PRICE:
            return self._pick_once(
                Intervention.PRICE_GAP_TRANSPARENCY,
                Intervention.TRUST_SIGNAL,
            )
        if Event.LONG_DWELL in events:
            return self._pick_once(Intervention.SIMPLIFIED_EXPLANATION)
        return Intervention.NONE

    def _balanced(self, step: Step, events: set[Event]) -> Intervention:
        # S3: trust barrier before sensitive quote data.
        if step == Step.S3_PERSONAL_DATA and self._has_hesitation(events):
            return self._pick_once(Intervention.TRUST_SIGNAL)

        # S4: biggest known drop-off. Match the nudge to persona intent.
        if step == Step.S4_INITIAL_PRICE:
            if self.persona_id == "franz" and (
                Event.BACK_NAV in events or Event.REPEATED_CHANGE in events
            ):
                return self._pick_once(
                    Intervention.MARKET_COMPARISON,
                    Intervention.PRICE_REFRAME,
                )
            if Event.CANCEL_INTENT in events or Event.PRICE_FIXATION in events:
                if self.persona_id == "peter":
                    return self._pick_once(
                        Intervention.SIMPLIFIED_EXPLANATION,
                        Intervention.PRICE_REFRAME,
                    )
                return self._pick_once(
                    Intervention.PRICE_REFRAME,
                    Intervention.MARKET_COMPARISON,
                )
            if Event.BACK_NAV in events:
                return self._pick_once(Intervention.MARKET_COMPARISON)

        # S5: add-ons are not removed; the Coach explains and keeps going.
        if step == Step.S5_ADD_ONS and self._has_hesitation(events):
            return self._pick_once(Intervention.SIMPLIFIED_EXPLANATION)

        # S6: health questions — reassure on why personal health data is needed.
        if step == Step.S6_HEALTH_QUESTIONS and self._has_hesitation(events):
            return self._pick_once(Intervention.TRUST_SIGNAL)

        # S7: final price shock. This is the strongest online-conversion save.
        if step == Step.S7_FINAL_PRICE and (
            Event.PRICE_GAP_SHOCK in events or Event.CANCEL_INTENT in events
        ):
            if self.persona_id == "franz":
                return self._pick_once(
                    Intervention.PRICE_GAP_TRANSPARENCY,
                    Intervention.MARKET_COMPARISON,
                    Intervention.SAVE_PROGRESS,
                )
            return self._pick_once(
                Intervention.PRICE_GAP_TRANSPARENCY,
                Intervention.TRUST_SIGNAL,
            )

        # S8: rare last-moment anxiety.
        if step == Step.S8_CONFIRM and Event.CANCEL_INTENT in events:
            return self._pick_once(Intervention.TRUST_SIGNAL)

        return Intervention.NONE

    @staticmethod
    def _has_hesitation(events: set[Event]) -> bool:
        return bool(events & {
            Event.LONG_DWELL,
            Event.CANCEL_INTENT,
            Event.BACK_NAV,
            Event.REPEATED_CHANGE,
            Event.PRICE_FIXATION,
        })

    def record(self, step: Step, intervention: Intervention) -> None:
        if intervention in {
            Intervention.NONE,
            Intervention.ADVISOR_ROUTE,
            Intervention.TARIFF_ROUTE_EXPLAINER,
        }:
            self.state.history.append((step, intervention))
            return
        self.state.interventions_shown += 1
        self.state.last_intervention = intervention
        self.state.shown_interventions.add(intervention)
        self.state.history.append((step, intervention))
