import { describe, expect, test } from "vitest";
import type { JourneySessionState, NormalizedEvent } from "@/shared/contracts";
import { deriveSignals } from "@/background/signal-detector";

const baseState: JourneySessionState = {
  routeFamily: "online_doctor",
  stage: "tariff_choice",
  baselinePriceMonthly: 41.3,
  latestPriceMonthly: 73.02,
  selectedCoverage: ["doctor_visits"],
  insuredPerson: "myself",
  selectedTariff: "optimal",
  selectedAddOns: [],
  fieldChangeCounts: {},
  lastDerivedContext: {},
  lastInteractionAt: Date.now(),
  lastAction: null,
  lastShownPlayByStage: {},
};

describe("deriveSignals", () => {
  test("detects long dwell from a step_leave event", () => {
    const event = makeEvent("step_leave", null, null, 30_000);
    expect(deriveSignals(event, baseState, [])).toContain("dwell");
  });

  test("detects inactivity", () => {
    const event = makeEvent("inactivity", "inactivity_timer", { idleMs: 30_000 });
    expect(deriveSignals(event, baseState, [])).toContain("inactivity");
  });

  test("detects repeated change", () => {
    const event = makeEvent("change", "socialversicherung", { filled: true });
    const state = {
      ...baseState,
      fieldChangeCounts: {
        socialversicherung: 2,
      },
    };
    expect(deriveSignals(event, state, [])).toContain("repeated_change");
  });

  test("detects back navigation", () => {
    const event = makeEvent("click", "back_button", null);
    expect(deriveSignals(event, baseState, [])).toContain("back_nav");
  });

  test("detects out-of-scope path choices", () => {
    const event = makeEvent("change", "insured_party_other", {
      intent: "out_of_scope_path",
      option: "andere_personen",
    });
    expect(deriveSignals(event, baseState, [])).toContain("path_oos");
  });

  test("detects out-of-scope tariff clicks", () => {
    const event = makeEvent("click", "selectionbutton_2", {
      intent: "out_of_scope_tariff",
      option: "opt_plus",
    });
    expect(deriveSignals(event, baseState, [])).toContain("tariff_click_oos");
  });

  test("detects price hover", () => {
    const event = makeEvent("pointerenter", "selectionbutton_1", { target: "price" });
    expect(deriveSignals(event, baseState, [])).toContain("price_hover");
  });
});

function makeEvent(
  type: NormalizedEvent["type"],
  elementKey: string | null,
  value: NormalizedEvent["value"],
  dwellMs: number | null = null,
): NormalizedEvent {
  return {
    derivedContext: {},
    dwellMs,
    elementKey,
    id: "evt_1",
    journeyStage: "tariff_choice",
    pageStepId: "s4_initial_price",
    sessionId: "session_1",
    ts: Date.now(),
    type,
    value,
  };
}
