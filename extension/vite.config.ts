import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
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
});
