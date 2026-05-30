import { readFileSync } from "node:fs";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { chromium, type BrowserContext, type Worker } from "playwright";

const pageMap = JSON.parse(
  readFileSync(new URL("../src/shared/uniqa-page-map.json", import.meta.url), "utf8"),
) as Array<{
  enabled: boolean;
  match: {
    requiredSelectorsAll?: string[];
    requiredSelectorsAny?: string[];
    requiredText?: string[];
  };
  pageStepId: string;
}>;

test("walks the verified live doctor path through step 6", async ({ page }) => {
  await gotoCalculator(page);
  await expect.poll(() => detectStep(page)).toBe("s1_coverage_scope");

  await completeCoreDoctorPath(page);
  await expect.poll(() => detectStep(page)).toBe("s6_personal_medical_data");
});

test("classifies an out-of-scope tariff click on the live tariff step", async ({ page }) => {
  await gotoCalculator(page);
  await reachTariffStep(page);
  await expect.poll(() => detectStep(page)).toBe("s4_initial_price");

  await page.evaluate(() => {
    (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals = [];
    document.addEventListener(
      "click",
      (event) => {
        const target = event.target as HTMLElement | null;
        const button = target?.closest("button");
        const ariaLabel = button?.getAttribute("aria-label") ?? "";
        if (/Wählen\s+(Opt\.\s*Plus|Premium)/i.test(ariaLabel)) {
          (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals?.push("tariff_click_oos");
        }
      },
      { capture: true },
    );
  });

  await page.getByRole("button", { name: "Wählen Opt. Plus" }).click();
  const signals = await page.evaluate(() => (window as Window & { __uniqaSignals?: string[] }).__uniqaSignals ?? []);
  expect(signals).toContain("tariff_click_oos");
});

test("detects the live step 7 screen after valid step 6 data", async ({ page }) => {
  await gotoCalculator(page);
  await reachStep7(page);
  await expect.poll(() => detectStep(page)).toBe("s7_final_price");
});

test("detects the current live terminal advisor-request screen", async ({ page }) => {
  await gotoCalculator(page);
  await reachStep8(page);
  await expect.poll(() => detectStep(page)).toBe("s8_confirm");
});

test("loads the built extension on the live calculator and stores coach interaction events", async () => {
  const port = await getFreePort();
  const apiOrigin = `http://127.0.0.1:${port}`;
  const extensionPath = buildExtension(apiOrigin);
  const userDataDir = mkdtempSync(join(tmpdir(), "uniqa-extension-"));
  const requests: Array<{
    derived_signals?: Record<string, boolean>;
    event_id?: string;
    event_type?: string;
    session_id?: string;
    step_id?: string | null;
  }> = [];

  const server = createServer(async (request, response) => {
    if (request.method !== "POST" || request.url !== "/api/v2/events") {
      response.writeHead(404).end();
      return;
    }

    const body = await readRequestBody(request);
    const payload = JSON.parse(body) as {
      derived_signals?: Record<string, boolean>;
      event_id?: string;
      event_type?: string;
      session_id?: string;
      step_id?: string | null;
    };
    const shouldRenderCoach = requests.length === 0;
    requests.push(payload);

    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(
      JSON.stringify({
        actions: shouldRenderCoach
          ? [
              {
                body: "This is a mocked coach action from the live smoke test.",
                cta: {
                  label: "Continue",
                  prompt: "Help me continue the current calculator step.",
                  target: "primary_cta",
                  telemetryKey: "live_smoke_continue",
                  type: "continue",
                },
                cooldownMs: 30_000,
                ctaLabel: "Continue",
                dismissible: true,
                id: "live_smoke_action",
                kind: "smoke_test",
                placement: "bottom-toast",
                title: "Live smoke coach action",
              },
            ]
          : [],
        policyVersion: 1,
        source: "remote",
      }),
    );
  });

  await new Promise<void>((resolveServer) => {
    server.listen(port, "127.0.0.1", resolveServer);
  });

  let context: BrowserContext | null = null;
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      args: [
        `--disable-extensions-except=${extensionPath}`,
        `--load-extension=${extensionPath}`,
      ],
      channel: "chromium",
      headless: true,
    });

    const serviceWorker =
      context.serviceWorkers()[0] ?? (await context.waitForEvent("serviceworker"));
    const page = context.pages()[0] ?? (await context.newPage());

    await page.goto("https://www.uniqa.at/rechner/krankenversicherung/");
    await dismissCookieBanner(page);

    await expect
      .poll(() =>
        page.evaluate(() =>
          Boolean(document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot),
        ),
      )
      .toBe(true);

    await expect
      .poll(() =>
        page.evaluate(
          () =>
            document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot?.textContent ?? "",
        ),
      )
      .toContain("Live smoke coach action");

    await page.evaluate(() => {
      const shadow = document.querySelector("#uniqa-conversion-coach-root")?.shadowRoot;
      const cta = shadow?.querySelector(".cta");
      const dismiss = shadow?.querySelector(".dismiss");
      if (!(cta instanceof HTMLButtonElement) || !(dismiss instanceof HTMLButtonElement)) {
        throw new Error("Coach action buttons were not rendered");
      }

      cta.click();
      dismiss.click();
    });

    await expect
      .poll(async () => {
        const events = await readStoredEvents(serviceWorker);
        const eventTypes = events.map((event) => event.type);
        return (
          eventTypes.includes("step_enter") &&
          eventTypes.includes("coach_impression") &&
          eventTypes.includes("coach_cta") &&
          eventTypes.includes("coach_dismiss")
        );
      })
      .toBe(true);

    const storedEvents = await readStoredEvents(serviceWorker);
    const flattenedEvents = storedEvents.map((event) => event.type);
    expect(flattenedEvents).toContain("step_enter");
    expect(flattenedEvents).toContain("coach_impression");
    expect(flattenedEvents).toContain("coach_cta");
    expect(flattenedEvents).toContain("coach_dismiss");
    expect(storedEvents.some((event) => event.pageStepId === "s1_coverage_scope")).toBe(true);
    expect(requests.some((request) => request.step_id === "s1_coverage_scope")).toBe(true);
    expect(requests.every((request) => typeof request.event_id === "string")).toBe(true);
  } finally {
    await context?.close();
    await new Promise<void>((resolveServer, rejectServer) => {
      server.close((error) => {
        if (error) {
          rejectServer(error);
          return;
        }
        resolveServer();
      });
    });
    rmSync(userDataDir, { force: true, recursive: true });
  }
});

