import type {
  NormalizedEvent,
  RuntimeChatRequest,
  RuntimeEventResponse,
  RuntimeInitResponse,
} from "@/shared/contracts";
import { CoachClient } from "@/background/coach-client";
import { FeatherlessChatClient } from "@/background/featherless-chat-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { ChromeStorageAdapter, UniqaStorage } from "@/background/storage";

type RuntimeMessage =
  | {
      type: "uniqa:event";
      event: NormalizedEvent;
    }
  | {
      type: "uniqa:chat";
      request: RuntimeChatRequest;
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
    void orchestrator.handleEvent(message.event)
      .then(sendResponse)
      .catch((error) => {
        console.error("[UNIQA Coach] Event handling failed.", error);
        sendResponse({
          actions: [],
          apiStatus: {
            endpoint: "chrome.runtime",
            lastUpdatedAt: Date.now(),
            message: error instanceof Error ? error.message : "Unknown extension runtime error",
            policyVersion: null,
            state: "error",
          },
          signals: [],
        } satisfies RuntimeEventResponse);
      });
    return true;
  }

  if (message.type === "uniqa:chat") {
    void chatClient.chat(message.request)
      .then(sendResponse)
      .catch((error) => {
        console.error("[UNIQA Coach] Chat failed.", error);
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
  return {
    chatModel: chatClient.getModelName(),
    chatModelOptions: chatClient.getModelOptions(),
    hasChatApiKey: await chatClient.hasConfiguredApiKey(),
    sessionId: session.sessionId,
  };
}
