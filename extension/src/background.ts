import type { NormalizedEvent, RuntimeEventResponse, RuntimeInitResponse } from "@/shared/contracts";
import { CoachClient } from "@/background/coach-client";
import { UniqaEventOrchestrator } from "@/background/orchestrator";
import { ChromeStorageAdapter, UniqaStorage } from "@/background/storage";

type RuntimeMessage =
  | {
      type: "uniqa:event";
      event: NormalizedEvent;
    }
  | {
      type: "uniqa:init";
      preferredSessionId?: string;
      url: string;
    };

const storage = new UniqaStorage(new ChromeStorageAdapter());
const orchestrator = new UniqaEventOrchestrator(storage, new CoachClient());

chrome.runtime.onMessage.addListener((message: RuntimeMessage, sender, sendResponse) => {
  if (message.type === "uniqa:init") {
    void handleInit(message, sender.tab?.id ?? -1).then(sendResponse);
    return true;
  }

  if (message.type === "uniqa:event") {
    void orchestrator.handleEvent(message.event).then(sendResponse);
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
    sessionId: session.sessionId,
  };
}
