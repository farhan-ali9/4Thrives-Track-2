import { describe, expect, test } from "vitest";
import { seedPolicy } from "@uniqa-conversion-coach/shared";
import type { CoachRequest, NormalizedEvent } from "@uniqa-conversion-coach/shared/contracts";
import { derivePolicyEvents, evaluateCoachRequest } from "../src/policy-engine";

describe("policy engine", () => {
  test("prioritizes advisor-only tariff routing over generic price nudges", () => {
    const request = makeRequest({
      coachStepId: "s4_initial_price",
      detectedSignals: ["tariff_click_oos", "dwell", "price_hover"],
      pageStepId: "s4_initial_price",
    });

    const actions = evaluateCoachRequest(request, seedPolicy);
    expect(actions[0]?.id).toBe("tariff_route_explainer");
  });

  test("respects the intervention budget for budgeted rules", () => {
    const request = makeRequest({
      coachStepId: "s4_initial_price",
      detectedSignals: ["dwell", "price_hover"],
      pageStepId: "s4_initial_price",
      recentEvents: [
        makeCoachImpression("trust_signal"),
        makeCoachImpression("price_reframe"),
        makeCoachImpression("market_comparison"),
      ],
    });

    const actions = evaluateCoachRequest(request, seedPolicy);
    expect(actions).toHaveLength(0);
  });

  test("allows bypass-budget routing rules even after the budget is spent", () => {
    const request = makeRequest({
      coachStepId: "s1_coverage_scope",
      detectedSignals: ["path_oos"],
      pageStepId: "s1_coverage_scope",
      recentEvents: [
        makeCoachImpression("trust_signal"),
        makeCoachImpression("price_reframe"),
        makeCoachImpression("market_comparison"),
      ],
    });

    const actions = evaluateCoachRequest(request, seedPolicy);
    expect(actions[0]?.id).toBe("advisor_route");
  });

  test("uses the step placement defaults when an intervention has no explicit placement", () => {
    const request = makeRequest({
      coachStepId: "s5_add_ons",
      detectedSignals: ["dwell"],
      pageStepId: "s5_add_ons",
    });

    const actions = evaluateCoachRequest(request, seedPolicy);
    expect(actions[0]?.id).toBe("simplified_explanation");
    expect(actions[0]?.placement).toBe("near-primary-cta");
  });

  test("derives final-price shock events from the current offer delta", () => {
    const request = makeRequest({
      coachStepId: "s7_final_price",
      currentOffer: {
        priceDelta: 4.2,
        selectedTariff: "optimal",
        visiblePrice: 72.4,
      },
      detectedSignals: [],
      pageStepId: "s7_final_price",
    });

    const events = derivePolicyEvents(request, seedPolicy);
    const actions = evaluateCoachRequest(request, seedPolicy);

    expect(events.has("price_gap_shock")).toBe(true);
    expect(actions[0]?.id).toBe("price_gap_transparency");
  });

  test("reassures on medical data hesitation", () => {
    const request = makeRequest({
      coachStepId: "s6_personal_medical_data",
      detectedSignals: ["inactivity"],
      pageStepId: "s6_personal_medical_data",
    });

    const actions = evaluateCoachRequest(request, seedPolicy);
    expect(actions[0]?.id).toBe("trust_signal");
  });
});

function makeRequest(overrides: Partial<CoachRequest>): CoachRequest {
  return {
    coachStepId: overrides.coachStepId ?? null,
    currentOffer: overrides.currentOffer ?? {
      priceDelta: null,
      selectedTariff: "optimal",
      visiblePrice: 68.14,
    },
    derivedContext: overrides.derivedContext ?? {},
    detectedSignals: overrides.detectedSignals ?? [],
    pageStepId: overrides.pageStepId ?? null,
    recentEvents: overrides.recentEvents ?? [],
    sessionId: overrides.sessionId ?? "session_1",
  };
}

function makeCoachImpression(actionId: string): NormalizedEvent {
  return {
    coachStepId: "s4_initial_price",
    derivedContext: {},
    dwellMs: null,
    elementKey: actionId,
    id: `evt_${actionId}`,
    pageStepId: "s4_initial_price",
    sessionId: "session_1",
    ts: Date.now(),
    type: "coach_impression",
    value: {
      actionKind: actionId,
    },
  };
}
