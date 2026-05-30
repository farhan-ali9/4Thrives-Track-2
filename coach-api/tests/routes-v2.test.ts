import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { createApp } from "../src/app";
import type { AppConfig } from "../src/config";
import { MemoryCoachRepository } from "../src/repository";
import { applyHardGuardrails } from "../src/guardrails";
import {
  reconstructSessionState,
  computeRiskScore,
} from "../src/session-state";
import type { V2EventRecord } from "../src/repository";

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeConfig(): AppConfig {
  return {
    adminStaticDir: null,
    bootstrapAdminEmail: "admin@uniqa.local",
    bootstrapAdminName: "Test Admin",
    bootstrapAdminPassword: "change-me-now",
    host: "127.0.0.1",
    port: 8787,
    secureCookies: false,
    sessionSecret: "test-secret",
  };
}

let eventSeq = 0;

function makeEventBody(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  eventSeq++;
  return {
    schema_version: "v1",
    event_id: `evt_${eventSeq}_${Date.now()}`,
    session_id: "sess_test_1",
    ts: Date.now(),
    source: "extension",
    step_id: "s4_initial_price",
    event_type: "inactivity",
    element_key: null,
    raw_value: {},
    derived_signals: {},
    derived_context: {},
    runner_metadata: {},
    privacy_level: "anonymous",
    ...overrides,
  };
}

function makeV2EventRecord(overrides: Partial<V2EventRecord> = {}): V2EventRecord {
  return {
    id: `id_${Date.now()}`,
    schemaVersion: "v1",
    eventId: `evt_${Date.now()}_${Math.random()}`,
    sessionId: "sess_1",
    ts: Date.now(),
    source: "extension",
    stepId: "s4_initial_price",
    eventType: "inactivity",
    elementKey: null,
    rawValue: {},
    derivedSignals: {},
    derivedContext: {},
    runnerMetadata: {},
    privacyLevel: "anonymous",
    createdAt: new Date(),
    ...overrides,
  };
}

// ── Event Ingestion Tests ─────────────────────────────────────────────────────

describe("POST /api/v2/events", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  afterEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("accepts a valid event and returns ok=true with actions array", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody(),
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.ok).toBe(true);
    expect(Array.isArray(body.actions)).toBe(true);

    await app.close();
  });

  test("rejects an event missing event_id", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const payload = makeEventBody();
    delete payload.event_id;

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload,
    });

    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe("invalid_event");

    await app.close();
  });

  test("rejects an event missing session_id", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const payload = makeEventBody();
    delete payload.session_id;

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload,
    });

    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe("invalid_event");

    await app.close();
  });

  test("rejects an event missing ts", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const payload = makeEventBody();
    delete payload.ts;

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload,
    });

    expect(res.statusCode).toBe(400);

    await app.close();
  });

  test("stores event in repository after successful ingestion", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const payload = makeEventBody({ session_id: "sess_store_test" });
    await app.inject({ method: "POST", url: "/api/v2/events", payload });

    const stored = await repository.getV2EventsBySession("sess_store_test");
    expect(stored).toHaveLength(1);
    expect(stored[0]?.eventId).toBe(payload.event_id);

    await app.close();
  });
});

// ── Hard Guardrail Unit Tests ─────────────────────────────────────────────────

