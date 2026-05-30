import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { describe, expect, test } from "vitest";
import { CoachClient } from "@/background/coach-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { MemoryStorageAdapter, UniqaStorage } from "@/background/storage";
import { DomInjector } from "@/content/dom-injector";
import type { NormalizedEvent } from "@/shared/contracts";
import { deriveContextFromDocument } from "@/shared/extractors";
import { resolvePageStep } from "@/shared/page-map";

describe("event orchestration", () => {
  test("routes a tariff click through the worker and renders a coach card", async () => {
    const doc = loadFixture("s4_initial_price.html");
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: doc,
    });
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: doc.defaultView,
    });

    const resolved = resolvePageStep(doc);
    expect(resolved?.pageStepId).toBe("s4_initial_price");
    const derivedContext = deriveContextFromDocument(doc, resolved, {});

    const storage = new UniqaStorage(new MemoryStorageAdapter());
    await storage.ensureSession(1, "https://www.uniqa.at/rechner/krankenversicherung/", "session_1");
    const orchestrator = new UniqaEventOrchestrator(
      storage,
      new CoachClient("http://127.0.0.1:1/evaluate", async () => {
        throw new Error("offline");
      }),
    );

    await orchestrator.handleEvent(makeEvent("step_enter", null, null, derivedContext));
    const response = await orchestrator.handleEvent(
      makeEvent("click", "selectionbutton_2", {
        intent: "out_of_scope_tariff",
        option: "opt_plus",
      }, derivedContext),
    );

    expect(response.actions[0]?.id).toBe("tariff_route_explainer");

    const injector = new DomInjector(() => undefined);
    injector.render(response.actions, resolved);

    const shadow = doc.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
    expect(shadow?.textContent).toContain("Opt. Plus und Premium brauchen Beratung");
  });
});

function makeEvent(
  type: NormalizedEvent["type"],
  elementKey: string | null,
  value: NormalizedEvent["value"],
  derivedContext: NormalizedEvent["derivedContext"],
): NormalizedEvent {
  return {
    coachStepId: "s4_initial_price",
    derivedContext,
    dwellMs: null,
    elementKey,
    id: `evt_${type}`,
    pageStepId: "s4_initial_price",
    sessionId: "session_1",
    ts: Date.now(),
    type,
    value,
  };
}

function loadFixture(filename: string): Document {
  const html = readFileSync(resolve(process.cwd(), "tests/fixtures", filename), "utf8");
  return new JSDOM(html).window.document;
}
