import { describe, expect, test } from "vitest";
import { CoachClient } from "@/background/coach-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { MemoryStorageAdapter, UniqaStorage } from "@/background/storage";
import type { JourneyDecision, NormalizedEvent } from "@/shared/contracts";

describe("runtime orchestrator", () => {
  test("classifies the doctor-only flow as online_doctor", async () => {
    const orchestrator = createOrchestrator();
    const response = await orchestrator.handleEvent(
      makeEvent("change", "coverage_doctor", {
        checked: true,
      }, {
        selectedCoverage: ["doctor_visits"],
      }, "coverage_choice"),
      "https://www.uniqa.at/rechner/krankenversicherung/",
    );

    expect(response.snapshot?.routeFamily).toBe("online_doctor");
    expect(response.snapshot?.eligibleGoals).toEqual(["converted_online"]);
  });

  test("classifies hospital selection as advisor_coverage", async () => {
    const orchestrator = createOrchestrator();
    const response = await orchestrator.handleEvent(
      makeEvent("change", "coverage_hospital", {
        checked: true,
        intent: "out_of_scope_path",
      }, {
        selectedCoverage: ["hospital"],
      }, "coverage_choice"),
      "https://www.uniqa.at/rechner/krankenversicherung/",
    );

    expect(response.snapshot?.routeFamily).toBe("advisor_coverage");
    expect(response.snapshot?.eligibleGoals).toEqual(["submitted_advisor_lead"]);
  });

  test("classifies other-persons selection as advisor_other_persons", async () => {
    const orchestrator = createOrchestrator();
    const response = await orchestrator.handleEvent(
      makeEvent("change", "insured_party_other", {
        checked: true,
        intent: "out_of_scope_path",
      }, {
        insuredPerson: "other_persons",
      }, "insured_person"),
      "https://www.uniqa.at/rechner/krankenversicherung/",
    );

    expect(response.snapshot?.routeFamily).toBe("advisor_other_persons");
  });

  test("classifies Opt. Plus selection as advisor_tariff", async () => {
    const orchestrator = createOrchestrator();
    const response = await orchestrator.handleEvent(
      makeEvent("click", "selectionbutton_2", {
        intent: "out_of_scope_tariff",
        option: "opt_plus",
      }, {
        selectedTariff: "opt. plus",
        visiblePriceMonthly: 105.07,
      }, "tariff_choice"),
      "https://www.uniqa.at/rechner/krankenversicherung/",
    );

    expect(response.snapshot?.routeFamily).toBe("advisor_tariff");
    expect(response.decision?.playId).toBe("online_tariff_recovery");
  });

  test("classifies mixed doctor and hospital coverage as advisor_coverage", async () => {
    const orchestrator = createOrchestrator();
    const response = await orchestrator.handleEvent(
      makeEvent("change", "coverage_mix", {
        checked: true,
      }, {
        selectedCoverage: ["doctor_visits", "hospital"],
      }, "coverage_choice"),
      "https://www.uniqa.at/rechner/krankenversicherung/",
    );

    expect(response.snapshot?.routeFamily).toBe("advisor_coverage");
  });
});

function createOrchestrator(): UniqaEventOrchestrator {
  const storage = new UniqaStorage(new MemoryStorageAdapter());
  const client = new CoachClient(
    "http://127.0.0.1:8787/api/runtime/decide",
    "http://127.0.0.1:8787/api/runtime/outcome",
    async (_url, init) => {
      const snapshot = JSON.parse(String(init?.body ?? "{}"));
      const decision: JourneyDecision | null =
        snapshot.routeFamily === "advisor_tariff"
          ? {
              decisionId: "dec_1",
              goal: "submitted_advisor_lead",
              playId: "online_tariff_recovery",
              priority: 100,
              cooldownMs: 45_000,
              cards: [],
              domMutations: [],
              chatPrompt: null,
            }
          : null;

      return {
        ok: true,
        status: 200,
        json: async () => ({ decision }),
      } as Response;
    },
  );
  return new UniqaEventOrchestrator(storage, client);
}

function makeEvent(
  type: NormalizedEvent["type"],
  elementKey: string | null,
  value: NormalizedEvent["value"],
  derivedContext: NormalizedEvent["derivedContext"],
  journeyStage: NormalizedEvent["journeyStage"],
): NormalizedEvent {
  return {
    derivedContext,
    dwellMs: null,
    elementKey,
    id: `evt_${Math.random()}`,
    journeyStage,
    pageStepId: "step",
    sessionId: "session_1",
    ts: Date.now(),
    type,
    value,
  };
}
