import type { NormalizedEvent, SignalKind, StepRuntimeState } from "@/shared/contracts";

const LONG_DWELL_MS = 25_000;

export function deriveSignals(
  event: NormalizedEvent,
  state: StepRuntimeState,
  recentEvents: NormalizedEvent[],
): SignalKind[] {
  const signals = new Set<SignalKind>();

  if (event.type === "step_leave" && (event.dwellMs ?? 0) >= LONG_DWELL_MS) {
    signals.add("dwell");
  }

  if (event.type === "scroll" && isScrollBack(event.value)) {
    signals.add("scroll_back");
  }

  if (event.type === "click" && isBackInteraction(event)) {
    signals.add("back_nav");
  }

  if ((event.type === "change" || event.type === "input") && isRepeatedChange(event, state)) {
    signals.add("repeated_change");
  }

  if (event.type === "pointerenter" && isPriceTarget(event)) {
    signals.add("price_hover");
  }

  if (event.type === "pointerenter" && isCancelTarget(event)) {
    signals.add("cancel_hover");
  }

  if (event.type === "click" && isOutOfScopeTariff(event)) {
    signals.add("tariff_click_oos");
  }

  if ((event.type === "click" || event.type === "change") && isOutOfScopePath(event)) {
    signals.add("path_oos");
  }

  if (event.type === "inactivity") {
    signals.add("inactivity");
  }

  if (!signals.size && isLingeringPriceHover(recentEvents)) {
    signals.add("price_hover");
  }

  return [...signals];
}

function isScrollBack(value: NormalizedEvent["value"]): boolean {
  return typeof value === "object" && value !== null && value.direction === "up";
}

function isBackInteraction(event: NormalizedEvent): boolean {
  const key = event.elementKey ?? "";
  return key.includes("back") || key.includes("zuruck") || key.includes("abbrechen");
}

function isRepeatedChange(event: NormalizedEvent, state: StepRuntimeState): boolean {
  if (!event.elementKey) {
    return false;
  }
  return (state.fieldChangeCounts[event.elementKey] ?? 0) >= 2;
}

function isPriceTarget(event: NormalizedEvent): boolean {
  const key = event.elementKey ?? "";
  return key.includes("price") || key.includes("selectionbutton") || key.includes("tariff");
}

function isCancelTarget(event: NormalizedEvent): boolean {
  const key = event.elementKey ?? "";
  return key.includes("back") || key.includes("abbrechen") || key.includes("cancel");
}

function isOutOfScopeTariff(event: NormalizedEvent): boolean {
  if (typeof event.value === "object" && event.value !== null && "intent" in event.value) {
    return event.value.intent === "out_of_scope_tariff";
  }
  const key = event.elementKey ?? "";
  return key.includes("opt_plus") || key.includes("premium");
}

function isOutOfScopePath(event: NormalizedEvent): boolean {
  if (typeof event.value === "object" && event.value !== null && "intent" in event.value) {
    return event.value.intent === "out_of_scope_path";
  }
  return false;
}

function isLingeringPriceHover(recentEvents: NormalizedEvent[]): boolean {
  const lastHover = [...recentEvents]
    .reverse()
    .find((event) => event.type === "pointerenter" && isPriceTarget(event));
  if (!lastHover) {
    return false;
  }
  return Date.now() - lastHover.ts <= 10_000;
}
