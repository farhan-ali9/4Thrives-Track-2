export interface AppConfig {
  host: string;
  port: number;
}

export function getConfigFromEnv(env: NodeJS.ProcessEnv = process.env): AppConfig {
  return {
    host: env.HOST ?? "0.0.0.0",
    port: Number(env.PORT ?? 8787),
  };
}
