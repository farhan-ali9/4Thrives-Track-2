import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export interface AppConfig {
  adminStaticDir: string | null;
  bootstrapAdminEmail: string;
  bootstrapAdminName: string;
  bootstrapAdminPassword: string;
  host: string;
  port: number;
  secureCookies: boolean;
  sessionSecret: string;
}

export function getConfigFromEnv(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const nodeEnv = env.NODE_ENV ?? "development";

  return {
    adminStaticDir: resolve(currentDir, "../../admin-portal/dist"),
    bootstrapAdminEmail: env.BOOTSTRAP_ADMIN_EMAIL ?? "admin@uniqa.local",
    bootstrapAdminName: env.BOOTSTRAP_ADMIN_NAME ?? "UNIQA Coach Admin",
    bootstrapAdminPassword: env.BOOTSTRAP_ADMIN_PASSWORD ?? "change-me-now",
    host: env.HOST ?? "0.0.0.0",
    port: Number(env.PORT ?? 8787),
    secureCookies: nodeEnv === "production",
    sessionSecret: env.SESSION_SECRET ?? "dev-session-secret",
  };
}
