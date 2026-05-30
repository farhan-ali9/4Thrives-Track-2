import type { RuntimeChatRequest, RuntimeChatResponse } from "@/shared/contracts";

const FEATHERLESS_ENDPOINT = "https://api.featherless.ai/v1/chat/completions";
const DEFAULT_MODEL = __FEATHERLESS_MODEL__;
const MODEL_OPTIONS = __FEATHERLESS_MODEL_OPTIONS__;
const BUILD_TIME_API_KEY = __FEATHERLESS_API_KEY__;
const STORAGE_KEY = "uniqa.featherlessApiKey";
const MODEL_STORAGE_KEY = "uniqa.featherlessModel";

interface FeatherlessResponse {
  choices?: Array<{
    message?: {
      content?: string;
    };
  }>;
}

export class FeatherlessChatClient {
  constructor(private readonly fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)) {}

  getModelName(): string {
    return DEFAULT_MODEL;
  }

  getModelOptions(): string[] {
    return MODEL_OPTIONS.length ? MODEL_OPTIONS : [DEFAULT_MODEL];
  }

  async hasConfiguredApiKey(): Promise<boolean> {
    return (await this.resolveApiKey()) !== null;
  }

  async chat(request: RuntimeChatRequest): Promise<RuntimeChatResponse> {
    const apiKey = await this.resolveApiKey(request.apiKey);
    if (!apiKey) {
      return {
        error: "missing_api_key",
        message: {
          role: "assistant",
          content: "Add your Featherless API key in the chat settings, then send the question again.",
        },
      };
    }

    const model = await this.resolveModel(request.model);

    try {
      const response = await this.fetchImpl(FEATHERLESS_ENDPOINT, {
        body: JSON.stringify({
          messages: [
            {
              role: "system",
              content: buildSystemPrompt(request, model),
            },
            ...request.messages.map((message) => ({
              content: message.content,
              role: message.role,
            })),
          ],
          model,
          temperature: 0.35,
        }),
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        method: "POST",
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(formatFeatherlessError(response.status, body, model));
      }

      const parsed = (await response.json()) as FeatherlessResponse;
      const content = parsed.choices?.[0]?.message?.content?.trim();
      return {
        message: {
          role: "assistant",
          content: content || "I could not generate an answer for that. Try asking in a simpler way.",
        },
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "chat_failed",
        message: {
          role: "assistant",
          content: error instanceof Error
            ? error.message
            : "I could not reach the Featherless model right now. Check the API key or network, then try again.",
        },
      };
    }
  }

  private async resolveApiKey(candidate?: string): Promise<string | null> {
    const trimmed = candidate?.trim();
    if (trimmed) {
      await chrome.storage.local.set({ [STORAGE_KEY]: trimmed });
      return trimmed;
    }

    const buildTimeKey = BUILD_TIME_API_KEY.trim();
    if (buildTimeKey) {
      return buildTimeKey;
    }

    const stored = await chrome.storage.local.get(STORAGE_KEY);
    const value = stored[STORAGE_KEY];
    return typeof value === "string" && value.trim() ? value.trim() : null;
  }

  private async resolveModel(candidate?: string): Promise<string> {
    const trimmed = candidate?.trim();
    if (trimmed) {
      await chrome.storage.local.set({ [MODEL_STORAGE_KEY]: trimmed });
      return trimmed;
    }

    const stored = await chrome.storage.local.get(MODEL_STORAGE_KEY);
    const value = stored[MODEL_STORAGE_KEY];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }

    return DEFAULT_MODEL;
  }
}

function buildSystemPrompt(request: RuntimeChatRequest, model: string): string {
  return [
    "You are the UNIQA Conversion Coach chat assistant embedded in the health-insurance calculator.",
    "Help the user understand the current step, private-doctor tariffs, price changes, and online completion.",
    "Keep answers concise, practical, and reassuring. Do not claim to be a licensed advisor.",
    "Scope: Start and Optimal can be completed online. Hospital, other persons, Opt. Plus, and Premium require advisor routing.",
    `Current model id: ${model}. If the user asks which model you are using, answer with this exact model id.`,
    `Current page step: ${request.pageStepId ?? "unknown"}.`,
    `Known context: ${JSON.stringify(request.context)}`,
  ].join("\n");
}

function formatFeatherlessError(status: number, body: string, model: string): string {
  const parsedMessage = parseFeatherlessMessage(body);
  const message = parsedMessage || `Featherless API returned ${status}.`;
  if (status === 403 && /gated|verify access|huggingface/i.test(message)) {
    return `The selected model (${model}) is gated on Featherless. Choose another model from the dropdown, or connect HuggingFace access for this model in Featherless.`;
  }
  if (status === 401 || status === 403) {
    return `Featherless rejected the request for ${model}: ${message}`;
  }
  return `Featherless could not run ${model}: ${message}`;
}

function parseFeatherlessMessage(body: string): string | null {
  if (!body.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(body) as { error?: { message?: unknown } };
    return typeof parsed.error?.message === "string" ? parsed.error.message : null;
  } catch {
    return body.slice(0, 220);
  }
}
