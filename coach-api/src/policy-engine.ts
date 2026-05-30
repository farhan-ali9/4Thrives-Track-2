import type {
  CoachAction,
  CoachCta,
  CoachPlacement,
  CoachRequest,
  NormalizedEvent,
} from "@uniqa-conversion-coach/shared/contracts";
import type {
  CoachPolicyDocument,
  CoachPolicyEvent,
  CoachPolicyIntervention,
  CoachPolicyRule,
} from "@uniqa-conversion-coach/shared/policy";

const LONG_DWELL_MS = 25_000;
const RECENT_PRICE_HOVER_WINDOW_MS = 10_000;

export function evaluateCoachRequest(
  request: CoachRequest,
  policy: CoachPolicyDocument,
): CoachAction[] {
  const canonicalStepId = request.pageStepId ?? request.coachStepId;
  const candidateStepIds = new Set(
    [request.pageStepId, request.coachStepId].filter(Boolean) as string[],
  );
  const events = derivePolicyEvents(request, policy);
  const shownInterventions = getShownInterventions(request.recentEvents);
  const budgetedImpressions = countBudgetedImpressions(request.recentEvents, policy);

  for (const rule of sortRules(policy.rules)) {
    if (!matchesRule(rule, candidateStepIds, events, policy)) {
      continue;
    }

    const chosenInterventionId = rule.interventions.find(
      (interventionId) =>
        !shownInterventions.has(interventionId) && interventionId in policy.interventions,
    );

    if (!chosenInterventionId) {
      return [];
    }

    const intervention = policy.interventions[chosenInterventionId];
    const bypassBudget = rule.bypassBudget || intervention.bypassBudget === true;
    if (!bypassBudget && budgetedImpressions >= policy.policy.maxInterventionsPerJourney) {
      return [];
    }

    return [materializeAction(chosenInterventionId, intervention, canonicalStepId, policy)];
  }

  return [];
}

export function derivePolicyEvents(
  request: CoachRequest,
  policy: CoachPolicyDocument,
): Set<CoachPolicyEvent> {
  const events = new Set<CoachPolicyEvent>();
  const signals = new Set(request.detectedSignals);

  if (signals.has("dwell")) {
    events.add("long_dwell");
  }
  if (signals.has("back_nav") || signals.has("scroll_back")) {
    events.add("back_nav");
  }
  if (signals.has("repeated_change")) {
    events.add("repeated_change");
  }
  if (signals.has("path_oos")) {
    events.add("oos_path");
  }
  if (signals.has("tariff_click_oos")) {
    events.add("oos_tariff");
  }
  if (signals.has("cancel_hover") || signals.has("inactivity")) {
    events.add("cancel_intent");
  }
  if (
    signals.has("price_hover") &&
    (signals.has("dwell") || hasRecentPriceHover(request.recentEvents))
  ) {
    events.add("price_fixation");
  }
  if (
    request.currentOffer.priceDelta !== null &&
    request.currentOffer.priceDelta >= policy.policy.priceGapShockThresholdEur
  ) {
    events.add("price_gap_shock");
  }

  if (!events.size) {
    events.add("none");
  }

  return events;
}

function sortRules(rules: CoachPolicyRule[]): CoachPolicyRule[] {
  return rules
    .map((rule, index) => ({ rule, index }))
    .filter(({ rule }) => rule.enabled !== false)
    .sort((left, right) => {
      if (left.rule.priority === right.rule.priority) {
        return left.index - right.index;
      }
      return left.rule.priority - right.rule.priority;
    })
    .map(({ rule }) => rule);
}

function matchesRule(
  rule: CoachPolicyRule,
  candidateStepIds: Set<string>,
  events: Set<CoachPolicyEvent>,
  policy: CoachPolicyDocument,
): boolean {
  if (rule.stepId && !candidateStepIds.has(rule.stepId)) {
    return false;
  }

  if (!rule.anyEvents.length && !rule.anyEventsGroup) {
    return true;
  }

  const hasExplicitEvent = rule.anyEvents.some((event) => events.has(event));
  if (hasExplicitEvent) {
    return true;
  }

  const groupEvents = resolveEventGroup(rule.anyEventsGroup, policy);
  return groupEvents.some((event) => events.has(event));
}

function resolveEventGroup(
  groupName: string | null,
  policy: CoachPolicyDocument,
): CoachPolicyEvent[] {
  if (groupName === "hesitation") {
    return policy.policy.hesitationEvents;
  }

  return [];
}

