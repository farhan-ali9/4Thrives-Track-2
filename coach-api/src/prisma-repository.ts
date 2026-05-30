import { PrismaClient, type Prisma } from "@prisma/client";
import { parsePolicyDocument } from "@uniqa-conversion-coach/shared/policy";
import type {
  AdminUserRecord,
  CoachRepository,
  CreatePolicyVersionInput,
  ExposureRecord,
  InferenceResultRecord,
  OutcomeRecord,
  PolicyVersionRecord,
  SessionTrace,
  StoreExposureInput,
  StoreInferenceResultInput,
  StoreOutcomeInput,
  StoreV2EventInput,
  UpsertAdminUserInput,
  V2EventRecord,
} from "./repository.js";

export class PrismaCoachRepository implements CoachRepository {
  constructor(private readonly prisma: PrismaClient) {}

  // ── Admin / Policy ──────────────────────────────────────────────────────────

  async createPolicyVersion(
    input: CreatePolicyVersionInput,
  ): Promise<PolicyVersionRecord> {
    const record = await this.prisma.$transaction(async (tx) => {
      const latest = await tx.policyVersion.findFirst({
        orderBy: {
          version: "desc",
        },
      });
      const version = (latest?.version ?? 0) + 1;

      if (input.makeActive) {
        await tx.policyVersion.updateMany({
          data: {
            isActive: false,
          },
          where: {
            isActive: true,
          },
        });
      }

      return tx.policyVersion.create({
        data: {
          createdByAdminId: input.createdByAdminId,
          isActive: input.makeActive,
          policy: input.policy as Prisma.InputJsonValue,
          restoredFromPolicyVersionId: input.restoredFromPolicyVersionId,
          version,
        },
      });
    });

    return mapPolicyVersion(record);
  }

  async findAdminByEmail(email: string): Promise<AdminUserRecord | null> {
    const record = await this.prisma.adminUser.findUnique({
      where: {
        email,
      },
    });
    return record ? mapAdminUser(record) : null;
  }

  async findAdminById(id: string): Promise<AdminUserRecord | null> {
    const record = await this.prisma.adminUser.findUnique({
      where: {
        id,
      },
    });
    return record ? mapAdminUser(record) : null;
  }

  async getActivePolicyVersion(): Promise<PolicyVersionRecord | null> {
    const record = await this.prisma.policyVersion.findFirst({
      orderBy: {
        version: "desc",
      },
      where: {
        isActive: true,
      },
    });
    return record ? mapPolicyVersion(record) : null;
  }

  async getPolicyVersionById(id: string): Promise<PolicyVersionRecord | null> {
    const record = await this.prisma.policyVersion.findUnique({
      where: {
        id,
      },
    });
    return record ? mapPolicyVersion(record) : null;
  }

  async listPolicyVersions(): Promise<PolicyVersionRecord[]> {
    const records = await this.prisma.policyVersion.findMany({
      orderBy: {
        version: "desc",
      },
    });
    return records.map(mapPolicyVersion);
  }

  async upsertAdminUser(input: UpsertAdminUserInput): Promise<AdminUserRecord> {
    const record = await this.prisma.adminUser.upsert({
      create: {
        email: input.email,
        name: input.name,
        passwordHash: input.passwordHash,
      },
      update: {
        name: input.name,
        passwordHash: input.passwordHash,
      },
      where: {
        email: input.email,
      },
    });

    return mapAdminUser(record);
  }

  // ── V2 Telemetry ────────────────────────────────────────────────────────────

  async storeV2Event(input: StoreV2EventInput): Promise<V2EventRecord> {
    const record = await this.prisma.sessionTraceEvent.create({
      data: {
        schemaVersion: input.schemaVersion,
        eventId: input.eventId,
        sessionId: input.sessionId,
        ts: BigInt(input.ts),
        source: input.source,
        stepId: input.stepId,
        eventType: input.eventType,
        elementKey: input.elementKey,
        rawValue: input.rawValue as Prisma.InputJsonValue,
        derivedSignals: input.derivedSignals as Prisma.InputJsonValue,
        derivedContext: input.derivedContext as Prisma.InputJsonValue,
        runnerMetadata: input.runnerMetadata as Prisma.InputJsonValue,
        privacyLevel: input.privacyLevel,
      },
    });
    return mapV2Event(record);
  }

