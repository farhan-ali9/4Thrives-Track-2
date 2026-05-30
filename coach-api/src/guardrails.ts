// Hard deterministic guardrails — not part of the trainable policy.
// These rules must fire regardless of what the policy engine says.
// Out-of-scope paths get advisor_handoff. Period.

export type GuardrailOutcome = "advisor_handoff" | "online";

export interface GuardrailResult {
  guardrail: string | null;
  outcome: GuardrailOutcome;
  allowedActions: string[];
  blockedActions: string[];
}

const COACHING_ACTIONS = [
  "price_transparency",
  "trust_signal",
  "simplified_explanation",
  "market_comparison",
  "online_alternative_explanation",
  "save_progress",
  "clear_next_step",
  "no_action",
  // v1 policy engine names
  "price_reframe",
  "market_comparison",
  "price_gap_transparency",
  "tariff_route_explainer",
];

const OOS_TARIFFS = new Set(["opt_plus", "opt. plus", "optplus", "premium"]);
const OOS_COVERAGES = new Set(["hospital", "sonderklasse", "hospital_coverage"]);
const OOS_INSURED_PERSONS = new Set(["other_persons", "others", "other"]);

export function applyHardGuardrails(state: {
  selectedTariff: string | null;
  coverage: string | null;
  insuredPerson: string | null;
  hasOosPathSignal: boolean;
}): GuardrailResult {
  const allowed = ["advisor_handoff"];

  if (state.coverage && OOS_COVERAGES.has(normalize(state.coverage))) {
    return {
      guardrail: "out_of_scope_advisor_coverage",
      outcome: "advisor_handoff",
      allowedActions: allowed,
      blockedActions: COACHING_ACTIONS,
    };
  }

  if (state.insuredPerson && OOS_INSURED_PERSONS.has(normalize(state.insuredPerson))) {
    return {
      guardrail: "out_of_scope_advisor_insured_person",
      outcome: "advisor_handoff",
      allowedActions: allowed,
      blockedActions: COACHING_ACTIONS,
    };
  }

  if (state.selectedTariff && OOS_TARIFFS.has(normalize(state.selectedTariff))) {
    return {
      guardrail: "out_of_scope_advisor_tariff",
      outcome: "advisor_handoff",
      allowedActions: allowed,
      blockedActions: COACHING_ACTIONS,
    };
  }

  if (state.hasOosPathSignal) {
    return {
      guardrail: "out_of_scope_advisor_path",
      outcome: "advisor_handoff",
      allowedActions: allowed,
      blockedActions: COACHING_ACTIONS,
    };
  }

  return {
    guardrail: null,
    outcome: "online",
    allowedActions: [...COACHING_ACTIONS, "advisor_handoff"],
    blockedActions: [],
  };
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[\s._-]+/g, "_");
}
