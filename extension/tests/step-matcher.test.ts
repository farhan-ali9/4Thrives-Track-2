import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { afterEach, describe, expect, test, vi } from "vitest";
import { deriveContextFromDocument } from "@/shared/extractors";
import { resolvePageStep } from "@/shared/page-map";

const fixtures = [
  "s1_coverage_scope",
  "s2_for_whom",
  "s3_quote_basics",
  "s4_initial_price",
  "s5_add_ons",
  "s6_personal_medical_data",
  "s7_final_price",
  "s8_confirm",
] as const;

describe("resolvePageStep", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test.each(fixtures)("matches %s", (fixtureName) => {
    const doc = loadFixture(`${fixtureName}.html`);
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe(fixtureName);
  });

  test("maps verified page steps to their canonical coach steps", () => {
    const quoteBasics = resolvePageStep(loadFixture("s3_quote_basics.html"));
    const medicalData = resolvePageStep(loadFixture("s6_personal_medical_data.html"));

    expect(quoteBasics?.journeyStage).toBe("quote_basics");
    expect(medicalData?.journeyStage).toBe("health_data");
  });

  test("extracts safe derived context on the tariff step", () => {
    const doc = loadFixture("s4_initial_price.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s4_initial_price");

    const context = deriveContextFromDocument(doc, resolved, {});
    expect(context.visiblePriceMonthly).toBe(41.3);
    expect(context.selectedTariff).toBeNull();
  });

  test("extracts live-safe context on the step 7 screen", () => {
    const doc = loadFixture("s7_final_price.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s7_final_price");

    const context = deriveContextFromDocument(doc, resolved, {
      visiblePriceMonthly: 73.02,
    });
    expect(context.fieldCompletion).toBe(0.5);
    expect(context.visiblePriceMonthly).toBe(73.02);
    expect(context.priceDeltaMonthly).toBe(0);
  });

  test("extracts live-safe context on the terminal advisor-request screen", () => {
    const doc = loadFixture("s8_confirm.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s8_confirm");

    const context = deriveContextFromDocument(doc, resolved, {
      visiblePriceMonthly: 73.02,
    });
    expect(context.fieldCompletion).toBe(0.25);
    expect(context.visiblePriceMonthly).toBe(73.02);
    expect(context.priceDeltaMonthly).toBe(0);
  });

  test("computes price delta against the previous visible price", () => {
    const doc = loadFixture("s5_add_ons.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s5_add_ons");

    const context = deriveContextFromDocument(doc, resolved, {
      visiblePriceMonthly: 41.3,
    });
    expect(context.visiblePriceMonthly).toBe(73.02);
    expect(context.priceDeltaMonthly).toBe(31.72);
  });

  test("tracks session duration without adding personal data", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-30T12:00:00Z"));

    const doc = loadFixture("s4_initial_price.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s4_initial_price");

    const initialContext = deriveContextFromDocument(doc, resolved, {});
    expect(initialContext.sessionDurationMs).toBe(0);

    vi.advanceTimersByTime(1_250);
    const nextContext = deriveContextFromDocument(doc, resolved, initialContext);
    expect(nextContext.sessionDurationMs).toBe(1_250);
  });
});

function loadFixture(filename: string): Document {
  const html = readFileSync(resolve(process.cwd(), "tests/fixtures", filename), "utf8");
  return new JSDOM(html).window.document;
}
