import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const pageMap = JSON.parse(
  readFileSync(new URL("../src/shared/uniqa-page-map.json", import.meta.url), "utf8"),
) as Array<{
  enabled: boolean;
  match: {
    requiredSelectorsAll?: string[];
    requiredSelectorsAny?: string[];
    requiredText?: string[];
  };
  pageStepId: string;
}>;

test("walks the verified live doctor path through step 6", async ({ page }) => {
  await page.goto("https://www.uniqa.at/rechner/krankenversicherung/");
  await dismissCookieBanner(page);
  await expect.poll(() => detectStep(page)).toBe("s1_coverage_scope");

  await page.getByRole("checkbox", { name: "Bei Arztbesuchen" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s2_for_whom");

  await page.getByRole("radio", { name: "Ich selbst" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s3_quote_basics");

  await page.getByRole("textbox", { name: "Geburtsdatum" }).fill("01.01.1990");
  await page.locator("[data-cy='ur-select-field-button']").click();
  await page.getByText("ÖGK").click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s4_initial_price");

  await page.getByRole("button", { name: "Wählen Optimal" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s5_add_ons");

  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s6_personal_medical_data");
});

test("classifies an out-of-scope tariff click on the live tariff step", async ({ page }) => {
  await page.goto("https://www.uniqa.at/rechner/krankenversicherung/");
  await dismissCookieBanner(page);
  await page.getByRole("checkbox", { name: "Bei Arztbesuchen" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByRole("radio", { name: "Ich selbst" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await page.getByRole("textbox", { name: "Geburtsdatum" }).fill("01.01.1990");
  await page.locator("[data-cy='ur-select-field-button']").click();
  await page.getByText("ÖGK").click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s4_initial_price");

  await page.evaluate(() => {
    (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals = [];
    document.addEventListener(
      "click",
      (event) => {
        const target = event.target as HTMLElement | null;
        const button = target?.closest("button");
        const ariaLabel = button?.getAttribute("aria-label") ?? "";
        if (/Wählen\s+(Opt\.\s*Plus|Premium)/i.test(ariaLabel)) {
          (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals?.push("tariff_click_oos");
        }
      },
      { capture: true },
    );
  });

  await page.getByRole("button", { name: "Wählen Opt. Plus" }).click();
  const signals = await page.evaluate(() => (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals ?? []);
  expect(signals).toContain("tariff_click_oos");
});

async function detectStep(page: Page): Promise<string | null> {
  const liveEntries = pageMap.filter((entry) => entry.enabled);
  return page.evaluate((entries) => {
    const normalize = (value: string | null | undefined) => (value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
    const docText = normalize(document.body?.innerText || document.body?.textContent || "");

    for (const entry of entries) {
      const requiredText = entry.match.requiredText ?? [];
      const requiredSelectorsAll = entry.match.requiredSelectorsAll ?? [];
      const requiredSelectorsAny = entry.match.requiredSelectorsAny ?? [];

      const matchesText = requiredText.every((needle) => docText.includes(normalize(needle)));
      const matchesAllSelectors = requiredSelectorsAll.every((selector) => document.querySelector(selector));
      const matchesAnySelector =
        requiredSelectorsAny.length === 0 || requiredSelectorsAny.some((selector) => document.querySelector(selector));

      if (matchesText && matchesAllSelectors && matchesAnySelector) {
        return entry.pageStepId;
      }
    }

    return null;
  }, liveEntries);
}

async function dismissCookieBanner(page: Page): Promise<void> {
  const rejectButton = page.getByRole("button", {
    name: "Alle ablehnen außer technisch notwendige Cookies",
  });

  if (await rejectButton.isVisible().catch(() => false)) {
    await rejectButton.click();
  }
}
