// /api/v2/* route handlers.
// Event ingestion → session reconstruction → hard guardrails → policy engine → telemetry storage.

import { randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import { seedPolicy } from "@uniqa-conversion-coach/shared";
import type {
  CoachAction,
  NormalizedEvent,
} from "@uniqa-conversion-coach/shared/contracts";
import type { CoachPolicyDocument } from "@uniqa-conversion-coach/shared/policy";
import { evaluateCoachRequest } from "./policy-engine.js";
import { applyHardGuardrails } from "./guardrails.js";
import {
  reconstructSessionState,
  computeRiskScore,
  deriveSignalKinds,
} from "./session-state.js";
import type {
  CoachRepository,
  PolicyVersionRecord,
  V2EventRecord,
} from "./repository.js";

// ── Intervention catalog for advisor_handoff action ───────────────────────────

const ADVISOR_HANDOFF_ACTION: CoachAction = {
  id: "advisor_route",
  kind: "advisor_handoff",
  placement: "bottom-toast",
  title: "Dieser Pfad braucht Beratung",
  body: "Krankenhaus oder weitere versicherte Personen brauchen persoenliche Beratung. Dieser Pfad ist ein sauberer Beratungsausstieg.",
  ctaLabel: "Verstanden",
  dismissible: true,
  cooldownMs: 120_000,
};

// ── Route registration ────────────────────────────────────────────────────────

export async function registerV2Routes(
  app: FastifyInstance,
  repository: CoachRepository,
  getActivePolicy: () => Promise<PolicyVersionRecord>,
): Promise<void> {
  // POST /api/v2/events
  // Ingest a raw extension event, run inference, return coach actions.
  app.post<{ Body: unknown }>("/api/v2/events", async (request, reply) => {
    const body = request.body as Record<string, unknown>;
    if (!body || typeof body !== "object") {
      return reply.code(400).send({ error: "invalid_body" });
    }

    const validationError = validateEventBody(body);
    if (validationError) {
      return reply
        .code(400)
        .send({ error: "invalid_event", message: validationError });
    }

    const eventInput = coerceEventBody(body);
    const t0 = Date.now();

    // Store the event
    await repository.storeV2Event(eventInput);

    // Load all session events + reconstruct state
    const allEvents = await repository.getV2EventsBySession(
      eventInput.sessionId,
    );
    const state = reconstructSessionState(eventInput.sessionId, allEvents);

    // Hard guardrails check
    const guardrail = applyHardGuardrails({
      selectedTariff: state.selectedTariff,
      coverage: state.coverage,
      insuredPerson: state.insuredPerson,
      hasOosPathSignal: state.hasOosPathSignal,
    });

    const riskScore = computeRiskScore(state);
    let actions: CoachAction[] = [];

    if (guardrail.outcome === "advisor_handoff") {
      actions = [ADVISOR_HANDOFF_ACTION];
    } else {
      // Apply cooldown and budget before running policy engine
      if (canRunInference(state)) {
        const policy = await getActivePolicy();
        actions = filterActionsByGuardrail(
          runPolicyEngine(state, allEvents, policy.policy),
          guardrail.allowedActions,
        );
      }
    }

    const chosenAction = actions[0] ?? null;
    const decisionId = `dec_${randomUUID()}`;

    await repository.storeInferenceResult({
      decisionId,
      sessionId: eventInput.sessionId,
      modelVersion: "rule_based_v1",
      experimentId: null,
      candidateSetVersion: null,
      chosenActionId: chosenAction?.id ?? null,
      rankedCandidates: actions,
      guardrailDecisions: guardrail.guardrail ? [guardrail] : [],
      latencyMs: Date.now() - t0,
      riskScore,
    });

    return { ok: true, actions };
  });

  // POST /api/v2/inference
  // Explicit inference call for a session (no new event storage).
  app.post<{ Body: unknown }>("/api/v2/inference", async (request, reply) => {
    const body = request.body as Record<string, unknown>;
    if (
      !body ||
      typeof body !== "object" ||
      typeof body.session_id !== "string"
    ) {
      return reply
        .code(400)
        .send({ error: "invalid_body", message: "session_id is required" });
    }

    const sessionId = body.session_id as string;
    const t0 = Date.now();

    const allEvents = await repository.getV2EventsBySession(sessionId);
    const state = reconstructSessionState(sessionId, allEvents);

    const guardrail = applyHardGuardrails({
      selectedTariff: state.selectedTariff,
      coverage: state.coverage,
      insuredPerson: state.insuredPerson,
      hasOosPathSignal: state.hasOosPathSignal,
    });

    const riskScore = computeRiskScore(state);
    let actions: CoachAction[] = [];

    if (guardrail.outcome === "advisor_handoff") {
      actions = [ADVISOR_HANDOFF_ACTION];
    } else if (canRunInference(state)) {
      const policy = await getActivePolicy();
      actions = filterActionsByGuardrail(
        runPolicyEngine(state, allEvents, policy.policy),
        guardrail.allowedActions,
      );
    }

    const chosenAction = actions[0] ?? null;
    const decisionId = `dec_${randomUUID()}`;

    await repository.storeInferenceResult({
      decisionId,
      sessionId,
      modelVersion: "rule_based_v1",
      experimentId: null,
      candidateSetVersion: null,
      chosenActionId: chosenAction?.id ?? null,
      rankedCandidates: actions,
      guardrailDecisions: guardrail.guardrail ? [guardrail] : [],
      latencyMs: Date.now() - t0,
      riskScore,
    });

    return {
      decision_id: decisionId,
      session_id: sessionId,
      risk_score: riskScore,
      guardrail: guardrail.guardrail,
      actions,
    };
  });

  // POST /api/v2/exposures
  // Log an intervention exposure (impression, dismiss, CTA).
  app.post<{ Body: unknown }>("/api/v2/exposures", async (request, reply) => {
    const body = request.body as Record<string, unknown>;
    if (!body || typeof body !== "object") {
      return reply.code(400).send({ error: "invalid_body" });
    }

    const missing = requireFields(body, [
      "exposure_id",
      "session_id",
      "decision_id",
      "action_id",
    ]);
    if (missing) {
      return reply
        .code(400)
        .send({ error: "invalid_exposure", message: missing });
    }

    await repository.storeExposure({
      exposureId: String(body.exposure_id),
      sessionId: String(body.session_id),
      decisionId: String(body.decision_id),
      actionId: String(body.action_id),
      impressionTs: toNumberOrNull(body.impression_ts),
      dismissTs: toNumberOrNull(body.dismiss_ts),
      ctaTs: toNumberOrNull(body.cta_ts),
      renderSuccess: body.render_success !== false,
    });

    return { ok: true };
  });

  // POST /api/v2/outcomes
  // Log the terminal journey outcome.
  app.post<{ Body: unknown }>("/api/v2/outcomes", async (request, reply) => {
    const body = request.body as Record<string, unknown>;
    if (!body || typeof body !== "object") {
      return reply.code(400).send({ error: "invalid_body" });
    }

    const missing = requireFields(body, ["session_id", "outcome"]);
    if (missing) {
      return reply
        .code(400)
        .send({ error: "invalid_outcome", message: missing });
    }

    const outcome = String(body.outcome);
    const allowedOutcomes = [
      "converted_online",
      "abandoned",
      "advisor_handoff",
    ];
    if (!allowedOutcomes.includes(outcome)) {
      return reply.code(400).send({
        error: "invalid_outcome",
        message: `outcome must be one of: ${allowedOutcomes.join(", ")}`,
      });
    }

    await repository.storeOutcome({
      sessionId: String(body.session_id),
      outcome,
      terminalStepId:
        typeof body.terminal_step_id === "string"
          ? body.terminal_step_id
          : null,
      advisorRouted: outcome === "advisor_handoff",
      converted: outcome === "converted_online",
      abandoned: outcome === "abandoned",
      endedAt: toNumberOrNull(body.ended_at) ?? Date.now(),
      finalTariff:
        typeof body.final_tariff === "string" ? body.final_tariff : null,
      finalVisiblePrice: toNumberOrNull(body.final_visible_price),
      priceDelta: toNumberOrNull(body.price_delta),
    });

    return { ok: true };
  });

  // GET /api/v2/sessions/:id
  // Return full session trace for replay and training.
  app.get<{ Params: { id: string } }>(
    "/api/v2/sessions/:id",
    async (request) => {
      const trace = await repository.getSessionTrace(request.params.id);
      return serializeTrace(trace);
    },
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function validateEventBody(body: Record<string, unknown>): string | null {
  if (typeof body.event_id !== "string" || !body.event_id) {
    return "event_id is required";
  }
  if (typeof body.session_id !== "string" || !body.session_id) {
    return "session_id is required";
  }
  if (typeof body.ts !== "number" && typeof body.ts !== "bigint") {
    return "ts must be a number";
  }
  if (typeof body.event_type !== "string" || !body.event_type) {
    return "event_type is required";
  }
  return null;
}

function coerceEventBody(body: Record<string, unknown>) {
  return {
    schemaVersion:
      typeof body.schema_version === "string" ? body.schema_version : "v1",
    eventId: String(body.event_id),
    sessionId: String(body.session_id),
    ts: Number(body.ts),
    source: typeof body.source === "string" ? body.source : "extension",
    stepId: typeof body.step_id === "string" ? body.step_id : null,
    eventType: String(body.event_type),
    elementKey: typeof body.element_key === "string" ? body.element_key : null,
    rawValue: isObject(body.raw_value) ? body.raw_value : {},
    derivedSignals: isObject(body.derived_signals) ? body.derived_signals : {},
    derivedContext: isObject(body.derived_context) ? body.derived_context : {},
    runnerMetadata: isObject(body.runner_metadata) ? body.runner_metadata : {},
    privacyLevel:
      typeof body.privacy_level === "string" ? body.privacy_level : "anonymous",
  };
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function requireFields(
  body: Record<string, unknown>,
  fields: string[],
): string | null {
  for (const f of fields) {
    if (!body[f]) return `${f} is required`;
  }
  return null;
}

function toNumberOrNull(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const MAX_INTERVENTIONS = 3;
const MIN_COOLDOWN_MS = 30_000;

function canRunInference(
  state: ReturnType<typeof reconstructSessionState>,
): boolean {
  if (state.interventionCount >= MAX_INTERVENTIONS) return false;
  if (
    state.lastInterventionTs !== null &&
    Date.now() - state.lastInterventionTs < MIN_COOLDOWN_MS
  ) {
    return false;
  }
  return true;
}

function filterActionsByGuardrail(
  actions: CoachAction[],
  allowedActions: string[],
): CoachAction[] {
  return actions.filter(
    (action) => allowedActions.includes(action.kind) || allowedActions.includes(action.id),
  );
}

function runPolicyEngine(
  state: ReturnType<typeof reconstructSessionState>,
  allEvents: V2EventRecord[],
  policy: CoachPolicyDocument,
): CoachAction[] {
  const signals = deriveSignalKinds(state);
  const recentNormalized = toNormalizedEvents(state.recentEvents);

  return evaluateCoachRequest(
    {
      sessionId: state.sessionId,
      pageStepId: state.currentStepId,
      coachStepId: state.currentStepId,
      recentEvents: recentNormalized,
      detectedSignals: signals as Parameters<
        typeof evaluateCoachRequest
      >[0]["detectedSignals"],
      derivedContext: {
        selectedTariff: state.selectedTariff,
        selectedAddOns: state.selectedAddons,
        visiblePrice: state.visiblePrice,
        priceDelta: state.priceDelta,
      },
      currentOffer: {
        visiblePrice: state.visiblePrice,
        priceDelta: state.priceDelta,
        selectedTariff: state.selectedTariff,
      },
    },
    policy,
  );
}

function toNormalizedEvents(events: V2EventRecord[]): NormalizedEvent[] {
  return events.map((e) => ({
    id: e.eventId,
    sessionId: e.sessionId,
    ts: e.ts,
    pageStepId: e.stepId,
    coachStepId: e.stepId,
    type: e.eventType as NormalizedEvent["type"],
    elementKey: e.elementKey,
    value: isObject(e.rawValue) ? e.rawValue : null,
    derivedContext: {},
    dwellMs: null,
  }));
}

function serializeTrace(trace: import("./repository").SessionTrace) {
  return {
    session_id: trace.sessionId,
    events: trace.events.map((e) => ({
      event_id: e.eventId,
      session_id: e.sessionId,
      ts: e.ts,
      step_id: e.stepId,
      event_type: e.eventType,
      element_key: e.elementKey,
      derived_signals: e.derivedSignals,
      derived_context: e.derivedContext,
      privacy_level: e.privacyLevel,
    })),
    decisions: trace.decisions.map((d) => ({
      decision_id: d.decisionId,
      session_id: d.sessionId,
      model_version: d.modelVersion,
      chosen_action_id: d.chosenActionId,
      risk_score: d.riskScore,
      guardrail_decisions: d.guardrailDecisions,
      latency_ms: d.latencyMs,
      created_at: d.createdAt.toISOString(),
    })),
    exposures: trace.exposures.map((ex) => ({
      exposure_id: ex.exposureId,
      session_id: ex.sessionId,
      decision_id: ex.decisionId,
      action_id: ex.actionId,
      impression_ts: ex.impressionTs,
      dismiss_ts: ex.dismissTs,
      cta_ts: ex.ctaTs,
      render_success: ex.renderSuccess,
    })),
    outcome: trace.outcome
      ? {
          session_id: trace.outcome.sessionId,
          outcome: trace.outcome.outcome,
          terminal_step_id: trace.outcome.terminalStepId,
          advisor_routed: trace.outcome.advisorRouted,
          converted: trace.outcome.converted,
          abandoned: trace.outcome.abandoned,
          ended_at: trace.outcome.endedAt,
          final_tariff: trace.outcome.finalTariff,
          final_visible_price: trace.outcome.finalVisiblePrice,
          price_delta: trace.outcome.priceDelta,
        }
      : null,
  };
}
