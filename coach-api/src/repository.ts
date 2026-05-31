import { randomUUID } from "node:crypto";
import type {
  JourneyDecision,
  JourneyOutcome,
  JourneySnapshot,
} from "@uniqa-conversion-coach/shared/contracts";

export interface RuntimeSnapshotRecord {
  id: string;
  sessionId: string;
  snapshot: JourneySnapshot;
  createdAt: Date;
}

export interface RuntimeDecisionRecord {
  id: string;
  sessionId: string;
  decision: JourneyDecision;
  createdAt: Date;
}

export interface OutcomeRecord {
  id: string;
  sessionId: string;
  outcome: JourneyOutcome;
  createdAt: Date;
}

export interface SessionTrace {
  sessionId: string;
  snapshots: RuntimeSnapshotRecord[];
  decisions: RuntimeDecisionRecord[];
  outcome: OutcomeRecord | null;
}

export interface RuntimeRepository {
  storeSnapshot(snapshot: JourneySnapshot): Promise<RuntimeSnapshotRecord>;
  getSnapshotsBySession(sessionId: string): Promise<RuntimeSnapshotRecord[]>;
  storeDecision(decision: JourneyDecision, sessionId: string): Promise<RuntimeDecisionRecord>;
  getDecisionsBySession(sessionId: string): Promise<RuntimeDecisionRecord[]>;
  storeOutcome(outcome: JourneyOutcome): Promise<OutcomeRecord>;
  getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null>;
  getSessionTrace(sessionId: string): Promise<SessionTrace>;
}

export class MemoryRuntimeRepository implements RuntimeRepository {
  private readonly snapshots = new Map<string, RuntimeSnapshotRecord[]>();
  private readonly decisions = new Map<string, RuntimeDecisionRecord[]>();
  private readonly outcomes = new Map<string, OutcomeRecord>();

  async storeSnapshot(snapshot: JourneySnapshot): Promise<RuntimeSnapshotRecord> {
    const record: RuntimeSnapshotRecord = {
      id: randomUUID(),
      sessionId: snapshot.sessionId,
      snapshot,
      createdAt: new Date(),
    };
    const entries = this.snapshots.get(snapshot.sessionId) ?? [];
    entries.push(record);
    this.snapshots.set(snapshot.sessionId, entries);
    return record;
  }

  async getSnapshotsBySession(sessionId: string): Promise<RuntimeSnapshotRecord[]> {
    return [...(this.snapshots.get(sessionId) ?? [])];
  }

  async storeDecision(decision: JourneyDecision, sessionId: string): Promise<RuntimeDecisionRecord> {
    const record: RuntimeDecisionRecord = {
      id: randomUUID(),
      sessionId,
      decision,
      createdAt: new Date(),
    };
    const entries = this.decisions.get(sessionId) ?? [];
    entries.push(record);
    this.decisions.set(sessionId, entries);
    return record;
  }

  async getDecisionsBySession(sessionId: string): Promise<RuntimeDecisionRecord[]> {
    return [...(this.decisions.get(sessionId) ?? [])];
  }

  async storeOutcome(outcome: JourneyOutcome): Promise<OutcomeRecord> {
    const record: OutcomeRecord = {
      id: randomUUID(),
      sessionId: outcome.sessionId,
      outcome,
      createdAt: new Date(),
    };
    this.outcomes.set(outcome.sessionId, record);
    return record;
  }

  async getOutcomeBySession(sessionId: string): Promise<OutcomeRecord | null> {
    return this.outcomes.get(sessionId) ?? null;
  }

  async getSessionTrace(sessionId: string): Promise<SessionTrace> {
    return {
      sessionId,
      snapshots: await this.getSnapshotsBySession(sessionId),
      decisions: await this.getDecisionsBySession(sessionId),
      outcome: await this.getOutcomeBySession(sessionId),
    };
  }
}