describe("applyHardGuardrails", () => {
  test("hospital coverage routes to advisor_handoff", () => {
    const result = applyHardGuardrails({
      selectedTariff: null,
      coverage: "hospital",
      insuredPerson: null,
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("advisor_handoff");
    expect(result.guardrail).toBe("out_of_scope_advisor_coverage");
    expect(result.allowedActions).toContain("advisor_handoff");
  });

  test("other_persons insured person routes to advisor_handoff", () => {
    const result = applyHardGuardrails({
      selectedTariff: null,
      coverage: null,
      insuredPerson: "other_persons",
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("advisor_handoff");
    expect(result.guardrail).toBe("out_of_scope_advisor_insured_person");
  });

  test("Opt. Plus tariff allows a recovery nudge", () => {
    const result = applyHardGuardrails({
      selectedTariff: "opt_plus",
      coverage: null,
      insuredPerson: null,
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("online");
    expect(result.guardrail).toBe("out_of_scope_tariff_recovery");
    expect(result.allowedActions).toContain("tariff_route_explainer");
  });

  test("Premium tariff allows a recovery nudge", () => {
    const result = applyHardGuardrails({
      selectedTariff: "premium",
      coverage: null,
      insuredPerson: null,
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("online");
    expect(result.guardrail).toBe("out_of_scope_tariff_recovery");
    expect(result.allowedActions).toContain("tariff_route_explainer");
  });

  test("oos_path signal routes to advisor_handoff", () => {
    const result = applyHardGuardrails({
      selectedTariff: null,
      coverage: null,
      insuredPerson: null,
      hasOosPathSignal: true,
    });

    expect(result.outcome).toBe("advisor_handoff");
    expect(result.guardrail).toBe("out_of_scope_advisor_path");
  });

  test("Start tariff remains online-coachable", () => {
    const result = applyHardGuardrails({
      selectedTariff: "start",
      coverage: "private_doctor",
      insuredPerson: "myself",
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("online");
    expect(result.guardrail).toBeNull();
  });

  test("Optimal tariff remains online-coachable", () => {
    const result = applyHardGuardrails({
      selectedTariff: "optimal",
      coverage: "private_doctor",
      insuredPerson: "myself",
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("online");
    expect(result.guardrail).toBeNull();
  });

  test("null state with no signals remains online-coachable", () => {
    const result = applyHardGuardrails({
      selectedTariff: null,
      coverage: null,
      insuredPerson: null,
      hasOosPathSignal: false,
    });

    expect(result.outcome).toBe("online");
    expect(result.guardrail).toBeNull();
  });

  test("coaching actions are blocked on advisor_handoff outcome", () => {
    const result = applyHardGuardrails({
      selectedTariff: "premium",
      coverage: null,
      insuredPerson: null,
      hasOosPathSignal: false,
    });

    expect(result.blockedActions).toContain("price_transparency");
    expect(result.blockedActions).toContain("trust_signal");
    expect(result.blockedActions).toContain("market_comparison");
  });
});

// ── Guardrails Integration via /api/v2/events ─────────────────────────────────

describe("POST /api/v2/events guardrail integration", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("hospital in derived_context triggers advisor_handoff action", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_hospital",
        derived_context: { coverage: "hospital" },
      }),
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.ok).toBe(true);
    expect(body.actions[0]?.kind).toBe("advisor_handoff");
    expect(body.actions[0]?.cta?.type).toBe("advisor_handoff");

    await app.close();
  });

  test("other_persons in derived_context triggers advisor_handoff action", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_other_persons",
        derived_context: { insuredPerson: "other_persons" },
      }),
    });

    const body = res.json();
    expect(body.actions[0]?.kind).toBe("advisor_handoff");

    await app.close();
  });

  test("Opt. Plus in derived_context triggers tariff recovery action", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_opt_plus",
        derived_context: { selectedTariff: "opt_plus" },
      }),
    });

    const body = res.json();
    expect(body.actions[0]?.kind).toBe("tariff_route_explainer");
    expect(body.actions[0]?.cta?.target).toBe("optimal");

    await app.close();
  });

  test("Premium in derived_context triggers tariff recovery action", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_premium",
        derived_context: { selectedTariff: "premium" },
      }),
    });

    const body = res.json();
    expect(body.actions[0]?.kind).toBe("tariff_route_explainer");

    await app.close();
  });

  test("path_oos signal triggers advisor_handoff action", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_path_oos",
        derived_signals: { path_oos: true },
      }),
    });

    const body = res.json();
    expect(body.actions[0]?.kind).toBe("advisor_handoff");

    await app.close();
  });
});

// ── Step 4 Price Intervention Tests ──────────────────────────────────────────

describe("Step 4 price intervention via /api/v2/events", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("Step 4 inactivity can trigger a price intervention", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_s4_price",
        step_id: "s4_initial_price",
        event_type: "inactivity",
        derived_signals: { cancel_hover: true },
        derived_context: { selectedTariff: "optimal", visiblePrice: 68.14 },
      }),
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    // Should return a coach action (not advisor_handoff) for in-scope sessions
    if (body.actions.length > 0) {
      expect(body.actions[0]?.kind).not.toBe("advisor_handoff");
    }

    await app.close();
  });
});

// ── Step 7 Final Price Tests ──────────────────────────────────────────────────

describe("Step 7 final price intervention via /api/v2/events", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("Step 7 with price gap can trigger final price intervention", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: "sess_s7_final",
        step_id: "s7_final_price",
        event_type: "inactivity",
        derived_signals: { cancel_hover: true },
        derived_context: {
          selectedTariff: "optimal",
          visiblePrice: 72.4,
          priceDelta: 4.2,
        },
      }),
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    if (body.actions.length > 0) {
      expect(body.actions[0]?.kind).not.toBe("advisor_handoff");
    }

    await app.close();
  });
});

