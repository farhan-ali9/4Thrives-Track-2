import type {
  CoachRuntimeState,
  NormalizedEvent,
  SessionRecord,
  StepRuntimeState,
} from "@/shared/contracts";

export const STORAGE_KEYS = {
  coachState: "uniqa.coachState",
  events: "uniqa.events",
  session: "uniqa.session",
  stepState: "uniqa.stepState",
} as const;

export interface StorageAdapter {
  get<T>(key: string): Promise<T | undefined>;
  set<T>(key: string, value: T): Promise<void>;
}

export class ChromeStorageAdapter implements StorageAdapter {
  async get<T>(key: string): Promise<T | undefined> {
    const result = await chrome.storage.local.get(key);
    return result[key] as T | undefined;
  }

  async set<T>(key: string, value: T): Promise<void> {
    await chrome.storage.local.set({ [key]: value });
  }
}

export class MemoryStorageAdapter implements StorageAdapter {
  private readonly store = new Map<string, unknown>();

  async get<T>(key: string): Promise<T | undefined> {
    return this.store.get(key) as T | undefined;
  }

  async set<T>(key: string, value: T): Promise<void> {
    this.store.set(key, value);
  }
}

type SessionMap = Record<string, SessionRecord>;
type EventMap = Record<string, NormalizedEvent[]>;
type StepStateMap = Record<string, StepRuntimeState>;
type CoachStateMap = Record<string, CoachRuntimeState>;

const DEFAULT_STEP_STATE: StepRuntimeState = {
  currentCoachStepId: null,
  currentStepId: null,
  fieldChangeCounts: {},
  initialVisiblePrice: null,
  lastActivityAt: null,
  lastDerivedContext: {},
  lastVisiblePrice: null,
  selectedAddOns: [],
  selectedTariff: null,
  stepEnteredAt: null,
};

const DEFAULT_COACH_STATE: CoachRuntimeState = {
  shownActionTimestamps: {},
};

export class UniqaStorage {
  constructor(
    private readonly adapter: StorageAdapter,
    private readonly maxEventsPerSession = 200,
  ) {}

  async ensureSession(tabId: number, url: string, preferredSessionId?: string): Promise<SessionRecord> {
    const sessions = (await this.adapter.get<SessionMap>(STORAGE_KEYS.session)) ?? {};
    const tabKey = String(tabId);
    const existing = sessions[tabKey];
    const nextSession: SessionRecord = {
      sessionId: preferredSessionId ?? existing?.sessionId ?? `uniqa_${tabId}_${Date.now()}`,
      tabId,
      url,
      startedAt: existing?.startedAt ?? Date.now(),
      lastSeenAt: Date.now(),
    };

    sessions[tabKey] = nextSession;
    await this.adapter.set(STORAGE_KEYS.session, sessions);
    return nextSession;
  }

  async appendEvent(sessionId: string, event: NormalizedEvent): Promise<NormalizedEvent[]> {
    const events = (await this.adapter.get<EventMap>(STORAGE_KEYS.events)) ?? {};
    const sessionEvents = events[sessionId] ?? [];
    sessionEvents.push(event);
    events[sessionId] = sessionEvents.slice(-this.maxEventsPerSession);
    await this.adapter.set(STORAGE_KEYS.events, events);
    return events[sessionId];
  }

  async getRecentEvents(sessionId: string, limit = 25): Promise<NormalizedEvent[]> {
    const events = (await this.adapter.get<EventMap>(STORAGE_KEYS.events)) ?? {};
    return (events[sessionId] ?? []).slice(-limit);
  }

  async getStepState(sessionId: string): Promise<StepRuntimeState> {
    const state = (await this.adapter.get<StepStateMap>(STORAGE_KEYS.stepState)) ?? {};
    return state[sessionId] ?? createDefaultStepState();
  }

  async setStepState(sessionId: string, stepState: StepRuntimeState): Promise<void> {
    const state = (await this.adapter.get<StepStateMap>(STORAGE_KEYS.stepState)) ?? {};
    state[sessionId] = stepState;
    await this.adapter.set(STORAGE_KEYS.stepState, state);
  }

  async getCoachState(sessionId: string): Promise<CoachRuntimeState> {
    const state = (await this.adapter.get<CoachStateMap>(STORAGE_KEYS.coachState)) ?? {};
    return state[sessionId] ?? createDefaultCoachState();
  }

  async setCoachState(sessionId: string, coachState: CoachRuntimeState): Promise<void> {
    const state = (await this.adapter.get<CoachStateMap>(STORAGE_KEYS.coachState)) ?? {};
    state[sessionId] = coachState;
    await this.adapter.set(STORAGE_KEYS.coachState, state);
  }
}

function createDefaultStepState(): StepRuntimeState {
  return {
    ...DEFAULT_STEP_STATE,
    fieldChangeCounts: {},
    lastDerivedContext: {},
    selectedAddOns: [],
  };
}

function createDefaultCoachState(): CoachRuntimeState {
  return {
    shownActionTimestamps: {},
  };
}
