import { randomUUID } from "node:crypto";
import { PrismaClient, type Prisma } from "@prisma/client";
import type {
  JourneyDecision,
  JourneyOutcome,
  JourneySnapshot,
} from "@uniqa-conversion-coach/shared/contracts";
import type {
  OutcomeRecord,
  RuntimeDecisionRecord,
  RuntimeRepository,
  RuntimeSnapshotRecord,
  SessionTrace,
} from "./repository.js";

export class PrismaCoachRepository implements RuntimeRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async storeSnapshot(snapshot: JourneySnapshot): Promise<RuntimeSnapshotRecord> {
    const record = await this.prisma.sessionTraceEvent.create({
      data: {
        schemaVersion: "runtime_snapshot_v1",
        eventId: `snapshot_${randomUUID()}`,
        sessionId: snapshot.sessionId,
        ts: BigInt(Date.now()),
        source: "extension_runtime",
        stepId: snapshot.stage,
        eventType: "journey_snapshot",
        elementKey: snapshot.lastAction?.elementKey ?? null,
        rawValue: {
          eligibleGoals: snapshot.eligibleGoals,
          lastAction: snapshot.lastAction,
          routeFamily: snapshot.routeFamily,
          signals: snapshot.signals,
          url: snapshot.url,
        } as Prisma.InputJsonValue,
        derivedSignals: snapshot.signals as unknown as Prisma.InputJsonValue,
        derivedContext: snapshot as unknown as Prisma.InputJsonValue,
        runnerMetadata: {} as Prisma.InputJsonValue,
        privacyLevel: "anonymous",
      },
    });

    return {
      id: record.id,
      sessionId: record.sessionId,
      snapshot,
      createdAt: record.createdAt,
    };
  }

  async getSnapshotsBySession(sessionId: string): Promise<RuntimeSnapshotRecord[]> {
    const records = await this.prisma.sessionTraceEvent.findMany({
      where: {
        eventType: "journey_snapshot",
        sessionId,
      },
      orderBy: { createdAt: "asc" },
    });

    return records.map((record) => ({
      id: record.id,
      sessionId: record.sessionId,
      snapshot: record.derivedContext as unknown as JourneySnapshot,
      createdAt: record.createdAt,
    }));
  }

  async storeDecision(
    decision: JourneyDecision,
    sessionId: string,
  ): Promise<RuntimeDecisionRecord> {
    const record = await this.prisma.modelInferenceResult.create({
      data: {
        decisionId: decision.decisionId,
        sessionId,
        modelVersion: "deterministic_runtime_v1",
        experimentId: decision.goal,
        candidateSetVersion: decision.playId,
        chosenActionId: decision.playId,
        rankedCandidates: decision.cards as unknown as Prisma.InputJsonValue,
        guardrailDecisions: decision.domMutations as unknown as Prisma.InputJsonValue,
        latencyMs: 0,
        riskScore: decision.priority,
      },
    });

    return {
      id: record.id,
      sessionId: record.sessionId,
      decision,
      createdAt: record.createdAt,
    };
  }

  async getDecisionsBySession(sessionId: string): Promise<RuntimeDecisionRecord[]> {
    const records = await this.prisma.modelInferenceResult.findMany({
      where: { sessionId },
      orderBy: { createdAt: "asc" },
    });

    return records.map((record) => ({
      id: record.id,
      sessionId: record.sessionId,
      decision: {
        decisionId: record.decisionId,
        goal: (record.experimentId as JourneyDecision["goal"] | null) ?? "converted_online",
        playId: (record.chosenActionId as JourneyDecision["playId"] | null) ?? "chat_handoff",
        priority: record.riskScore,
        cooldownMs: record.latencyMs,
        cards: record.rankedCandidates as unknown as JourneyDecision["cards"],
        domMutations: record.guardrailDecisions as unknown as JourneyDecision["domMutations"],
        chatPrompt: null,
      },
      createdAt: record.createdAt,
    }));
  }

  async storeOutcome(outcome: JourneyOutcome): Promise<OutcomeRecord> {
    const record = await this.prisma.journeyOutcome.upsert({
      where: { sessionId: outcome.sessionId },
      create: {
        sessionId: outcome.sessionId,
        outcome: outcome.outcome,
        terminalStepId: outcome.terminalStage,
        advisorRouted: outcome.routeFamily !== "online_doctor",
        converted: outcome.outcome === "converted_online",
        abandoned: outcome.outcome === "abandoned",
        endedAt: BigInt(outcome.decidedAt),
        finalTariff: outcome.finalTariff,
        finalVisiblePrice: outcome.finalPriceMonthly,
        priceDelta: null,
      },
      update: {
        outcome: outcome.outcome,
        terminalStepId: outcome.terminalStage,
        advisorRouted: outcome.routeFamily !== "online_doctor",
        converted: outcome.outcome === "converted_online",
        abandoned: outcome.outcome === "abandoned",
        endedAt: BigInt(outcome.decidedAt),
        finalTariff: outcome.finalTariff,
        finalVisiblePrice: outcome.finalPriceMonthly,
      },
    });

    return {
      id: record.id,
      sessionId: record.sessionId,
      outcome,
      createdAt: record.createdAt,
    };
  }

  async getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null> {
    const record = await this.prisma.journeyOutcome.findUnique({
      where: { sessionId },
    });
    if (!record) {
      return null;
    }

    return {
      id: record.id,
      sessionId: record.sessionId,
      outcome: {
        sessionId: record.sessionId,
        routeFamily: record.advisorRouted ? "advisor_tariff" : "online_doctor",
        terminalStage: (record.terminalStepId as JourneyOutcome["terminalStage"] | null) ?? "done",
        outcome: record.outcome as JourneyOutcome["outcome"],
        finalTariff: record.finalTariff,
        finalPriceMonthly: record.finalVisiblePrice,
        decidedAt: Number(record.endedAt ?? BigInt(record.createdAt.getTime())),
      },
      createdAt: record.createdAt,
    };
  }

  async getSessionTrace(sessionId: string): Promise<SessionTrace> {
    const [snapshots, decisions, outcome] = await Promise.all([
      this.getSnapshotsBySession(sessionId),
      this.getDecisionsBySession(sessionId),
      this.getOutcomeBySession(sessionId),
    ]);
    return {
      sessionId,
      snapshots,
      decisions,
      outcome,
    };
  }
}
