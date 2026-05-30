import { existsSync } from "node:fs";
import cookie from "@fastify/cookie";
import cors from "@fastify/cors";
import staticFiles from "@fastify/static";
import Fastify, { type FastifyInstance } from "fastify";
import {
  parsePolicyDocument,
  seedPolicy,
  type CoachPolicyDocument,
} from "@uniqa-conversion-coach/shared";
import type { CoachRequest, CoachResponse } from "@uniqa-conversion-coach/shared/contracts";
import {
  clearSessionCookie,
  hashPassword,
  readAuthenticatedUser,
  setSessionCookie,
  verifyPassword,
} from "./auth";
import type { AppConfig } from "./config";
import { evaluateCoachRequest } from "./policy-engine";
import type { CoachRepository, PolicyVersionRecord } from "./repository";
import { registerV2Routes } from "./routes-v2";

interface CreateAppOptions {
  config: AppConfig;
  logger?: boolean;
  repository: CoachRepository;
  seedPolicyDocument?: CoachPolicyDocument;
}

export async function createApp(options: CreateAppOptions): Promise<FastifyInstance> {
  const app = Fastify({
    logger: options.logger ?? false,
  });

  await app.register(cookie, {
    hook: "onRequest",
    secret: options.config.sessionSecret,
  });
  await app.register(cors, {
    credentials: true,
    origin: true,
  });

  const staticDir = options.config.adminStaticDir;
  const hasStaticAdmin = Boolean(staticDir && existsSync(staticDir));
  if (hasStaticAdmin && staticDir) {
    await app.register(staticFiles, {
      index: ["index.html"],
      prefix: "/",
      root: staticDir,
      wildcard: false,
    });
  }

  await ensureBootstrapState(
    options.repository,
    options.config,
    options.seedPolicyDocument ?? seedPolicy,
  );

  app.get("/healthz", async () => ({
    status: "ok",
  }));

  await registerV2Routes(app, options.repository, () =>
    getRequiredActivePolicy(options.repository),
  );

  app.post<{ Body: CoachRequest; Reply: CoachResponse }>(
    "/api/v1/coach/evaluate",
    async (request) => {
      const activePolicy = await getRequiredActivePolicy(options.repository);
      return {
        actions: evaluateCoachRequest(request.body, activePolicy.policy),
        policyVersion: activePolicy.version,
        source: "remote",
      };
    },
  );

  app.post<{ Body: { email?: string; password?: string } }>(
    "/api/v1/admin/login",
    async (request, reply) => {
      const email = request.body?.email?.trim().toLowerCase();
      const password = request.body?.password ?? "";
      if (!email || !password) {
        return reply.code(400).send({
          error: "invalid_credentials",
        });
      }

      const user = await options.repository.findAdminByEmail(email);
      if (!user || !(await verifyPassword(password, user.passwordHash))) {
        return reply.code(401).send({
          error: "invalid_credentials",
        });
      }

      setSessionCookie(
        reply,
        {
          email: user.email,
          userId: user.id,
        },
        options.config.secureCookies,
      );

      return {
        user: serializeUser(user),
      };
    },
  );

  app.post("/api/v1/admin/logout", async (_request, reply) => {
    clearSessionCookie(reply, options.config.secureCookies);
    return {
      ok: true,
    };
  });

  app.get("/api/v1/admin/me", async (request, reply) => {
    const user = await readAuthenticatedUser(request, options.repository);
    if (!user) {
      return reply.code(401).send({
        error: "unauthorized",
      });
    }

    return {
      user: serializeUser(user),
    };
  });

  app.get("/api/v1/admin/policy", async (request, reply) => {
    const user = await readAuthenticatedUser(request, options.repository);
    if (!user) {
      return reply.code(401).send({
        error: "unauthorized",
      });
    }

    const activePolicy = await getRequiredActivePolicy(options.repository);
    return serializePolicyVersion(activePolicy);
  });

  app.put("/api/v1/admin/policy", async (request, reply) => {
    const user = await readAuthenticatedUser(request, options.repository);
    if (!user) {
      return reply.code(401).send({
        error: "unauthorized",
      });
    }

    try {
      const parsedPolicy = parsePolicyDocument(request.body);
      const nextPolicy = await options.repository.createPolicyVersion({
        createdByAdminId: user.id,
        makeActive: true,
        policy: parsedPolicy,
        restoredFromPolicyVersionId: null,
      });
      return serializePolicyVersion(nextPolicy);
    } catch (error) {
      return reply.code(400).send({
        error: "invalid_policy",
        message: error instanceof Error ? error.message : "Unknown validation error",
      });
    }
  });

  app.get("/api/v1/admin/policies", async (request, reply) => {
    const user = await readAuthenticatedUser(request, options.repository);
    if (!user) {
      return reply.code(401).send({
        error: "unauthorized",
      });
    }

    const policies = await options.repository.listPolicyVersions();
    return {
      policies: policies.map(serializePolicyVersionSummary),
    };
  });

  app.post<{ Params: { id: string } }>(
    "/api/v1/admin/policies/:id/restore",
    async (request, reply) => {
      const user = await readAuthenticatedUser(request, options.repository);
      if (!user) {
        return reply.code(401).send({
          error: "unauthorized",
        });
      }

      const existing = await options.repository.getPolicyVersionById(request.params.id);
      if (!existing) {
        return reply.code(404).send({
          error: "policy_not_found",
        });
      }

      const restored = await options.repository.createPolicyVersion({
        createdByAdminId: user.id,
        makeActive: true,
        policy: existing.policy,
        restoredFromPolicyVersionId: existing.id,
      });

      return serializePolicyVersion(restored);
    },
  );

  if (hasStaticAdmin) {
    app.get("/*", async (request, reply) => {
      if (request.url.startsWith("/api/")) {
        return reply.code(404).send({
          error: "not_found",
        });
      }
      return reply.sendFile("index.html");
    });
  }

  return app;
}

