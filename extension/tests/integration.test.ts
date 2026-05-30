import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { afterEach, describe, expect, test } from "vitest";
import { CoachClient } from "@/background/coach-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { MemoryStorageAdapter, UniqaStorage } from "@/background/storage";
import { DomInjector } from "@/content/dom-injector";
import type { CoachApiStatus, NormalizedEvent } from "@/shared/contracts";
import { deriveContextFromDocument } from "@/shared/extractors";
import { resolvePageStep } from "@/shared/page-map";

describe("event orchestration", () => {
  afterEach(() => {
    if (originalFetch) {
      Object.defineProperty(globalThis, "fetch", {
        configurable: true,
        value: originalFetch,
        writable: true,
      });
    }
  });

  test("renders a remote coach response for a tariff click", async () => {
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
      new CoachClient("http://127.0.0.1:8787/api/v1/coach/evaluate", async (_url, init) => {
        const parsedRequest = JSON.parse(String(init?.body ?? "{}")) as {
          detectedSignals?: string[];
        };
        const shouldReturnAction = parsedRequest.detectedSignals?.includes("tariff_click_oos");

        return {
          json: async () => ({
            actions: shouldReturnAction
              ? [
                  {
                    body: "Opt. Plus und Premium brauchen Beratung. Fuer einen direkten Online-Abschluss bleiben Start und Optimal die passenden Optionen.",
                    cooldownMs: 90_000,
                    ctaLabel: "Optimal pruefen",
                    dismissible: true,
                    id: "tariff_route_explainer",
                    kind: "tariff_route_explainer",
                    placement: "near-primary-cta",
                    title: "Opt. Plus und Premium brauchen Beratung",
                  },
                ]
              : [],
            policyVersion: 7,
            source: "remote",
          }),
          ok: true,
        } as Response;
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
    expect(response.apiStatus.state).toBe("connected");

    const injector = new DomInjector(() => undefined);
    injector.updateStatus(makeConnectedStatus());
    injector.render(response.actions, resolved);

    const shadow = doc.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
    expect(shadow?.textContent).toContain("Opt. Plus und Premium brauchen Beratung");
    expect(shadow?.textContent).toContain("Connected to coach API");
  });

  test("returns no actions when the remote coach request fails", async () => {
    const client = new CoachClient("http://127.0.0.1:8787/api/v1/coach/evaluate", async () => {
      throw new Error("offline");
    });

    const response = await client.evaluate(makeEvent("click", "selectionbutton_2", null, {}));
    expect(response.response.actions).toHaveLength(0);
    expect(response.response.policyVersion).toBeNull();
    expect(response.response.source).toBe("remote_error");
    expect(response.apiStatus.state).toBe("error");
  });

  test("uses a bound default fetch in worker-like environments", async () => {
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      value: function (
        this: typeof globalThis,
        _input: RequestInfo | URL,
        _init?: RequestInit,
      ): Promise<Response> {
        if (this !== globalThis) {
          throw new TypeError("Illegal invocation");
        }

        return Promise.resolve({
          json: async () => ({
            actions: [],
            policyVersion: 11,
            source: "remote",
          }),
          ok: true,
        } as Response);
      },
      writable: true,
    });

    const client = new CoachClient();
    const response = await client.evaluate(makeEvent("step_enter", null, null, {}));

    expect(response.apiStatus.state).toBe("connected");
    expect(response.response.policyVersion).toBe(11);
  });
});

const originalFetch = globalThis.fetch;

function makeConnectedStatus(): CoachApiStatus {
  return {
    endpoint: "http://127.0.0.1:8787/api/v1/coach/evaluate",
    lastUpdatedAt: Date.now(),
    message: "Connected to coach API (policy v7)",
    policyVersion: 7,
    state: "connected",
  };
}

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
