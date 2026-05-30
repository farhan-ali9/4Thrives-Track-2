import type { DerivedContext, NormalizedEventType, ResolvedStep } from "@/shared/contracts";
import { readText } from "@/shared/dom-utils";
import { deriveContextFromDocument } from "@/shared/extractors";
import { slugify } from "@/shared/dom-utils";
import { queryFirst } from "@/shared/page-map";

export interface InteractionEvent {
  type: Extract<
    NormalizedEventType,
    "click" | "change" | "input" | "focus" | "blur" | "scroll" | "pointerenter" | "inactivity"
  >;
  elementKey: string | null;
  value: Record<string, unknown> | string | number | boolean | null;
  derivedContext: DerivedContext;
}

export class DataCollector {
  private lastScrollY = window.scrollY;
  private inactivityTimer: number | null = null;
  private lastActivityAt = Date.now();

  constructor(
    private readonly getCurrentStep: () => ResolvedStep | null,
    private readonly getCurrentContext: () => DerivedContext,
    private readonly onInteraction: (event: InteractionEvent) => void,
  ) {}

  start(): void {
    document.addEventListener("click", this.handleClick, true);
    document.addEventListener("change", this.handleChange, true);
    document.addEventListener("input", this.handleInput, true);
    document.addEventListener("focus", this.handleFocus, true);
    document.addEventListener("blur", this.handleBlur, true);
    document.addEventListener("pointerenter", this.handlePointerEnter, true);
    window.addEventListener("scroll", this.handleScroll, { passive: true });
    this.resetInactivityTimer();
  }

  stop(): void {
    document.removeEventListener("click", this.handleClick, true);
    document.removeEventListener("change", this.handleChange, true);
    document.removeEventListener("input", this.handleInput, true);
    document.removeEventListener("focus", this.handleFocus, true);
    document.removeEventListener("blur", this.handleBlur, true);
    document.removeEventListener("pointerenter", this.handlePointerEnter, true);
    window.removeEventListener("scroll", this.handleScroll);
    if (this.inactivityTimer !== null) {
      window.clearTimeout(this.inactivityTimer);
      this.inactivityTimer = null;
    }
  }

  private readonly handleClick = (event: Event): void => {
    this.resetInactivityTimer();
    const element = resolveInteractiveElement(event.target);
    if (!element) {
      return;
    }
    this.emit("click", element, buildSanitizedValue(element));
  };

  private readonly handleChange = (event: Event): void => {
    this.resetInactivityTimer();
    const element = resolveInteractiveElement(event.target);
    if (!element) {
      return;
    }
    this.emit("change", element, buildSanitizedValue(element));
  };

  private readonly handleInput = (event: Event): void => {
    this.resetInactivityTimer();
    const element = resolveInteractiveElement(event.target);
    if (!element) {
      return;
    }
    this.emit("input", element, buildSanitizedValue(element));
  };

  private readonly handleFocus = (event: Event): void => {
    this.resetInactivityTimer();
    const element = resolveInteractiveElement(event.target);
    if (!element) {
      return;
    }
    this.emit("focus", element, null);
  };

  private readonly handleBlur = (event: Event): void => {
    this.resetInactivityTimer();
    const element = resolveInteractiveElement(event.target);
    if (!element) {
      return;
    }
    this.emit("blur", element, null);
  };

  private readonly handlePointerEnter = (event: Event): void => {
    this.resetInactivityTimer();
    if (!(event.target instanceof Element)) {
      return;
    }

    const currentStep = this.getCurrentStep();
    if (!currentStep) {
      return;
    }

    const isPriceTarget = matchesAnySelector(event.target, currentStep.config.selectors.priceTargets ?? []);
    const isCancelTarget = matchesAnySelector(event.target, currentStep.config.selectors.cancelTargets ?? []);
    if (!isPriceTarget && !isCancelTarget) {
      return;
    }

    this.onInteraction({
      derivedContext: this.buildDerivedContext(),
      elementKey: buildPointerElementKey(event.target),
      type: "pointerenter",
      value: {
        target: isPriceTarget ? "price" : "cancel",
      },
    });
  };

  private readonly handleScroll = (): void => {
    this.resetInactivityTimer();
    const nextScrollY = window.scrollY;
    const direction = nextScrollY < this.lastScrollY ? "up" : "down";
    const delta = Math.abs(nextScrollY - this.lastScrollY);
    this.lastScrollY = nextScrollY;

    if (delta < 32) {
      return;
    }

    this.onInteraction({
      derivedContext: this.buildDerivedContext(),
      elementKey: "window_scroll",
      type: "scroll",
      value: {
        delta,
        direction,
      },
    });
  };

  private emit(
    type: InteractionEvent["type"],
    element: HTMLElement | HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
    value: InteractionEvent["value"],
  ): void {
    this.onInteraction({
      derivedContext: this.buildDerivedContext(),
      elementKey: buildElementKey(element),
      type,
      value,
    });
  }

