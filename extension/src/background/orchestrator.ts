import type {
  CoachAction,
  CoachApiStatus,
  CoachRequest,
  CoachRuntimeState,
  DerivedContext,
  NormalizedEvent,
  RuntimeEventResponse,
  SignalKind,
  StepRuntimeState,
} from "@/shared/contracts";
import { CoachClient } from "./coach-client";
import { deriveSignals } from "./signal-detector";
import { UniqaStorage } from "./storage";

const DEFAULT_API_STATUS: CoachApiStatus = {
  endpoint:
    (import.meta.env?.VITE_COACH_API_ORIGIN ?? "http://127.0.0.1:8787").replace(/\/+$/, "") +
    "/api/v2/events",
  lastUpdatedAt: 0,
  message: "Waiting for first coach API call",
  policyVersion: null,
  state: "starting",
};

export class UniqaEventOrchestrator {
  private readonly sessionQueues = new Map<string, Promise<void>>();

  constructor(
    private readonly storage: UniqaStorage,
    private readonly coachClient: CoachClient,
  ) {}

  async handleEvent(event: NormalizedEvent): Promise<RuntimeEventResponse> {
    return this.runSequentially(event.sessionId, async () => {
      await this.storage.appendEvent(event.sessionId, event);
      const recentEvents = await this.storage.getRecentEvents(event.sessionId);
      const updatedStepState = await this.updateStepState(event);
      const signals = deriveSignals(event, updatedStepState, recentEvents);

      if (!shouldEvaluateCoach(event, signals)) {
        return { actions: [], apiStatus: DEFAULT_API_STATUS, signals };
      }

      const coachRequest = this.buildCoachRequest(event, recentEvents, updatedStepState, signals);
      const evaluation = await this.coachClient.evaluate({
        event,
        fallbackRequest: coachRequest,
        signals,
      });
      const actions = await this.filterActionsByCooldown(
        event.sessionId,
        event.ts,
        evaluation.response.actions,
      );

      return {
        actions,
        apiStatus: evaluation.apiStatus,
        signals,
      };
    });
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

  private async updateStepState(event: NormalizedEvent): Promise<StepRuntimeState> {
    const current = await this.storage.getStepState(event.sessionId);
    const next: StepRuntimeState = {
      ...current,
      fieldChangeCounts: { ...current.fieldChangeCounts },
      lastDerivedContext: { ...current.lastDerivedContext },
      selectedAddOns: [...current.selectedAddOns],
    };

    if (event.type === "step_enter") {
      next.currentStepId = event.pageStepId;
      next.currentCoachStepId = event.coachStepId;
      next.fieldChangeCounts = {};
      next.stepEnteredAt = event.ts;
    }

    if (event.type !== "inactivity") {
      next.lastActivityAt = event.ts;
    }

    if ((event.type === "input" || event.type === "change") && event.elementKey) {
      next.fieldChangeCounts[event.elementKey] = (next.fieldChangeCounts[event.elementKey] ?? 0) + 1;
    }

    const mergedContext = mergeContext(next.lastDerivedContext, event.derivedContext);
    if (mergedContext.visiblePrice !== undefined) {
      if (next.initialVisiblePrice === null && mergedContext.visiblePrice !== null) {
        next.initialVisiblePrice = mergedContext.visiblePrice;
      }
      next.lastVisiblePrice = mergedContext.visiblePrice ?? next.lastVisiblePrice;
    }

    if (mergedContext.selectedTariff) {
      next.selectedTariff = mergedContext.selectedTariff;
    }

    if (typeof event.value === "object" && event.value !== null && "option" in event.value) {
      const option = event.value.option;
      if (typeof option === "string" && event.pageStepId === "s4_initial_price") {
        next.selectedTariff = option;
      }
    }

    if (mergedContext.selectedAddOns?.length) {
      next.selectedAddOns = [...mergedContext.selectedAddOns];
    }

    next.lastDerivedContext = mergedContext;
    await this.storage.setStepState(event.sessionId, next);
    return next;
  }

  private buildCoachRequest(
    event: NormalizedEvent,
    recentEvents: NormalizedEvent[],
    state: StepRuntimeState,
    signals: SignalKind[],
  ): CoachRequest {
    const visiblePrice = state.lastVisiblePrice ?? event.derivedContext.visiblePrice ?? null;
    const priceDelta =
      visiblePrice !== null && state.initialVisiblePrice !== null
        ? Number((visiblePrice - state.initialVisiblePrice).toFixed(2))
        : event.derivedContext.priceDelta ?? null;

    const derivedContext: DerivedContext = {
      ...state.lastDerivedContext,
      ...event.derivedContext,
      lastInteractionMs:
        state.lastActivityAt !== null ? Math.max(0, event.ts - state.lastActivityAt) : undefined,
      priceDelta,
      selectedAddOns: state.selectedAddOns,
      selectedTariff: state.selectedTariff,
      visiblePrice,
    };

    return {
      coachStepId: event.coachStepId,
      currentOffer: {
        priceDelta,
        selectedTariff: state.selectedTariff,
        visiblePrice,
      },
      derivedContext,
      detectedSignals: signals,
      pageStepId: event.pageStepId,
      recentEvents,
      sessionId: event.sessionId,
    };
  }

  private async filterActionsByCooldown(
    sessionId: string,
    timestamp: number,
    actions: CoachAction[],
  ): Promise<CoachAction[]> {
    const coachState = await this.storage.getCoachState(sessionId);
    const nextCoachState: CoachRuntimeState = {
      shownActionTimestamps: { ...coachState.shownActionTimestamps },
    };

    const filtered = actions.filter((action) => {
      const lastShown = coachState.shownActionTimestamps[action.id];
      if (lastShown && timestamp - lastShown < action.cooldownMs) {
        return false;
      }
      nextCoachState.shownActionTimestamps[action.id] = timestamp;
      return true;
    });

    await this.storage.setCoachState(sessionId, nextCoachState);
    return filtered;
  }
}

function mergeContext(base: DerivedContext, next: DerivedContext): DerivedContext {
  const merged: DerivedContext = { ...base, ...next };
  if (next.selectedAddOns) {
    merged.selectedAddOns = [...next.selectedAddOns];
  }
  return merged;
}

function shouldEvaluateCoach(event: NormalizedEvent, signals: SignalKind[]): boolean {
  if (event.type === "step_enter" || event.type === "price_changed") {
    return true;
  }
  return signals.length > 0;
}