  async getV2EventsBySession(sessionId: string): Promise<V2EventRecord[]> {
    const records = await this.prisma.sessionTraceEvent.findMany({
      orderBy: { ts: "asc" },
      where: { sessionId },
    });
    return records.map(mapV2Event);
  }

  async storeInferenceResult(
    input: StoreInferenceResultInput,
  ): Promise<InferenceResultRecord> {
    const record = await this.prisma.modelInferenceResult.create({
      data: {
        decisionId: input.decisionId,
        sessionId: input.sessionId,
        modelVersion: input.modelVersion,
        experimentId: input.experimentId,
        candidateSetVersion: input.candidateSetVersion,
        chosenActionId: input.chosenActionId,
        rankedCandidates: input.rankedCandidates as Prisma.InputJsonValue,
        guardrailDecisions: input.guardrailDecisions as Prisma.InputJsonValue,
        latencyMs: input.latencyMs,
        riskScore: input.riskScore,
      },
    });
    return mapInferenceResult(record);
  }

  async getInferenceResultsBySession(
    sessionId: string,
  ): Promise<InferenceResultRecord[]> {
    const records = await this.prisma.modelInferenceResult.findMany({
      orderBy: { createdAt: "asc" },
      where: { sessionId },
    });
    return records.map(mapInferenceResult);
  }

  async storeExposure(input: StoreExposureInput): Promise<ExposureRecord> {
    const record = await this.prisma.interventionExposure.create({
      data: {
        exposureId: input.exposureId,
        sessionId: input.sessionId,
        decisionId: input.decisionId,
        actionId: input.actionId,
        impressionTs:
          input.impressionTs !== null ? BigInt(input.impressionTs) : null,
        dismissTs: input.dismissTs !== null ? BigInt(input.dismissTs) : null,
        ctaTs: input.ctaTs !== null ? BigInt(input.ctaTs) : null,
        renderSuccess: input.renderSuccess,
      },
    });
    return mapExposure(record);
  }

  async getExposuresBySession(sessionId: string): Promise<ExposureRecord[]> {
    const records = await this.prisma.interventionExposure.findMany({
      orderBy: { createdAt: "asc" },
      where: { sessionId },
    });
    return records.map(mapExposure);
  }

  async storeOutcome(input: StoreOutcomeInput): Promise<OutcomeRecord> {
    const record = await this.prisma.journeyOutcome.upsert({
      create: {
        sessionId: input.sessionId,
        outcome: input.outcome,
        terminalStepId: input.terminalStepId,
        advisorRouted: input.advisorRouted,
        converted: input.converted,
        abandoned: input.abandoned,
        endedAt: input.endedAt !== null ? BigInt(input.endedAt) : null,
        finalTariff: input.finalTariff,
        finalVisiblePrice: input.finalVisiblePrice,
        priceDelta: input.priceDelta,
      },
      update: {
        outcome: input.outcome,
        terminalStepId: input.terminalStepId,
        advisorRouted: input.advisorRouted,
        converted: input.converted,
        abandoned: input.abandoned,
        endedAt: input.endedAt !== null ? BigInt(input.endedAt) : null,
        finalTariff: input.finalTariff,
        finalVisiblePrice: input.finalVisiblePrice,
        priceDelta: input.priceDelta,
      },
      where: { sessionId: input.sessionId },
    });
    return mapOutcome(record);
  }

  async getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null> {
    const record = await this.prisma.journeyOutcome.findUnique({
      where: { sessionId },
    });
    return record ? mapOutcome(record) : null;
  }

  async getSessionTrace(sessionId: string): Promise<SessionTrace> {
    const [events, decisions, exposures, outcome] = await Promise.all([
      this.getV2EventsBySession(sessionId),
      this.getInferenceResultsBySession(sessionId),
      this.getExposuresBySession(sessionId),
      this.getOutcomeBySession(sessionId),
    ]);
    return { sessionId, events, decisions, exposures, outcome };
  }
}

// ── Mappers ───────────────────────────────────────────────────────────────────

function mapAdminUser(record: {
  id: string;
  email: string;
  name: string | null;
  passwordHash: string;
  createdAt: Date;
  updatedAt: Date;
}): AdminUserRecord {
  return {
    createdAt: record.createdAt,
    email: record.email,
    id: record.id,
    name: record.name,
    passwordHash: record.passwordHash,
    updatedAt: record.updatedAt,
  };
}

