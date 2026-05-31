import type { DerivedContext, ResolvedStep } from "@/shared/contracts";
import { deriveContextFromDocument } from "@/shared/extractors";
import { resolvePageStep } from "@/shared/page-map";

export interface ObserverEvent {
  type: "step_enter" | "step_leave" | "step_resolved" | "price_changed";
  step: ResolvedStep | null;
  derivedContext: DerivedContext;
  dwellMs: number | null;
}

export class PageObserver {
  private readonly mutationObserver: MutationObserver;
  private currentStep: ResolvedStep | null = null;
  private currentContext: DerivedContext = {};
  private enteredAt: number | null = null;
  private scheduled = false;
  private lastVisiblePriceMonthly: number | null = null;
  private cleanupHistoryHook: (() => void) | null = null;

  constructor(private readonly onEvent: (event: ObserverEvent) => void) {
    this.mutationObserver = new MutationObserver(() => {
      this.scheduleSync();
    });
  }

  start(): void {
    this.cleanupHistoryHook = patchHistory(() => {
      this.scheduleSync();
    });

    window.addEventListener("popstate", this.handleNavigation);
    window.addEventListener("beforeunload", this.handleBeforeUnload);
    document.addEventListener("visibilitychange", this.handleVisibilityChange);
    this.mutationObserver.observe(document.body, {
      attributes: true,
      childList: true,
      subtree: true,
      characterData: true,
    });

    this.sync();
  }

  stop(): void {
    this.mutationObserver.disconnect();
    window.removeEventListener("popstate", this.handleNavigation);
    window.removeEventListener("beforeunload", this.handleBeforeUnload);
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
    this.cleanupHistoryHook?.();
  }

  getCurrentStep(): ResolvedStep | null {
    return this.currentStep;
  }

  getCurrentContext(): DerivedContext {
    return this.currentContext;
  }

  private readonly handleNavigation = (): void => {
    this.scheduleSync();
  };

  private readonly handleBeforeUnload = (): void => {
    if (!this.currentStep || this.enteredAt === null) {
      return;
    }

    this.onEvent({
      derivedContext: this.currentContext,
      dwellMs: Date.now() - this.enteredAt,
      step: this.currentStep,
      type: "step_leave",
    });
  };

  private readonly handleVisibilityChange = (): void => {
    if (document.visibilityState === "hidden") {
      this.handleBeforeUnload();
      return;
    }

    this.scheduleSync();
  };

  private scheduleSync(): void {
    if (this.scheduled) {
      return;
    }

    this.scheduled = true;
    window.setTimeout(() => {
      this.scheduled = false;
      this.sync();
    }, 75);
  }

  private sync(): void {
    const resolved = resolvePageStep(document);
    const nextContext = deriveContextFromDocument(document, resolved, this.currentContext);
    const stepChanged = resolved?.pageStepId !== this.currentStep?.pageStepId;

    if (stepChanged && this.currentStep && this.enteredAt !== null) {
      this.onEvent({
        derivedContext: this.currentContext,
        dwellMs: Date.now() - this.enteredAt,
        step: this.currentStep,
        type: "step_leave",
      });
    }

    if (stepChanged) {
      this.currentStep = resolved;
      this.currentContext = nextContext;
      this.enteredAt = resolved ? Date.now() : null;
      this.lastVisiblePriceMonthly = nextContext.visiblePriceMonthly ?? null;

      if (resolved) {
        this.onEvent({
          derivedContext: nextContext,
          dwellMs: null,
          step: resolved,
          type: "step_enter",
        });
        this.onEvent({
          derivedContext: nextContext,
          dwellMs: null,
          step: resolved,
          type: "step_resolved",
        });
      }
      return;
    }

    this.currentContext = nextContext;
    if (resolved) {
      const nextPrice = nextContext.visiblePriceMonthly ?? null;
      if (nextPrice !== null && this.lastVisiblePriceMonthly !== nextPrice) {
        this.lastVisiblePriceMonthly = nextPrice;
        this.onEvent({
          derivedContext: nextContext,
          dwellMs: null,
          step: resolved,
          type: "price_changed",
        });
      }
    }
  }
}

function patchHistory(callback: () => void): () => void {
  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;

  history.pushState = function patchedPushState(...args) {
    const result = originalPushState.apply(this, args);
    callback();
    return result;
  };

  history.replaceState = function patchedReplaceState(...args) {
    const result = originalReplaceState.apply(this, args);
    callback();
    return result;
  };

  return () => {
    history.pushState = originalPushState;
    history.replaceState = originalReplaceState;
  };
}
