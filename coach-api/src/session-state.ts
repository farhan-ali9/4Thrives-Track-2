// Session state reconstruction from v2 event history.
// Tracks what the backend knows about the user's journey without DOM access.

import type { V2EventRecord } from "./repository.js";

const RECENT_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
const MAX_RECENT_EVENTS = 30;

export interface ReconstructedSessionState {
  sessionId: string;
  currentStepId: string | null;
  coverage: string | null;
  insuredPerson: string | null;
  selectedTariff: string | null;
  selectedAddons: string[];
  visiblePrice: number | null;
  priceDelta: number | null;
  recentEvents: V2EventRecord[];
  interventionCount: number;
  lastInterventionTs: number | null;
  advisorRouted: boolean;
  converted: boolean;
  abandoned: boolean;
  // Derived signal flags for policy engine / guardrails
  hasOosPathSignal: boolean;
  hasOosTariffClickSignal: boolean;
  hasDwellSignal: boolean;
  hasBackNavSignal: boolean;
  hasCancelHoverSignal: boolean;
  hasPriceHoverSignal: boolean;
  hasRepeatedChangeSignal: boolean;
  hasPriceGapShock: boolean;
}

export function reconstructSessionState(
  sessionId: string,
  events: V2EventRecord[],
): ReconstructedSessionState {
  const sorted = [...events].sort((a, b) => a.ts - b.ts);
  const now = Date.now();
  const cutoff = now - RECENT_WINDOW_MS;

  const recent = sorted.filter((e) => e.ts >= cutoff).slice(-MAX_RECENT_EVENTS);

  let currentStepId: string | null = null;
  let coverage: string | null = null;
  let insuredPerson: string | null = null;
  let selectedTariff: string | null = null;
  let selectedAddons: string[] = [];
  let visiblePrice: number | null = null;
  let priceDelta: number | null = null;
  let interventionCount = 0;
  let lastInterventionTs: number | null = null;
  let advisorRouted = false;
  let converted = false;
  let abandoned = false;

  // Signal accumulators (true if any event in the session carries the signal)
  let hasOosPathSignal = false;
  let hasOosTariffClickSignal = false;
  let hasDwellSignal = false;
  let hasBackNavSignal = false;
  let hasCancelHoverSignal = false;
  let hasPriceHoverSignal = false;
  let hasRepeatedChangeSignal = false;

  for (const event of sorted) {
    const dc = event.derivedContext;
    const ds = event.derivedSignals;

    // Step tracking
    if (event.stepId) {
      currentStepId = event.stepId;
    }

    // Extract state from derivedContext (extension should populate these)
    if (dc.selectedTariff && typeof dc.selectedTariff === "string") {
      selectedTariff = dc.selectedTariff;
    }
    if (dc.coverage && typeof dc.coverage === "string") {
      coverage = dc.coverage;
    }
    if (dc.insuredPerson && typeof dc.insuredPerson === "string") {
      insuredPerson = dc.insuredPerson;
    }
    if (Array.isArray(dc.selectedAddOns)) {
      selectedAddons = dc.selectedAddOns as string[];
    }
    if (
      dc.visiblePrice !== undefined &&
      dc.visiblePrice !== null &&
      typeof dc.visiblePrice === "number"
    ) {
      visiblePrice = dc.visiblePrice;
    }
    if (
      dc.priceDelta !== undefined &&
      dc.priceDelta !== null &&
      typeof dc.priceDelta === "number"
    ) {
      priceDelta = dc.priceDelta;
    }

    // Extract signals from derivedSignals map
    if (ds.path_oos === true) hasOosPathSignal = true;
    if (ds.tariff_click_oos === true) hasOosTariffClickSignal = true;
    if (ds.dwell === true) hasDwellSignal = true;
    if (ds.back_nav === true || ds.scroll_back === true)
      hasBackNavSignal = true;
    if (ds.cancel_hover === true) hasCancelHoverSignal = true;
    if (ds.price_hover === true) hasPriceHoverSignal = true;
    if (ds.repeated_change === true) hasRepeatedChangeSignal = true;

    // Also infer signals from event_type
    if (event.eventType === "inactivity") hasCancelHoverSignal = true;

    // Intervention tracking (coach impressions)
    if (event.eventType === "coach_impression") {
      interventionCount++;
      lastInterventionTs = event.ts;
    }

    // Outcome signals from element_key
    if (
      event.eventType === "coach_cta" &&
      event.elementKey === "advisor_route"
    ) {
      advisorRouted = true;
    }
  }

  // Price gap shock: priceDelta >= 3 EUR (matches policy threshold)
  const hasPriceGapShock = priceDelta !== null && priceDelta >= 3;

  return {
    sessionId,
    currentStepId,
    coverage,
    insuredPerson,
    selectedTariff,
    selectedAddons,
    visiblePrice,
    priceDelta,
    recentEvents: recent,
    interventionCount,
    lastInterventionTs,
    advisorRouted,
    converted,
    abandoned,
    hasOosPathSignal,
    hasOosTariffClickSignal,
    hasDwellSignal,
    hasBackNavSignal,
    hasCancelHoverSignal,
    hasPriceHoverSignal,
    hasRepeatedChangeSignal,
    hasPriceGapShock,
  };
}

// Risk score: 0–100 based on behavioral signals and step context.
// 0–29 low, 30–59 medium, 60–79 high, 80–100 critical.
export function computeRiskScore(state: ReconstructedSessionState): number {
  let score = 0;

  if (state.hasCancelHoverSignal) score += 25;
  if (state.hasBackNavSignal) score += 20;
  if (state.hasDwellSignal) score += 15;
  if (state.hasPriceGapShock) score += 20;
  if (state.hasPriceHoverSignal) score += 15;
  if (state.hasRepeatedChangeSignal) score += 10;
  if (state.hasOosTariffClickSignal) score += 5;

  // Step-based risk boost
  if (state.currentStepId === "s7_final_price") score += 20;
  else if (state.currentStepId === "s4_initial_price") score += 15;

  return Math.min(100, score);
}

// Convert reconstructed state + current event to SignalKind[] for the policy engine.
export function deriveSignalKinds(state: ReconstructedSessionState): string[] {
  const signals: string[] = [];
  if (state.hasDwellSignal) signals.push("dwell");
  if (state.hasBackNavSignal) signals.push("back_nav");
  if (state.hasRepeatedChangeSignal) signals.push("repeated_change");
  if (state.hasCancelHoverSignal) signals.push("cancel_hover", "inactivity");
  if (state.hasPriceHoverSignal) signals.push("price_hover");
  if (state.hasOosTariffClickSignal) signals.push("tariff_click_oos");
  if (state.hasOosPathSignal) signals.push("path_oos");
  return signals;
}
