import { randomUUID } from "node:crypto";
import type { CoachPolicyDocument } from "@uniqa-conversion-coach/shared/policy";

// ─── Admin / Policy ──────────────────────────────────────────────────────────

export interface AdminUserRecord {
  id: string;
  email: string;
  name: string | null;
  passwordHash: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface PolicyVersionRecord {
  id: string;
  version: number;
  isActive: boolean;
  policy: CoachPolicyDocument;
  createdAt: Date;
  updatedAt: Date;
  createdByAdminId: string | null;
  restoredFromPolicyVersionId: string | null;
}

export interface CreatePolicyVersionInput {
  createdByAdminId: string | null;
  makeActive: boolean;
  policy: CoachPolicyDocument;
  restoredFromPolicyVersionId: string | null;
}

export interface UpsertAdminUserInput {
  email: string;
  name: string | null;
  passwordHash: string;
}

// ─── V2 Telemetry ─────────────────────────────────────────────────────────────

export interface V2EventRecord {
  id: string;
  schemaVersion: string;
  eventId: string;
  sessionId: string;
  ts: number;
  source: string;
  stepId: string | null;
  eventType: string;
  elementKey: string | null;
  rawValue: Record<string, unknown>;
  derivedSignals: Record<string, unknown>;
  derivedContext: Record<string, unknown>;
  runnerMetadata: Record<string, unknown>;
  privacyLevel: string;
  createdAt: Date;
}

export interface StoreV2EventInput {
  schemaVersion: string;
  eventId: string;
  sessionId: string;
  ts: number;
  source: string;
  stepId: string | null;
  eventType: string;
  elementKey: string | null;
  rawValue: Record<string, unknown>;
  derivedSignals: Record<string, unknown>;
  derivedContext: Record<string, unknown>;
  runnerMetadata: Record<string, unknown>;
  privacyLevel: string;
}

export interface InferenceResultRecord {
  id: string;
  decisionId: string;
  sessionId: string;
  modelVersion: string;
  experimentId: string | null;
  candidateSetVersion: string | null;
  chosenActionId: string | null;
  rankedCandidates: unknown[];
  guardrailDecisions: unknown[];
  latencyMs: number;
  riskScore: number;
  createdAt: Date;
}

export interface StoreInferenceResultInput {
  decisionId: string;
  sessionId: string;
  modelVersion: string;
  experimentId: string | null;
  candidateSetVersion: string | null;
  chosenActionId: string | null;
  rankedCandidates: unknown[];
  guardrailDecisions: unknown[];
  latencyMs: number;
  riskScore: number;
}

export interface ExposureRecord {
  id: string;
  exposureId: string;
  sessionId: string;
  decisionId: string;
  actionId: string;
  impressionTs: number | null;
  dismissTs: number | null;
  ctaTs: number | null;
  renderSuccess: boolean;
  createdAt: Date;
}

export interface StoreExposureInput {
  exposureId: string;
  sessionId: string;
  decisionId: string;
  actionId: string;
  impressionTs: number | null;
  dismissTs: number | null;
  ctaTs: number | null;
  renderSuccess: boolean;
}

export interface OutcomeRecord {
  id: string;
  sessionId: string;
  outcome: string;
  terminalStepId: string | null;
  advisorRouted: boolean;
  converted: boolean;
  abandoned: boolean;
  endedAt: number | null;
  finalTariff: string | null;
  finalVisiblePrice: number | null;
  priceDelta: number | null;
  createdAt: Date;
}

export interface StoreOutcomeInput {
  sessionId: string;
  outcome: string;
  terminalStepId: string | null;
  advisorRouted: boolean;
  converted: boolean;
  abandoned: boolean;
  endedAt: number | null;
  finalTariff: string | null;
  finalVisiblePrice: number | null;
  priceDelta: number | null;
}

export interface SessionTrace {
  sessionId: string;
  events: V2EventRecord[];
  decisions: InferenceResultRecord[];
  exposures: ExposureRecord[];
  outcome: OutcomeRecord | null;
}

// ─── Repository Interface ─────────────────────────────────────────────────────

export interface CoachRepository {
  // Admin / Policy
  createPolicyVersion(input: CreatePolicyVersionInput): Promise<PolicyVersionRecord>;
  findAdminByEmail(email: string): Promise<AdminUserRecord | null>;
  findAdminById(id: string): Promise<AdminUserRecord | null>;
  getActivePolicyVersion(): Promise<PolicyVersionRecord | null>;
  getPolicyVersionById(id: string): Promise<PolicyVersionRecord | null>;
  listPolicyVersions(): Promise<PolicyVersionRecord[]>;
  upsertAdminUser(input: UpsertAdminUserInput): Promise<AdminUserRecord>;

  // V2 Telemetry
  storeV2Event(input: StoreV2EventInput): Promise<V2EventRecord>;
  getV2EventsBySession(sessionId: string): Promise<V2EventRecord[]>;
  storeInferenceResult(input: StoreInferenceResultInput): Promise<InferenceResultRecord>;
  getInferenceResultsBySession(sessionId: string): Promise<InferenceResultRecord[]>;
  storeExposure(input: StoreExposureInput): Promise<ExposureRecord>;
  getExposuresBySession(sessionId: string): Promise<ExposureRecord[]>;
  storeOutcome(input: StoreOutcomeInput): Promise<OutcomeRecord>;
  getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null>;
  getSessionTrace(sessionId: string): Promise<SessionTrace>;
}

// ─── In-Memory Implementation ─────────────────────────────────────────────────

export class MemoryCoachRepository implements CoachRepository {
  private readonly adminUsers = new Map<string, AdminUserRecord>();
  private readonly adminUsersByEmail = new Map<string, string>();
  private readonly policyVersions = new Map<string, PolicyVersionRecord>();

