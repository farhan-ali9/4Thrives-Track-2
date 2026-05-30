import type {
  CoachAction,
  DerivedContext,
  NormalizedEvent,
  RuntimeEventResponse,
  RuntimeInitResponse,
} from "@/shared/contracts";
import { createId } from "@/shared/runtime";
import { DataCollector, type InteractionEvent } from "@/content/data-collector";
import { DomInjector } from "@/content/dom-injector";
import { PageObserver, type ObserverEvent } from "@/content/page-observer";

async function bootstrap(): Promise<void> {
  if (!document.body) {
    return;
  }

  const init = (await chrome.runtime.sendMessage({
    type: "uniqa:init",
    url: window.location.href,
  })) as RuntimeInitResponse;

  const injector = new DomInjector((interaction) => {
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
  });

  async function emit(event: NormalizedEvent): Promise<RuntimeEventResponse> {
    try {
      return (await chrome.runtime.sendMessage({
        event,
        type: "uniqa:event",
      })) as RuntimeEventResponse;
    } catch (error) {
      injector.updateStatus({
        endpoint: "chrome.runtime",
        lastUpdatedAt: Date.now(),
        message: error instanceof Error ? error.message : "Unknown extension runtime error",
        policyVersion: null,
        state: "error",
      });
      throw error;
    }
  }

  async function renderActions(actions: CoachAction[], context: DerivedContext): Promise<void> {
    const displayed = injector.render(actions, observer.getCurrentStep());
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
      if (event.type === "step_enter") {
        injector.clear();
      }

      const runtimeEvent = buildObserverEvent(init.sessionId, event);
      const response = await emit(runtimeEvent);
      injector.updateStatus(response.apiStatus);
      if (response.actions.length) {
        await renderActions(response.actions, event.derivedContext);
      } else if (response.apiStatus.state === "connected") {
        injector.addLogMessage("API reachable, no coach action for this event");
      }
    })();
  });

  const collector = new DataCollector(
    () => observer.getCurrentStep(),
    () => observer.getCurrentContext(),
    (interaction: InteractionEvent) => {
      void (async () => {
        const response = await emit(buildInteractionEvent(init.sessionId, observer, interaction));
        injector.updateStatus(response.apiStatus);
        if (response.actions.length) {
          await renderActions(response.actions, interaction.derivedContext);
        } else if (response.apiStatus.state === "connected") {
          injector.addLogMessage("API reachable, no coach action for this interaction");
        }
      })();
    },
  );

  observer.start();
  collector.start();
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