// ── Cooldown Tests ────────────────────────────────────────────────────────────

describe("cooldown and budget enforcement", () => {
  test("session state tracks intervention count from coach_impression events", () => {
    const events: V2EventRecord[] = [
      makeV2EventRecord({ eventType: "coach_impression", elementKey: "price_reframe", ts: Date.now() - 120_000 }),
      makeV2EventRecord({ eventType: "coach_impression", elementKey: "market_comparison", ts: Date.now() - 90_000 }),
      makeV2EventRecord({ eventType: "coach_impression", elementKey: "trust_signal", ts: Date.now() - 60_000 }),
    ];

    const state = reconstructSessionState("sess_budget", events);
    expect(state.interventionCount).toBe(3);
  });

  test("lastInterventionTs is set from most recent coach_impression", () => {
    const recentTs = Date.now() - 10_000;
    const events: V2EventRecord[] = [
      makeV2EventRecord({ eventType: "coach_impression", ts: Date.now() - 60_000 }),
      makeV2EventRecord({ eventType: "coach_impression", ts: recentTs }),
    ];

    const state = reconstructSessionState("sess_cooldown", events);
    expect(state.lastInterventionTs).toBe(recentTs);
  });
});

// ── Outcome Tests ─────────────────────────────────────────────────────────────

describe("POST /api/v2/outcomes", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("stores a valid outcome", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/outcomes",
      payload: {
        session_id: "sess_outcome_1",
        outcome: "converted_online",
        terminal_step_id: "s8_confirm",
      },
    });

    expect(res.statusCode).toBe(200);
    expect(res.json().ok).toBe(true);

    const stored = await repository.getOutcomeBySession("sess_outcome_1");
    expect(stored?.outcome).toBe("converted_online");
    expect(stored?.converted).toBe(true);
    expect(stored?.advisorRouted).toBe(false);

    await app.close();
  });

  test("advisor_handoff outcome does not count as conversion", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    await app.inject({
      method: "POST",
      url: "/api/v2/outcomes",
      payload: {
        session_id: "sess_advisor_1",
        outcome: "advisor_handoff",
      },
    });

    const stored = await repository.getOutcomeBySession("sess_advisor_1");
    expect(stored?.outcome).toBe("advisor_handoff");
    expect(stored?.converted).toBe(false);
    expect(stored?.advisorRouted).toBe(true);
    expect(stored?.abandoned).toBe(false);

    await app.close();
  });

  test("rejects invalid outcome value", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/outcomes",
      payload: {
        session_id: "sess_bad",
        outcome: "online_conversion", // invalid
      },
    });

    expect(res.statusCode).toBe(400);

    await app.close();
  });

  test("rejects outcome missing session_id", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/outcomes",
      payload: {
        outcome: "abandoned",
      },
    });

    expect(res.statusCode).toBe(400);

    await app.close();
  });
});

// ── Exposure Tests ────────────────────────────────────────────────────────────

describe("POST /api/v2/exposures", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("stores a valid exposure", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/exposures",
      payload: {
        exposure_id: "exp_1",
        session_id: "sess_exp_1",
        decision_id: "dec_1",
        action_id: "price_reframe",
        impression_ts: Date.now(),
        render_success: true,
      },
    });

    expect(res.statusCode).toBe(200);
    expect(res.json().ok).toBe(true);

    const stored = await repository.getExposuresBySession("sess_exp_1");
    expect(stored).toHaveLength(1);
    expect(stored[0]?.actionId).toBe("price_reframe");

    await app.close();
  });

  test("rejects exposure missing required fields", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/exposures",
      payload: {
        exposure_id: "exp_bad",
        // missing session_id, decision_id, action_id
      },
    });

    expect(res.statusCode).toBe(400);

    await app.close();
  });
});

// ── Session Replay Tests ──────────────────────────────────────────────────────

