import { PrismaClient } from "@prisma/client";
import { createApp } from "./app";
import { getConfigFromEnv } from "./config";
import { PrismaCoachRepository } from "./prisma-repository";

const prisma = new PrismaClient();
const config = getConfigFromEnv();
const app = await createApp({
  config,
  logger: true,
  repository: new PrismaCoachRepository(prisma),
});

const shutdown = async (): Promise<void> => {
  await app.close();
  await prisma.$disconnect();
};

process.on("SIGINT", () => {
  void shutdown().finally(() => process.exit(0));
});
process.on("SIGTERM", () => {
  void shutdown().finally(() => process.exit(0));
});

await app.listen({
  host: config.host,
  port: config.port,
});
