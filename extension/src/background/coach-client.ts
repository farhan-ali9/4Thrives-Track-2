import type {
  CoachApiStatus,
  CoachRequest,
  CoachResponse,
  NormalizedEvent,
  SignalKind,
} from "@/shared/contracts";
import { createLogger } from "@/shared/logger";

const log = createLogger("coach-client");

const DEFAULT_ORIGIN = (
  import.meta.env?.VITE_COACH_API_ORIGIN ?? "http://127.0.0.1:8787"
).replace(/\/+$/, "");
const DEFAULT_V2_ENDPOINT = `${DEFAULT_ORIGIN}/api/v2/events`;
const DEFAULT_LEGACY_ENDPOINT = `${DEFAULT_ORIGIN}/api/v1/coach/evaluate`;

export interface CoachEvaluationResult {
  apiStatus: CoachApiStatus;
  response: CoachResponse;
}

export interface CoachEvaluationInput {
  event: NormalizedEvent;
  fallbackRequest: CoachRequest;
  signals: SignalKind[];
}

export class CoachClient {
  constructor(
    private readonly primaryEndpoint = DEFAULT_V2_ENDPOINT,
    private readonly legacyEndpoint = DEFAULT_LEGACY_ENDPOINT,
    private readonly fetchImpl: typeof fetch = (input, init) => globalThis.fetch(input, init),
  ) {}

  async evaluate(input: CoachEvaluationInput): Promise<CoachEvaluationResult> {
    log.debug("POST coach event", {
      endpoint: this.primaryEndpoint,
      eventType: input.event.type,
      signals: input.signals,
      stepId: input.event.pageStepId,
    });
    try {
      const response = await this.fetchImpl(this.primaryEndpoint, {
        body: JSON.stringify(buildV2EventPayload(input.event, input.signals)),
        headers: {
          "Content-Type": "application/json",
        },
        method: "POST",
      });

      if (response.status === 404 || response.status === 405) {
        log.warn("Primary v2 endpoint unavailable; falling back to legacy", {
          endpoint: this.primaryEndpoint,
          status: response.status,
        });
        return await this.evaluateLegacy(input.fallbackRequest);
      }

      if (!response.ok) {
        throw new Error(`Coach API returned ${response.status}`);
      }

      const parsed = (await response.json()) as {
        actions?: CoachResponse["actions"];
      };
      const apiStatus: CoachApiStatus = {
        endpoint: this.primaryEndpoint,
        lastUpdatedAt: Date.now(),
        message: "Connected to coach API (v2 events)",
        policyVersion: null,
        state: "connected",
      };
      log.info("Coach API connected (v2 events)", {
        actions: parsed.actions?.length ?? 0,
        endpoint: this.primaryEndpoint,
      });
      return {
        apiStatus,
        response: {
          actions: parsed.actions ?? [],
          policyVersion: null,
          source: "remote",
        },
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown coach API error";
      const apiStatus: CoachApiStatus = {
        endpoint: this.primaryEndpoint,
        lastUpdatedAt: Date.now(),
        message,
        policyVersion: null,
        state: "error",
      };
      log.error("Coach API request failed", {
        endpoint: this.primaryEndpoint,
        message,
      });
      return {
        apiStatus,
        response: {
          actions: [],
          policyVersion: null,
          source: "remote_error",
        },
      };
    }
  }

  private async evaluateLegacy(request: CoachRequest): Promise<CoachEvaluationResult> {
    const response = await this.fetchImpl(this.legacyEndpoint, {
      body: JSON.stringify(request),
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Coach API returned ${response.status}`);
    }

    const parsed = (await response.json()) as CoachResponse;
    const apiStatus: CoachApiStatus = {
      endpoint: this.legacyEndpoint,
      lastUpdatedAt: Date.now(),
      message: `Connected to coach API${parsed.policyVersion !== null ? ` (policy v${parsed.policyVersion})` : ""}`,
      policyVersion: parsed.policyVersion,
      state: "connected",
    };
    log.info("Coach API connected (legacy evaluate)", {
      actions: parsed.actions?.length ?? 0,
      endpoint: this.legacyEndpoint,
      policyVersion: parsed.policyVersion,
    });
    return {
      apiStatus,
      response: parsed,
    };
  }
}

function buildV2EventPayload(event: NormalizedEvent, signals: SignalKind[]): Record<string, unknown> {
  return {
    schema_version: "v1",
    event_id: event.id,
    session_id: event.sessionId,
    ts: event.ts,
    source: "extension",
    step_id: event.pageStepId,
    event_type: event.type,
    element_key: event.elementKey,
    raw_value: normalizeRawValue(event.value),
    derived_signals: Object.fromEntries(signals.map((signal) => [signal, true])),
    derived_context: event.derivedContext,
    runner_metadata: {},
    privacy_level: "anonymous",
  };
}

function normalizeRawValue(value: NormalizedEvent["value"]): Record<string, unknown> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value;
  }

  if (value === null) {
    return {};
  }

  return { value };
}
