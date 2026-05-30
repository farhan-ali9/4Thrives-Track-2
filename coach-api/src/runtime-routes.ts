import type { FastifyInstance } from "fastify";
import type {
  JourneyOutcome,
  JourneySnapshot,
} from "@uniqa-conversion-coach/shared/contracts";
import { decideJourney } from "./journey-strategy.js";
import type { RuntimeRepository } from "./repository.js";

export async function registerRuntimeRoutes(
  app: FastifyInstance,
  repository: RuntimeRepository,
): Promise<void> {
  app.post<{ Body: JourneySnapshot }>("/api/runtime/decide", async (request, reply) => {
    const snapshot = request.body;
    const error = validateSnapshot(snapshot);
    if (error) {
      return reply.code(400).send({ error: "invalid_snapshot", message: error });
    }

    const decision = decideJourney(snapshot);
    await persistDecisionTelemetry(app, repository, snapshot, decision);

    return {
      decision,
    };
  });

  app.post<{ Body: JourneyOutcome }>("/api/runtime/outcome", async (request, reply) => {
    const outcome = request.body;
    const error = validateOutcome(outcome);
    if (error) {
      return reply.code(400).send({ error: "invalid_outcome", message: error });
    }

    await persistOutcomeTelemetry(app, repository, outcome);
    return { ok: true };
  });

  app.get<{ Params: { id: string } }>("/api/runtime/sessions/:id", async (request) => {
    const trace = await repository.getSessionTrace(request.params.id);
    return {
      sessionId: trace.sessionId,
      snapshots: trace.snapshots.map((entry) => ({
        createdAt: entry.createdAt.toISOString(),
        snapshot: entry.snapshot,
      })),
      decisions: trace.decisions.map((entry) => ({
        createdAt: entry.createdAt.toISOString(),
        decision: entry.decision,
      })),
      outcome: trace.outcome
        ? {
            createdAt: trace.outcome.createdAt.toISOString(),
            outcome: trace.outcome.outcome,
          }
        : null,
    };
  });
}

async function persistDecisionTelemetry(
  app: FastifyInstance,
  repository: RuntimeRepository,
  snapshot: JourneySnapshot,
  decision: ReturnType<typeof decideJourney>,
): Promise<void> {
  try {
    await repository.storeSnapshot(snapshot);
    if (decision) {
      await repository.storeDecision(decision, snapshot.sessionId);
    }
  } catch (error) {
    app.log.warn(
      {
        error: error instanceof Error ? error.message : String(error),
        routeFamily: snapshot.routeFamily,
        sessionId: snapshot.sessionId,
        stage: snapshot.stage,
      },
      "Runtime telemetry persistence failed; returning decision anyway",
    );
  }
}

async function persistOutcomeTelemetry(
  app: FastifyInstance,
  repository: RuntimeRepository,
  outcome: JourneyOutcome,
): Promise<void> {
  try {
    await repository.storeOutcome(outcome);
  } catch (error) {
    app.log.warn(
      {
        error: error instanceof Error ? error.message : String(error),
        outcome: outcome.outcome,
        routeFamily: outcome.routeFamily,
        sessionId: outcome.sessionId,
      },
      "Runtime outcome persistence failed; keeping runtime response successful",
    );
  }
}

function validateSnapshot(snapshot: JourneySnapshot | undefined): string | null {
  if (!snapshot || typeof snapshot !== "object") {
    return "snapshot body is required";
  }
  if (!snapshot.sessionId) {
    return "sessionId is required";
  }
  if (!snapshot.routeFamily) {
    return "routeFamily is required";
  }
  if (!snapshot.stage) {
    return "stage is required";
  }
  if (!Array.isArray(snapshot.signals)) {
    return "signals must be an array";
  }
  if (!Array.isArray(snapshot.eligibleGoals) || snapshot.eligibleGoals.length === 0) {
    return "eligibleGoals must be a non-empty array";
  }
  return null;
}

function validateOutcome(outcome: JourneyOutcome | undefined): string | null {
  if (!outcome || typeof outcome !== "object") {
    return "outcome body is required";
  }
  if (!outcome.sessionId) {
    return "sessionId is required";
  }
  if (!outcome.routeFamily) {
    return "routeFamily is required";
  }
  if (!outcome.terminalStage) {
    return "terminalStage is required";
  }
  if (!outcome.outcome) {
    return "outcome is required";
  }
  return null;
}
