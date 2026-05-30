import type {
  JourneyOutcome,
  NormalizedEvent,
  RuntimeChatRequest,
  RuntimeEventResponse,
  RuntimeInitResponse,
} from "@/shared/contracts";
import { CoachClient } from "@/background/coach-client";
import { FeatherlessChatClient } from "@/background/featherless-chat-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { ChromeStorageAdapter, UniqaStorage } from "@/background/storage";
import { createLogger } from "@/shared/logger";

const log = createLogger("background");

type RuntimeMessage =
  | {
      type: "uniqa:event";
      event: NormalizedEvent;
      url: string;
    }
  | {
      type: "uniqa:chat";
      request: RuntimeChatRequest;
    }
  | {
      type: "uniqa:outcome";
      outcome: JourneyOutcome;
    }
  | {
      type: "uniqa:init";
      preferredSessionId?: string;
      url: string;
    };

const storage = new UniqaStorage(new ChromeStorageAdapter());
const orchestrator = new UniqaEventOrchestrator(storage, new CoachClient());
const chatClient = new FeatherlessChatClient();

chrome.runtime.onMessage.addListener((message: RuntimeMessage, sender, sendResponse) => {
  if (message.type === "uniqa:init") {
    void handleInit(message, sender.tab?.id ?? -1)
      .then(sendResponse)
      .catch((error) => {
        console.error("[UNIQA Coach] Init failed.", error);
        sendResponse(null);
      });
    return true;
  }

  if (message.type === "uniqa:event") {
    void orchestrator.handleEvent(message.event, message.url)
      .then(sendResponse)
      .catch((error) => {
        log.error("Event handling failed", {
          error: error instanceof Error ? error.message : String(error),
          type: message.event?.type,
        });
        sendResponse({
          apiStatus: {
            endpoint: "chrome.runtime",
            lastUpdatedAt: Date.now(),
            message: error instanceof Error ? error.message : "Unknown extension runtime error",
            state: "error",
          },
          decision: null,
          snapshot: null,
          signals: [],
        } satisfies RuntimeEventResponse);
      });
    return true;
  }

  if (message.type === "uniqa:outcome") {
    void orchestrator.finalizeOutcome(message.outcome)
      .then(sendResponse)
      .catch((error) => {
        log.error("Outcome handling failed", {
          error: error instanceof Error ? error.message : String(error),
        });
        sendResponse({
          endpoint: "chrome.runtime",
          lastUpdatedAt: Date.now(),
          message: error instanceof Error ? error.message : "Unknown extension runtime error",
          state: "error",
        });
      });
    return true;
  }

  if (message.type === "uniqa:chat") {
    void chatClient.chat(message.request)
      .then(sendResponse)
      .catch((error) => {
        log.error("Chat failed", {
          error: error instanceof Error ? error.message : String(error),
        });
        sendResponse({
          error: "chat_failed",
          message: {
            role: "assistant",
            content: "The chat failed unexpectedly. Reload the extension and try again.",
          },
        });
      });
    return true;
  }

  return false;
});

async function handleInit(
  message: Extract<RuntimeMessage, { type: "uniqa:init" }>,
  tabId: number,
): Promise<RuntimeInitResponse> {
  const session = await storage.ensureSession(tabId, message.url, message.preferredSessionId);
  log.info("Session initialized", {
    sessionId: session.sessionId,
    tabId,
    url: message.url,
  });
  return {
    chatModel: chatClient.getModelName(),
    chatModelOptions: chatClient.getModelOptions(),
    hasChatApiKey: await chatClient.hasConfiguredApiKey(),
    sessionId: session.sessionId,
  };
}
