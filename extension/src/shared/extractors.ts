import type { DerivedContext, ExtractorConfig, ResolvedStep } from "./contracts";
import { computeAgeBand, parseEuroValue, readText } from "./dom-utils";
import { queryFirst } from "./page-map";

const SOCIAL_PROVIDER_CODES: Record<string, string> = {
  "BVAEB-EB": "bvaeb_eb",
  "BVAEB-OEB": "bvaeb_oeb",
  "KFA Wien,NÖ,Sbg,Ktn": "kfa_wien_noe_sbg_ktn",
  "ÖGK": "ogk",
  "SVS gew.Wirtschaft Sach": "svs_gewerbe",
  "SVS Landwirtschaft": "svs_landwirtschaft",
};

function queryAll(doc: Document, selectors: string[]): Element[] {
  const seen = new Set<Element>();
  const elements: Element[] = [];

  for (const selector of selectors) {
    for (const match of Array.from(doc.querySelectorAll(selector))) {
      if (!seen.has(match)) {
        seen.add(match);
        elements.push(match);
      }
    }
  }

  return elements;
}

function readInputValue(element: Element | null): string {
  if (!element) {
    return "";
  }
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    return element.value;
  }
  return readText(element);
}

function extractSelectedTariffFromDom(doc: Document): string | null {
  const pressed = doc.querySelector("[aria-pressed='true'][aria-label^='Wählen ']") as HTMLElement | null;
  if (pressed?.getAttribute("aria-label")) {
    return pressed.getAttribute("aria-label")!.replace(/^Wählen\s+/i, "").trim().toLowerCase();
  }

  const selected = doc.querySelector("[data-selected='true'][aria-label^='Wählen ']") as HTMLElement | null;
  if (selected?.getAttribute("aria-label")) {
    return selected.getAttribute("aria-label")!.replace(/^Wählen\s+/i, "").trim().toLowerCase();
  }

  return null;
}

function extractSelectedAddOns(doc: Document, selectors: string[]): string[] {
  const values: string[] = [];

  for (const element of queryAll(doc, selectors)) {
    if (!(element instanceof HTMLInputElement) || element.type !== "checkbox" || !element.checked) {
      continue;
    }

    const label = element.closest("label");
    const text = readText(label) || readText(element.parentElement) || element.getAttribute("aria-label") || "selected_add_on";
    values.push(text.toLowerCase());
  }

  return values;
}

function extractFieldCompletion(doc: Document, selectors: string[]): number | null {
  const fields = queryAll(doc, selectors).filter((element) => {
    if (element instanceof HTMLInputElement) {
      return !["hidden", "submit", "button"].includes(element.type);
    }
    return true;
  });

  if (!fields.length) {
    return null;
  }

  let completed = 0;
  for (const field of fields) {
    if (field instanceof HTMLInputElement) {
      if (field.type === "checkbox" || field.type === "radio") {
        if (field.checked) {
          completed += 1;
        }
        continue;
      }
      if (field.value.trim()) {
        completed += 1;
      }
      continue;
    }

    if (field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
      if (field.value.trim()) {
        completed += 1;
      }
      continue;
    }

    if (readText(field)) {
      completed += 1;
    }
  }

  return Number((completed / fields.length).toFixed(2));
}

function extractValidationErrorCount(doc: Document): number {
  return doc.querySelectorAll("[aria-invalid='true'], input:invalid, select:invalid, textarea:invalid").length;
}

function extractVisiblePrice(doc: Document, selectors: string[]): number | null {
  for (const element of queryAll(doc, selectors)) {
    const text = readText(element);
    const scopedValue = parseRelevantOfferPrice(text);
    const value = scopedValue ?? parseEuroValue(text);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function parseRelevantOfferPrice(text: string): number | null {
  const patterns = [
    /Unser Angebot[^0-9]*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*EUR/iu,
    /Voraussichtliche Prämie[^0-9]*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*EUR/iu,
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      return parseEuroValue(`${match[1]} EUR`);
    }
  }

  return null;
}

function extractSocialInsuranceProvider(doc: Document, selectors: string[]): string | null {
  const text = readInputValue(queryFirst(doc, selectors));
  return SOCIAL_PROVIDER_CODES[text] ?? null;
}

export function deriveContextFromDocument(
  doc: Document,
  resolvedStep: ResolvedStep | null,
  baseContext: DerivedContext = {},
): DerivedContext {
  if (!resolvedStep) {
    return { ...baseContext };
  }

  const result: DerivedContext = { ...baseContext };

  for (const extractor of resolvedStep.config.extractors) {
    applyExtractor(doc, extractor, result);
  }

  return result;
}

function applyExtractor(doc: Document, extractor: ExtractorConfig, result: DerivedContext): void {
  const selectors = extractor.selectors ?? [];

  switch (extractor.kind) {
    case "ageBandFromDate": {
      const value = readInputValue(queryFirst(doc, selectors));
      result.ageBand = computeAgeBand(value);
      return;
    }
    case "socialInsuranceProvider": {
      result.socialInsuranceProviderCode = extractSocialInsuranceProvider(doc, selectors);
      return;
    }
    case "selectedTariff": {
      result.selectedTariff = extractSelectedTariffFromDom(doc);
      return;
    }
    case "selectedAddOns": {
      result.selectedAddOns = extractSelectedAddOns(doc, selectors);
      return;
    }
    case "fieldCompletion": {
      result.fieldCompletion = extractFieldCompletion(doc, selectors);
      return;
    }
    case "validationErrorCount": {
      result.validationErrorCount = extractValidationErrorCount(doc);
      return;
    }
    case "visiblePrice": {
      result.visiblePrice = extractVisiblePrice(doc, selectors);
      return;
    }
    case "priceDelta": {
      const current = extractVisiblePrice(doc, selectors);
      if (current !== null) {
        result.priceDelta =
          result.visiblePrice !== undefined && result.visiblePrice !== null
            ? Number((current - result.visiblePrice).toFixed(2))
            : result.priceDelta ?? null;
      }
      return;
    }
    case "sessionTiming": {
      return;
    }
    default: {
      const neverReached: never = extractor.kind;
      throw new Error(`Unsupported extractor kind: ${neverReached}`);
    }
  }
}
