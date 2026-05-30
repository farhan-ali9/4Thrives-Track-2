import type {
  CoachApiStatus,
  JourneyDecision,
  JourneyOutcome,
  JourneyRouteFamily,
  JourneySessionState,
  JourneySignal,
  JourneySnapshot,
  NormalizedEvent,
  RuntimeEventResponse,
} from "@/shared/contracts";
import { createLogger } from "@/shared/logger";
import { CoachClient } from "./coach-client";
import { deriveSignals } from "./signal-detector";
import { UniqaStorage } from "./storage";

const log = createLogger("orchestrator");

const DEFAULT_API_STATUS: CoachApiStatus = {
  endpoint: `${(import.meta.env?.VITE_COACH_API_ORIGIN ?? "http://127.0.0.1:8787").replace(/\/+$/, "")}/api/runtime/decide`,
  lastUpdatedAt: 0,
  message: "Waiting for first runtime API call",
  state: "starting",
};

export class UniqaEventOrchestrator {
  private readonly sessionQueues = new Map<string, Promise<void>>();

  constructor(
    private readonly storage: UniqaStorage,
    private readonly coachClient: CoachClient,
  ) {}

  async handleEvent(event: NormalizedEvent, url: string): Promise<RuntimeEventResponse> {
    return this.runSequentially(event.sessionId, async () => {
      await this.storage.appendEvent(event.sessionId, event);
      const recentEvents = await this.storage.getRecentEvents(event.sessionId);
      const updatedState = await this.updateJourneyState(event);
      const signals = deriveSignals(event, updatedState, recentEvents);

      const snapshot = this.buildSnapshot(event, updatedState, signals, url);
      await this.storage.appendSnapshot(event.sessionId, snapshot);

      if (!shouldDecide(event, signals, snapshot)) {
        return {
          decision: null,
          apiStatus: DEFAULT_API_STATUS,
          snapshot,
          signals,
        };
      }

      const result = await this.coachClient.decide(snapshot);
      const decision = await this.filterDecisionByCooldown(
        event.sessionId,
        snapshot.stage,
        result.decision,
        event.ts,
      );

      return {
        decision,
        apiStatus: result.apiStatus,
        snapshot,
        signals,
      };
    });
  }

  async finalizeOutcome(outcome: JourneyOutcome): Promise<CoachApiStatus> {
    await this.storage.appendOutcome(outcome.sessionId, outcome);
    return this.coachClient.sendOutcome(outcome);
  }

  private async runSequentially<T>(sessionId: string, task: () => Promise<T>): Promise<T> {
    const previous = this.sessionQueues.get(sessionId) ?? Promise.resolve();
    let releaseQueue: (() => void) | null = null;
    const current = new Promise<void>((resolve) => {
      releaseQueue = resolve;
    });
    const queue = previous.then(() => current);

    this.sessionQueues.set(sessionId, queue);
    await previous;

    try {
      return await task();
    } finally {
      releaseQueue?.();
      if (this.sessionQueues.get(sessionId) === queue) {
        this.sessionQueues.delete(sessionId);
      }
    }
  }

  private async updateJourneyState(event: NormalizedEvent): Promise<JourneySessionState> {
    const current = await this.storage.getJourneyState(event.sessionId);
    const mergedContext = mergeContext(current.lastDerivedContext, event.derivedContext);
    const next: JourneySessionState = {
      ...current,
      selectedCoverage: [...current.selectedCoverage],
      selectedAddOns: [...current.selectedAddOns],
      fieldChangeCounts: { ...current.fieldChangeCounts },
      lastDerivedContext: mergedContext,
      lastShownPlayByStage: { ...current.lastShownPlayByStage },
    };

    next.stage = event.journeyStage ?? next.stage;

    if (mergedContext.selectedCoverage?.length) {
      next.selectedCoverage = [...mergedContext.selectedCoverage];
    }
    if (mergedContext.insuredPerson) {
      next.insuredPerson = mergedContext.insuredPerson;
    }
    if (mergedContext.selectedTariff) {
      next.selectedTariff = mergedContext.selectedTariff;
    }
    if (mergedContext.selectedAddOns?.length) {
      next.selectedAddOns = [...mergedContext.selectedAddOns];
    }
    if (mergedContext.visiblePriceMonthly !== undefined) {
      if (next.baselinePriceMonthly === null && mergedContext.visiblePriceMonthly !== null) {
        next.baselinePriceMonthly = mergedContext.visiblePriceMonthly;
      }
      next.latestPriceMonthly = mergedContext.visiblePriceMonthly ?? next.latestPriceMonthly;
    }

    if (event.type !== "inactivity") {
      next.lastInteractionAt = event.ts;
    }

    if ((event.type === "input" || event.type === "change") && event.elementKey) {
      next.fieldChangeCounts[event.elementKey] = (next.fieldChangeCounts[event.elementKey] ?? 0) + 1;
    }

    next.lastAction = {
      elementKey: event.elementKey,
      type: event.type,
      value: event.value,
    };
    next.routeFamily = classifyRouteFamily(next);

    await this.storage.setJourneyState(event.sessionId, next);
    return next;
  }

