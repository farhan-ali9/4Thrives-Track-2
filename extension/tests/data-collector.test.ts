import { afterEach, describe, expect, test, vi } from "vitest";
import { DataCollector, type InteractionEvent } from "@/content/data-collector";
import { resolvePageStep } from "@/shared/page-map";

const activeCollectors: DataCollector[] = [];

describe("DataCollector", () => {
  afterEach(() => {
    while (activeCollectors.length) {
      activeCollectors.pop()?.stop();
    }
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  test("classifies the hospital choice as an out-of-scope path", () => {
    const events = mountCollector(`
      <h1>Wo möchten Sie abgesichert sein?</h1>
      <label><input type="checkbox" /> Bei Arztbesuchen</label>
      <label><input id="hospital-choice" type="checkbox" /> Im Krankenhaus</label>
      <button data-cy="nextStepButton">Weiter</button>
      <button data-cy="backButton">Abbrechen</button>
    `);

    const hospitalChoice = document.querySelector("#hospital-choice") as HTMLInputElement;
    hospitalChoice.checked = true;
    hospitalChoice.dispatchEvent(new Event("change", { bubbles: true }));

    expect(events[0]).toMatchObject({
      type: "change",
      value: {
        checked: true,
        intent: "out_of_scope_path",
        option: "im_krankenhaus",
      },
    });
  });

  test("classifies the other-persons choice as an out-of-scope path", () => {
    const events = mountCollector(`
      <h1>Wer soll versichert werden?</h1>
      <label><input data-cy="insuredPartyPolicyHolder" name="insured-party" type="radio" /> Ich selbst</label>
      <label><input id="other-party" data-cy="insuredPartyOther" name="insured-party" type="radio" /> Andere Personen</label>
      <button data-cy="nextStepButton">Weiter</button>
      <button data-cy="backButton">Zurück</button>
    `);

    const otherParty = document.querySelector("#other-party") as HTMLInputElement;
    otherParty.checked = true;
    otherParty.dispatchEvent(new Event("change", { bubbles: true }));

    expect(events[0]).toMatchObject({
      type: "change",
      value: {
        checked: true,
        intent: "out_of_scope_path",
        option: "andere_personen",
      },
    });
  });

  test("classifies a premium tariff click as out of scope", () => {
    const events = mountCollector(`
      <div>Voraussichtliche Prämie</div>
      <table>
        <tr>
          <th>Start</th>
          <th>Optimal</th>
          <th>Opt. Plus</th>
          <th>Premium</th>
        </tr>
        <tr>
          <td>41,30 EUR</td>
          <td>73,02 EUR</td>
          <td>105,07 EUR</td>
          <td>152,35 EUR</td>
        </tr>
      </table>
      <button data-cy="selectionButton_0" aria-label="Wählen Start">Wählen</button>
      <button data-cy="selectionButton_1" aria-label="Wählen Optimal">Wählen</button>
      <button data-cy="selectionButton_2" aria-label="Wählen Opt. Plus">Wählen</button>
      <button id="premium-button" data-cy="selectionButton_3" aria-label="Wählen Premium">Wählen</button>
      <button data-cy="nextStepButton">Weiter</button>
    `);

    const premiumButton = document.querySelector("#premium-button") as HTMLButtonElement;
    premiumButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    expect(events[0]).toMatchObject({
      elementKey: "selectionbutton_3",
      type: "click",
      value: {
        intent: "out_of_scope_tariff",
        option: "premium",
      },
    });
  });

  test("tracks hover on price and cancel targets", () => {
    const events = mountCollector(`
      <div>Voraussichtliche Prämie</div>
      <table>
        <tr>
          <th>Start</th>
          <th>Optimal</th>
          <th>Opt. Plus</th>
          <th>Premium</th>
        </tr>
        <tr>
          <td>41,30 EUR</td>
          <td>73,02 EUR</td>
          <td>105,07 EUR</td>
          <td>152,35 EUR</td>
        </tr>
      </table>
      <button data-cy="selectionButton_0" aria-label="Wählen Start">Wählen</button>
      <button id="optimal-button" data-cy="selectionButton_1" aria-label="Wählen Optimal">Wählen</button>
      <button data-cy="selectionButton_2" aria-label="Wählen Opt. Plus">Wählen</button>
      <button data-cy="selectionButton_3" aria-label="Wählen Premium">Wählen</button>
      <button id="back-button" data-cy="backButton">Zurück</button>
      <button data-cy="nextStepButton">Weiter</button>
    `);

    const optimalButton = document.querySelector("#optimal-button") as HTMLButtonElement;
    optimalButton.dispatchEvent(new Event("pointerenter", { bubbles: true }));

    const backButton = document.querySelector("#back-button") as HTMLButtonElement;
    backButton.dispatchEvent(new Event("pointerenter", { bubbles: true }));

    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "pointerenter",
          value: {
            target: "price",
          },
        }),
        expect.objectContaining({
          type: "pointerenter",
          value: {
            target: "cancel",
          },
        }),
      ]),
    );
  });

  test("emits inactivity after 30 seconds without interaction", () => {
    vi.useFakeTimers();
    const events = mountCollector(`
      <h1>Wer soll versichert werden?</h1>
      <label><input data-cy="insuredPartyPolicyHolder" name="insured-party" type="radio" /> Ich selbst</label>
      <label><input data-cy="insuredPartyOther" name="insured-party" type="radio" /> Andere Personen</label>
      <button data-cy="nextStepButton">Weiter</button>
      <button data-cy="backButton">Zurück</button>
    `);

    vi.advanceTimersByTime(30_000);

    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          elementKey: "inactivity_timer",
          type: "inactivity",
          value: {
            idleMs: 30_000,
          },
        }),
      ]),
    );
  });

  test("captures scroll direction when the scroll delta is meaningful", () => {
    const events = mountCollector(`
      <h1>Wer soll versichert werden?</h1>
      <label><input data-cy="insuredPartyPolicyHolder" name="insured-party" type="radio" /> Ich selbst</label>
      <label><input data-cy="insuredPartyOther" name="insured-party" type="radio" /> Andere Personen</label>
      <button data-cy="nextStepButton">Weiter</button>
      <button data-cy="backButton">Zurück</button>
    `);

    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 120,
    });
    window.dispatchEvent(new Event("scroll"));

    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          elementKey: "window_scroll",
          type: "scroll",
          value: {
            delta: 120,
            direction: "down",
          },
        }),
      ]),
    );
  });
});

function mountCollector(bodyMarkup: string): InteractionEvent[] {
  document.body.innerHTML = bodyMarkup;
  const step = resolvePageStep(document);
  expect(step).not.toBeNull();

  const events: InteractionEvent[] = [];
  const collector = new DataCollector(
    () => step,
    () => ({}),
    (event) => {
      events.push(event);
    },
  );
  collector.start();
  activeCollectors.push(collector);
  return events;
}
