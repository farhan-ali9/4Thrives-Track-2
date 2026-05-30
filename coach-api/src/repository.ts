import { randomUUID } from "node:crypto";
import type { CoachPolicyDocument } from "@uniqa-conversion-coach/shared/policy";

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

export interface CoachRepository {
  createPolicyVersion(input: CreatePolicyVersionInput): Promise<PolicyVersionRecord>;
  findAdminByEmail(email: string): Promise<AdminUserRecord | null>;
  findAdminById(id: string): Promise<AdminUserRecord | null>;
  getActivePolicyVersion(): Promise<PolicyVersionRecord | null>;
  getPolicyVersionById(id: string): Promise<PolicyVersionRecord | null>;
  listPolicyVersions(): Promise<PolicyVersionRecord[]>;
  upsertAdminUser(input: UpsertAdminUserInput): Promise<AdminUserRecord>;
}

export class MemoryCoachRepository implements CoachRepository {
  private readonly adminUsers = new Map<string, AdminUserRecord>();
  private readonly adminUsersByEmail = new Map<string, string>();
  private readonly policyVersions = new Map<string, PolicyVersionRecord>();

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
}
