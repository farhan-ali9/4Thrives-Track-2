import type {
  CoachAction,
  DerivedContext,
  NormalizedEvent,
  RuntimeChatResponse,
  RuntimeEventResponse,
  RuntimeInitResponse,
} from "@/shared/contracts";
import { createId } from "@/shared/runtime";
import { createLogger } from "@/shared/logger";
import { DataCollector, type InteractionEvent } from "@/content/data-collector";
import { DomInjector } from "@/content/dom-injector";
import { PageObserver, type ObserverEvent } from "@/content/page-observer";

const log = createLogger("content");

const EMPTY_EVENT_RESPONSE: RuntimeEventResponse = {
  actions: [],
  apiStatus: {
    endpoint: "chrome.runtime",
    lastUpdatedAt: Date.now(),
    message: "No runtime response",
    policyVersion: null,
    state: "error",
  },
  signals: [],
};
let extensionContextInvalidated = false;

async function bootstrap(): Promise<void> {
  log.info("Bootstrapping content script", { url: window.location.href });
  if (!document.body) {
    log.warn("document.body missing at bootstrap; content script disabled for this page.");
    return;
  }

  const preferredSessionId =
    (window as Window & { __UNIQA_PREFERRED_SESSION_ID?: unknown }).__UNIQA_PREFERRED_SESSION_ID;
  const init = await sendRuntimeMessage<RuntimeInitResponse>({
    preferredSessionId:
      typeof preferredSessionId === "string" && preferredSessionId.trim().length > 0
        ? preferredSessionId
        : undefined,
    type: "uniqa:init",
    url: window.location.href,
  });
  if (!init) {
    log.warn("Background init failed; content script disabled for this page.");
    return;
  }
  log.info("Background init succeeded", {
    chatModel: init.chatModel,
    hasChatApiKey: init.hasChatApiKey,
    sessionId: init.sessionId,
  });

  const injector = new DomInjector(
    (interaction) => {
      const observerStep = observer.getCurrentStep();
      const context = observer.getCurrentContext();
      void emit({
        coachStepId: observerStep?.coachStepId ?? null,
        derivedContext: context,
        dwellMs: null,
        elementKey: interaction.action.id,
        id: createId("evt"),
        pageStepId: observerStep?.pageStepId ?? null,
        sessionId: init.sessionId,
        ts: Date.now(),
        type: interaction.type,
        value: {
          actionKind: interaction.action.kind,
          cta: interaction.cta,
          ctaResult: interaction.result,
          placement: interaction.action.placement,
        },
      });
    },
    async (request) => {
      const step = observer.getCurrentStep();
      const response = await sendRuntimeMessage<RuntimeChatResponse>({
        request: {
          apiKey: request.apiKey,
          context: observer.getCurrentContext(),
          messages: request.messages,
          model: request.model,
          pageStepId: step?.pageStepId ?? null,
          sessionId: init.sessionId,
        },
        type: "uniqa:chat",
      });
      return (
        response?.message ?? {
          role: "assistant",
          content: "The chat is disconnected. Reload the calculator page and try again.",
        }
      );
    },
    init.hasChatApiKey,
    init.chatModel,
    init.chatModelOptions,
  );

  async function emit(event: NormalizedEvent): Promise<RuntimeEventResponse> {
    const response = await sendRuntimeMessage<RuntimeEventResponse>({
      event,
      type: "uniqa:event",
    });
    if (!response) {
      log.warn("No runtime response for event; using empty fallback", {
        pageStepId: event.pageStepId,
        type: event.type,
      });
      return EMPTY_EVENT_RESPONSE;
    }
    log.debug("Event response", {
      actions: response.actions.length,
      apiState: response.apiStatus.state,
      pageStepId: event.pageStepId,
      signals: response.signals,
      type: event.type,
    });
    return response;
  }

  async function renderActions(
    actions: CoachAction[] | undefined,
    context: DerivedContext,
  ): Promise<void> {
    if (!actions?.length) {
      log.debug("renderActions called with no actions; nothing to render");
      return;
    }

    const displayed = injector.render(actions, observer.getCurrentStep());
    log.info("Rendered coach actions", {
      displayed: displayed.length,
      ids: displayed.map((action) => action.id),
      received: actions.length,
      step: observer.getCurrentStep()?.pageStepId ?? null,
    });
    if (displayed.length) {
      injector.addLogMessage(
        `Rendered ${displayed.length} coach action${displayed.length === 1 ? "" : "s"}`,
      );
    }
    for (const action of displayed) {
      await emit({
        coachStepId: observer.getCurrentStep()?.coachStepId ?? null,
        derivedContext: context,
        dwellMs: null,
        elementKey: action.id,
        id: createId("evt"),
        pageStepId: observer.getCurrentStep()?.pageStepId ?? null,
        sessionId: init.sessionId,
        ts: Date.now(),
        type: "coach_impression",
        value: {
          actionKind: action.kind,
          placement: action.placement,
        },
      });
    }
  }

  const observer = new PageObserver((event: ObserverEvent) => {
    void (async () => {
      log.debug("Observer event", {
        dwellMs: event.dwellMs,
        step: event.step?.pageStepId ?? null,
        type: event.type,
      });
      if (event.type === "step_enter") {
        injector.clear();
      }

      const runtimeEvent = buildObserverEvent(init.sessionId, event);
      const response = await emit(runtimeEvent);
      injector.updateStatus(response.apiStatus);
      if (response.actions.length) {
        await renderActions(response.actions, event.derivedContext);
      } else if (response.apiStatus.state === "connected") {
        log.debug("API reachable, no coach action for this event", {
          step: event.step?.pageStepId ?? null,
          type: event.type,
        });
        injector.addLogMessage("API reachable, no coach action for this event");
      } else {
        log.warn("Coach API not connected for event", {
          apiState: response.apiStatus.state,
          message: response.apiStatus.message,
          type: event.type,
        });
      }
    })();
  });

  const collector = new DataCollector(
    () => observer.getCurrentStep(),
    () => observer.getCurrentContext(),
    (interaction: InteractionEvent) => {
      void (async () => {
        log.debug("Interaction event", {
          elementKey: interaction.elementKey,
          step: observer.getCurrentStep()?.pageStepId ?? null,
          type: interaction.type,
        });
        const response = await emit(buildInteractionEvent(init.sessionId, observer, interaction));
        injector.updateStatus(response.apiStatus);
        if (response.actions.length) {
          await renderActions(response.actions, interaction.derivedContext);
        } else if (response.apiStatus.state === "connected") {
          log.debug("API reachable, no coach action for this interaction", {
            elementKey: interaction.elementKey,
            type: interaction.type,
          });
          injector.addLogMessage("API reachable, no coach action for this interaction");
        } else {
          log.warn("Coach API not connected for interaction", {
            apiState: response.apiStatus.state,
            message: response.apiStatus.message,
            type: interaction.type,
          });
        }
      })();
    },
  );

  observer.start();
  collector.start();
  log.info("Observer and collector started");
}

