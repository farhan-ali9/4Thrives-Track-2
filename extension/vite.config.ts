import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig, loadEnv, type Plugin } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));
const repoDir = resolve(rootDir, "..");

loadEnvFile(resolve(repoDir, ".env"));
loadEnvFile(resolve(rootDir, ".env"), true);

const featherlessApiKey =
  process.env.VITE_FEATHERLESS_API_KEY ?? process.env.FEATHERLESS_API_KEY ?? "";
const defaultModelFallback = "meta-llama/Meta-Llama-3.1-8B-Instruct";
const modelCandidates = parseModelList(
  process.env.VITE_FEATHERLESS_MODEL ?? process.env.LLM_DEFAULT_MODEL ?? defaultModelFallback,
);
const featherlessModel = modelCandidates[0] ?? defaultModelFallback;
const featherlessModelOptions = uniqueModels([
  ...modelCandidates,
  ...parseModelList(process.env.VITE_FEATHERLESS_MODEL_OPTIONS),
  ...parseModelList(process.env.FEATHERLESS_MODEL_OPTIONS),
  ...parseModelList(process.env.LESS_MODEL_OPTIONS),
]);

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, "");
  const apiOrigins = resolveCoachApiOrigins(env);

  return {
    build: {
      emptyOutDir: true,
      outDir: "dist",
      sourcemap: true,
      target: "es2022",
      rollupOptions: {
        input: {
          background: resolve(rootDir, "src/background.ts"),
          content: resolve(rootDir, "src/content.ts"),
        },
        output: {
          assetFileNames: "assets/[name][extname]",
          chunkFileNames: "chunks/[name].js",
          entryFileNames: "[name].js",
          format: "es",
        },
      },
    },
    define: {
      __FEATHERLESS_API_KEY__: JSON.stringify(featherlessApiKey),
      __FEATHERLESS_MODEL__: JSON.stringify(featherlessModel),
      __FEATHERLESS_MODEL_OPTIONS__: JSON.stringify(featherlessModelOptions),
    },
    plugins: [manifestPlugin(apiOrigins)],
    resolve: {
      alias: {
        "@": resolve(rootDir, "src"),
      },
    },
    test: {
      environment: "jsdom",
      include: ["tests/**/*.test.ts"],
      setupFiles: ["tests/setup.ts"],
    },
  };
});

function manifestPlugin(apiOrigins: string[]): Plugin {
  return {
    generateBundle() {
      this.emitFile({
        fileName: "manifest.json",
        source: JSON.stringify(
          {
            manifest_version: 3,
            name: "UNIQA Conversion Coach",
            description:
              "Hackathon extension that observes the UNIQA calculator and injects conversion coach nudges.",
            version: "0.1.0",
            minimum_chrome_version: "114",
            permissions: ["storage"],
            host_permissions: [
              "https://www.uniqa.at/*",
              "https://api.featherless.ai/*",
              ...apiOrigins.map((origin) => `${origin}/*`),
            ],
            background: {
              service_worker: "background.js",
              type: "module",
            },
            action: {
              default_title: "UNIQA Conversion Coach",
            },
            content_scripts: [
              {
                matches: ["https://www.uniqa.at/rechner/krankenversicherung/*"],
                js: ["content.js"],
                run_at: "document_idle",
              },
            ],
          },
          null,
          2,
        ),
        type: "asset",
      });
    },
    name: "extension-manifest-plugin",
  };
}

function resolveCoachApiOrigins(env: Record<string, string>): string[] {
  const origins = new Set<string>(["http://127.0.0.1:8787"]);
  for (const value of [env.VITE_COACH_API_ORIGIN, env.VITE_COACH_API_EXTRA_ORIGINS]) {
    if (!value) {
      continue;
    }

    for (const entry of value.split(",")) {
      const trimmed = entry.trim().replace(/\/+$/, "");
      if (trimmed) {
        origins.add(trimmed);
      }
    }
  }

  return [...origins];
}

function loadEnvFile(path: string, override = false): void {
  if (!existsSync(path)) {
    return;
  }

  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const separator = trimmed.indexOf("=");
    if (separator === -1) {
      continue;
    }

    const key = trimmed.slice(0, separator).trim();
    const rawValue = trimmed.slice(separator + 1).trim();
    const value = rawValue.replace(/^['"]|['"]$/g, "");
    if (override || process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

function parseModelList(value: string | undefined): string[] {
  const trimmed = value?.trim();
  if (!trimmed) {
    return [];
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) {
      return parsed
        .filter((model): model is string => typeof model === "string")
        .map(cleanModel)
        .filter(Boolean);
    }
  } catch {
    // Plain env strings are the common path; fall through to separator split.
  }

  return trimmed
    .replace(/^\[|\]$/g, "")
    .split(/[,;|]/)
    .map(cleanModel)
    .filter(Boolean);
}

function cleanModel(model: string): string {
  return model.trim().replace(/^['"]|['"]$/g, "");
}

function uniqueModels(models: string[]): string[] {
  return [...new Set(models.map(cleanModel).filter(Boolean))];
}
