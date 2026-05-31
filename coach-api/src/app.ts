import cors from "@fastify/cors";
import Fastify, { type FastifyInstance } from "fastify";
import type { AppConfig } from "./config.js";
import type { RuntimeRepository } from "./repository.js";
import { registerRuntimeRoutes } from "./runtime-routes.js";

interface CreateAppOptions {
  config: AppConfig;
  logger?: boolean;
  repository: RuntimeRepository;
}

export async function createApp(
  options: CreateAppOptions,
): Promise<FastifyInstance> {
  const app = Fastify({
    logger: options.logger ?? false,
  });

  await app.register(cors, {
    credentials: true,
    origin: true,
  });

  app.get("/healthz", async () => ({
    status: "ok",
  }));

  await registerRuntimeRoutes(app, options.repository);

  return app;
}