async function sendRuntimeMessage<T>(message: Record<string, unknown>): Promise<T | null> {
  if (extensionContextInvalidated) {
    return null;
  }

  try {
    return (await chrome.runtime.sendMessage(message)) as T;
  } catch (error) {
    if (isExtensionContextInvalidated(error)) {
      extensionContextInvalidated = true;
      log.warn("Extension was reloaded. Refresh this page to reconnect the coach.");
      return null;
    }
    log.warn("Runtime message failed", {
      error: error instanceof Error ? error.message : String(error),
      type: message.type,
    });
    return null;
  }
}

function isExtensionContextInvalidated(error: unknown): boolean {
  return error instanceof Error && error.message.includes("Extension context invalidated");
}

function buildObserverEvent(sessionId: string, event: ObserverEvent): NormalizedEvent {
  return {
    coachStepId: event.step?.coachStepId ?? null,
    derivedContext: event.derivedContext,
    dwellMs: event.dwellMs,
    elementKey: null,
    id: createId("evt"),
    pageStepId: event.step?.pageStepId ?? null,
    sessionId,
    ts: Date.now(),
    type: event.type,
    value: null,
  };
}

function buildInteractionEvent(
  sessionId: string,
  observer: PageObserver,
  event: InteractionEvent,
): NormalizedEvent {
  const step = observer.getCurrentStep();
  return {
    coachStepId: step?.coachStepId ?? null,
    derivedContext: event.derivedContext,
    dwellMs: null,
    elementKey: event.elementKey,
    id: createId("evt"),
    pageStepId: step?.pageStepId ?? null,
    sessionId,
    ts: Date.now(),
    type: event.type,
    value: event.value,
  };
}

void bootstrap();
