import { describe, expect, test } from "vitest";
import { createApp } from "../src/app";
import { MemoryRuntimeRepository, type RuntimeRepository } from "../src/repository";
import type { AppConfig } from "../src/config";
import type { JourneyOutcome, JourneySnapshot } from "@uniqa-conversion-coach/shared/contracts";

function makeConfig(): AppConfig {
  return {
    host: "127.0.0.1",
    port: 8787,
  };
}

describe("runtime routes", () => {
  test("stores a snapshot and returns a deterministic decision", async () => {
    const repository = new MemoryRuntimeRepository();
    const app = await createApp({ config: makeConfig(), repository });

    const response = await app.inject({
      method: "POST",
      url: "/api/runtime/decide",
      payload: makeSnapshot({
        routeFamily: "advisor_tariff",
        stage: "tariff_choice",
        selectedTariff: "premium",
        eligibleGoals: ["submitted_advisor_lead"],
      }),
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().decision.playId).toBe("online_tariff_recovery");

    const trace = await repository.getSessionTrace("session_1");
    expect(trace.snapshots).toHaveLength(1);
    expect(trace.decisions).toHaveLength(1);

    await app.close();
  });

  test("stores an outcome and exposes it via the replay endpoint", async () => {
    const repository = new MemoryRuntimeRepository();
    const app = await createApp({ config: makeConfig(), repository });

    await app.inject({
      method: "POST",
      url: "/api/runtime/decide",
      payload: makeSnapshot({}),
    });

    const outcome: JourneyOutcome = {
      sessionId: "session_1",
      routeFamily: "online_doctor",
      terminalStage: "done",
      outcome: "converted_online",
      finalTariff: "optimal",
      finalPriceMonthly: 68.14,
      decidedAt: Date.now(),
    };

    const storeResponse = await app.inject({
      method: "POST",
      url: "/api/runtime/outcome",
      payload: outcome,
    });
    expect(storeResponse.statusCode).toBe(200);

    const replayResponse = await app.inject({
      method: "GET",
      url: "/api/runtime/sessions/session_1",
    });

    expect(replayResponse.statusCode).toBe(200);
    expect(replayResponse.json().outcome.outcome.outcome).toBe("converted_online");
    expect(replayResponse.json().snapshots).toHaveLength(1);

    await app.close();
  });

  test("still returns a decision when telemetry persistence fails", async () => {
    const repository: RuntimeRepository = {
      async storeSnapshot() {
        throw new Error("db unavailable");
      },
      async getSnapshotsBySession() {
        return [];
      },
      async storeDecision() {
        throw new Error("db unavailable");
      },
      async getDecisionsBySession() {
        return [];
      },
      async storeOutcome() {
        throw new Error("db unavailable");
      },
      async getOutcomeBySession() {
        return null;
      },
      async getSessionTrace(sessionId: string) {
        return {
          sessionId,
          snapshots: [],
          decisions: [],
          outcome: null,
        };
      },
    };
    const app = await createApp({ config: makeConfig(), repository });

    const response = await app.inject({
      method: "POST",
      url: "/api/runtime/decide",
      payload: makeSnapshot({
        routeFamily: "advisor_tariff",
        stage: "tariff_choice",
        selectedTariff: "premium",
        eligibleGoals: ["submitted_advisor_lead"],
      }),
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().decision.playId).toBe("online_tariff_recovery");

    await app.close();
  });
});

function makeSnapshot(overrides: Partial<JourneySnapshot>): JourneySnapshot {
  return {
    sessionId: "session_1",
    url: "https://www.uniqa.at/rechner/krankenversicherung/",
    routeFamily: "online_doctor",
    stage: "quote_basics",
    selectedCoverage: ["doctor_visits"],
    insuredPerson: "myself",
    selectedTariff: "start",
    selectedAddOns: [],
    visiblePriceMonthly: 38.74,
    visiblePriceDaily: 1.29,
    priceDeltaMonthly: null,
    fieldCompletion: 0.5,
    validationErrorCount: 0,
    signals: [],
    lastAction: null,
    eligibleGoals: ["converted_online"],
    ...overrides,
  };
}
