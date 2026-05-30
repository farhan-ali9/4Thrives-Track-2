import { defineConfig } from "@playwright/test";

export default defineConfig({
  retries: 0,
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  timeout: 60_000,
  use: {
    baseURL: "https://www.uniqa.at/rechner/krankenversicherung/",
    headless: true,
    trace: "retain-on-failure",
  },
});
