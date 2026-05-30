import { existsSync, mkdirSync, mkdtempSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const extensionDir = resolve(scriptDir, "..");
const buildDir = resolve(extensionDir, "dist");
const outputDir = resolve(extensionDir, "demo-artifacts");

if (!existsSync(buildDir)) {
  throw new Error("Build the extension first with `npm run build` inside extension/.");
}

mkdirSync(outputDir, { recursive: true });

const userDataDir = mkdtempSync(join(tmpdir(), "uniqa-extension-demo-"));
const context = await chromium.launchPersistentContext(userDataDir, {
  args: [
    `--disable-extensions-except=${buildDir}`,
    `--load-extension=${buildDir}`,
  ],
  headless: false,
});

try {
  const page = context.pages()[0] ?? (await context.newPage());
  await page.goto("https://www.uniqa.at/rechner/krankenversicherung/");

  await page.getByRole("checkbox", { name: "Bei Arztbesuchen" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByRole("radio", { name: "Ich selbst" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByRole("textbox", { name: "Geburtsdatum" }).fill("01.01.1990");
  await page.locator("[data-cy='ur-select-field-button']").click();
  await page.getByText("ÖGK").click();
  await page.getByRole("button", { name: "Weiter" }).click();

  await page.getByRole("button", { name: "Wählen Optimal" }).hover();
  await page.locator("#uniqa-conversion-coach-root").waitFor({ state: "attached" });
  await page.waitForTimeout(750);
  await page.screenshot({ path: resolve(outputDir, "price-nudge.png"), fullPage: true });

  await page.getByRole("button", { name: "Wählen Opt. Plus" }).click();
  await page.waitForTimeout(750);
  await page.screenshot({ path: resolve(outputDir, "advisor-explainer.png"), fullPage: true });

  await page.getByRole("button", { name: "Wählen Optimal" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.waitForTimeout(750);
  await page.screenshot({ path: resolve(outputDir, "addons-step.png"), fullPage: true });

  console.log(`Saved demo screenshots to ${outputDir}`);
  console.log("Close the browser window when you are done.");
} catch (error) {
  console.error(error);
  await context.close();
  process.exitCode = 1;
}
