import type {
  CoachAction,
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
  const canonicalStepId = request.coachStepId ?? request.pageStepId;
  const events = derivePolicyEvents(request, policy);
  const shownInterventions = getShownInterventions(request.recentEvents);
  const budgetedImpressions = countBudgetedImpressions(request.recentEvents, policy);

  for (const rule of sortRules(policy.rules)) {
    if (!matchesRule(rule, canonicalStepId, events, policy)) {
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
  canonicalStepId: string | null,
  events: Set<CoachPolicyEvent>,
  policy: CoachPolicyDocument,
): boolean {
  if (rule.stepId && rule.stepId !== canonicalStepId) {
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
    cooldownMs: intervention.cooldownMs ?? policy.actionDefaults.cooldownMs,
    ctaLabel: intervention.ctaLabel,
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
