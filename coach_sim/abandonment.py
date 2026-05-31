"""Abandonment reason classifier and UNIQA product suggestions.

Maps (step, detected_events, persona_id) -> a human-readable reason why the
user stopped, plus a concrete recommendation UNIQA can act on. This gives the
track partner visibility into the *why* behind every drop-off, not just the
*where*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .detector import Event
from .journey import Step


@dataclass
class AbandonmentInsight:
    step: str
    persona: str
    reason: str           # why the user left
    signal_evidence: str  # which behavioral signals triggered this conclusion
    suggestion: str       # concrete UNIQA product/UX recommendation


# Master taxonomy: (step, frozenset of matching events) -> (reason, suggestion)
# Evaluated in order; first match wins.
_TAXONOMY: list[tuple[Step, frozenset[Event], str, str]] = [

    # ── S3: personal data ──────────────────────────────────────────────────
    (Step.S3_PERSONAL_DATA, frozenset({Event.CANCEL_INTENT}),
     "User unwilling to submit DOB and social insurance number — privacy concern "
     "about why sensitive data is collected at the quote stage.",
     "Add a one-line in-context note next to each field: 'Your DOB determines age "
     "brackets; your SV number is only used to pre-fill known health conditions. "
     "No data is stored until you complete the purchase.' Keep the note under "
     "the field, not in a separate modal."),

    # ── S4: initial price ─────────────────────────────────────────────────
    (Step.S4_INITIAL_PRICE, frozenset({Event.CANCEL_INTENT}),
     "User showed clear abandonment intent at the initial price screen — "
     "hovered Cancel or went inactive without selecting a tariff.",
     "Add a 'Not sure? Save your quote' CTA that emails the user a resume "
     "link. This captures users who are price-sensitive but not yet decided, "
     "giving UNIQA a low-friction retargeting touchpoint without requiring "
     "an account or commitment."),

    # ── S4: initial price ──────────────────────────────────────────────────
    (Step.S4_INITIAL_PRICE, frozenset({Event.OUT_OF_SCOPE_TARIFF, Event.BACK_NAV}),
     "User clicked Opt. Plus or Premium expecting to complete online, discovered "
     "it requires an advisor call, felt misled and abandoned.",
     "Visually separate advisor-only tariffs with a lock icon and a short label "
     "'Requires a 15-min advisory call' *before* displaying the price — not after "
     "the click. This sets expectations and converts a confusion exit into an "
     "intentional advisor handoff."),

    (Step.S4_INITIAL_PRICE, frozenset({Event.PRICE_FIXATION, Event.CANCEL_INTENT}),
     "User fixated on the monthly price for an extended period then abandoned — "
     "price anchoring: the quoted amount feels high relative to their expectation.",
     "Surface a daily-cost reframe directly on the tariff card ('EUR 2.25/day') "
     "alongside the monthly figure, without requiring the user to hover or click. "
     "Also show a one-line market benchmark: 'In the lower third of Austrian "
     "private-doctor tariffs for equivalent cover.'"),

    (Step.S4_INITIAL_PRICE, frozenset({Event.BACK_NAV}),
     "User navigated back after seeing the price — likely to reconsider or "
     "compare with an alternative they have in mind.",
     "Introduce a 'Save my quote' CTA on the tariff selection screen. "
     "A saved-quote email keeps the user in the funnel across sessions and "
     "gives UNIQA a retargeting touchpoint without requiring an account."),

    (Step.S4_INITIAL_PRICE, frozenset({Event.LONG_DWELL}),
     "User spent significantly longer than average on the price screen without "
     "making a selection — decision paralysis from four tariff options.",
     "Add a 'Most popular for someone like you' highlight on Optimal based on "
     "the inputs already collected. Reducing four choices to one recommended "
     "option with a clear rationale cuts decision paralysis."),

    # ── S5: add-ons ─────────────────────────────────────────────────────────
    (Step.S5_ADD_ONS, frozenset({Event.CANCEL_INTENT}),
     "User abandoned at the add-on selection step — optional extras added "
     "unexpected complexity and felt like up-selling pressure.",
     "Change the add-on UX from opt-in checkboxes to a single 'Skip / Keep "
     "recommended bundle' toggle. Pre-select the most common bundle for the "
     "user's age group; let them remove items rather than add them. "
     "This reduces friction while maintaining average order value."),

    (Step.S5_ADD_ONS, frozenset({Event.LONG_DWELL}),
     "User dwelled long on the add-on screen without completing — likely "
     "reading coverage descriptions without understanding what they need.",
     "Condense each add-on to a single-sentence benefit statement in plain "
     "language ('Covers pregnancy costs up to EUR 2,000'). Link to details "
     "only for users who click 'Learn more'."),

    # ── S6: health questions ────────────────────────────────────────────────
    (Step.S6_HEALTH_QUESTIONS, frozenset({Event.CANCEL_INTENT}),
     "User stopped at the health questionnaire — discomfort sharing medical "
     "history or concern that honest answers will raise the price significantly.",
     "Add a persistent banner during this section: 'Your answers adjust your "
     "premium calculation. They are not shared with third parties and do not "
     "affect what is covered under your policy.' Also add a real-time price "
     "estimator showing how the current answers affect the final figure — "
     "removing the fear of a surprise at S7."),

    (Step.S6_HEALTH_QUESTIONS, frozenset({Event.LONG_DWELL}),
     "User spent excessive time on the health questionnaire — form fatigue "
     "from too many yes/no questions without context.",
     "Group related health conditions into collapsible sections with a "
     "single parent question ('Have you had any cardiovascular conditions in "
     "the past 5 years?'). Show a progress indicator within the health "
     "section ('3 of 5 question groups complete')."),

    # ── S7: final price ─────────────────────────────────────────────────────
    (Step.S7_FINAL_PRICE, frozenset({Event.PRICE_GAP_SHOCK, Event.CANCEL_INTENT}),
     "Final premium materially higher than the initial estimate — user felt "
     "misled by the gap and abandoned at the commitment step.",
     "At S4, replace the single initial price with a transparent range: "
     "'Optimal: EUR 68–84/month depending on your health profile.' "
     "At S7, show a one-line breakdown: '+EUR X.XX because [condition].' "
     "Transparency at S4 prevents shock at S7; the breakdown at S7 converts "
     "shock into understanding."),

    (Step.S7_FINAL_PRICE, frozenset({Event.CANCEL_INTENT}),
     "User abandoned at the final price confirmation — last-minute cold feet "
     "at the commitment point, not necessarily price-driven.",
     "Add three trust elements directly on the S7 screen: (1) '14-day "
     "cancellation, no questions asked', (2) a count of recent online "
     "purchases ('847 people completed online this month'), (3) a one-line "
     "quote from a verified customer. These reduce purchase anxiety without "
     "changing the price."),

    (Step.S7_FINAL_PRICE, frozenset({Event.PRICE_FIXATION}),
     "User hovered on the final price for an unusually long time — likely "
     "mentally comparing to competitor quotes or their budget ceiling.",
     "Add a market comparison widget at S7 (same as S4 but for the "
     "personalised final price): 'Your personalised Optimal at EUR X.XX is "
     "in the lower half of equivalent plans from Austrian private insurers.' "
     "Concrete benchmark data converts a doubt into a confirmed decision."),

    # ── S8: confirm ─────────────────────────────────────────────────────────
    (Step.S8_CONFIRM, frozenset({Event.CANCEL_INTENT}),
     "User abandoned at the final confirmation screen — last-second anxiety "
     "about submitting personal data and payment details.",
     "Restructure the S8 summary page: lead with the coverage benefits "
     "('What you get') before showing the price and payment section. "
     "Add a prominent '14-day free cancellation' badge immediately above "
     "the submit button. Consider a one-click Apple/Google Pay option to "
     "reduce form friction at the final step."),
]

# Fallback when no specific pattern matches.
_FALLBACK: dict[Step, tuple[str, str]] = {
    Step.S1_COVERAGE_SCOPE: (
        "User left at the first step before selecting a coverage type.",
        "Review the S1 screen for clarity — test whether renaming 'Bei Arztbesuchen' "
        "to 'Doctor visits & outpatient care' reduces early exits from users who "
        "are unsure which option applies to them."
    ),
    Step.S2_FOR_WHOM: (
        "User left at the 'for whom' step before selecting themselves or another person.",
        "Add a brief clarification: 'Select Myself if you are buying for yourself. "
        "To insure a family member, select Other persons — an advisor will help.' "
        "This removes ambiguity for users buying for a partner or child."
    ),
    Step.S3_PERSONAL_DATA: (
        "User left before completing the personal data step.",
        "Investigate whether the social insurance number field is causing "
        "hesitation — test removing it from the quote flow and collecting it "
        "only at purchase completion."
    ),
    Step.S4_INITIAL_PRICE: (
        "User left at tariff selection without a clear single signal.",
        "Run a qualitative user test on the tariff comparison screen to "
        "identify whether confusion, price, or lack of guidance is the "
        "primary driver."
    ),
    Step.S5_ADD_ONS: (
        "User left at the add-on selection step — likely overwhelmed by optional "
        "extras presented as a separate decision after the tariff was chosen.",
        "Change add-ons from opt-in checkboxes to a single pre-selected bundle "
        "with a 'Remove extras' toggle. Alternatively, move add-on upsell to a "
        "post-purchase email sequence — this removes friction from the core funnel "
        "without sacrificing average order value."
    ),
    Step.S6_HEALTH_QUESTIONS: (
        "User left during the health questionnaire.",
        "Audit the number of health questions against what is strictly "
        "required for pricing; remove any that can be inferred from age or "
        "standard actuarial tables."
    ),
    Step.S7_FINAL_PRICE: (
        "User left at the final price without a clear primary signal.",
        "Investigate the size of the price delta between S4 and S7 for "
        "this segment — a delta above EUR 5 correlates with the highest "
        "abandonment rates."
    ),
    Step.S8_CONFIRM: (
        "User abandoned at the final confirmation screen — last-second anxiety "
        "about committing, likely triggered by the payment or terms section.",
        "Restructure S8: show the coverage summary and '14-day free cancellation' "
        "badge before the payment section, not after. Add a one-click payment "
        "option (Apple/Google Pay) to reduce manual form entry at the last step. "
        "Surface 2-3 short customer quotes directly above the submit button."
    ),
}


def classify(step: Step, events: Sequence[Event],
             persona_id: str) -> AbandonmentInsight:
    """Return the best-matching abandonment reason and UNIQA suggestion.

    Matching is in two passes:
    1. Signal-based rules (taxonomy): require at least one matching event.
    2. Step-level fallback (rich content per step, not a generic message).
    """
    event_set = frozenset(e for e in events if e != Event.NONE)

    # Pass 1 — signal-based match.
    for rule_step, rule_events, reason, suggestion in _TAXONOMY:
        if rule_step == step and rule_events & event_set:
            evidence = ", ".join(
                e.value for e in rule_events if e in event_set
            ) or "behavioural pattern"
            return AbandonmentInsight(
                step=step.value,
                persona=persona_id,
                reason=reason,
                signal_evidence=evidence,
                suggestion=suggestion,
            )

    # Pass 2 — step-level fallback with actionable content.
    fallback_reason, fallback_suggestion = _FALLBACK.get(step, (None, None))
    if fallback_reason:
        return AbandonmentInsight(
            step=step.value,
            persona=persona_id,
            reason=fallback_reason,
            signal_evidence="step-level pattern (low signal strength)",
            suggestion=fallback_suggestion,
        )

    return AbandonmentInsight(
        step=step.value,
        persona=persona_id,
        reason=f"User abandoned at {step.value} without a dominant behavioural signal.",
        signal_evidence="none",
        suggestion=(
            "Instrument this step with real click-stream data to identify "
            "whether the drop is price-, trust-, or complexity-driven before "
            "committing to a fix."
        ),
    )


def insights_from_results(results: list) -> list[AbandonmentInsight]:
    """Classify abandonment reasons across a batch of JourneyResults.

    Re-runs the detector on the terminal step's raw signals so this works
    for both baseline runs (no coach, no coach_events) and coached runs.
    """
    from .detector import Detector
    detector = Detector()
    insights = []
    for r in results:
        if not r.abandoned or not r.steps:
            continue

        # The last StepObservation is the actual funnel step where the user left.
        # r.terminal_step is Step.ABANDONED (the state machine terminal), not useful.
        last_obs = r.steps[-1]
        try:
            actual_step = Step(last_obs.step_id)
        except ValueError:
            continue

        # Re-run detector on the raw signals — works for baseline and coached runs.
        at_s7 = actual_step == Step.S7_FINAL_PRICE
        events = detector.detect(
            list(last_obs.signals),
            initial_price=r.initial_price_eur if at_s7 else None,
            final_price=r.final_price_eur if at_s7 else None,
        )

        insights.append(classify(actual_step, events, r.persona_id))
    return insights


__all__ = ["AbandonmentInsight", "classify", "insights_from_results"]
