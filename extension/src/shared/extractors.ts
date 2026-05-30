import type { DerivedContext, ExtractorConfig, ResolvedStep } from "./contracts";
import { computeAgeBand, parseEuroValue, readText } from "./dom-utils";
import { queryFirst } from "./page-map";

const documentSessionStartedAt = new WeakMap<Document, number>();

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
  if (isTextInputElement(element) || isTextAreaElement(element)) {
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
    if (!isInputElement(element) || element.type !== "checkbox" || !element.checked) {
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
    if (isInputElement(element)) {
      return !["hidden", "submit", "button"].includes(element.type);
    }
    return true;
  });

  if (!fields.length) {
    return null;
  }

  let completed = 0;
  for (const field of fields) {
    if (isInputElement(field)) {
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

    if (isTextAreaElement(field) || isSelectElement(field)) {
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
    applyExtractor(doc, extractor, result, baseContext);
  }

  return result;
}

function applyExtractor(
  doc: Document,
  extractor: ExtractorConfig,
  result: DerivedContext,
  baseContext: DerivedContext,
): void {
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
        const previousVisiblePrice = baseContext.visiblePrice ?? null;
        result.priceDelta =
          previousVisiblePrice !== null
            ? Number((current - previousVisiblePrice).toFixed(2))
            : result.priceDelta ?? null;
      }
      return;
    }
    case "sessionTiming": {
      result.sessionDurationMs = getSessionDurationMs(doc);
      return;
    }
    default: {
      const neverReached: never = extractor.kind;
      throw new Error(`Unsupported extractor kind: ${neverReached}`);
    }
  }
}

function getSessionDurationMs(doc: Document): number {
  const existingStart = documentSessionStartedAt.get(doc);
  const now = Date.now();
  if (existingStart === undefined) {
    documentSessionStartedAt.set(doc, now);
    return 0;
  }

  return Math.max(0, now - existingStart);
}

function isInputElement(element: Element): element is HTMLInputElement {
  const view = element.ownerDocument?.defaultView;
  return Boolean(view && element instanceof view.HTMLInputElement);
}

function isTextInputElement(element: Element): element is HTMLInputElement {
  return isInputElement(element);
}

function isTextAreaElement(element: Element): element is HTMLTextAreaElement {
  const view = element.ownerDocument?.defaultView;
  return Boolean(view && element instanceof view.HTMLTextAreaElement);
}

function isSelectElement(element: Element): element is HTMLSelectElement {
  const view = element.ownerDocument?.defaultView;
  return Boolean(view && element instanceof view.HTMLSelectElement);
}
