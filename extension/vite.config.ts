import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig, loadEnv, type Plugin } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

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