  private buildSnapshot(
    event: NormalizedEvent,
    state: JourneySessionState,
    signals: JourneySignal[],
    url: string,
  ): JourneySnapshot {
    const stage = state.stage ?? event.journeyStage;
    if (!stage) {
      throw new Error("Cannot build runtime snapshot without a stage");
    }

    const visiblePriceMonthly = state.latestPriceMonthly ?? event.derivedContext.visiblePriceMonthly ?? null;
    const baseline = state.baselinePriceMonthly;
    const priceDeltaMonthly =
      visiblePriceMonthly !== null && baseline !== null
        ? Number((visiblePriceMonthly - baseline).toFixed(2))
        : event.derivedContext.priceDeltaMonthly ?? null;

    return {
      sessionId: event.sessionId,
      url,
      routeFamily: state.routeFamily,
      stage,
      selectedCoverage: [...state.selectedCoverage],
      insuredPerson: state.insuredPerson,
      selectedTariff: state.selectedTariff,
      selectedAddOns: [...state.selectedAddOns],
      visiblePriceMonthly,
      visiblePriceDaily:
        visiblePriceMonthly !== null ? Number((visiblePriceMonthly / 30).toFixed(2)) : null,
      priceDeltaMonthly,
      fieldCompletion: state.lastDerivedContext.fieldCompletion ?? null,
      validationErrorCount: state.lastDerivedContext.validationErrorCount ?? 0,
      signals,
      lastAction: state.lastAction,
      eligibleGoals:
        state.routeFamily === "online_doctor"
          ? ["converted_online"]
          : ["submitted_advisor_lead"],
    };
  }

  private async filterDecisionByCooldown(
    sessionId: string,
    stage: JourneySnapshot["stage"],
    decision: JourneyDecision | null,
    timestamp: number,
  ): Promise<JourneyDecision | null> {
    if (!decision) {
      return null;
    }

    const state = await this.storage.getJourneyState(sessionId);
    const lastShown = state.lastShownPlayByStage[stage];
    if (lastShown && lastShown.playId === decision.playId && timestamp - lastShown.shownAt < decision.cooldownMs) {
      log.debug("Suppressing decision by cooldown", {
        playId: decision.playId,
        stage,
      });
      return null;
    }

    await this.storage.markDecisionShown(sessionId, stage, decision, timestamp);
    return decision;
  }
}

function shouldDecide(
  event: NormalizedEvent,
  signals: JourneySignal[],
  snapshot: JourneySnapshot,
): boolean {
  if (event.type === "step_enter" || event.type === "price_changed") {
    return true;
  }
  if (snapshot.routeFamily !== "online_doctor" && snapshot.stage === "advisor_contact") {
    return true;
  }
  return signals.length > 0;
}

function mergeContext(base: JourneySessionState["lastDerivedContext"], next: JourneySessionState["lastDerivedContext"]) {
  const merged = { ...base, ...next };
  if (next.selectedAddOns) {
    merged.selectedAddOns = [...next.selectedAddOns];
  }
  if (next.selectedCoverage) {
    merged.selectedCoverage = [...next.selectedCoverage];
  }
  return merged;
}

function classifyRouteFamily(state: JourneySessionState): JourneyRouteFamily {
  if (
    state.selectedCoverage.includes("hospital") ||
    (state.selectedCoverage.includes("hospital") && state.selectedCoverage.includes("doctor_visits"))
  ) {
    return "advisor_coverage";
  }
  if (state.insuredPerson === "other_persons") {
    return "advisor_other_persons";
  }
  if (state.selectedTariff && ["opt. plus", "opt_plus", "premium"].includes(state.selectedTariff)) {
    return "advisor_tariff";
  }
  return "online_doctor";
}
