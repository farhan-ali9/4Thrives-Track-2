import type { CoachRequest, CoachResponse } from "@/shared/contracts";
import { evaluateCoachRequest } from "@/shared/mock-coach-engine";

const DEFAULT_ENDPOINT = "http://127.0.0.1:8787/evaluate";

export class CoachClient {
  constructor(
    private readonly endpoint = DEFAULT_ENDPOINT,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  async evaluate(request: CoachRequest): Promise<CoachResponse> {
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
      return {
        ...parsed,
        source: "remote",
      };
    } catch {
      return evaluateCoachRequest(request);
    }
  }
}
