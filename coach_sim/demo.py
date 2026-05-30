"""Scripted before/after transcript for the Franz example from the brief.

    python -m coach_sim.demo
"""
from __future__ import annotations

import random

from .coach import Coach, CoachConfig, INTERVENTION_COPY, Intervention
from .detector import Detector
from .personas import PERSONAS, PersonaBot
from .sim import run_journey


def _print_trace(label: str, result) -> None:
    print(f"\n=== {label} ===")
    for obs in result.steps:
        line = f"[{obs.step_id}] action={obs.action} dwell={obs.dwell_seconds:.1f}s"
        if obs.intervention_shown and obs.intervention_shown != "none":
            iv = Intervention(obs.intervention_shown)
            copy = INTERVENTION_COPY.get(iv, "")
            tag = "OK" if obs.intervention_accepted else "NO"
            line += f"\n    [COACH {tag}] {iv.value}: {copy}"
        print(line)
    outcome = ("CONVERTED" if result.converted else
               "ADVISOR_ROUTED" if result.advisor_routed else
               "ABANDONED")
    print(f"--> {outcome}\n")


def main() -> None:
    seed = "franz-demo"
    # Force a would-be completer so the contrast is meaningful.
    bot_a = PersonaBot(PERSONAS["franz"], random.Random(seed),
                       wants_purchase=True)
    bot_b = PersonaBot(PERSONAS["franz"], random.Random(seed),
                       wants_purchase=True)
    baseline = run_journey(bot_a)
    coached = run_journey(bot_b,
                          coach=Coach(CoachConfig(policy="balanced"),
                                      persona_id=bot_b.persona.id),
                          detector=Detector())
    _print_trace("Franz - without Coach (baseline)", baseline)
    _print_trace("Franz - with Coach (balanced policy)", coached)


if __name__ == "__main__":
    main()