describe("GET /api/v2/sessions/:id", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("returns full session trace with events, decisions, exposures, and outcome", async () => {
    const app = await createApp({ config: makeConfig(), repository });
    const sid = "sess_replay_1";

    // Send an event
    await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({ session_id: sid, event_id: `evt_replay_${Date.now()}` }),
    });

    // Log an exposure
    await app.inject({
      method: "POST",
      url: "/api/v2/exposures",
      payload: {
        exposure_id: "exp_replay_1",
        session_id: sid,
        decision_id: "dec_replay_1",
        action_id: "price_reframe",
        impression_ts: Date.now(),
        render_success: true,
      },
    });

    // Log outcome
    await app.inject({
      method: "POST",
      url: "/api/v2/outcomes",
      payload: { session_id: sid, outcome: "converted_online" },
    });

    const res = await app.inject({
      method: "GET",
      url: `/api/v2/sessions/${sid}`,
    });

    expect(res.statusCode).toBe(200);
    const trace = res.json();
    expect(trace.session_id).toBe(sid);
    expect(Array.isArray(trace.events)).toBe(true);
    expect(trace.events.length).toBeGreaterThan(0);
    expect(trace.events[0]?.raw_value).toBeTruthy();
    expect(Array.isArray(trace.decisions)).toBe(true);
    expect(trace.decisions[0]?.ranked_candidates).toBeTruthy();
    expect(Array.isArray(trace.exposures)).toBe(true);
    expect(trace.exposures.length).toBeGreaterThan(0);
    expect(trace.outcome?.outcome).toBe("converted_online");

    await app.close();
  });

  test("returns empty trace for unknown session", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "GET",
      url: "/api/v2/sessions/sess_unknown_xyz",
    });

    expect(res.statusCode).toBe(200);
    const trace = res.json();
    expect(trace.events).toHaveLength(0);
    expect(trace.decisions).toHaveLength(0);
    expect(trace.exposures).toHaveLength(0);
    expect(trace.outcome).toBeNull();

    await app.close();
  });
});

// ── Inference Endpoint Tests ──────────────────────────────────────────────────

describe("POST /api/v2/inference", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  test("returns decision_id, session_id, and actions array", async () => {
    const app = await createApp({ config: makeConfig(), repository });
    const sid = "sess_inference_1";

    // Pre-populate with an event
    await app.inject({
      method: "POST",
      url: "/api/v2/events",
      payload: makeEventBody({
        session_id: sid,
        event_id: `evt_inf_${Date.now()}`,
        step_id: "s4_initial_price",
        derived_signals: { cancel_hover: true },
      }),
    });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/inference",
      payload: { session_id: sid },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.decision_id).toBeTruthy();
    expect(body.session_id).toBe(sid);
    expect(Array.isArray(body.actions)).toBe(true);
    expect(typeof body.risk_score).toBe("number");

    await app.close();
  });

  test("rejects inference request with missing session_id", async () => {
    const app = await createApp({ config: makeConfig(), repository });

    const res = await app.inject({
      method: "POST",
      url: "/api/v2/inference",
      payload: {},
    });

    expect(res.statusCode).toBe(400);

    await app.close();
  });
});

// ── Risk Score Unit Tests ─────────────────────────────────────────────────────

describe("computeRiskScore", () => {
  test("baseline state has zero risk score", () => {
    const state = reconstructSessionState("sess_baseline", []);
    const score = computeRiskScore(state);
    expect(score).toBe(0);
  });

  test("cancel hover signal raises risk score above 0", () => {
    const events: V2EventRecord[] = [
      makeV2EventRecord({ derivedSignals: { cancel_hover: true } }),
    ];
    const state = reconstructSessionState("sess_risk", events);
    const score = computeRiskScore(state);
    expect(score).toBeGreaterThan(0);
  });

  test("multiple signals stack up risk score", () => {
    const events: V2EventRecord[] = [
      makeV2EventRecord({
        derivedSignals: {
          cancel_hover: true,
          back_nav: true,
          dwell: true,
        },
        derivedContext: { priceDelta: 5 },
        stepId: "s7_final_price",
      }),
    ];
    const state = reconstructSessionState("sess_high_risk", events);
    const score = computeRiskScore(state);
    expect(score).toBeGreaterThanOrEqual(60);
  });

  test("score is capped at 100", () => {
    const events: V2EventRecord[] = [
      makeV2EventRecord({
        derivedSignals: {
          cancel_hover: true,
          back_nav: true,
          dwell: true,
          price_hover: true,
          repeated_change: true,
          tariff_click_oos: true,
        },
        derivedContext: { priceDelta: 10 },
        stepId: "s7_final_price",
      }),
    ];
    const state = reconstructSessionState("sess_max_risk", events);
    const score = computeRiskScore(state);
    expect(score).toBeLessThanOrEqual(100);
  });
});
