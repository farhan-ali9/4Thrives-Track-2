import { describe, expect, test } from "vitest";
import type { JourneySnapshot } from "@uniqa-conversion-coach/shared/contracts";
import { decideJourney } from "../src/journey-strategy";

describe("journey strategy", () => {
  test("returns trust_builder for quote basics on the online route", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "quote_basics",
    }));

    expect(decision?.playId).toBe("trust_builder");
  });

  test("returns trust_builder on health data step entry", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "health_data",
      signals: [],
    }));

    expect(decision?.playId).toBe("trust_builder");
    expect(decision?.cards[0]?.body).toContain("persoenliche Pruefung");
    expect(decision?.cards[0]?.cta?.label).toBe("Warum wird das hier abgefragt?");
  });

  test("returns price_reframe for the tariff choice stage", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "tariff_choice",
      visiblePriceMonthly: 68.14,
      visiblePriceDaily: 2.27,
    }));

    expect(decision?.playId).toBe("price_reframe");
    expect(decision?.domMutations.some((entry) => entry.kind === "tariff_badges")).toBe(true);
  });

  test("tailors the tariff popup for Start", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "tariff_choice",
      selectedTariff: "start",
      visiblePriceMonthly: 38.74,
      visiblePriceDaily: 1.29,
    }));

    expect(decision?.cards[0]?.title).toBe("Start preislich eingeordnet");
    expect(decision?.cards[0]?.body).toContain("schlankere Online-Tarif");
    expect(decision?.cards[0]?.cta?.label).toBe("Warum Start?");
  });

  test("tailors the tariff popup for Optimal", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "tariff_choice",
      selectedTariff: "optimal",
      visiblePriceMonthly: 68.14,
      visiblePriceDaily: 2.27,
    }));

    expect(decision?.cards[0]?.title).toBe("Optimal preislich eingeordnet");
    expect(decision?.cards[0]?.body).toContain("mehr Leistung als bei Start");
    expect(decision?.cards[0]?.cta?.label).toBe("Warum Optimal?");
  });

  test("returns online_tariff_recovery for advisor tariffs", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "advisor_tariff",
      stage: "tariff_choice",
      selectedTariff: "premium",
    }));

    expect(decision?.playId).toBe("online_tariff_recovery");
  });

  test("returns price_change_explainer when the final price changes", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "online_doctor",
      stage: "price_review",
      visiblePriceMonthly: 74.82,
      priceDeltaMonthly: 6.68,
    }));

    expect(decision?.playId).toBe("price_change_explainer");
  });

  test("returns advisor_lead_push on advisor contact stages", () => {
    const decision = decideJourney(makeSnapshot({
      routeFamily: "advisor_coverage",
      stage: "advisor_contact",
    }));

    expect(decision?.playId).toBe("advisor_lead_push");
  });
});

function makeSnapshot(overrides: Partial<JourneySnapshot>): JourneySnapshot {
  return {
    sessionId: "session_1",
    url: "https://www.uniqa.at/rechner/krankenversicherung/",
    routeFamily: "online_doctor",
    stage: "tariff_choice",
    selectedCoverage: ["doctor_visits"],
    insuredPerson: "myself",
    selectedTariff: "optimal",
    selectedAddOns: [],
    visiblePriceMonthly: 68.14,
    visiblePriceDaily: 2.27,
    priceDeltaMonthly: null,
    fieldCompletion: 1,
    validationErrorCount: 0,
    signals: [],
    lastAction: null,
    eligibleGoals: ["converted_online"],
    ...overrides,
  };
}
