import type { CoachApiStatus, CoachRequest, CoachResponse } from "@/shared/contracts";

const DEFAULT_ORIGIN = (
  import.meta.env?.VITE_COACH_API_ORIGIN ?? "http://127.0.0.1:8787"
).replace(/\/+$/, "");
const DEFAULT_ENDPOINT = `${DEFAULT_ORIGIN}/api/v1/coach/evaluate`;

export interface CoachEvaluationResult {
  apiStatus: CoachApiStatus;
  response: CoachResponse;
}

export class CoachClient {
  constructor(
    private readonly endpoint = DEFAULT_ENDPOINT,
    private readonly fetchImpl: typeof fetch = (input, init) => globalThis.fetch(input, init),
  ) {}

  async evaluate(request: CoachRequest): Promise<CoachEvaluationResult> {
    try {
      const response = await this.fetchImpl(this.endpoint, {
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
        endpoint: this.endpoint,
        lastUpdatedAt: Date.now(),
        message: `Connected to coach API${parsed.policyVersion !== null ? ` (policy v${parsed.policyVersion})` : ""}`,
        policyVersion: parsed.policyVersion,
        state: "connected",
      };
      console.info("[UNIQA Coach] API connected", apiStatus);
      return {
        apiStatus,
        response: parsed,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown coach API error";
      const apiStatus: CoachApiStatus = {
        endpoint: this.endpoint,
        lastUpdatedAt: Date.now(),
        message,
        policyVersion: null,
        state: "error",
      };
      console.warn("[UNIQA Coach] API error", apiStatus);
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
}
