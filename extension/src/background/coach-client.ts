import type {
  CoachApiStatus,
  JourneyDecision,
  JourneyOutcome,
  JourneySnapshot,
} from "@/shared/contracts";
import { createLogger } from "@/shared/logger";

const log = createLogger("runtime-client");

const DEFAULT_ORIGIN = (
  import.meta.env?.VITE_COACH_API_ORIGIN ?? "http://127.0.0.1:8787"
).replace(/\/+$/, "");

export interface RuntimeDecisionResult {
  apiStatus: CoachApiStatus;
  decision: JourneyDecision | null;
}

export class CoachClient {
  constructor(
    private readonly decideEndpoint = `${DEFAULT_ORIGIN}/api/runtime/decide`,
    private readonly outcomeEndpoint = `${DEFAULT_ORIGIN}/api/runtime/outcome`,
    private readonly fetchImpl: typeof fetch = (input, init) => globalThis.fetch(input, init),
  ) {}

  async decide(snapshot: JourneySnapshot): Promise<RuntimeDecisionResult> {
    try {
      const response = await this.fetchImpl(this.decideEndpoint, {
        body: JSON.stringify(snapshot),
        headers: {
          "Content-Type": "application/json",
        },
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Runtime API returned ${response.status}`);
      }

      const parsed = (await response.json()) as { decision?: JourneyDecision | null };
      return {
        apiStatus: {
          endpoint: this.decideEndpoint,
          lastUpdatedAt: Date.now(),
          message: "Connected to runtime API",
          state: "connected",
        },
        decision: parsed.decision ?? null,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown runtime API error";
      log.error("Runtime decide request failed", {
        endpoint: this.decideEndpoint,
        message,
      });
      return {
        apiStatus: {
          endpoint: this.decideEndpoint,
          lastUpdatedAt: Date.now(),
          message,
          state: "error",
        },
        decision: null,
      };
    }
  }

  async sendOutcome(outcome: JourneyOutcome): Promise<CoachApiStatus> {
    try {
      const response = await this.fetchImpl(this.outcomeEndpoint, {
        body: JSON.stringify(outcome),
        headers: {
          "Content-Type": "application/json",
        },
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Runtime API returned ${response.status}`);
      }
      return {
        endpoint: this.outcomeEndpoint,
        lastUpdatedAt: Date.now(),
        message: "Outcome stored",
        state: "connected",
      };
    } catch (error) {
      return {
        endpoint: this.outcomeEndpoint,
        lastUpdatedAt: Date.now(),
        message: error instanceof Error ? error.message : "Unknown runtime API error",
        state: "error",
      };
    }
  }
}