function mapPolicyVersion(record: {
  id: string;
  version: number;
  isActive: boolean;
  policy: Prisma.JsonValue;
  createdAt: Date;
  updatedAt: Date;
  createdByAdminId: string | null;
  restoredFromPolicyVersionId: string | null;
}): PolicyVersionRecord {
  return {
    createdAt: record.createdAt,
    createdByAdminId: record.createdByAdminId,
    id: record.id,
    isActive: record.isActive,
    policy: parsePolicyDocument(record.policy),
    restoredFromPolicyVersionId: record.restoredFromPolicyVersionId,
    updatedAt: record.updatedAt,
    version: record.version,
  };
}

function mapV2Event(record: {
  id: string;
  schemaVersion: string;
  eventId: string;
  sessionId: string;
  ts: bigint;
  source: string;
  stepId: string | null;
  eventType: string;
  elementKey: string | null;
  rawValue: Prisma.JsonValue;
  derivedSignals: Prisma.JsonValue;
  derivedContext: Prisma.JsonValue;
  runnerMetadata: Prisma.JsonValue;
  privacyLevel: string;
  createdAt: Date;
}): V2EventRecord {
  return {
    id: record.id,
    schemaVersion: record.schemaVersion,
    eventId: record.eventId,
    sessionId: record.sessionId,
    ts: Number(record.ts),
    source: record.source,
    stepId: record.stepId,
    eventType: record.eventType,
    elementKey: record.elementKey,
    rawValue: (record.rawValue as Record<string, unknown>) ?? {},
    derivedSignals: (record.derivedSignals as Record<string, unknown>) ?? {},
    derivedContext: (record.derivedContext as Record<string, unknown>) ?? {},
    runnerMetadata: (record.runnerMetadata as Record<string, unknown>) ?? {},
    privacyLevel: record.privacyLevel,
    createdAt: record.createdAt,
  };
}

function mapInferenceResult(record: {
  id: string;
  decisionId: string;
  sessionId: string;
  modelVersion: string;
  experimentId: string | null;
  candidateSetVersion: string | null;
  chosenActionId: string | null;
  rankedCandidates: Prisma.JsonValue;
  guardrailDecisions: Prisma.JsonValue;
  latencyMs: number;
  riskScore: number;
  createdAt: Date;
}): InferenceResultRecord {
  return {
    id: record.id,
    decisionId: record.decisionId,
    sessionId: record.sessionId,
    modelVersion: record.modelVersion,
    experimentId: record.experimentId,
    candidateSetVersion: record.candidateSetVersion,
    chosenActionId: record.chosenActionId,
    rankedCandidates: (record.rankedCandidates as unknown[]) ?? [],
    guardrailDecisions: (record.guardrailDecisions as unknown[]) ?? [],
    latencyMs: record.latencyMs,
    riskScore: record.riskScore,
    createdAt: record.createdAt,
  };
}

function mapExposure(record: {
  id: string;
  exposureId: string;
  sessionId: string;
  decisionId: string;
  actionId: string;
  impressionTs: bigint | null;
  dismissTs: bigint | null;
  ctaTs: bigint | null;
  renderSuccess: boolean;
  createdAt: Date;
}): ExposureRecord {
  return {
    id: record.id,
    exposureId: record.exposureId,
    sessionId: record.sessionId,
    decisionId: record.decisionId,
    actionId: record.actionId,
    impressionTs:
      record.impressionTs !== null ? Number(record.impressionTs) : null,
    dismissTs: record.dismissTs !== null ? Number(record.dismissTs) : null,
    ctaTs: record.ctaTs !== null ? Number(record.ctaTs) : null,
    renderSuccess: record.renderSuccess,
    createdAt: record.createdAt,
  };
}

function mapOutcome(record: {
  id: string;
  sessionId: string;
  outcome: string;
  terminalStepId: string | null;
  advisorRouted: boolean;
  converted: boolean;
  abandoned: boolean;
  endedAt: bigint | null;
  finalTariff: string | null;
  finalVisiblePrice: number | null;
  priceDelta: number | null;
  createdAt: Date;
}): OutcomeRecord {
  return {
    id: record.id,
    sessionId: record.sessionId,
    outcome: record.outcome,
    terminalStepId: record.terminalStepId,
    advisorRouted: record.advisorRouted,
    converted: record.converted,
    abandoned: record.abandoned,
    endedAt: record.endedAt !== null ? Number(record.endedAt) : null,
    finalTariff: record.finalTariff,
    finalVisiblePrice: record.finalVisiblePrice,
    priceDelta: record.priceDelta,
    createdAt: record.createdAt,
  };
}