async function ensureBootstrapState(
  repository: CoachRepository,
  config: AppConfig,
  initialPolicy: CoachPolicyDocument,
): Promise<void> {
  await repository.upsertAdminUser({
    email: config.bootstrapAdminEmail.toLowerCase(),
    name: config.bootstrapAdminName,
    passwordHash: await hashPassword(config.bootstrapAdminPassword),
  });

  const activePolicy = await repository.getActivePolicyVersion();
  if (!activePolicy) {
    await repository.createPolicyVersion({
      createdByAdminId: null,
      makeActive: true,
      policy: initialPolicy,
      restoredFromPolicyVersionId: null,
    });
  }
}

async function getRequiredActivePolicy(repository: CoachRepository): Promise<PolicyVersionRecord> {
  const activePolicy = await repository.getActivePolicyVersion();
  if (!activePolicy) {
    throw new Error("No active policy configured");
  }
  return activePolicy;
}

function serializeUser(user: { id: string; email: string; name: string | null }) {
  return {
    email: user.email,
    id: user.id,
    name: user.name,
  };
}

function serializePolicyVersion(record: PolicyVersionRecord) {
  return {
    createdAt: record.createdAt.toISOString(),
    createdByAdminId: record.createdByAdminId,
    id: record.id,
    isActive: record.isActive,
    policy: record.policy,
    restoredFromPolicyVersionId: record.restoredFromPolicyVersionId,
    updatedAt: record.updatedAt.toISOString(),
    version: record.version,
  };
}

function serializePolicyVersionSummary(record: PolicyVersionRecord) {
  return {
    createdAt: record.createdAt.toISOString(),
    createdByAdminId: record.createdByAdminId,
    id: record.id,
    isActive: record.isActive,
    restoredFromPolicyVersionId: record.restoredFromPolicyVersionId,
    updatedAt: record.updatedAt.toISOString(),
    version: record.version,
  };
}
