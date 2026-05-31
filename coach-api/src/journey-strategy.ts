import type {
  CoachCta,
  JourneyCard,
  JourneyDecision,
  JourneyDomMutation,
  JourneyGoal,
  JourneySnapshot,
  PlayId,
} from "@uniqa-conversion-coach/shared/contracts";
import { randomUUID } from "node:crypto";

export function decideJourney(snapshot: JourneySnapshot): JourneyDecision | null {
  const play = choosePlay(snapshot);
  if (!play) {
    return null;
  }

  return {
    decisionId: `dec_${randomUUID()}`,
    goal: defaultGoal(snapshot),
    playId: play.playId,
    priority: play.priority,
    cooldownMs: play.cooldownMs,
    cards: play.cards,
    domMutations: play.domMutations,
    chatPrompt: play.chatPrompt,
  };
}

function choosePlay(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> | null {
  if (snapshot.routeFamily === "advisor_coverage" || snapshot.routeFamily === "advisor_other_persons") {
    if (snapshot.stage === "coverage_choice" || snapshot.stage === "insured_person") {
      return scopeClarifier(snapshot);
    }
    if (snapshot.stage === "advisor_contact" || snapshot.stage === "price_review") {
      return advisorLeadPush(snapshot);
    }
    return scopeClarifier(snapshot);
  }

  if (snapshot.routeFamily === "advisor_tariff") {
    if (snapshot.stage === "tariff_choice") {
      return onlineTariffRecovery(snapshot);
    }
    return advisorLeadPush(snapshot);
  }

  if (snapshot.stage === "quote_basics") {
    return trustBuilder(snapshot);
  }
  if (snapshot.stage === "tariff_choice") {
    return priceReframe(snapshot);
  }
  if (snapshot.stage === "options" && shouldReactToHesitation(snapshot)) {
    return chatHandoff(snapshot, "Optionales Zusatzpaket kurz erklaeren");
  }
  if (snapshot.stage === "health_data") {
    return trustBuilder(snapshot);
  }
  if (snapshot.stage === "price_review") {
    return priceChangeExplainer(snapshot);
  }
  if (snapshot.stage === "checkout" || snapshot.stage === "done") {
    return checkoutReassurance(snapshot);
  }

  return null;
}

function defaultGoal(snapshot: JourneySnapshot): JourneyGoal {
  return snapshot.routeFamily === "online_doctor" ? "converted_online" : "submitted_advisor_lead";
}

function scopeClarifier(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  const title =
    snapshot.routeFamily === "advisor_other_persons"
      ? "Dieser Weg braucht persoenliche Beratung"
      : "Dieser Schutz wird mit Beratung abgeschlossen";
  const body =
    snapshot.routeFamily === "advisor_other_persons"
      ? "Versicherungen fuer andere Personen werden mit einer Berateranfrage fortgesetzt. Wir helfen Ihnen jetzt beim schnellsten Weg dorthin."
      : "Krankenhaus-Schutz oder kombinierte Deckung werden mit einer Berateranfrage fortgesetzt. Der Online-Rechner zeigt Ihnen jetzt den passenden Beratungsweg.";

  return buildDecision("scope_clarifier", 95, 120_000, title, body, {
    label: "Warum Beratung?",
    type: "open_chat",
    target: "chat",
    prompt: "Warum brauche ich fuer diesen Weg Beratung und wie geht es jetzt weiter?",
    telemetryKey: "scope_clarifier_chat",
  }, [
    inlineNote("inline_scope", title, body),
    advisorProgress("advisor_progress", "Noch 2 Minuten bis zur Anfrage"),
    chatLink("scope_chat", "Warum brauche ich Beratung?", "Warum brauche ich fuer diesen Weg Beratung?"),
  ]);
}

function trustBuilder(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  const isHealthData = snapshot.stage === "health_data";
  return buildDecision(
    "trust_builder",
    80,
    90_000,
    isHealthData ? "Warum diese Angaben noetig sind" : "Warum diese Angaben noetig sind",
    isHealthData
      ? "Diese Angaben werden fuer die persoenliche Pruefung und den finalen Abschluss genutzt. Sie helfen dabei, den passenden Tarif korrekt online abzuschliessen."
      : "Geburtsdatum und Sozialversicherung werden nur fuer die individuelle Praemienberechnung genutzt. Der Abschluss startet erst in den spaeteren Schritten.",
    {
      label: isHealthData ? "Warum wird das hier abgefragt?" : "Frage klaeren",
      type: "open_chat",
      target: "chat",
      prompt: isHealthData
        ? "Warum werden diese persoenlichen Angaben jetzt abgefragt und was passiert danach?"
        : "Warum werden diese Daten abgefragt und was passiert als naechstes?",
      telemetryKey: "trust_builder_chat",
    },
    [
      inlineNote(
        "trust_note",
        isHealthData ? "Sicher fuer den Abschluss" : "Sicher zur Praemienberechnung",
        isHealthData
          ? "Die Angaben dienen der korrekten Pruefung Ihres Online-Abschlusses."
          : "Die Angaben dienen nur der Berechnung.",
      ),
      chatLink(
        "trust_chat",
        "Warum wird das abgefragt?",
        isHealthData
          ? "Warum werden diese persoenlichen Angaben jetzt abgefragt?"
          : "Warum werden diese Daten abgefragt?",
      ),
    ],
  );
}

function priceReframe(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  const monthly = snapshot.visiblePriceMonthly;
  const daily = snapshot.visiblePriceDaily;
  const selectedTariff = normalizeTariff(snapshot.selectedTariff);
  const title =
    selectedTariff === "start"
      ? "Start preislich eingeordnet"
      : selectedTariff === "optimal"
        ? "Optimal preislich eingeordnet"
        : "Preis direkt eingeordnet";
  const body = buildTariffPriceBody(selectedTariff, monthly, daily);
  const prompt =
    selectedTariff === "start"
      ? "Warum passt Start preislich gut fuer den Online-Abschluss?"
      : selectedTariff === "optimal"
        ? "Warum lohnt sich Optimal gegenueber Start?"
        : "Warum ist der Tarif so hoch und welcher Online-Tarif passt am besten?";
  const ctaLabel =
    selectedTariff === "start"
      ? "Warum Start?"
      : selectedTariff === "optimal"
        ? "Warum Optimal?"
        : "Warum ist der Tarif so hoch?";

  return buildDecision(
    "price_reframe",
    85,
    60_000,
    title,
    body,
    {
      label: ctaLabel,
      type: "open_chat",
      target: "chat",
      prompt,
      telemetryKey: "price_reframe_chat",
    },
    [
      priceReframeMutation("price_reframe", body),
      tariffBadges("tariff_badges"),
      chatLink("price_chat", ctaLabel, prompt),
    ],
  );
}

function onlineTariffRecovery(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  const selectedTariff = snapshot.selectedTariff ? capitalize(snapshot.selectedTariff) : "dieser Tarif";
  return buildDecision(
    "online_tariff_recovery",
    100,
    45_000,
    `${selectedTariff} braucht Beratung`,
    "Wenn Sie direkt online abschliessen wollen, bleiben Start und Optimal die passenden Tarife. Fuer Opt. Plus und Premium koennen Sie alternativ eine Berateranfrage senden.",
    {
      label: "Optimal online pruefen",
      type: "select_tariff",
      target: "optimal",
      prompt: "Warum ist Optimal online abschliessbar und wie unterscheidet es sich?",
      telemetryKey: "online_tariff_recovery_optimal",
    },
    [
      tariffBadges("tariff_recovery_badges"),
      inlineNote("tariff_recovery_note", "Online oder Beratung", "Start und Optimal online, Opt. Plus und Premium mit Beratung."),
      chatLink("tariff_recovery_chat", "Warum braucht dieser Tarif Beratung?", "Warum brauche ich fuer diesen Tarif Beratung?"),
    ],
  );
}

function priceChangeExplainer(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  const delta = snapshot.priceDeltaMonthly;
  const body =
    delta && delta > 0
      ? `Der finale Preis liegt um EUR ${formatAmount(delta)} ueber dem ersten Richtwert. Der Unterschied entsteht durch Ihre individuellen Angaben, der Online-Abschluss bleibt aber weiter moeglich.`
      : "Der finale Preis basiert auf Ihren individuellen Angaben. Sie koennen den Abschluss weiterhin direkt online fortsetzen.";

  return buildDecision(
    "price_change_explainer",
    90,
    60_000,
    "Preisveraenderung erklaert",
    body,
    {
      label: "Preis erklaeren",
      type: "open_chat",
      target: "chat",
      prompt: "Warum hat sich der Preis geaendert und welche Online-Option habe ich jetzt?",
      telemetryKey: "price_change_explainer_chat",
    },
    [
      priceReframeMutation("price_change_reframe", body),
      inlineNote("price_change_note", "Sie koennen weiter online abschliessen", body),
      chatLink("price_change_chat", "Warum hat sich der Preis geaendert?", "Warum hat sich der Preis geaendert?"),
    ],
  );
}

function advisorLeadPush(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  return buildDecision(
    "advisor_lead_push",
    88,
    60_000,
    "Berateranfrage fast erledigt",
    "Die restlichen Angaben sichern den passenden Rueckruf oder Termin. Bleiben Sie auf diesem Weg, damit der richtige Beratungsfall direkt vorbereitet wird.",
    {
      label: "Beratungsweg erklaeren",
      type: "open_chat",
      target: "chat",
      prompt: "Welche Angaben brauche ich noch fuer die Berateranfrage?",
      telemetryKey: "advisor_lead_push_chat",
    },
    [
      advisorProgress("advisor_progress_push", "Noch 2 Minuten bis zur Anfrage"),
      inlineNote("advisor_push_note", "Passende Beratung vorbereiten", "Mit den restlichen Angaben wird die Anfrage vollstaendig."),
    ],
  );
}

function checkoutReassurance(snapshot: JourneySnapshot): Omit<JourneyDecision, "decisionId" | "goal"> {
  return buildDecision(
    "checkout_reassurance",
    75,
    60_000,
    "Sie sind fast fertig",
    "Pruefen Sie die letzten Angaben in Ruhe. Der Tarif und die gezeigte Praemie bleiben in diesem Abschlussweg erhalten.",
    {
      label: "Letzten Schritt erklaeren",
      type: "open_chat",
      target: "chat",
      prompt: "Was passiert im letzten Schritt des Online-Abschlusses?",
      telemetryKey: "checkout_reassurance_chat",
    },
    [inlineNote("checkout_note", "Letzter Schritt", "Danach ist der Online-Abschluss abgeschlossen.")],
  );
}

function chatHandoff(
  snapshot: JourneySnapshot,
  title: string,
): Omit<JourneyDecision, "decisionId" | "goal"> {
  return buildDecision(
    "chat_handoff",
    65,
    60_000,
    title,
    "Wenn Sie unsicher sind, koennen Sie direkt aus diesem Schritt eine kurze Erklaerung anfordern.",
    {
      label: "Mit Coach fragen",
      type: "open_chat",
      target: "chat",
      prompt: title,
      telemetryKey: "chat_handoff",
    },
    [chatLink("generic_chat", "Mit Coach fragen", title)],
  );
}

function shouldReactToHesitation(snapshot: JourneySnapshot): boolean {
  return snapshot.signals.some((signal) =>
    ["dwell", "inactivity", "cancel_hover", "back_nav", "repeated_change"].includes(signal),
  );
}

function buildDecision(
  playId: PlayId,
  priority: number,
  cooldownMs: number,
  title: string,
  body: string,
  cta: CoachCta | null,
  domMutations: JourneyDomMutation[],
): Omit<JourneyDecision, "decisionId" | "goal"> {
  const card: JourneyCard = {
    id: `${playId}_card`,
    placement: "near-primary-cta",
    tone: playId === "scope_clarifier" || playId === "online_tariff_recovery" ? "warning" : "value",
    title,
    body,
    cta,
    dismissible: true,
  };

  return {
    playId,
    priority,
    cooldownMs,
    cards: [card],
    domMutations,
    chatPrompt: cta?.prompt ?? null,
  };
}

function priceReframeMutation(id: string, body: string): JourneyDomMutation {
  return {
    id,
    kind: "price_reframe",
    placement: "near-primary-cta",
    title: "Monatlich und taeglich eingeordnet",
    body,
    selector: null,
    label: null,
    prompt: null,
    target: null,
  };
}

function tariffBadges(id: string): JourneyDomMutation {
  return {
    id,
    kind: "tariff_badges",
    placement: "inline-top-of-step",
    title: "Tarifstatus",
    body: "Start und Optimal: Online abschliessbar. Opt. Plus und Premium: Beratung erforderlich.",
    selector: null,
    label: null,
    prompt: null,
    target: null,
  };
}

function inlineNote(id: string, title: string, body: string): JourneyDomMutation {
  return {
    id,
    kind: "inline_note",
    placement: "near-primary-cta",
    title,
    body,
    selector: null,
    label: null,
    prompt: null,
    target: null,
  };
}

function advisorProgress(id: string, body: string): JourneyDomMutation {
  return {
    id,
    kind: "advisor_progress",
    placement: "inline-top-of-step",
    title: "Beratungsweg",
    body,
    selector: null,
    label: null,
    prompt: null,
    target: null,
  };
}

function chatLink(id: string, label: string, prompt: string): JourneyDomMutation {
  return {
    id,
    kind: "chat_link",
    placement: "near-primary-cta",
    title: null,
    body: null,
    selector: null,
    label,
    prompt,
    target: "chat",
  };
}

function formatAmount(value: number): string {
  return value.toFixed(2).replace(".", ",");
}

function buildTariffPriceBody(
  selectedTariff: "start" | "optimal" | null,
  monthly: number | null,
  daily: number | null,
): string {
  if (selectedTariff === "start") {
    if (monthly !== null && daily !== null) {
      return `Start liegt aktuell bei EUR ${formatAmount(monthly)} pro Monat, also rund EUR ${formatAmount(daily)} pro Tag. Das ist der schlankere Online-Tarif fuer einen guenstigen Einstieg.`;
    }
    return "Start ist der schlankere Online-Tarif fuer einen guenstigen Einstieg.";
  }

  if (selectedTariff === "optimal") {
    if (monthly !== null && daily !== null) {
      return `Optimal liegt aktuell bei EUR ${formatAmount(monthly)} pro Monat, also rund EUR ${formatAmount(daily)} pro Tag. Damit erhalten Sie mehr Leistung als bei Start und bleiben trotzdem komplett online abschliessbar.`;
    }
    return "Optimal bietet mehr Leistung als Start und bleibt komplett online abschliessbar.";
  }

  if (monthly !== null && daily !== null) {
    return `Die aktuelle Praemie liegt bei EUR ${formatAmount(monthly)} pro Monat, also rund EUR ${formatAmount(daily)} pro Tag. Start und Optimal bleiben online abschliessbar.`;
  }

  return "Start und Optimal bleiben online abschliessbar. Wir ordnen die Tarife direkt fuer Sie ein.";
}

function normalizeTariff(value: string | null): "start" | "optimal" | null {
  if (!value) {
    return null;
  }

  const normalized = value.toLowerCase().replace(/[\s._-]+/g, "");
  if (normalized === "start") {
    return "start";
  }
  if (normalized === "optimal") {
    return "optimal";
  }
  return null;
}

function capitalize(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
