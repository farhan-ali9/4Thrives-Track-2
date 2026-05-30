import { PrismaClient, type Prisma } from "@prisma/client";
import { parsePolicyDocument } from "@uniqa-conversion-coach/shared/policy";
import type {
  AdminUserRecord,
  CoachRepository,
  CreatePolicyVersionInput,
  PolicyVersionRecord,
  UpsertAdminUserInput,
} from "./repository";

export class PrismaCoachRepository implements CoachRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async createPolicyVersion(input: CreatePolicyVersionInput): Promise<PolicyVersionRecord> {
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
}

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
