import type {
  ChatMessage,
  CoachApiStatus,
  JourneyDecision,
  ResolvedStep,
} from "@/shared/contracts";

const ROOT_ID = "uniqa-conversion-coach-root";

const STYLES = `
  :host {
    all: initial;
  }

  .layer {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 2147483646;
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  .status {
    position: fixed;
    left: 14px;
    bottom: 14px;
    display: grid;
    gap: 8px;
    pointer-events: auto;
  }

  .pill {
    border: 0;
    border-radius: 999px;
    background: rgba(6, 23, 56, 0.94);
    color: #fff;
    padding: 8px 12px;
    display: inline-flex;
    gap: 8px;
    align-items: center;
    cursor: pointer;
    box-shadow: 0 12px 28px rgba(6, 23, 56, 0.24);
  }

  .pill[data-state="connected"] {
    background: rgba(27, 102, 59, 0.96);
  }

  .pill[data-state="error"] {
    background: rgba(150, 36, 48, 0.96);
  }

  .panel {
    display: none;
    max-width: 320px;
    background: rgba(6, 23, 56, 0.96);
    color: #fff;
    border-radius: 16px;
    padding: 14px;
    box-shadow: 0 18px 42px rgba(6, 23, 56, 0.28);
  }

  .panel[data-open="true"] {
    display: block;
  }

  .panel-title {
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
  }

  .panel-copy, .log-entry {
    font-size: 12px;
    line-height: 1.4;
    color: rgba(255, 255, 255, 0.84);
  }

  .log-entry + .log-entry {
    margin-top: 6px;
  }

  .card-wrap {
    position: fixed;
    right: 16px;
    bottom: 86px;
    max-width: 340px;
    pointer-events: auto;
  }

  .card {
    background: linear-gradient(135deg, #07163a 0%, #0e699b 100%);
    color: #fff;
    border-radius: 18px;
    padding: 14px;
    box-shadow: 0 18px 42px rgba(6, 23, 56, 0.28);
  }

  .card-title {
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 6px;
  }

  .card-body {
    font-size: 13px;
    line-height: 1.45;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 12px;
  }

  .card-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .card-cta,
  .card-dismiss,
  .chat-send,
  .chat-prompt {
    border: 0;
    border-radius: 999px;
    font: inherit;
    cursor: pointer;
  }

  .card-cta,
  .chat-send,
  .chat-prompt {
    background: #fff;
    color: #07163a;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 12px;
  }

  .card-dismiss {
    background: transparent;
    color: rgba(255, 255, 255, 0.84);
    text-decoration: underline;
    font-size: 13px;
    padding: 8px 0;
  }

  .chat-dock {
    position: fixed;
    right: 14px;
    bottom: 14px;
    pointer-events: auto;
  }

  .chat-launcher {
    width: 48px;
    height: 48px;
    border-radius: 999px;
    border: 0;
    background: #07163a;
    color: #fff;
    font-size: 18px;
    font-weight: 800;
    cursor: pointer;
    box-shadow: 0 12px 28px rgba(6, 23, 56, 0.24);
  }

  .chat-panel {
    display: none;
    width: min(360px, calc(100vw - 28px));
    height: 430px;
    margin-bottom: 12px;
    background: #fff;
    color: #10203d;
    border-radius: 20px;
    box-shadow: 0 24px 60px rgba(6, 23, 56, 0.28);
    overflow: hidden;
  }

  .chat-panel[data-open="true"] {
    display: grid;
    grid-template-rows: auto auto 1fr auto;
  }

  .chat-header {
    padding: 14px 16px 8px;
    border-bottom: 1px solid rgba(6, 23, 56, 0.08);
  }

  .chat-title {
    font-size: 14px;
    font-weight: 700;
  }

  .chat-subtitle {
    margin-top: 4px;
    font-size: 12px;
    color: #5a6b85;
  }

  .chat-prompts {
    display: flex;
    gap: 8px;
    padding: 10px 14px;
    overflow-x: auto;
    border-bottom: 1px solid rgba(6, 23, 56, 0.08);
  }

  .chat-messages {
    padding: 14px;
    overflow: auto;
    display: grid;
    gap: 10px;
    background: #f4f7fb;
  }

  .chat-msg {
    padding: 10px 12px;
    border-radius: 14px;
    font-size: 13px;
    line-height: 1.45;
    max-width: 88%;
    white-space: pre-wrap;
  }

  .chat-msg[data-role="assistant"] {
    background: #fff;
    color: #10203d;
    justify-self: start;
  }

  .chat-msg[data-role="user"] {
    background: #07163a;
    color: #fff;
    justify-self: end;
  }

  .chat-form {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px;
    padding: 12px;
    border-top: 1px solid rgba(6, 23, 56, 0.08);
  }

  .chat-input {
    border-radius: 14px;
    border: 1px solid rgba(6, 23, 56, 0.16);
    padding: 10px 12px;
    font: inherit;
    font-size: 13px;
  }
`;

export interface RenderInteraction {
  cta: string | null;
  decision: JourneyDecision;
  result: "dismissed" | "sent" | "clicked";
  type: "coach_cta" | "coach_dismiss";
}

