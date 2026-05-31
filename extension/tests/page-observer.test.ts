import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";
import { PageObserver, type ObserverEvent } from "@/content/page-observer";

describe("PageObserver", () => {
  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  test("emits step leave and enter when the live step changes", async () => {
    vi.useFakeTimers();
    document.body.innerHTML = loadFixtureBody("s4_initial_price.html");

    const events: ObserverEvent[] = [];
    const observer = new PageObserver((event) => {
      events.push(event);
    });
    observer.start();

    expect(events.map((event) => event.type)).toEqual(["step_enter", "step_resolved"]);
    expect(events[0]?.step?.pageStepId).toBe("s4_initial_price");

    vi.advanceTimersByTime(500);
    document.body.innerHTML = loadFixtureBody("s5_add_ons.html");
    await Promise.resolve();
    vi.advanceTimersByTime(100);

    expect(events.map((event) => event.type)).toEqual([
      "step_enter",
      "step_resolved",
      "step_leave",
      "step_enter",
      "step_resolved",
    ]);
    expect(events[2]?.step?.pageStepId).toBe("s4_initial_price");
    expect(events[2]?.dwellMs).toBeGreaterThanOrEqual(500);
    expect(events[3]?.step?.pageStepId).toBe("s5_add_ons");

    observer.stop();
  });

  test("emits price_changed when the visible price changes within the same step", async () => {
    vi.useFakeTimers();
    document.body.innerHTML = loadFixtureBody("s4_initial_price.html");

    const events: ObserverEvent[] = [];
    const observer = new PageObserver((event) => {
      events.push(event);
    });
    observer.start();

    const firstPriceCell = document.querySelector("td");
    expect(firstPriceCell).not.toBeNull();
    firstPriceCell!.textContent = "45,00 EUR";

    await Promise.resolve();
    vi.advanceTimersByTime(100);

    const priceChanged = events.find((event) => event.type === "price_changed");
    expect(priceChanged?.step?.pageStepId).toBe("s4_initial_price");
    expect(priceChanged?.derivedContext.visiblePriceMonthly).toBe(45);

    observer.stop();
  });
});

function loadFixtureBody(filename: string): string {
  const html = readFileSync(resolve(process.cwd(), "tests/fixtures", filename), "utf8");
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  return bodyMatch?.[1]?.trim() ?? html;
}
