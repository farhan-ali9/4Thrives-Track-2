import { afterEach, describe, expect, test } from "vitest";
import { DomInjector } from "@/content/dom-injector";
import type { JourneyDecision, ResolvedStep } from "@/shared/contracts";

describe("DomInjector", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    document.getElementById("uniqa-conversion-coach-root")?.remove();
  });

  test("keeps runtime UI in the popup and does not inject inline page elements", () => {
    document.body.innerHTML = `
      <div id="step-anchor">Voraussichtliche Praemie</div>
      <button data-cy="selectionButton_0" aria-label="Wählen Start">Wählen</button>
      <button data-cy="selectionButton_1" aria-label="Wählen Optimal">Wählen</button>
      <button data-cy="selectionButton_2" aria-label="Wählen Opt. Plus">Wählen</button>
      <button data-cy="selectionButton_3" aria-label="Wählen Premium">Wählen</button>
      <button data-cy="nextStepButton">Weiter</button>
    `;

    const injector = new DomInjector(() => undefined, async () => ({
      role: "assistant",
      content: "ok",
    }), true, "test-model", ["test-model"]);

    injector.render(makeDecision(), makeStep());
    injector.render(makeDecision(), makeStep());

    expect(document.querySelectorAll("[data-uniqa-runtime-owned='true']").length).toBe(0);
    expect(document.body.textContent).not.toContain("Online abschliessbar");
    expect(document.body.textContent).not.toContain("Beratung erforderlich");
    expect(
      document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot?.textContent ?? "",
    ).toContain("Preis eingeordnet");
  });

  test("publishes popup lifecycle state for the browser runner", () => {
    const injector = new DomInjector(() => undefined, async () => ({
      role: "assistant",
      content: "ok",
    }), true, "test-model", ["test-model"]);

    injector.clear("s3_quote_basics");
    injector.beginDecisionCycle("s4_initial_price");
    injector.render(makeDecision(), makeStep());

    const state = (window as Window & {
      __UNIQA_COACH_STATE__?: {
        cardCount: number;
        currentStepId: string | null;
        decisionState: string;
        playId: string | null;
        requestFinishedAt: number;
        requestStartedAt: number;
      };
    }).__UNIQA_COACH_STATE__;

    expect(state?.currentStepId).toBe("s4_initial_price");
    expect(state?.decisionState).toBe("rendered");
    expect(state?.playId).toBe("price_reframe");
    expect(state?.cardCount).toBe(1);
    expect((state?.requestFinishedAt ?? 0) >= (state?.requestStartedAt ?? 0)).toBe(true);
  });
});

function makeDecision(): JourneyDecision {
  return {
    decisionId: "dec_1",
    goal: "converted_online",
    playId: "price_reframe",
    priority: 80,
    cooldownMs: 30_000,
    chatPrompt: "Warum ist der Tarif so hoch?",
    cards: [
      {
        id: "card_1",
        placement: "near-primary-cta",
        tone: "value",
        title: "Preis eingeordnet",
        body: "EUR 73,02 pro Monat und rund EUR 2,43 pro Tag.",
        cta: null,
        dismissible: true,
      },
    ],
    domMutations: [
      {
        id: "mutation_1",
        kind: "price_reframe",
        placement: "near-primary-cta",
        title: "Monatlich und taeglich",
        body: "EUR 73,02 pro Monat und rund EUR 2,43 pro Tag.",
        selector: null,
        label: null,
        prompt: null,
        target: null,
      },
      {
        id: "mutation_2",
        kind: "tariff_badges",
        placement: "inline-top-of-step",
        title: null,
        body: null,
        selector: null,
        label: null,
        prompt: null,
        target: null,
      },
    ],
  };
}

function makeStep(): ResolvedStep {
  return {
    pageStepId: "s4_initial_price",
    journeyStage: "tariff_choice",
    injectionAnchor: "near-primary-cta",
    config: {
      pageStepId: "s4_initial_price",
      journeyStage: "tariff_choice",
      verified: true,
      enabled: true,
      match: {},
      selectors: {
        stepAnchor: ["#step-anchor"],
        primaryCta: ["[data-cy='nextStepButton']"],
        backButton: [],
      },
      extractors: [],
      injectionAnchor: "near-primary-cta",
    },
  };
}
