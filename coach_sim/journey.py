"""15-step UNIQA health-insurance funnel as a state machine.

Only the in-scope private-doctor / "myself" / Start+Optimal path can lead
to a CONVERTED terminal state. All other branches terminate in
ADVISOR_ROUTED (valid exit, not a conversion).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Step(str, Enum):
    START = "start"
    S1_COVERAGE_SCOPE = "s1_coverage_scope"      # at-doctor vs hospital
    S2_FOR_WHOM = "s2_for_whom"                  # myself vs other persons
    S3_PERSONAL_DATA = "s3_personal_data"        # DOB + social insurance #
    S4_INITIAL_PRICE = "s4_initial_price"        # 4 tariffs shown (66% drop)
    S5_ADD_ONS = "s5_add_ons"                    # optional coverage (24% drop)
    S6_HEALTH_QUESTIONS = "s6_health_questions"
    S7_FINAL_PRICE = "s7_final_price"            # personal data, final premium (78% drop)
    S8_CONFIRM = "s8_confirm"
    CONVERTED = "converted"
    ABANDONED = "abandoned"
    ADVISOR_ROUTED = "advisor_routed"


TERMINAL = {Step.CONVERTED, Step.ABANDONED, Step.ADVISOR_ROUTED}

# Canonical forward order for the in-scope path.
IN_SCOPE_ORDER = [
    Step.START,
    Step.S1_COVERAGE_SCOPE,
    Step.S2_FOR_WHOM,
    Step.S3_PERSONAL_DATA,
    Step.S4_INITIAL_PRICE,
    Step.S5_ADD_ONS,
    Step.S6_HEALTH_QUESTIONS,
    Step.S7_FINAL_PRICE,
    Step.S8_CONFIRM,
    Step.CONVERTED,
]


STEP_META: dict[Step, dict[str, str]] = {
    Step.S1_COVERAGE_SCOPE: {
        "phase": "Inputs",
        "number": "1",
        "short": "Coverage type",
    },
    Step.S2_FOR_WHOM: {
        "phase": "Inputs",
        "number": "2",
        "short": "Insured person",
    },
    Step.S3_PERSONAL_DATA: {
        "phase": "Inputs",
        "number": "3",
        "short": "Quote data",
    },
    Step.S4_INITIAL_PRICE: {
        "phase": "Product",
        "number": "4",
        "short": "Initial price",
    },
    Step.S5_ADD_ONS: {
        "phase": "Product",
        "number": "5",
        "short": "Add-ons",
    },
    Step.S6_HEALTH_QUESTIONS: {
        "phase": "Inputs",
        "number": "6",
        "short": "Health questions",
    },
    Step.S7_FINAL_PRICE: {
        "phase": "Recommendation",
        "number": "7",
        "short": "Final price",
    },
    Step.S8_CONFIRM: {
        "phase": "Closing",
        "number": "8",
        "short": "Purchase",
    },
}


@dataclass
class StepContext:
    """What a persona bot sees on a given step."""
    step: Step
    title: str
    description: str
    options: list[str]
    is_critical_dropoff: bool = False
    shows_price_eur: float | None = None
    shows_final_price_eur: float | None = None


def context_for(step: Step, *, initial_price: float = 38.74,
                final_price: float = 0.0) -> StepContext:
    """Build the UI context the persona reasons over."""
    if step == Step.S1_COVERAGE_SCOPE:
        return StepContext(
            step, "Where do you want coverage?",
            "Two cards: at doctor visits, in hospital. Multi-select.",
            ["at_doctor", "hospital", "both"],
        )
    if step == Step.S2_FOR_WHOM:
        return StepContext(
            step, "Who should be insured?",
            "Self vs. other persons.",
            ["myself", "other_persons"],
        )
    if step == Step.S3_PERSONAL_DATA:
        return StepContext(
            step, "Personal data for premium estimate",
            "Date of birth + social insurance number.",
            ["submit", "back", "abandon"],
        )
    if step == Step.S4_INITIAL_PRICE:
        return StepContext(
            step, "Tariff selection",
            ("Four tariffs side by side. Start €38.74, Optimal €68.14, "
             "Opt.Plus €96.66 (advisor only), Premium €140.16 (advisor only)."),
            ["select_start", "select_optimal", "select_opt_plus",
             "select_premium", "back", "abandon"],
            is_critical_dropoff=True,
            shows_price_eur=initial_price,
        )
    if step == Step.S5_ADD_ONS:
        return StepContext(
            step, "Additional coverage",
            "Optional add-ons (Becoming Parents, Feeling Fit, Growing Mentally).",
            ["continue", "back", "abandon"],
            is_critical_dropoff=True,
        )
    if step == Step.S6_HEALTH_QUESTIONS:
        return StepContext(
            step, "Health questions",
            "Several yes/no questions on pre-existing conditions.",
            ["continue", "back", "abandon"],
        )
    if step == Step.S7_FINAL_PRICE:
        return StepContext(
            step, "Personal data + final price",
            "Final premium shown, often higher than initial estimate.",
            ["confirm", "back", "abandon"],
            is_critical_dropoff=True,
            shows_final_price_eur=final_price,
        )
    if step == Step.S8_CONFIRM:
        return StepContext(
            step, "Confirm and purchase",
            "Review summary, accept terms, submit.",
            ["confirm", "back", "abandon"],
        )
    return StepContext(step, str(step), "", [])


def next_step(current: Step, action: str) -> Step:
    """Advance the state machine given the persona's action."""
    # Out-of-scope terminations.
    if action in {"hospital", "both"}:
        return Step.ADVISOR_ROUTED
    if action == "other_persons":
        return Step.ADVISOR_ROUTED
    if action in {"select_opt_plus", "select_premium"}:
        return Step.ADVISOR_ROUTED
    if action == "abandon":
        return Step.ABANDONED

    forward = {
        Step.START: Step.S1_COVERAGE_SCOPE,
        Step.S1_COVERAGE_SCOPE: Step.S2_FOR_WHOM,
        Step.S2_FOR_WHOM: Step.S3_PERSONAL_DATA,
        Step.S3_PERSONAL_DATA: Step.S4_INITIAL_PRICE,
        Step.S4_INITIAL_PRICE: Step.S5_ADD_ONS,
        Step.S5_ADD_ONS: Step.S6_HEALTH_QUESTIONS,
        Step.S6_HEALTH_QUESTIONS: Step.S7_FINAL_PRICE,
        Step.S7_FINAL_PRICE: Step.S8_CONFIRM,
        Step.S8_CONFIRM: Step.CONVERTED,
    }
    if action == "back":
        # Backwards navigation never converts on the same step; persona may
        # then choose to abandon or continue on the next visit. For the
        # state machine we keep the user on the same step (the next loop
        # iteration gives them another chance, with detector signals raised).
        return current
    return forward.get(current, current)