function getShownInterventions(recentEvents: NormalizedEvent[]): Set<string> {
  return new Set(
    recentEvents
      .filter((event) => event.type === "coach_impression" && event.elementKey)
      .map((event) => event.elementKey as string),
  );
}

function countBudgetedImpressions(
  recentEvents: NormalizedEvent[],
  policy: CoachPolicyDocument,
): number {
  return recentEvents.filter((event) => {
    if (event.type !== "coach_impression" || !event.elementKey) {
      return false;
    }

    const intervention = policy.interventions[event.elementKey];
    return Boolean(intervention && intervention.bypassBudget !== true);
  }).length;
}

function materializeAction(
  interventionId: string,
  intervention: CoachPolicyIntervention,
  canonicalStepId: string | null,
  policy: CoachPolicyDocument,
): CoachAction {
  const stepPlacement = canonicalStepId
    ? (policy.placementByStep as Record<string, CoachPlacement | string | undefined>)[canonicalStepId]
    : undefined;

  return {
    body: intervention.body,
    cta: materializeCta(interventionId, intervention, canonicalStepId),
    cooldownMs: intervention.cooldownMs ?? policy.actionDefaults.cooldownMs,
    ctaLabel: intervention.cta?.label ?? intervention.ctaLabel,
    dismissible: intervention.dismissible ?? policy.actionDefaults.dismissible,
    id: interventionId,
    kind: interventionId,
    placement:
      intervention.placement ??
      (typeof stepPlacement === "string" ? (stepPlacement as CoachPlacement) : undefined) ??
      policy.actionDefaults.placement,
    title: intervention.title,
  };
}

function materializeCta(
  interventionId: string,
  intervention: CoachPolicyIntervention,
  canonicalStepId: string | null,
): CoachCta | null {
  if (intervention.cta === null || intervention.ctaLabel === null) {
    return intervention.cta ?? null;
  }

  if (intervention.cta) {
    return {
      label: intervention.cta.label,
      prompt: intervention.cta.prompt ?? null,
      target: intervention.cta.target ?? null,
      telemetryKey: intervention.cta.telemetryKey ?? interventionId,
      type: intervention.cta.type,
    };
  }

  const label = intervention.ctaLabel;
  if (!label) {
    return null;
  }

  const target = defaultCtaTarget(interventionId, canonicalStepId);
  return {
    label,
    prompt: defaultChatPrompt(interventionId),
    target: target.target,
    telemetryKey: interventionId,
    type: target.type,
  };
}

function defaultCtaTarget(
  interventionId: string,
  canonicalStepId: string | null,
): Pick<CoachCta, "target" | "type"> {
  if (interventionId === "tariff_route_explainer") {
    return { target: "optimal", type: "select_tariff" };
  }
  if (interventionId === "advisor_route") {
    return { target: "advisor", type: "advisor_handoff" };
  }
  if (interventionId === "save_progress") {
    return { target: "progress", type: "save_progress" };
  }
  if (canonicalStepId === "s3_personal_data" || canonicalStepId === "s6_personal_medical_data") {
    return { target: "step_anchor", type: "focus_field" };
  }
  return { target: "primary_cta", type: "continue" };
}

function defaultChatPrompt(interventionId: string): string | null {
  if (interventionId === "price_reframe" || interventionId === "market_comparison") {
    return "Help me compare the online tariffs and understand the current monthly price.";
  }
  if (interventionId === "trust_signal") {
    return "Explain why this information is needed and what happens next.";
  }
  if (interventionId === "price_gap_transparency") {
    return "Explain why the final price changed and whether I can still continue online.";
  }
  if (interventionId === "simplified_explanation") {
    return "Help me decide whether to continue with or without optional add-ons.";
  }
  return null;
}

function hasRecentPriceHover(recentEvents: NormalizedEvent[]): boolean {
  const lastHover = [...recentEvents]
    .reverse()
    .find(
      (event) =>
        event.type === "pointerenter" &&
        (isPriceHoverEvent(event) || (event.dwellMs ?? 0) >= LONG_DWELL_MS),
    );

  if (!lastHover) {
    return false;
  }

  return Date.now() - lastHover.ts <= RECENT_PRICE_HOVER_WINDOW_MS;
}

function isPriceHoverEvent(event: NormalizedEvent): boolean {
  return (
    typeof event.value === "object" &&
    event.value !== null &&
    "target" in event.value &&
    event.value.target === "price"
  );
}
