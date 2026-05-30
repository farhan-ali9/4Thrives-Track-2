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
      new CoachClient(
        "http://127.0.0.1:8787/api/v2/events",
        "http://127.0.0.1:8787/api/v1/coach/evaluate",
        async (_url, init) => {
          const parsedRequest = JSON.parse(String(init?.body ?? "{}")) as {
            derived_signals?: Record<string, boolean>;
            event_id?: string;
            event_type?: string;
            session_id?: string;
            step_id?: string | null;
          };
          expect(parsedRequest.event_id).toBeTruthy();
          expect(parsedRequest.session_id).toBe("session_1");
          expect(parsedRequest.step_id).toBe("s4_initial_price");
          const shouldReturnAction =
            parsedRequest.event_type === "click" &&
            Boolean(parsedRequest.derived_signals?.tariff_click_oos);

          return {
            json: async () => ({
              actions: shouldReturnAction
                ? [
                    {
                      body: "Opt. Plus und Premium brauchen Beratung. Fuer einen direkten Online-Abschluss bleiben Start und Optimal die passenden Optionen.",
                      cta: {
                        label: "Optimal pruefen",
                        prompt: "Help me compare Optimal with advisor-only tariffs.",
                        target: "optimal",
                        telemetryKey: "tariff_route_select_optimal",
                        type: "select_tariff",
                      },
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
              ok: true,
            }),
            ok: true,
            status: 200,
          } as Response;
        },
      ),
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
    expect(
      (doc.defaultView as Window & { __UNIQA_COACH_STATE__?: { actionable: boolean } })
        .__UNIQA_COACH_STATE__?.actionable,
    ).toBe(true);
  });

  test("returns no actions when the remote coach request fails", async () => {
    const client = new CoachClient(
      "http://127.0.0.1:8787/api/v2/events",
      "http://127.0.0.1:8787/api/v1/coach/evaluate",
      async () => {
        throw new Error("offline");
      },
    );

    const response = await client.evaluate(makeEvaluationInput(makeEvent("click", "selectionbutton_2", null, {})));
    expect(response.response.actions).toHaveLength(0);
    expect(response.response.policyVersion).toBeNull();
    expect(response.response.source).toBe("remote_error");
    expect(response.apiStatus.state).toBe("error");
  });

  test("uses a bound default fetch in worker-like environments for v2 events", async () => {
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
            ok: true,
          }),
          ok: true,
          status: 200,
        } as Response);
      },
      writable: true,
    });

    const client = new CoachClient();
    const response = await client.evaluate(
      makeEvaluationInput(makeEvent("step_enter", null, null, {})),
    );

    expect(response.apiStatus.state).toBe("connected");
    expect(response.apiStatus.endpoint).toContain("/api/v2/events");
    expect(response.response.policyVersion).toBeNull();
  });

  test("falls back to the legacy inference endpoint when v2 events is unavailable", async () => {
    let callCount = 0;
    const client = new CoachClient(
      "http://127.0.0.1:8787/api/v2/events",
      "http://127.0.0.1:8787/api/v1/coach/evaluate",
      async (url, init) => {
        callCount += 1;
        if (String(url).endsWith("/api/v2/events")) {
          return {
            json: async () => ({ error: "not_found" }),
            ok: false,
            status: 404,
          } as Response;
        }

        const parsedFallback = JSON.parse(String(init?.body ?? "{}")) as {
          detectedSignals?: string[];
        };
        expect(parsedFallback.detectedSignals).toContain("tariff_click_oos");
        return {
          json: async () => ({
            actions: [],
            policyVersion: 17,
            source: "remote",
          }),
          ok: true,
          status: 200,
        } as Response;
      },
    );

    const response = await client.evaluate(
      makeEvaluationInput(
        makeEvent("click", "selectionbutton_3", {
          intent: "out_of_scope_tariff",
          option: "premium",
        }, {}),
        ["tariff_click_oos"],
      ),
    );

    expect(callCount).toBe(2);
    expect(response.apiStatus.endpoint).toContain("/api/v1/coach/evaluate");
    expect(response.response.policyVersion).toBe(17);
  });

  test("serializes concurrent observer events for the same session", async () => {
    const storage = new UniqaStorage(new MemoryStorageAdapter());
    await storage.ensureSession(1, "https://www.uniqa.at/rechner/krankenversicherung/", "session_1");

    const orchestrator = new UniqaEventOrchestrator(
      storage,
      new CoachClient(
        "http://127.0.0.1:8787/api/v2/events",
        "http://127.0.0.1:8787/api/v1/coach/evaluate",
        async () => {
          return {
            json: async () => ({
              actions: [],
              ok: true,
            }),
            ok: true,
            status: 200,
          } as Response;
        },
      ),
    );

    await Promise.all([
      orchestrator.handleEvent(makeEvent("step_enter", null, null, derivedContextForStep())),
      orchestrator.handleEvent(makeEvent("step_resolved", null, null, derivedContextForStep())),
    ]);

    const storedEvents = await storage.getRecentEvents("session_1");
    expect(storedEvents.map((event) => event.type)).toEqual(["step_enter", "step_resolved"]);
  });
});

const originalFetch = globalThis.fetch;

function makeConnectedStatus(): CoachApiStatus {
  return {
    endpoint: "http://127.0.0.1:8787/api/v2/events",
    lastUpdatedAt: Date.now(),
    message: "Connected to coach API (v2 events)",
    policyVersion: null,
    state: "connected",
  };
}

function derivedContextForStep() {
  return {
    fieldCompletion: 0,
    sessionDurationMs: 0,
    validationErrorCount: 0,
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

function makeEvaluationInput(event: NormalizedEvent, signals = ["tariff_click_oos"]) {
  return {
    event,
    fallbackRequest: {
      coachStepId: event.coachStepId,
      currentOffer: {
        priceDelta: null,
        selectedTariff: null,
        visiblePrice: null,
      },
      derivedContext: event.derivedContext,
      detectedSignals: signals,
      pageStepId: event.pageStepId,
      recentEvents: [event],
      sessionId: event.sessionId,
    },
    signals,
  };
}

function loadFixture(filename: string): Document {
  const html = readFileSync(resolve(process.cwd(), "tests/fixtures", filename), "utf8");
  return new JSDOM(html).window.document;
}
