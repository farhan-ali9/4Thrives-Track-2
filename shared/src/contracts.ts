export type CoachPlacement =
  | "inline-top-of-step"
  | "near-primary-cta"
  | "bottom-toast";

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

export type SignalKind =
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
  selectedTariff?: string | null;
  selectedAddOns?: string[];
  fieldCompletion?: number | null;
  validationErrorCount?: number;
  visiblePrice?: number | null;
  priceDelta?: number | null;
  sessionDurationMs?: number;
  lastInteractionMs?: number;
}

export interface NormalizedEvent {
  id: string;
  sessionId: string;
  ts: number;
  pageStepId: string | null;
  coachStepId: string | null;
  type: NormalizedEventType;
  elementKey: string | null;
  value: Record<string, unknown> | string | number | boolean | null;
  derivedContext: DerivedContext;
  dwellMs: number | null;
}

export interface CurrentOffer {
  visiblePrice: number | null;
  priceDelta: number | null;
  selectedTariff: string | null;
}

export interface CoachRequest {
  sessionId: string;
  pageStepId: string | null;
  coachStepId: string | null;
  recentEvents: NormalizedEvent[];
  detectedSignals: SignalKind[];
  derivedContext: DerivedContext;
  currentOffer: CurrentOffer;
}

export interface CoachAction {
  id: string;
  kind: string;
  placement: CoachPlacement;
  title: string;
  body: string;
  ctaLabel: string | null;
  dismissible: boolean;
  cooldownMs: number;
}

export interface CoachResponse {
  actions: CoachAction[];
  source: "remote" | "remote_error";
  policyVersion: number | null;
}

export interface CoachApiStatus {
  endpoint: string;
  lastUpdatedAt: number;
  message: string;
  policyVersion: number | null;
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
    | "selectedTariff"
    | "selectedAddOns"
    | "fieldCompletion"
    | "validationErrorCount"
    | "visiblePrice"
    | "priceDelta"
    | "sessionTiming";
  selectors?: string[];
  scopeSelector?: string;
}

export interface UniqaPageMapEntry {
  pageStepId: string;
  coachStepId: string;
  verified: boolean;
  enabled: boolean;
  match: StepMatchConfig;
  selectors: StepSelectorConfig;
  extractors: ExtractorConfig[];
  injectionAnchor: CoachPlacement;
}

export interface ResolvedStep {
  pageStepId: string;
  coachStepId: string;
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

export interface StepRuntimeState {
  currentStepId: string | null;
  currentCoachStepId: string | null;
  stepEnteredAt: number | null;
  lastActivityAt: number | null;
  lastVisiblePrice: number | null;
  initialVisiblePrice: number | null;
  selectedTariff: string | null;
  selectedAddOns: string[];
  fieldChangeCounts: Record<string, number>;
  lastDerivedContext: DerivedContext;
}

export interface CoachRuntimeState {
  shownActionTimestamps: Record<string, number>;
}

export interface RuntimeInitResponse {
  sessionId: string;
}

export interface RuntimeEventResponse {
  actions: CoachAction[];
  apiStatus: CoachApiStatus;
  signals: SignalKind[];
}