  // v2 telemetry stores
  private readonly v2Events = new Map<string, V2EventRecord>();
  private readonly inferenceResults = new Map<string, InferenceResultRecord>();
  private readonly exposures = new Map<string, ExposureRecord>();
  private readonly outcomes = new Map<string, OutcomeRecord>();

  // ── Admin / Policy ──────────────────────────────────────────────────────────

  async createPolicyVersion(input: CreatePolicyVersionInput): Promise<PolicyVersionRecord> {
    const version = Math.max(0, ...[...this.policyVersions.values()].map((entry) => entry.version)) + 1;
    const id = randomUUID();
    const timestamp = new Date();
    const record: PolicyVersionRecord = {
      createdAt: timestamp,
      createdByAdminId: input.createdByAdminId,
      id,
      isActive: input.makeActive,
      policy: input.policy,
      restoredFromPolicyVersionId: input.restoredFromPolicyVersionId,
      updatedAt: timestamp,
      version,
    };

    if (input.makeActive) {
      for (const existing of this.policyVersions.values()) {
        existing.isActive = false;
        existing.updatedAt = timestamp;
      }
    }

    this.policyVersions.set(id, record);
    return record;
  }

  async findAdminByEmail(email: string): Promise<AdminUserRecord | null> {
    const id = this.adminUsersByEmail.get(email);
    return id ? (this.adminUsers.get(id) ?? null) : null;
  }

  async findAdminById(id: string): Promise<AdminUserRecord | null> {
    return this.adminUsers.get(id) ?? null;
  }

  async getActivePolicyVersion(): Promise<PolicyVersionRecord | null> {
    return (
      [...this.policyVersions.values()]
        .filter((entry) => entry.isActive)
        .sort((left, right) => right.version - left.version)[0] ?? null
    );
  }

  async getPolicyVersionById(id: string): Promise<PolicyVersionRecord | null> {
    return this.policyVersions.get(id) ?? null;
  }

  async listPolicyVersions(): Promise<PolicyVersionRecord[]> {
    return [...this.policyVersions.values()].sort((left, right) => right.version - left.version);
  }

  async upsertAdminUser(input: UpsertAdminUserInput): Promise<AdminUserRecord> {
    const existing = await this.findAdminByEmail(input.email);
    const timestamp = new Date();

    if (existing) {
      const updated: AdminUserRecord = {
        ...existing,
        email: input.email,
        name: input.name,
        passwordHash: input.passwordHash,
        updatedAt: timestamp,
      };
      this.adminUsers.set(updated.id, updated);
      this.adminUsersByEmail.set(updated.email, updated.id);
      return updated;
    }

    const created: AdminUserRecord = {
      createdAt: timestamp,
      email: input.email,
      id: randomUUID(),
      name: input.name,
      passwordHash: input.passwordHash,
      updatedAt: timestamp,
    };
    this.adminUsers.set(created.id, created);
    this.adminUsersByEmail.set(created.email, created.id);
    return created;
  }

  // ── V2 Telemetry ────────────────────────────────────────────────────────────

  async storeV2Event(input: StoreV2EventInput): Promise<V2EventRecord> {
    const record: V2EventRecord = {
      ...input,
      id: randomUUID(),
      createdAt: new Date(),
    };
    this.v2Events.set(record.eventId, record);
    return record;
  }

  async getV2EventsBySession(sessionId: string): Promise<V2EventRecord[]> {
    return [...this.v2Events.values()]
      .filter((e) => e.sessionId === sessionId)
      .sort((a, b) => a.ts - b.ts);
  }

  async storeInferenceResult(input: StoreInferenceResultInput): Promise<InferenceResultRecord> {
    const record: InferenceResultRecord = {
      ...input,
      id: randomUUID(),
      createdAt: new Date(),
    };
    this.inferenceResults.set(record.decisionId, record);
    return record;
  }

  async getInferenceResultsBySession(sessionId: string): Promise<InferenceResultRecord[]> {
    return [...this.inferenceResults.values()]
      .filter((r) => r.sessionId === sessionId)
      .sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
  }

  async storeExposure(input: StoreExposureInput): Promise<ExposureRecord> {
    const record: ExposureRecord = {
      ...input,
      id: randomUUID(),
      createdAt: new Date(),
    };
    this.exposures.set(record.exposureId, record);
    return record;
  }

  async getExposuresBySession(sessionId: string): Promise<ExposureRecord[]> {
    return [...this.exposures.values()]
      .filter((e) => e.sessionId === sessionId)
      .sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
  }

  async storeOutcome(input: StoreOutcomeInput): Promise<OutcomeRecord> {
    const record: OutcomeRecord = {
      ...input,
      id: randomUUID(),
      createdAt: new Date(),
    };
    this.outcomes.set(record.sessionId, record);
    return record;
  }

  async getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null> {
    return this.outcomes.get(sessionId) ?? null;
  }

  async getSessionTrace(sessionId: string): Promise<SessionTrace> {
    return {
      sessionId,
      events: await this.getV2EventsBySession(sessionId),
      decisions: await this.getInferenceResultsBySession(sessionId),
      exposures: await this.getExposuresBySession(sessionId),
      outcome: await this.getOutcomeBySession(sessionId),
    };
  }
}
