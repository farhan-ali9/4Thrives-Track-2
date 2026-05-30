import pageMapJson from "./uniqa-page-map.json";
import type { ResolvedStep, UniqaPageMapEntry } from "./contracts";

export const uniqaPageMap = pageMapJson as UniqaPageMapEntry[];

function normalizeText(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function documentText(doc: Document): string {
  return normalizeText(doc.body?.innerText || doc.body?.textContent || "");
}

function hasAllText(doc: Document, requiredText: string[]): boolean {
  const text = documentText(doc);
  return requiredText.every((entry) => text.includes(normalizeText(entry)));
}

function hasAllSelectors(doc: Document, selectors: string[]): boolean {
  return selectors.every((selector) => doc.querySelector(selector));
}

function hasAnySelector(doc: Document, selectors: string[]): boolean {
  return selectors.length === 0 || selectors.some((selector) => doc.querySelector(selector));
}

export function resolvePageStep(doc: Document): ResolvedStep | null {
  for (const entry of uniqaPageMap) {
    if (!entry.enabled) {
      continue;
    }

    const match = entry.match;
    if (match.requiredText && !hasAllText(doc, match.requiredText)) {
      continue;
    }
    if (match.requiredSelectorsAll && !hasAllSelectors(doc, match.requiredSelectorsAll)) {
      continue;
    }
    if (match.requiredSelectorsAny && !hasAnySelector(doc, match.requiredSelectorsAny)) {
      continue;
    }

    return {
      pageStepId: entry.pageStepId,
      journeyStage: entry.journeyStage,
      injectionAnchor: entry.injectionAnchor,
      config: entry,
    };
  }

  return null;
}

export function queryFirst(doc: Document, selectors: string[]): Element | null {
  for (const selector of selectors) {
    const node = doc.querySelector(selector);
    if (node) {
      return node;
    }
  }
  return null;
}
