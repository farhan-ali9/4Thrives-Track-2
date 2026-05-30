"""Aggregate JourneyResult lists into conversion / drop-off / annoyance."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .journey import IN_SCOPE_ORDER, Step
from .personas import FUNNEL_WEIGHTS
from .sim import JourneyResult


@dataclass
class Aggregate:
    runs: int
    converted: int
    advisor_routed: int
    abandoned: int
    conversion_rate: float
    advisor_rate: float
    survival_per_step: dict[str, float]
    dropoff_per_step: dict[str, float]
    interventions_shown: int = 0
    interventions_accepted: int = 0
    annoyance_rate: float = 0.0   # shown but not accepted, per shown
    trigger_precision: float = 0.0


def aggregate(results: list[JourneyResult]) -> Aggregate:
    runs = len(results)
    converted = sum(r.converted for r in results)
    advisor = sum(r.advisor_routed for r in results)
    abandoned = sum(r.abandoned for r in results)

    # Survival per in-scope step: fraction of runs that REACHED that step.
    reached = Counter()
    for r in results:
        seen = set()
        for obs in r.steps:
            seen.add(obs.step_id)
        for sid in seen:
            reached[sid] += 1
    survival = {step.value: reached[step.value] / runs
                for step in IN_SCOPE_ORDER
                if step not in {Step.START, Step.CONVERTED}}

    # Drop-off per step = fraction of those who reached the step that
    # then did NOT reach the next in-scope step.
    dropoff: dict[str, float] = {}
    order = [s for s in IN_SCOPE_ORDER if s not in {Step.START, Step.CONVERTED}]
    for i, step in enumerate(order):
        reached_here = reached[step.value]
        if reached_here == 0:
            dropoff[step.value] = 0.0
            continue
        if i + 1 < len(order):
            reached_next = reached[order[i + 1].value]
        else:
            reached_next = converted
        dropoff[step.value] = max(0.0, 1.0 - reached_next / reached_here)

    shown = sum(r.interventions_shown for r in results)
    accepted = sum(r.interventions_accepted for r in results)
    annoyance = (shown - accepted) / shown if shown else 0.0
    precision = accepted / shown if shown else 0.0

    return Aggregate(
        runs=runs,
        converted=converted,
        advisor_routed=advisor,
        abandoned=abandoned,
        conversion_rate=converted / runs if runs else 0.0,
        advisor_rate=advisor / runs if runs else 0.0,
        survival_per_step=survival,
        dropoff_per_step=dropoff,
        interventions_shown=shown,
        interventions_accepted=accepted,
        annoyance_rate=annoyance,
        trigger_precision=precision,
    )


def per_persona(results: list[JourneyResult]) -> dict[str, Aggregate]:
    by: dict[str, list[JourneyResult]] = defaultdict(list)
    for r in results:
        by[r.persona_id].append(r)
    return {pid: aggregate(rs) for pid, rs in by.items()}


def weighted_from_personas(per: dict[str, Aggregate],
                           weights: dict[str, float] | None = None) -> Aggregate:
    """Build the official funnel-mix view: Franz 50%, Judith 30%, Peter 20%.

    Counts remain approximate because the weighted view represents a synthetic
    traffic mix, while rates are the evaluation numbers judges care about.
    """
    weights = weights or FUNNEL_WEIGHTS
    available = {pid: weights.get(pid, 0.0) for pid in per}
    total_weight = sum(available.values()) or 1.0
    norm = {pid: w / total_weight for pid, w in available.items()}

    runs = round(sum(per[pid].runs * norm[pid] for pid in per))
    converted_rate = sum(per[pid].conversion_rate * norm[pid] for pid in per)
    advisor_rate = sum(per[pid].advisor_rate * norm[pid] for pid in per)
    abandoned_rate = sum((per[pid].abandoned / per[pid].runs) * norm[pid]
                         for pid in per if per[pid].runs)
    converted = round(converted_rate * runs)
    advisor = round(advisor_rate * runs)
    abandoned = max(0, runs - converted - advisor)

    step_ids = [s.value for s in IN_SCOPE_ORDER if s not in {Step.START, Step.CONVERTED}]
    survival = {
        sid: sum(per[pid].survival_per_step.get(sid, 0.0) * norm[pid]
                 for pid in per)
        for sid in step_ids
    }
    dropoff = {
        sid: sum(per[pid].dropoff_per_step.get(sid, 0.0) * norm[pid]
                 for pid in per)
        for sid in step_ids
    }

    shown = round(sum(per[pid].interventions_shown * norm[pid] for pid in per))
    accepted = round(sum(per[pid].interventions_accepted * norm[pid] for pid in per))
    annoyance = (shown - accepted) / shown if shown else 0.0
    precision = accepted / shown if shown else 0.0

    return Aggregate(
        runs=runs,
        converted=converted,
        advisor_routed=advisor,
        abandoned=abandoned,
        conversion_rate=converted_rate,
        advisor_rate=advisor_rate,
        survival_per_step=survival,
        dropoff_per_step=dropoff,
        interventions_shown=shown,
        interventions_accepted=accepted,
        annoyance_rate=annoyance,
        trigger_precision=precision,
    )