async function detectStep(page: Page): Promise<string | null> {
  const liveEntries = pageMap.filter((entry) => entry.enabled);
  return page.evaluate((entries) => {
    const normalize = (value: string | null | undefined) => (value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
    const docText = normalize(document.body?.innerText || document.body?.textContent || "");

    for (const entry of entries) {
      const requiredText = entry.match.requiredText ?? [];
      const requiredSelectorsAll = entry.match.requiredSelectorsAll ?? [];
      const requiredSelectorsAny = entry.match.requiredSelectorsAny ?? [];

      const matchesText = requiredText.every((needle) => docText.includes(normalize(needle)));
      const matchesAllSelectors = requiredSelectorsAll.every((selector) => document.querySelector(selector));
      const matchesAnySelector =
        requiredSelectorsAny.length === 0 || requiredSelectorsAny.some((selector) => document.querySelector(selector));

      if (matchesText && matchesAllSelectors && matchesAnySelector) {
        return entry.pageStepId;
      }
    }

    return null;
  }, liveEntries);
}

async function gotoCalculator(page: Page): Promise<void> {
  await page.goto("https://www.uniqa.at/rechner/krankenversicherung/");
  await dismissCookieBanner(page);
}

async function reachTariffStep(page: Page): Promise<void> {
  await page.getByRole("checkbox", { name: "Bei Arztbesuchen" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s2_for_whom");

  await page.getByRole("radio", { name: "Ich selbst" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s3_quote_basics");

  await page.getByRole("textbox", { name: "Geburtsdatum" }).fill("01.01.1990");
  await page.locator("[data-cy='ur-select-field-button']").click();
  await page.getByText("ÖGK").click();
  await page.getByRole("button", { name: "Weiter" }).click();
}

async function completeCoreDoctorPath(page: Page): Promise<void> {
  await reachTariffStep(page);
  await expect.poll(() => detectStep(page)).toBe("s4_initial_price");

  await page.getByRole("button", { name: "Wählen Optimal" }).click();
  await page.getByRole("button", { name: "Weiter" }).click();
  await expect.poll(() => detectStep(page)).toBe("s5_add_ons");

  await page.getByRole("button", { name: "Weiter" }).click();
}

async function reachStep7(page: Page): Promise<void> {
  await completeCoreDoctorPath(page);
  await expect.poll(() => detectStep(page)).toBe("s6_personal_medical_data");

  await page.getByText("männlich").click();
  const textInputs = page.locator("input[type='text']");
  await textInputs.nth(0).fill("Max");
  await textInputs.nth(1).fill("Tester");
  await textInputs.nth(2).fill(generateSv(1, 1, 1990));
  await textInputs.nth(3).fill("max.tester@example.com");
  await textInputs.nth(4).fill("+436641234567");
  await textInputs.nth(5).fill("180");
  await textInputs.nth(6).fill("80");
  await page.getByText("nein").click();
  await page.getByText("kein behandelnder Arzt").click();
  await page.getByRole("button", { name: "Weiter" }).click();
}

async function reachStep8(page: Page): Promise<void> {
  await reachStep7(page);
  await expect.poll(() => detectStep(page)).toBe("s7_final_price");

  await chooseNoForQuestionGroup(page, "insuranceInPast7Years");
  await chooseNoForQuestionGroup(page, "rejectedApplication");
  await page.getByRole("button", { name: "Weiter" }).click();

  await chooseNoForQuestionGroup(page, "diagnoses");
  await chooseNoForQuestionGroup(page, "musculoskeletalSystem");
  await page.getByRole("button", { name: "Weiter" }).click();

  await chooseNoForQuestionGroup(page, "rehabilitationPlanned");
  await chooseNoForQuestionGroup(page, "therapiesPlanned");
  await page.getByRole("button", { name: "Weiter" }).click();
}

async function dismissCookieBanner(page: Page): Promise<void> {
  const buttons = [
    page.getByRole("button", {
      name: "Alle ablehnen außer technisch notwendige Cookies",
    }),
    page.getByRole("button", {
      name: /alle ablehnen/i,
    }),
  ];

  for (const button of buttons) {
    if (await button.isVisible().catch(() => false)) {
      await button.click({ force: true });
      return;
    }
  }
}

function generateSv(day: number, month: number, year: number): string {
  const yy = String(year).slice(-2);
  const dd = String(day).padStart(2, "0");
  const mm = String(month).padStart(2, "0");
  const birth = `${dd}${mm}${yy}`;

  for (let serial = 100; serial <= 999; serial += 1) {
    const digits = `${String(serial).padStart(3, "0")}${birth}`.split("").map(Number);
    const checksum =
      (3 * digits[0] +
        7 * digits[1] +
        9 * digits[2] +
        5 * digits[3] +
        8 * digits[4] +
        4 * digits[5] +
        2 * digits[6] +
        digits[7] +
        6 * digits[8]) %
      11;

    if (checksum !== 10) {
      return `${String(serial).padStart(3, "0")}${checksum}${birth}`;
    }
  }

  throw new Error("Unable to generate a valid test SV number");
}

async function chooseNoForQuestionGroup(page: Page, dataCy: string): Promise<void> {
  const group = page.locator(`[data-cy='${dataCy}']`);
  const noInput = group.locator("label").filter({ hasText: /^nein$/i }).locator("input");
  if ((await noInput.count()) > 0) {
    await noInput.first().check({ force: true });
    return;
  }

  const radioInputs = group.locator("input[type='radio']");
  const count = await radioInputs.count();
  if (count === 0) {
    throw new Error(`No radio inputs found for question group ${dataCy}`);
  }

  await radioInputs.nth(count - 1).check({ force: true });
}

function buildExtension(apiOrigin: string): string {
  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  execFileSync(npmCommand, ["run", "build"], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      VITE_COACH_API_ORIGIN: apiOrigin,
    },
    stdio: "pipe",
  });
  return resolve(process.cwd(), "dist");
}

async function readStoredEvents(serviceWorker: Worker): Promise<Array<{ pageStepId: string | null; type: string }>> {
  const storage = (await serviceWorker.evaluate(async () => {
    return chrome.storage.local.get(["uniqa.events"]);
  })) as { ["uniqa.events"]?: Record<string, Array<{ pageStepId: string | null; type: string }>> };
  return Object.values(storage["uniqa.events"] ?? {}).flat();
}

function readRequestBody(request: IncomingMessage): Promise<string> {
  return new Promise((resolveBody, rejectBody) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    });
    request.on("end", () => {
      resolveBody(Buffer.concat(chunks).toString("utf8"));
    });
    request.on("error", rejectBody);
  });
}

async function getFreePort(): Promise<number> {
  return await new Promise<number>((resolvePort, rejectPort) => {
    const probe = createServer();
    probe.once("error", rejectPort);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      if (!address || typeof address === "string") {
        rejectPort(new Error("Unable to resolve a free localhost port"));
        return;
      }

      const { port } = address;
      probe.close((error) => {
        if (error) {
          rejectPort(error);
          return;
        }
        resolvePort(port);
      });
    });
  });
}
