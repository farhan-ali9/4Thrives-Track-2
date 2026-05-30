import type { CoachAction, CoachRequest, CoachResponse } from "./contracts";

function buildAction(action: CoachAction): CoachAction {
  return action;
}

export function evaluateCoachRequest(request: CoachRequest): CoachResponse {
  const actions: CoachAction[] = [];
  const signals = new Set(request.detectedSignals);
  const stepId = request.pageStepId;

  if (signals.has("path_oos")) {
    actions.push(
      buildAction({
        id: "advisor_route",
        kind: "advisor_route",
        placement: "bottom-toast",
        title: "Dieser Pfad braucht Beratung",
        body: "Für Krankenhaus oder andere Personen führt UNIQA in einen Beratungspfad. Für den Online-Abschluss bleiben Sie bei Arztbesuchen und Ich selbst.",
        ctaLabel: "Verstanden",
        dismissible: true,
        cooldownMs: 120_000,
      }),
    );
  }

  if (stepId === "s3_quote_basics" && (signals.has("inactivity") || signals.has("repeated_change"))) {
    actions.push(
      buildAction({
        id: "trust_signal",
        kind: "trust_signal",
        placement: "inline-top-of-step",
        title: "Warum diese Daten nötig sind",
        body: "Geburtsdatum und Sozialversicherungsträger dienen nur zur vorläufigen Prämienberechnung. Es wird noch nichts abgeschlossen.",
        ctaLabel: "Weiter",
        dismissible: true,
        cooldownMs: 90_000,
      }),
    );
  }

  if (stepId === "s4_initial_price" && signals.has("tariff_click_oos")) {
    actions.push(
      buildAction({
        id: "tariff_route_explainer",
        kind: "tariff_route_explainer",
        placement: "near-primary-cta",
        title: "Opt. Plus und Premium brauchen Beratung",
        body: "Wenn Sie jetzt online abschließen möchten, bleiben Start und Optimal die passenden Tarife. Optimal deckt mehr ab und bleibt online abschließbar.",
        ctaLabel: "Optimal prüfen",
        dismissible: true,
        cooldownMs: 90_000,
      }),
    );
  }

  if (
    stepId === "s4_initial_price" &&
    (signals.has("price_hover") || signals.has("dwell") || signals.has("scroll_back") || signals.has("inactivity"))
  ) {
    actions.push(
      buildAction({
        id: "price_reframe",
        kind: "price_reframe",
        placement: "inline-top-of-step",
        title: "Preis kurz eingeordnet",
        body: "Optimal liegt hier bei rund EUR 2,43 pro Tag und bleibt vollständig online abschließbar.",
        ctaLabel: "Tarife vergleichen",
        dismissible: true,
        cooldownMs: 90_000,
      }),
    );
  }

  if (stepId === "s5_add_ons" && signals.has("dwell")) {
    actions.push(
      buildAction({
        id: "addons_clarifier",
        kind: "simplified_explanation",
        placement: "near-primary-cta",
        title: "Extras sind optional",
        body: "Sie können hier ohne Zusatzbausteine weitergehen und später immer noch ergänzen, wenn ein Bedarf klarer wird.",
        ctaLabel: "Ohne Extras weiter",
        dismissible: true,
        cooldownMs: 90_000,
      }),
    );
  }

  if (stepId === "s6_personal_medical_data" && (signals.has("inactivity") || signals.has("repeated_change"))) {
    actions.push(
      buildAction({
        id: "medical_form_reassurance",
        kind: "trust_signal",
        placement: "inline-top-of-step",
        title: "Formular mit sensiblen Angaben",
        body: "Für die finale Einschätzung braucht UNIQA diese Angaben vollständig. Die Extension speichert davon selbst keine Rohwerte.",
        ctaLabel: "Weiter ausfüllen",
        dismissible: true,
        cooldownMs: 120_000,
      }),
    );
  }

  return {
    actions,
    source: "fixture",
  };
}
