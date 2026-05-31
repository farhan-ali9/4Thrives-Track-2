export type CoachPlacement =
  | "inline-top-of-step"
  | "near-primary-cta"
  | "bottom-toast";

export type CoachCtaType =
  | "select_tariff"
  | "continue"
  | "focus_field"
  | "open_chat"
  | "advisor_handoff"
  | "save_progress";

export interface CoachCta {
  label: string;
  type: CoachCtaType;
  target: string | null;
  prompt: string | null;
  telemetryKey: string | null;
}

export type JourneyRouteFamily =
  | "online_doctor"
  | "advisor_coverage"
  | "advisor_other_persons"
  | "advisor_tariff";

export type JourneyStage =
  | "coverage_choice"
  | "insured_person"
  | "quote_basics"
  | "tariff_choice"
  | "options"
  | "health_data"
  | "price_review"
  | "advisor_contact"
  | "checkout"
  | "done";

export type JourneyGoal = "converted_online" | "submitted_advisor_lead";

export type PlayId =
  | "scope_clarifier"
  | "trust_builder"
  | "price_reframe"
  | "online_tariff_recovery"
  | "price_change_explainer"
  | "advisor_lead_push"
  | "checkout_reassurance"
  | "chat_handoff";

export type JourneySignal =
  | "dwell"
  | "scroll_back"
  | "back_nav"
  | "repeated_change"
  | "price_hover"
  | "cancel_hover"
  | "tariff_click_oos"
  | "path_oos"
  | "inactivity";

export interface DerivedContext {
  ageBand?: string | null;
  socialInsuranceProviderCode?: string | null;
  selectedCoverage?: string[] | null;
  insuredPerson?: string | null;
  selectedTariff?: string | null;
  selectedAddOns?: string[];
  fieldCompletion?: number | null;
  validationErrorCount?: number;
  visiblePriceMonthly?: number | null;
  visiblePriceDaily?: number | null;
  priceDeltaMonthly?: number | null;
  sessionDurationMs?: number;
  lastInteractionMs?: number;
}

export type NormalizedEventType =
  | "step_enter"
  | "step_leave"
  | "step_resolved"
  | "price_changed"
  | "click"
  | "change"
  | "input"
  | "focus"
  | "blur"
  | "scroll"
  | "pointerenter"
  | "inactivity"
  | "visibility_change"
  | "coach_impression"
  | "coach_dismiss"
  | "coach_cta";

export interface NormalizedEvent {
  id: string;
  sessionId: string;
  ts: number;
  pageStepId: string | null;
  journeyStage: JourneyStage | null;
  type: NormalizedEventType;
  elementKey: string | null;
  value: Record<string, unknown> | string | number | boolean | null;
  derivedContext: DerivedContext;
  dwellMs: number | null;
}

export interface JourneySnapshot {
  sessionId: string;
  url: string;
  routeFamily: JourneyRouteFamily;
  stage: JourneyStage;
  selectedCoverage: string[];
  insuredPerson: string | null;
  selectedTariff: string | null;
  selectedAddOns: string[];
  visiblePriceMonthly: number | null;
  visiblePriceDaily: number | null;
  priceDeltaMonthly: number | null;
  fieldCompletion: number | null;
  validationErrorCount: number;
  signals: JourneySignal[];
  lastAction: {
    elementKey: string | null;
    type: NormalizedEventType;
    value: Record<string, unknown> | string | number | boolean | null;
  } | null;
  eligibleGoals: JourneyGoal[];
}

export type JourneyCardTone = "info" | "value" | "warning" | "success";

export interface JourneyCard {
  id: string;
  placement: CoachPlacement;
  tone: JourneyCardTone;
  title: string;
  body: string;
  cta: CoachCta | null;
  dismissible: boolean;
}

export type JourneyDomMutationKind =
  | "price_reframe"
  | "tariff_badges"
  | "inline_note"
  | "advisor_progress"
  | "chat_link";

