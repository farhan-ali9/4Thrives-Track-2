import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { createApp } from "../src/app";
import type { AppConfig } from "../src/config";
import { MemoryCoachRepository } from "../src/repository";

describe("coach api app", () => {
  let repository: MemoryCoachRepository;

  beforeEach(() => {
    repository = new MemoryCoachRepository();
  });

  afterEach(async () => {
    repository = new MemoryCoachRepository();
  });

  test("logs in, saves a new policy version, and restores an older version", async () => {
    const app = await createApp({
      config: makeConfig(),
      repository,
    });

    const loginResponse = await app.inject({
      method: "POST",
      payload: {
        email: "admin@uniqa.local",
        password: "change-me-now",
      },
      url: "/api/v1/admin/login",
    });

    expect(loginResponse.statusCode).toBe(200);
    const cookie = readCookie(loginResponse.headers["set-cookie"]);
    expect(cookie).toContain("conversion_coach_admin=");

    const meResponse = await app.inject({
      headers: {
        cookie,
      },
      method: "GET",
      url: "/api/v1/admin/me",
    });
    expect(meResponse.statusCode).toBe(200);

    const policyResponse = await app.inject({
      headers: {
        cookie,
      },
      method: "GET",
      url: "/api/v1/admin/policy",
    });
    const policyRecord = policyResponse.json();
    policyRecord.policy.interventions.tariff_route_explainer.title = "Updated coach title";

    const saveResponse = await app.inject({
      headers: {
        cookie,
      },
      method: "PUT",
      payload: policyRecord.policy,
      url: "/api/v1/admin/policy",
    });
    expect(saveResponse.statusCode).toBe(200);
    expect(saveResponse.json().version).toBe(2);

    const versionsResponse = await app.inject({
      headers: {
        cookie,
      },
      method: "GET",
      url: "/api/v1/admin/policies",
    });
    const versions = versionsResponse.json().policies;
    expect(versions).toHaveLength(2);

    const originalVersionId = versions.find((entry: { version: number }) => entry.version === 1)?.id;
    expect(originalVersionId).toBeTruthy();

    const restoreResponse = await app.inject({
      headers: {
        cookie,
      },
      method: "POST",
      url: `/api/v1/admin/policies/${originalVersionId}/restore`,
    });
    expect(restoreResponse.statusCode).toBe(200);
    expect(restoreResponse.json().version).toBe(3);
    expect(restoreResponse.json().restoredFromPolicyVersionId).toBe(originalVersionId);

    await app.close();
  });

  test("rejects invalid policy payloads for admin saves", async () => {
    const app = await createApp({
      config: makeConfig(),
      repository,
    });

    const loginResponse = await app.inject({
      method: "POST",
      payload: {
        email: "admin@uniqa.local",
        password: "change-me-now",
      },
      url: "/api/v1/admin/login",
    });

    const saveResponse = await app.inject({
      headers: {
        cookie: readCookie(loginResponse.headers["set-cookie"]),
      },
      method: "PUT",
      payload: {
        foo: "bar",
      },
      url: "/api/v1/admin/policy",
    });

    expect(saveResponse.statusCode).toBe(400);
    expect(saveResponse.json().error).toBe("invalid_policy");

    await app.close();
  });

  test("returns coach actions from the active policy without admin auth", async () => {
    const app = await createApp({
      config: makeConfig(),
      repository,
    });

    const evaluateResponse = await app.inject({
      method: "POST",
      payload: {
        coachStepId: "s4_initial_price",
        currentOffer: {
          priceDelta: null,
          selectedTariff: "optimal",
          visiblePrice: 68.14,
        },
        derivedContext: {},
        detectedSignals: ["tariff_click_oos"],
        pageStepId: "s4_initial_price",
        recentEvents: [],
        sessionId: "session_1",
      },
      url: "/api/v1/coach/evaluate",
    });

    expect(evaluateResponse.statusCode).toBe(200);
    const payload = evaluateResponse.json();
    expect(payload.source).toBe("remote");
    expect(payload.policyVersion).toBe(1);
    expect(payload.actions[0]?.id).toBe("tariff_route_explainer");

    await app.close();
  });
});

function makeConfig(): AppConfig {
  return {
    adminStaticDir: null,
    bootstrapAdminEmail: "admin@uniqa.local",
    bootstrapAdminName: "Test Admin",
    bootstrapAdminPassword: "change-me-now",
    host: "127.0.0.1",
    port: 8787,
    secureCookies: false,
    sessionSecret: "test-secret",
  };
}

function readCookie(cookieHeader: string | string[] | undefined): string {
  const header = Array.isArray(cookieHeader) ? cookieHeader[0] : cookieHeader;
  return header?.split(";")[0] ?? "";
}
