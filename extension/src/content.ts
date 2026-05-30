import type {
  CoachAction,
  DerivedContext,
  RuntimeChatResponse,
  NormalizedEvent,
  RuntimeEventResponse,
  RuntimeInitResponse,
} from "@/shared/contracts";
import { createId } from "@/shared/runtime";
import { DataCollector, type InteractionEvent } from "@/content/data-collector";
import { DomInjector } from "@/content/dom-injector";
import { PageObserver, type ObserverEvent } from "@/content/page-observer";

const EMPTY_EVENT_RESPONSE: RuntimeEventResponse = { actions: [], signals: [] };
let extensionContextInvalidated = false;

async function bootstrap(): Promise<void> {
  if (!document.body) {
    return;
  }

  const init = await sendRuntimeMessage<RuntimeInitResponse>({
    type: "uniqa:init",
    url: window.location.href,
  });
  if (!init) {
    console.warn("[UNIQA Coach] Background init failed; content script disabled for this page.");
    return;
  }

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
    return (
      (await sendRuntimeMessage<RuntimeEventResponse>({
        event,
        type: "uniqa:event",
      })) ?? EMPTY_EVENT_RESPONSE
    );
  }

  async function renderActions(
    actions: CoachAction[] | undefined,
    context: DerivedContext,
  ): Promise<void> {
    if (!actions?.length) {
      return;
    }

    const displayed = injector.render(actions, observer.getCurrentStep());
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
      if (event.type === "step_enter") {
        injector.clear();
      }

      const runtimeEvent = buildObserverEvent(init.sessionId, event);
      const response = await emit(runtimeEvent);
      await renderActions(response.actions, event.derivedContext);
    })();
  });

  const collector = new DataCollector(
    () => observer.getCurrentStep(),
    () => observer.getCurrentContext(),
    (interaction: InteractionEvent) => {
      void (async () => {
        const response = await emit(buildInteractionEvent(init.sessionId, observer, interaction));
        await renderActions(response.actions, interaction.derivedContext);
      })();
    },
  );

  observer.start();
  collector.start();
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
      console.warn("[UNIQA Coach] Extension was reloaded. Refresh this page to reconnect the coach.");
      return null;
    }
    console.warn("[UNIQA Coach] Runtime message failed.", error);
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
