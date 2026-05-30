import type {
  JourneyDecision,
  JourneyOutcome,
  JourneySessionState,
  JourneySnapshot,
  NormalizedEvent,
  SessionRecord,
} from "@/shared/contracts";

export const STORAGE_KEYS = {
  events: "uniqa.events",
  journeyState: "uniqa.journeyState",
  outcomes: "uniqa.outcomes",
  session: "uniqa.session",
  snapshots: "uniqa.snapshots",
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
type SnapshotMap = Record<string, JourneySnapshot[]>;
type OutcomeMap = Record<string, JourneyOutcome[]>;
type JourneyStateMap = Record<string, JourneySessionState>;

const DEFAULT_JOURNEY_STATE: JourneySessionState = {
  routeFamily: "online_doctor",
  stage: null,
  baselinePriceMonthly: null,
  latestPriceMonthly: null,
  selectedCoverage: [],
  insuredPerson: null,
  selectedTariff: null,
  selectedAddOns: [],
  fieldChangeCounts: {},
  lastDerivedContext: {},
  lastInteractionAt: null,
  lastAction: null,
  lastShownPlayByStage: {},
};

export class UniqaStorage {
  constructor(
    private readonly adapter: StorageAdapter,
    private readonly maxEntriesPerSession = 200,
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
    const entries = (await this.adapter.get<EventMap>(STORAGE_KEYS.events)) ?? {};
    const sessionEvents = entries[sessionId] ?? [];
    sessionEvents.push(event);
    entries[sessionId] = sessionEvents.slice(-this.maxEntriesPerSession);
    await this.adapter.set(STORAGE_KEYS.events, entries);
    return entries[sessionId];
  }

  async getRecentEvents(sessionId: string, limit = 25): Promise<NormalizedEvent[]> {
    const entries = (await this.adapter.get<EventMap>(STORAGE_KEYS.events)) ?? {};
    return (entries[sessionId] ?? []).slice(-limit);
  }

  async getJourneyState(sessionId: string): Promise<JourneySessionState> {
    const entries = (await this.adapter.get<JourneyStateMap>(STORAGE_KEYS.journeyState)) ?? {};
    return entries[sessionId] ?? createDefaultJourneyState();
  }

  async setJourneyState(sessionId: string, state: JourneySessionState): Promise<void> {
    const entries = (await this.adapter.get<JourneyStateMap>(STORAGE_KEYS.journeyState)) ?? {};
    entries[sessionId] = state;
    await this.adapter.set(STORAGE_KEYS.journeyState, entries);
  }

  async appendSnapshot(sessionId: string, snapshot: JourneySnapshot): Promise<void> {
    const entries = (await this.adapter.get<SnapshotMap>(STORAGE_KEYS.snapshots)) ?? {};
    const sessionSnapshots = entries[sessionId] ?? [];
    sessionSnapshots.push(snapshot);
    entries[sessionId] = sessionSnapshots.slice(-this.maxEntriesPerSession);
    await this.adapter.set(STORAGE_KEYS.snapshots, entries);
  }

  async appendOutcome(sessionId: string, outcome: JourneyOutcome): Promise<void> {
    const entries = (await this.adapter.get<OutcomeMap>(STORAGE_KEYS.outcomes)) ?? {};
    const sessionOutcomes = entries[sessionId] ?? [];
    sessionOutcomes.push(outcome);
    entries[sessionId] = sessionOutcomes.slice(-10);
    await this.adapter.set(STORAGE_KEYS.outcomes, entries);
  }

  async markDecisionShown(
    sessionId: string,
    stage: NonNullable<JourneySessionState["stage"]>,
    decision: JourneyDecision,
    shownAt: number,
  ): Promise<void> {
    const state = await this.getJourneyState(sessionId);
    const next: JourneySessionState = {
      ...state,
      fieldChangeCounts: { ...state.fieldChangeCounts },
      lastDerivedContext: { ...state.lastDerivedContext },
      selectedAddOns: [...state.selectedAddOns],
      selectedCoverage: [...state.selectedCoverage],
      lastShownPlayByStage: {
        ...state.lastShownPlayByStage,
        [stage]: {
          playId: decision.playId,
          shownAt,
        },
      },
    };
    await this.setJourneyState(sessionId, next);
  }
}

function createDefaultJourneyState(): JourneySessionState {
  return {
    ...DEFAULT_JOURNEY_STATE,
    fieldChangeCounts: {},
    lastDerivedContext: {},
    selectedAddOns: [],
    selectedCoverage: [],
    lastShownPlayByStage: {},
  };
}
