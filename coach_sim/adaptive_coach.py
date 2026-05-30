"""Adaptive Coach — Thompson Sampling over intervention candidates.

Replaces the hardcoded intervention ordering in coach.py with a learned
Beta-distribution prior per (step, persona, intervention). After each
simulation batch the caller updates the priors from observed accept/reject
outcomes; over iterations the coach converges on the best intervention for
each persona at each drop-off step.

Usage:
    policy = AdaptivePolicy()
    coach  = AdaptiveCoach(policy, persona_id="franz")
    result = run_journey(bot, coach=coach, detector=Detector())
    policy.update_from_result(result)   # learn from this journey
    policy.save(Path("coach_sim/results/learned_policy.json"))
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .coach import Coach, CoachConfig, Intervention
from .detector import Event
from .journey import Step
from .sim import JourneyResult


# Which interventions are candidates at each step.
# The adaptive policy learns the best ordering within each group.
CANDIDATES: dict[Step, list[Intervention]] = {
    Step.S3_PERSONAL_DATA: [
        Intervention.TRUST_SIGNAL,
    ],
    Step.S4_INITIAL_PRICE: [
        Intervention.PRICE_REFRAME,
        Intervention.MARKET_COMPARISON,
        Intervention.SIMPLIFIED_EXPLANATION,
    ],
    Step.S5_ADD_ONS: [
        Intervention.SIMPLIFIED_EXPLANATION,
        Intervention.TRUST_SIGNAL,
    ],
    Step.S6_HEALTH_QUESTIONS: [
        Intervention.TRUST_SIGNAL,
        Intervention.SIMPLIFIED_EXPLANATION,
    ],
    Step.S7_FINAL_PRICE: [
        Intervention.PRICE_GAP_TRANSPARENCY,
        Intervention.MARKET_COMPARISON,
        Intervention.TRUST_SIGNAL,
        Intervention.SAVE_PROGRESS,
    ],
    Step.S8_CONFIRM: [
        Intervention.TRUST_SIGNAL,
        Intervention.SAVE_PROGRESS,
    ],
}


@dataclass
class BetaPrior:
    """Beta(alpha, beta) distribution over acceptance probability."""
    alpha: float = 2.0   # pseudo-successes — start optimistic
    beta_: float = 2.0   # pseudo-failures

    def sample(self, rng: random.Random) -> float:
        return rng.betavariate(self.alpha, self.beta_)

    def update(self, accepted: bool) -> None:
        if accepted:
            self.alpha += 1.0
        else:
            self.beta_ += 1.0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta_)

    @property
    def observations(self) -> int:
        return max(0, int(self.alpha + self.beta_ - 4))  # subtract initial priors


class AdaptivePolicy:
    """Per-(step, persona, intervention) Beta priors updated from journey outcomes."""

    def __init__(self) -> None:
        self._priors: dict[tuple[str, str, str], BetaPrior] = {}
        self._rng = random.Random(0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _key(self, step: Step, persona_id: str, iv: Intervention) -> tuple[str, str, str]:
        return (step.value, persona_id, iv.value)

    def _prior(self, step: Step, persona_id: str, iv: Intervention) -> BetaPrior:
        key = self._key(step, persona_id, iv)
        if key not in self._priors:
            self._priors[key] = BetaPrior()
        return self._priors[key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def choose(self, step: Step, persona_id: str,
               exclude: set[Intervention] | None = None) -> Intervention:
        """Thompson sampling: return the candidate with the highest sampled rate."""
        candidates = [
            iv for iv in CANDIDATES.get(step, [])
            if iv not in (exclude or set())
        ]
        if not candidates:
            return Intervention.NONE
        return max(candidates,
                   key=lambda iv: self._prior(step, persona_id, iv).sample(self._rng))

    def update(self, step: Step, persona_id: str,
               intervention: Intervention, accepted: bool) -> None:
        self._prior(step, persona_id, intervention).update(accepted)

    def update_from_result(self, result: JourneyResult) -> None:
        """Batch-update from a completed journey trace."""
        for step, _events, intervention, accepted in result.coach_events:
            if intervention in {Intervention.NONE, Intervention.ADVISOR_ROUTE}:
                continue
            if accepted is None:
                continue
            self.update(step, result.persona_id, intervention, bool(accepted))

    def acceptance_table(self) -> list[dict]:
        """Return a sorted summary of learned acceptance rates."""
        rows = []
        for (step, pid, iv), prior in self._priors.items():
            rows.append({
                "step": step,
                "persona": pid,
                "intervention": iv,
                "mean_accept": round(prior.mean, 3),
                "observations": prior.observations,
            })
        return sorted(rows, key=lambda r: -r["mean_accept"])

    def save(self, path: Path) -> None:
        data = {
            f"{s}|{p}|{iv}": {"alpha": pr.alpha, "beta": pr.beta_}
            for (s, p, iv), pr in self._priors.items()
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> "AdaptivePolicy":
        inst = cls()
        for k, v in json.loads(path.read_text()).items():
            parts = k.split("|")
            if len(parts) == 3:
                inst._priors[tuple(parts)] = BetaPrior(  # type: ignore[arg-type]
                    alpha=v["alpha"], beta_=v["beta"]
                )
        return inst


class AdaptiveCoach(Coach):
    """Coach whose intervention selection is driven by AdaptivePolicy."""

    def __init__(self, adaptive_policy: AdaptivePolicy,
                 persona_id: str | None = None,
                 max_interventions: int = 3) -> None:
        super().__init__(
            CoachConfig(policy="balanced",
                        max_interventions_per_journey=max_interventions),
            persona_id=persona_id,
        )
        self.adaptive_policy = adaptive_policy

    def choose(self, step: Step, events: list[Event]) -> Intervention:
        event_set = set(events)

        # Scope exits are always deterministic.
        if Event.OUT_OF_SCOPE_PATH in event_set:
            return Intervention.ADVISOR_ROUTE
        if Event.OUT_OF_SCOPE_TARIFF in event_set:
            return Intervention.TARIFF_ROUTE_EXPLAINER

        if self.state.interventions_shown >= self.cfg.max_interventions_per_journey:
            return Intervention.NONE

        # Only intervene when there is a real hesitation signal.
        hesitation = {
            Event.LONG_DWELL, Event.CANCEL_INTENT, Event.BACK_NAV,
            Event.REPEATED_CHANGE, Event.PRICE_FIXATION, Event.PRICE_GAP_SHOCK,
        }
        if not (event_set & hesitation):
            return Intervention.NONE

        pid = self.persona_id or "franz"
        return self._pick_once(
            self.adaptive_policy.choose(step, pid, self.state.shown_interventions)
        )


__all__ = ["AdaptivePolicy", "AdaptiveCoach", "BetaPrior", "CANDIDATES"]
