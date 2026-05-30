import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@uniqa-conversion-coach/shared": resolve(
        __dirname,
        "../shared/dist/index.js",
      ),
      "@uniqa-conversion-coach/shared/contracts": resolve(
        __dirname,
        "../shared/dist/contracts.js",
      ),
      "@uniqa-conversion-coach/shared/policy": resolve(
        __dirname,
        "../shared/dist/policy.js",
      ),
      "@uniqa-conversion-coach/shared/seed-policy": resolve(
        __dirname,
        "../shared/dist/seed-policy.js",
      ),
    },
  },
  test: {
    environment: "node",
  },
});