interface ChatRequestPayload {
  apiKey?: string;
  messages: ChatMessage[];
  model?: string;
}

export class DomInjector {
  private readonly root: HTMLDivElement;
  private readonly shadow: ShadowRoot;
  private readonly layer: HTMLDivElement;
  private readonly statusPill: HTMLButtonElement;
  private readonly statusPanel: HTMLDivElement;
  private readonly statusLog: HTMLDivElement;
  private readonly cardWrap: HTMLDivElement;
  private readonly chatDock: HTMLDivElement;
  private readonly chatPanel: HTMLDivElement;
  private readonly chatMessages: HTMLDivElement;
  private readonly chatPrompts: HTMLDivElement;
  private readonly chatInput: HTMLInputElement;
  private readonly chatSend: HTMLButtonElement;
  private readonly chatLauncher: HTMLButtonElement;
  private readonly hasChatApiKey: boolean;
  private readonly chatModel: string;
  private readonly chatModelOptions: string[];
  private readonly onInteraction: (interaction: RenderInteraction) => void;
  private readonly onChatRequest: (request: ChatRequestPayload) => Promise<ChatMessage>;
  private currentDecision: JourneyDecision | null = null;
  private chatOpen = false;
  private chatMessagesState: ChatMessage[] = [];

  constructor(
    onInteraction: (interaction: RenderInteraction) => void,
    onChatRequest: (request: ChatRequestPayload) => Promise<ChatMessage>,
    hasChatApiKey: boolean,
    chatModel: string,
    chatModelOptions: string[],
  ) {
    this.onInteraction = onInteraction;
    this.onChatRequest = onChatRequest;
    this.hasChatApiKey = hasChatApiKey;
    this.chatModel = chatModel;
    this.chatModelOptions = chatModelOptions;

    this.root = document.getElementById(ROOT_ID) as HTMLDivElement | null ?? document.createElement("div");
    this.root.id = ROOT_ID;
    if (!this.root.isConnected) {
      document.documentElement.appendChild(this.root);
    }
    this.shadow = this.root.shadowRoot ?? this.root.attachShadow({ mode: "open" });
    this.shadow.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLES;
    this.layer = document.createElement("div");
    this.layer.className = "layer";

    const status = document.createElement("div");
    status.className = "status";
    this.statusPill = document.createElement("button");
    this.statusPill.className = "pill";
    this.statusPill.dataset.state = "starting";
    this.statusPill.textContent = "UNIQA Runtime";
    this.statusPill.addEventListener("click", () => {
      this.statusPanel.dataset.open = this.statusPanel.dataset.open === "true" ? "false" : "true";
    });

    this.statusPanel = document.createElement("div");
    this.statusPanel.className = "panel";
    this.statusPanel.dataset.open = "false";
    const statusTitle = document.createElement("div");
    statusTitle.className = "panel-title";
    statusTitle.textContent = "Runtime status";
    const statusCopy = document.createElement("div");
    statusCopy.className = "panel-copy";
    statusCopy.textContent = "The extension decides locally, then asks the runtime API for one conversion play.";
    this.statusLog = document.createElement("div");
    this.statusPanel.append(statusTitle, statusCopy, this.statusLog);
    status.append(this.statusPill, this.statusPanel);

    this.cardWrap = document.createElement("div");
    this.cardWrap.className = "card-wrap";

    this.chatDock = document.createElement("div");
    this.chatDock.className = "chat-dock";
    this.chatPanel = document.createElement("div");
    this.chatPanel.className = "chat-panel";
    this.chatPanel.dataset.open = "false";
    const chatHeader = document.createElement("div");
    chatHeader.className = "chat-header";
    const chatTitle = document.createElement("div");
    chatTitle.className = "chat-title";
    chatTitle.textContent = "Conversion Coach";
    const chatSubtitle = document.createElement("div");
    chatSubtitle.className = "chat-subtitle";
    chatSubtitle.textContent = this.hasChatApiKey
      ? `Chat model: ${this.chatModelOptions[0] ?? this.chatModel}`
      : "Chat is available after adding an API key.";
    chatHeader.append(chatTitle, chatSubtitle);
    this.chatPrompts = document.createElement("div");
    this.chatPrompts.className = "chat-prompts";
    this.chatMessages = document.createElement("div");
    this.chatMessages.className = "chat-messages";
    this.chatInput = document.createElement("input");
    this.chatInput.className = "chat-input";
    this.chatInput.placeholder = "Frage zum aktuellen Schritt";
    this.chatSend = document.createElement("button");
    this.chatSend.className = "chat-send";
    this.chatSend.textContent = "Senden";
    const chatForm = document.createElement("form");
    chatForm.className = "chat-form";
    chatForm.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.submitChat(this.chatInput.value.trim());
    });
    chatForm.append(this.chatInput, this.chatSend);
    this.chatPanel.append(chatHeader, this.chatPrompts, this.chatMessages, chatForm);
    this.chatLauncher = document.createElement("button");
    this.chatLauncher.className = "chat-launcher";
    this.chatLauncher.textContent = "?";
    this.chatLauncher.addEventListener("click", () => {
      this.setChatOpen(!this.chatOpen);
    });
    this.chatDock.append(this.chatPanel, this.chatLauncher);

    this.layer.append(status, this.cardWrap, this.chatDock);
    this.shadow.append(style, this.layer);

    this.renderChatPrompts([]);
    this.renderMessages();
  }

  clear(): void {
    this.currentDecision = null;
    this.cardWrap.replaceChildren();
  }

  updateStatus(status: CoachApiStatus): void {
    this.statusPill.dataset.state = status.state;
    this.statusPill.textContent = `UNIQA Runtime: ${status.state}`;
    this.addLogMessage(status.message);
  }

  addLogMessage(message: string): void {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
    this.statusLog.prepend(entry);
    while (this.statusLog.childElementCount > 6) {
      this.statusLog.lastElementChild?.remove();
    }
  }

  render(decision: JourneyDecision, step: ResolvedStep | null): JourneyDecision | null {
    this.clear();
    this.currentDecision = decision;
    this.renderCard(decision);
    this.renderChatPrompts(
      decision.domMutations
        .filter((mutation) => mutation.kind === "chat_link" && mutation.label && mutation.prompt)
        .map((mutation) => ({ label: mutation.label!, prompt: mutation.prompt! })),
    );
    return decision;
  }

  private renderCard(decision: JourneyDecision): void {
    const card = decision.cards[0];
    if (!card) {
      return;
    }

    const wrap = document.createElement("div");
    wrap.className = "card";
    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = card.title;
    const body = document.createElement("div");
    body.className = "card-body";
    body.textContent = card.body;
    const actions = document.createElement("div");
    actions.className = "card-actions";

    if (card.cta) {
      const cta = document.createElement("button");
      cta.className = "card-cta";
      cta.textContent = card.cta.label;
      cta.addEventListener("click", () => {
        this.handleDecisionCta(decision, card.cta?.label ?? null, card.cta?.prompt ?? null);
      });
      actions.appendChild(cta);
    }

    if (card.dismissible) {
      const dismiss = document.createElement("button");
      dismiss.className = "card-dismiss";
      dismiss.textContent = "Ausblenden";
      dismiss.addEventListener("click", () => {
        this.cardWrap.replaceChildren();
        this.onInteraction({
          cta: null,
          decision,
          result: "dismissed",
          type: "coach_dismiss",
        });
      });
      actions.appendChild(dismiss);
    }

    wrap.append(title, body, actions);
    this.cardWrap.appendChild(wrap);
  }

  private handleDecisionCta(decision: JourneyDecision, label: string | null, prompt: string | null): void {
    if (prompt) {
      this.setChatOpen(true);
      void this.submitChat(prompt, true);
    }
    this.onInteraction({
      cta: label,
      decision,
      result: "clicked",
      type: "coach_cta",
    });
  }

  private renderChatPrompts(prompts: Array<{ label: string; prompt: string }>): void {
    this.chatPrompts.replaceChildren();
    for (const prompt of prompts.slice(0, 3)) {
      const button = document.createElement("button");
      button.className = "chat-prompt";
      button.type = "button";
      button.textContent = prompt.label;
      button.addEventListener("click", () => {
        this.setChatOpen(true);
        void this.submitChat(prompt.prompt, true);
      });
      this.chatPrompts.appendChild(button);
    }
  }

  private async submitChat(message: string, fromPreset = false): Promise<void> {
    if (!message) {
      return;
    }

    this.chatInput.value = "";
    const userMessage: ChatMessage = {
      role: "user",
      content: message,
    };
    this.chatMessagesState.push(userMessage);
    this.renderMessages();

    const assistantMessage = await this.onChatRequest({
      messages: this.chatMessagesState,
      model: this.chatModel,
    });
    this.chatMessagesState.push(assistantMessage);
    this.renderMessages();

    if (this.currentDecision) {
      this.onInteraction({
        cta: fromPreset ? message : "chat_send",
        decision: this.currentDecision,
        result: "sent",
        type: "coach_cta",
      });
    }
  }

  private renderMessages(): void {
    this.chatMessages.replaceChildren();
    if (!this.chatMessagesState.length) {
      const starter = document.createElement("div");
      starter.className = "chat-msg";
      starter.dataset.role = "assistant";
      starter.textContent = this.hasChatApiKey
        ? "Stellen Sie eine kurze Frage zum aktuellen Tarif oder Schritt."
        : "Verbinden Sie einen API-Schluessel, um Chat-Antworten zu erhalten.";
      this.chatMessages.appendChild(starter);
      return;
    }

    for (const message of this.chatMessagesState) {
      const bubble = document.createElement("div");
      bubble.className = "chat-msg";
      bubble.dataset.role = message.role;
      bubble.textContent = message.content;
      this.chatMessages.appendChild(bubble);
    }
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  private setChatOpen(open: boolean): void {
    this.chatOpen = open;
    this.chatPanel.dataset.open = open ? "true" : "false";
  }
}
