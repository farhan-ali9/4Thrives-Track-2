import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { describe, expect, test } from "vitest";
import { deriveContextFromDocument } from "@/shared/extractors";
import { resolvePageStep } from "@/shared/page-map";

const fixtures = [
  "s1_coverage_scope",
  "s2_for_whom",
  "s3_quote_basics",
  "s4_initial_price",
  "s5_add_ons",
  "s6_personal_medical_data",
] as const;

describe("resolvePageStep", () => {
  test.each(fixtures)("matches %s", (fixtureName) => {
    const doc = loadFixture(`${fixtureName}.html`);
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe(fixtureName);
  });

  test("extracts safe derived context on the tariff step", () => {
    const doc = loadFixture("s4_initial_price.html");
    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s4_initial_price");

    const context = deriveContextFromDocument(doc, resolved, {});
    expect(context.visiblePrice).toBe(41.3);
    expect(context.selectedTariff).toBeNull();
  });
});

function loadFixture(filename: string): Document {
  const html = readFileSync(resolve(process.cwd(), "tests/fixtures", filename), "utf8");
  return new JSDOM(html).window.document;
}