  private buildDerivedContext(): DerivedContext {
    const step = this.getCurrentStep();
    return deriveContextFromDocument(document, step, this.getCurrentContext());
  }

  private resetInactivityTimer(): void {
    if (this.inactivityTimer !== null) {
      window.clearTimeout(this.inactivityTimer);
    }
    this.lastActivityAt = Date.now();

    this.scheduleInactivityTimer(getShortestInactivityThresholdMs());
  }

  private scheduleInactivityTimer(delayMs: number): void {
    this.inactivityTimer = window.setTimeout(() => {
      const thresholdMs = getInactivityThresholdMs(this.getCurrentStep()?.pageStepId ?? null);
      const idleMs = Date.now() - this.lastActivityAt;
      if (idleMs < thresholdMs) {
        this.scheduleInactivityTimer(thresholdMs - idleMs);
        return;
      }

      this.onInteraction({
        derivedContext: this.buildDerivedContext(),
        elementKey: "inactivity_timer",
        type: "inactivity",
        value: {
          idleMs,
        },
      });
    }, delayMs);
  }
}

const DEFAULT_INACTIVITY_MS = 30_000;
const STEP_INACTIVITY_MS: Record<string, number> = {
  s4_initial_price: 12_000,
  s6_personal_medical_data: 18_000,
  s7_final_price: 12_000,
};

function getInactivityThresholdMs(stepId: string | null): number {
  return (stepId && STEP_INACTIVITY_MS[stepId]) || DEFAULT_INACTIVITY_MS;
}

function getShortestInactivityThresholdMs(): number {
  return Math.min(DEFAULT_INACTIVITY_MS, ...Object.values(STEP_INACTIVITY_MS));
}

function resolveInteractiveElement(
  target: EventTarget | null,
): HTMLElement | HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null {
  if (!(target instanceof Element)) {
    return null;
  }

  return (
    (target.closest("button, input, textarea, select, [role='button'], [role='radio'], [role='checkbox']") as
      | HTMLElement
      | HTMLInputElement
      | HTMLTextAreaElement
      | HTMLSelectElement
      | null) ?? null
  );
}

function buildElementKey(
  element: HTMLElement | HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): string {
  const parts = [
    element.getAttribute("data-cy"),
    element.getAttribute("aria-label"),
    element.getAttribute("name"),
    "placeholder" in element ? element.placeholder : null,
    readAssociatedLabel(element),
    element.textContent,
  ].filter(Boolean) as string[];

  return slugify(parts[0] ?? "unknown_element");
}

function buildPointerElementKey(element: Element): string {
  const raw =
    element.getAttribute("data-cy") ||
    element.getAttribute("aria-label") ||
    element.textContent ||
    element.tagName;
  return slugify(raw);
}

function readAssociatedLabel(
  element: HTMLElement | HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): string | null {
  if ("labels" in element && element.labels?.length) {
    return element.labels[0]?.textContent?.trim() ?? null;
  }

  const label = element.closest("label");
  if (label) {
    return label.textContent?.trim() ?? null;
  }

  return null;
}

function buildSanitizedValue(
  element: HTMLElement | HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): Record<string, unknown> | null {
  if (element instanceof HTMLInputElement) {
    if (element.type === "checkbox" || element.type === "radio") {
      const label = readAssociatedLabel(element) ?? element.getAttribute("aria-label") ?? "option";
      const normalized = slugify(label);
      if (normalized.includes("krankenhaus") || normalized.includes("andere_personen")) {
        return {
          checked: element.checked,
          intent: "out_of_scope_path",
          option: normalized,
        };
      }

      return {
        checked: element.checked,
        option: normalized,
      };
    }

    return {
      filled: element.value.trim().length > 0,
    };
  }

  if (element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
    return {
      filled: element.value.trim().length > 0,
    };
  }

  const ariaLabel = element.getAttribute("aria-label") ?? "";
  const optionLabel = normalizeChoiceLabel(ariaLabel || readText(element));
  if (!optionLabel) {
    return null;
  }

  if (optionLabel.includes("krankenhaus") || optionLabel.includes("andere_personen")) {
    return {
      intent: "out_of_scope_path",
      option: optionLabel,
    };
  }

  if (optionLabel === "opt_plus" || optionLabel === "premium") {
    return {
      intent: "out_of_scope_tariff",
      option: optionLabel,
    };
  }

  return {
    option: optionLabel,
  };
}

function matchesAnySelector(element: Element, selectors: string[]): boolean {
  for (const selector of selectors) {
    if (element.matches(selector) || element.closest(selector)) {
      return true;
    }
  }
  return false;
}

export function findPrimaryAnchor(step: ResolvedStep | null): Element | null {
  if (!step) {
    return null;
  }
  return queryFirst(document, step.config.selectors.primaryCta);
}

function normalizeChoiceLabel(raw: string | null): string | null {
  const normalized = slugify((raw ?? "").replace(/^Wahlen?\s+/i, "").replace(/^Wählen\s+/i, ""));
  return normalized || null;
}