export interface JourneyDomMutation {
  id: string;
  kind: JourneyDomMutationKind;
  placement: CoachPlacement;
  title: string | null;
  body: string | null;
  selector: string | null;
  label: string | null;
  prompt: string | null;
  target: string | null;
}

export interface JourneyDecision {
  decisionId: string;
  goal: JourneyGoal;
  playId: PlayId;
  priority: number;
  cooldownMs: number;
  cards: JourneyCard[];
  domMutations: JourneyDomMutation[];
  chatPrompt: string | null;
}

export interface JourneyOutcome {
  sessionId: string;
  routeFamily: JourneyRouteFamily;
  terminalStage: JourneyStage;
  outcome: "converted_online" | "submitted_advisor_lead" | "abandoned";
  finalTariff: string | null;
  finalPriceMonthly: number | null;
  decidedAt: number;
}

export interface CoachApiStatus {
  endpoint: string;
  lastUpdatedAt: number;
  message: string;
  state: "starting" | "connected" | "error";
}

export interface StepMatchConfig {
  requiredText?: string[];
  requiredSelectorsAll?: string[];
  requiredSelectorsAny?: string[];
}

export interface StepSelectorConfig {
  stepAnchor: string[];
  primaryCta: string[];
  backButton: string[];
  cancelTargets?: string[];
  priceTargets?: string[];
  priceText?: string[];
  outOfScopeTariffButtons?: string[];
  outOfScopePathChoices?: string[];
  addOnCheckboxes?: string[];
}

export interface ExtractorConfig {
  key: keyof DerivedContext;
  kind:
    | "ageBandFromDate"
    | "socialInsuranceProvider"
    | "selectedCoverage"
    | "insuredPerson"
    | "selectedTariff"
    | "selectedAddOns"
    | "fieldCompletion"
    | "validationErrorCount"
    | "visiblePriceMonthly"
    | "priceDeltaMonthly"
    | "sessionTiming";
  selectors?: string[];
  scopeSelector?: string;
}

export interface UniqaPageMapEntry {
  pageStepId: string;
  journeyStage: JourneyStage;
  verified: boolean;
  enabled: boolean;
  match: StepMatchConfig;
  selectors: StepSelectorConfig;
  extractors: ExtractorConfig[];
  injectionAnchor: CoachPlacement;
}

export interface ResolvedStep {
  pageStepId: string;
  journeyStage: JourneyStage;
  injectionAnchor: CoachPlacement;
  config: UniqaPageMapEntry;
}

export interface SessionRecord {
  sessionId: string;
  tabId: number;
  url: string;
  startedAt: number;
  lastSeenAt: number;
}

export interface JourneySessionState {
  routeFamily: JourneyRouteFamily;
  stage: JourneyStage | null;
  baselinePriceMonthly: number | null;
  latestPriceMonthly: number | null;
  selectedCoverage: string[];
  insuredPerson: string | null;
  selectedTariff: string | null;
  selectedAddOns: string[];
  fieldChangeCounts: Record<string, number>;
  lastDerivedContext: DerivedContext;
  lastInteractionAt: number | null;
  lastAction: JourneySnapshot["lastAction"];
  lastShownPlayByStage: Partial<Record<JourneyStage, { playId: PlayId; shownAt: number }>>;
}

export interface RuntimeInitResponse {
  hasChatApiKey: boolean;
  chatModel: string;
  chatModelOptions: string[];
  sessionId: string;
}

export interface RuntimeEventResponse {
  decision: JourneyDecision | null;
  apiStatus: CoachApiStatus;
  snapshot: JourneySnapshot | null;
  signals: JourneySignal[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface RuntimeChatRequest {
  apiKey?: string;
  context: DerivedContext;
  messages: ChatMessage[];
  model?: string;
  routeFamily: JourneyRouteFamily | null;
  stage: JourneyStage | null;
  sessionId: string;
}

export interface RuntimeChatResponse {
  message: ChatMessage;
  error?: string;
}
