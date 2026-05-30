import type {
  ChatMessage,
  CoachAction,
  CoachApiStatus,
  CoachPlacement,
  ResolvedStep,
} from "@/shared/contracts";
import { queryFirst } from "@/shared/page-map";

const ROOT_ID = "uniqa-conversion-coach-root";

const STYLES = `
  :host {
    all: initial;
  }

  .layer {
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Open Sans", sans-serif;
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 2147483646;
  }

  .status-wrap {
    bottom: 24px;
    display: grid;
    gap: 10px;
    left: 24px;
    max-width: 360px;
    pointer-events: auto;
    position: fixed;
  }

  .status-pill {
    align-items: center;
    appearance: none;
    backdrop-filter: blur(14px);
    background: rgba(7, 22, 58, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 999px;
    box-shadow: 0 12px 32px rgba(7, 22, 58, 0.2);
    color: #ffffff;
    cursor: pointer;
    display: inline-flex;
    gap: 10px;
    justify-self: start;
    padding: 10px 14px;
  }

  .status-pill[data-state="connected"] {
    background: rgba(19, 91, 58, 0.94);
  }

  .status-pill[data-state="error"] {
    background: rgba(134, 28, 45, 0.95);
  }

  .status-dot {
    border-radius: 999px;
    display: inline-block;
    flex: 0 0 auto;
    height: 9px;
    width: 9px;
  }

  .status-pill[data-state="starting"] .status-dot {
    background: #ffd24c;
  }

  .status-pill[data-state="connected"] .status-dot {
    background: #91f2bd;
  }

  .status-pill[data-state="error"] .status-dot {
    background: #ff9aad;
  }

  .status-pill-text {
    display: grid;
    gap: 2px;
    text-align: left;
  }

  .status-pill-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .status-pill-message {
    color: rgba(255, 255, 255, 0.82);
    font-size: 11px;
    line-height: 1.25;
  }

  .status-panel {
    backdrop-filter: blur(16px);
    background: rgba(7, 22, 58, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    box-shadow: 0 18px 50px rgba(7, 22, 58, 0.24);
    color: #ffffff;
    padding: 14px;
  }

  .status-panel[hidden] {
    display: none;
  }

  .status-panel-title {
    display: block;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
  }

  .status-meta,
  .status-log {
    color: rgba(255, 255, 255, 0.84);
    display: grid;
    font-size: 12px;
    gap: 6px;
    line-height: 1.35;
  }

  .status-section-label {
    color: rgba(255, 255, 255, 0.64);
    display: block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 5px;
    margin-top: 12px;
    text-transform: uppercase;
  }

  .status-log-entry {
    align-items: start;
    display: grid;
    gap: 2px;
    grid-template-columns: 56px 1fr;
  }

  .status-log-time {
    color: rgba(255, 255, 255, 0.54);
    font-variant-numeric: tabular-nums;
  }

  .card {
    background: linear-gradient(135deg, #07163a 0%, #0f6bb3 100%);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    box-shadow: 0 18px 50px rgba(7, 22, 58, 0.28);
    color: #ffffff;
    max-width: 360px;
    min-width: 260px;
    padding: 16px 16px 14px;
    pointer-events: auto;
    position: fixed;
  }

  .card[data-placement="bottom-toast"] {
    bottom: 24px;
    right: 24px;
  }

  .eyebrow {
    color: rgba(255, 255, 255, 0.76);
    display: block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    text-transform: uppercase;
  }

  .title {
    display: block;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: 6px;
  }

  .body {
    color: rgba(255, 255, 255, 0.92);
    display: block;
    font-size: 13px;
    line-height: 1.45;
    margin-bottom: 14px;
  }

  .actions {
    align-items: center;
    display: flex;
    gap: 10px;
  }

  .cta,
  .dismiss {
    appearance: none;
    border: 0;
    border-radius: 999px;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    padding: 8px 12px;
  }

  .cta {
    background: #f6f7f9;
    color: #07163a;
    font-weight: 700;
  }

  .dismiss {
    background: transparent;
    color: rgba(255, 255, 255, 0.78);
    text-decoration: underline;
  }

  .chat-dock {
    bottom: 22px;
    pointer-events: auto;
    position: fixed;
    right: 22px;
    z-index: 2147483647;
  }

  .chat-launcher {
    align-items: center;
    appearance: none;
    background: #07163a;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 999px;
    box-shadow: 0 14px 34px rgba(7, 22, 58, 0.28);
    color: #ffffff;
    cursor: pointer;
    display: flex;
    font: inherit;
    font-size: 22px;
    font-weight: 800;
    height: 58px;
    justify-content: center;
    width: 58px;
  }

  .chat-panel {
    background: #ffffff;
    border: 1px solid rgba(7, 22, 58, 0.12);
    border-radius: 16px;
    box-shadow: 0 22px 58px rgba(7, 22, 58, 0.28);
    color: #10203d;
    display: flex;
    flex-direction: column;
    height: min(560px, calc(100vh - 48px));
    overflow: hidden;
    width: min(420px, calc(100vw - 32px));
  }

  .chat-header {
    align-items: center;
    background: #07163a;
    color: #ffffff;
    display: flex;
    gap: 10px;
    justify-content: space-between;
    padding: 13px 14px;
  }

  .chat-heading {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .chat-title {
    font-size: 14px;
    font-weight: 800;
  }

  .chat-subtitle {
    color: rgba(255, 255, 255, 0.74);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chat-close {
    appearance: none;
    background: rgba(255, 255, 255, 0.12);
    border: 0;
    border-radius: 999px;
    color: #ffffff;
    cursor: pointer;
    font: inherit;
    height: 30px;
    width: 30px;
  }

  .chat-messages {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    padding: 14px;
  }

  .chat-message {
    border-radius: 13px;
    font-size: 13px;
    line-height: 1.42;
    max-width: 86%;
    padding: 9px 11px;
    white-space: pre-wrap;
  }

  .chat-message.assistant {
    align-self: flex-start;
    background: #eef4fb;
    color: #10203d;
  }

  .chat-message.user {
    align-self: flex-end;
    background: #0f6bb3;
    color: #ffffff;
  }

  .chat-key,
  .chat-model {
    border-top: 1px solid #e5edf6;
    display: grid;
    gap: 6px;
    padding: 10px 12px 0;
  }

  .chat-model label {
    color: #5c6a80;
    font-size: 11px;
    font-weight: 800;
  }

  .chat-key input,
  .chat-model select {
    background: #ffffff;
    border: 1px solid #ccd8e6;
    border-radius: 10px;
    box-sizing: border-box;
    color: #10203d;
    font: inherit;
    font-size: 12px;
    padding: 8px 10px;
    width: 100%;
  }

  .chat-form {
    align-items: flex-end;
    display: grid;
    gap: 8px;
    grid-template-columns: 1fr auto;
    padding: 10px 12px 12px;
  }

  .chat-input {
    border: 1px solid #ccd8e6;
    border-radius: 12px;
    box-sizing: border-box;
    color: #10203d;
    font: inherit;
    font-size: 13px;
    max-height: 110px;
    min-height: 42px;
    padding: 10px 11px;
    resize: vertical;
    width: 100%;
  }

  .chat-send {
    appearance: none;
    background: #07163a;
    border: 0;
    border-radius: 12px;
    color: #ffffff;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    font-weight: 800;
    min-height: 42px;
    padding: 0 14px;
  }
`;

export interface CoachInteraction {
  action: CoachAction;
  type: "coach_cta" | "coach_dismiss";
}

export interface ChatRequest {
  apiKey?: string;
  messages: ChatMessage[];
  model: string;
}

interface VisibleLogEntry {
  message: string;
  timestamp: number;
}

export class DomInjector {
  private readonly host: HTMLDivElement;
  private readonly shadowRootRef: ShadowRoot;
  private readonly layer: HTMLDivElement;
  private readonly statusWrap: HTMLDivElement;
  private readonly statusPill: HTMLButtonElement;
  private readonly statusMessage: HTMLSpanElement;
  private readonly statusPanel: HTMLDivElement;
  private readonly statusMeta: HTMLDivElement;
  private readonly statusLog: HTMLDivElement;
  private readonly chatDock: HTMLDivElement;
  private readonly chatMessages: ChatMessage[] = [
    {
      role: "assistant",
      content: "Hi, I can help with the current UNIQA calculator step. Ask about tariffs, price changes, or what to choose next.",
    },
  ];
  private currentStep: ResolvedStep | null = null;
  private activeActions = new Map<string, CoachAction>();
  private impressed = new Set<string>();
  private expanded = false;
  private lastStatusKey: string | null = null;
  private statusLogs: VisibleLogEntry[] = [];
  private chatOpen = false;
  private chatLoading = false;
  private selectedChatModel = this.chatModel;

  constructor(
    private readonly onInteraction: (interaction: CoachInteraction) => void,
    private readonly onChatRequest: (request: ChatRequest) => Promise<ChatMessage>,
    private readonly hasConfiguredChatApiKey = false,
    private readonly chatModel = "unknown model",
    private readonly chatModelOptions = [chatModel],
  ) {
    this.host = document.createElement("div");
    this.host.id = ROOT_ID;
    this.shadowRootRef = this.host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLES;
    this.layer = document.createElement("div");
    this.layer.className = "layer";

    this.statusWrap = document.createElement("div");
    this.statusWrap.className = "status-wrap";
    this.statusPill = document.createElement("button");
    this.statusPill.className = "status-pill";
    this.statusPill.type = "button";
    this.statusPill.addEventListener("click", () => {
      this.expanded = !this.expanded;
      this.statusPanel.hidden = !this.expanded;
    });

    const statusDot = document.createElement("span");
    statusDot.className = "status-dot";
    const statusText = document.createElement("span");
    statusText.className = "status-pill-text";
    const statusTitle = document.createElement("span");
    statusTitle.className = "status-pill-title";
    statusTitle.textContent = "Coach API";
    this.statusMessage = document.createElement("span");
    this.statusMessage.className = "status-pill-message";
    statusText.append(statusTitle, this.statusMessage);
    this.statusPill.append(statusDot, statusText);

    this.statusPanel = document.createElement("div");
    this.statusPanel.className = "status-panel";
    this.statusPanel.hidden = true;
    const panelTitle = document.createElement("strong");
    panelTitle.className = "status-panel-title";
    panelTitle.textContent = "Extension status";
    this.statusMeta = document.createElement("div");
    this.statusMeta.className = "status-meta";
    const logLabel = document.createElement("span");
    logLabel.className = "status-section-label";
    logLabel.textContent = "Recent events";
    this.statusLog = document.createElement("div");
    this.statusLog.className = "status-log";
    this.statusPanel.append(panelTitle, this.statusMeta, logLabel, this.statusLog);

    this.statusWrap.append(this.statusPill, this.statusPanel);
    this.layer.append(this.statusWrap);
    this.chatDock = document.createElement("div");
    this.chatDock.className = "chat-dock";
    this.shadowRootRef.append(style, this.layer, this.chatDock);
    document.body.appendChild(this.host);
    this.renderChat();

    window.addEventListener("scroll", this.reposition, { passive: true });
    window.addEventListener("resize", this.reposition);

    this.updateStatus({
      endpoint: "waiting",
      lastUpdatedAt: Date.now(),
      message: "Initializing extension",
      policyVersion: null,
      state: "starting",
    });
  }

  clear(): void {
    this.activeActions.clear();
    this.layer.replaceChildren(this.statusWrap);
  }

  render(actions: CoachAction[], step: ResolvedStep | null): CoachAction[] {
    this.currentStep = step;
    this.layer.replaceChildren(this.statusWrap);
    this.activeActions.clear();

    const displayed: CoachAction[] = [];
    for (const action of actions) {
      const card = this.renderCard(action);
      this.activeActions.set(action.id, action);
      this.layer.appendChild(card);
      displayed.push(action);
    }

    this.reposition();
    return displayed.filter((action) => {
      if (this.impressed.has(action.id)) {
        return false;
      }
      this.impressed.add(action.id);
      return true;
    });
  }

  updateStatus(status: CoachApiStatus): void {
    this.statusPill.dataset.state = status.state;
    this.statusMessage.textContent = status.message;
    const formattedTime = formatTime(status.lastUpdatedAt);
    this.statusMeta.replaceChildren(
      buildMetaLine(`State: ${status.state}`),
      buildMetaLine(`Endpoint: ${status.endpoint}`),
      buildMetaLine(
        `Policy: ${status.policyVersion !== null ? `v${status.policyVersion}` : "not available"}`,
      ),
      buildMetaLine(`Updated: ${formattedTime}`),
    );

    const dedupeKey = `${status.state}:${status.policyVersion ?? "none"}:${status.message}`;
    if (this.lastStatusKey !== dedupeKey) {
      this.lastStatusKey = dedupeKey;
      this.pushLogEntry(status.lastUpdatedAt, status.message);
    }
  }

  addLogMessage(message: string, timestamp = Date.now()): void {
    this.pushLogEntry(timestamp, message);
  }

  private renderCard(action: CoachAction): HTMLElement {
    const card = document.createElement("section");
    card.className = "card";
    card.dataset.actionId = action.id;
    card.dataset.placement = action.placement;

    const eyebrow = document.createElement("span");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "Conversion Coach";

    const title = document.createElement("strong");
    title.className = "title";
    title.textContent = action.title;

    const body = document.createElement("span");
    body.className = "body";
    body.textContent = action.body;

    const actions = document.createElement("div");
    actions.className = "actions";

    if (action.ctaLabel) {
      const cta = document.createElement("button");
      cta.className = "cta";
      cta.type = "button";
      cta.textContent = action.ctaLabel;
      cta.addEventListener("click", () => {
        this.onInteraction({ action, type: "coach_cta" });
      });
      actions.appendChild(cta);
    }

    if (action.dismissible) {
      const dismiss = document.createElement("button");
      dismiss.className = "dismiss";
      dismiss.type = "button";
      dismiss.textContent = "Schließen";
      dismiss.addEventListener("click", () => {
        this.onInteraction({ action, type: "coach_dismiss" });
        card.remove();
        this.activeActions.delete(action.id);
      });
      actions.appendChild(dismiss);
    }

    card.append(eyebrow, title, body, actions);
    return card;
  }

  private renderChat(): void {
    this.chatDock.replaceChildren();

    if (!this.chatOpen) {
      const launcher = document.createElement("button");
      launcher.className = "chat-launcher";
      launcher.type = "button";
      launcher.textContent = "?";
      launcher.title = "Open UNIQA Coach chat";
      launcher.addEventListener("click", () => {
        this.chatOpen = true;
        this.renderChat();
      });
      this.chatDock.appendChild(launcher);
      return;
    }

    const panel = document.createElement("section");
    panel.className = "chat-panel";

    const header = document.createElement("div");
    header.className = "chat-header";

    const heading = document.createElement("div");
    heading.className = "chat-heading";
    const title = document.createElement("strong");
    title.className = "chat-title";
    title.textContent = "UNIQA Coach Chat";
    const subtitle = document.createElement("span");
    subtitle.className = "chat-subtitle";
    subtitle.textContent = `Featherless · ${this.selectedChatModel}`;
    heading.append(title, subtitle);

    const close = document.createElement("button");
    close.className = "chat-close";
    close.type = "button";
    close.textContent = "x";
    close.addEventListener("click", () => {
      this.chatOpen = false;
      this.renderChat();
    });
    header.append(heading, close);

    const messages = document.createElement("div");
    messages.className = "chat-messages";
    for (const message of this.chatMessages) {
      const bubble = document.createElement("div");
      bubble.className = `chat-message ${message.role}`;
      bubble.textContent = message.content;
      messages.appendChild(bubble);
    }
    if (this.chatLoading) {
      const bubble = document.createElement("div");
      bubble.className = "chat-message assistant";
      bubble.textContent = "Thinking...";
      messages.appendChild(bubble);
    }

    const keyWrap = document.createElement("div");
    keyWrap.className = "chat-key";
    const keyInput = document.createElement("input");
    keyInput.autocomplete = "off";
    keyInput.placeholder = "Featherless API key (saved locally after first send)";
    keyInput.type = "password";
    if (!this.hasConfiguredChatApiKey) {
      keyWrap.appendChild(keyInput);
    }

    const modelWrap = document.createElement("div");
    modelWrap.className = "chat-model";
    const modelLabel = document.createElement("label");
    modelLabel.textContent = "Model";
    const modelSelect = document.createElement("select");
    for (const model of this.normalizedModelOptions()) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      option.selected = model === this.selectedChatModel;
      modelSelect.appendChild(option);
    }
    modelSelect.addEventListener("change", () => {
      this.selectedChatModel = modelSelect.value;
      this.renderChat();
    });
    modelWrap.append(modelLabel, modelSelect);

    const form = document.createElement("form");
    form.className = "chat-form";
    const input = document.createElement("textarea");
    input.className = "chat-input";
    input.placeholder = "Ask the coach...";
    input.rows = 2;
    const send = document.createElement("button");
    send.className = "chat-send";
    send.disabled = this.chatLoading;
    send.textContent = this.chatLoading ? "..." : "Send";
    send.type = "submit";
    form.append(input, send);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.submitChat(input.value, keyInput.value);
    });

    if (keyWrap.childElementCount > 0) {
      panel.append(header, messages, modelWrap, keyWrap, form);
    } else {
      panel.append(header, messages, modelWrap, form);
    }
    this.chatDock.appendChild(panel);
    messages.scrollTop = messages.scrollHeight;
    input.focus();
  }

  private async submitChat(rawMessage: string, rawApiKey: string): Promise<void> {
    const content = rawMessage.trim();
    const apiKey = rawApiKey.trim();
    if (!content || this.chatLoading) {
      return;
    }

    this.chatMessages.push({ role: "user", content });
    this.chatLoading = true;
    this.renderChat();

    const reply = await this.onChatRequest({
      apiKey: apiKey || undefined,
      messages: [...this.chatMessages],
      model: this.selectedChatModel,
    });
    this.chatMessages.push(reply);
    this.chatLoading = false;
    this.renderChat();
  }

  private normalizedModelOptions(): string[] {
    const options = [this.chatModel, ...this.chatModelOptions]
      .map((model) => model.trim())
      .filter(Boolean);
    return [...new Set(options)];
  }

  private readonly reposition = (): void => {
    for (const node of Array.from(this.layer.children)) {
      if (!(node instanceof HTMLElement) || node === this.statusWrap) {
        continue;
      }

      const placement = (node.dataset.placement as CoachPlacement | undefined) ?? "bottom-toast";
      if (placement === "bottom-toast") {
        node.style.bottom = "24px";
        node.style.left = "auto";
        node.style.right = "24px";
        node.style.top = "auto";
        continue;
      }

      const anchor = resolveAnchor(this.currentStep, placement);
      if (!anchor) {
        node.style.top = "24px";
        node.style.left = "24px";
        continue;
      }

      const rect = anchor.getBoundingClientRect();
      node.style.left = `${Math.max(16, Math.min(rect.left, window.innerWidth - 392))}px`;
      node.style.top =
        placement === "near-primary-cta"
          ? `${Math.max(16, rect.top - node.offsetHeight - 12)}px`
          : `${Math.max(16, rect.top + 8)}px`;
    }
  };

  private pushLogEntry(timestamp: number, message: string): void {
    this.statusLogs = [{ message, timestamp }, ...this.statusLogs].slice(0, 8);
    this.statusLog.replaceChildren(
      ...this.statusLogs.map((entry) => {
        const row = document.createElement("div");
        row.className = "status-log-entry";
        const time = document.createElement("span");
        time.className = "status-log-time";
        time.textContent = formatTime(entry.timestamp);
        const text = document.createElement("span");
        text.textContent = entry.message;
        row.append(time, text);
        return row;
      }),
    );
  }
}

function resolveAnchor(step: ResolvedStep | null, placement: CoachPlacement): Element | null {
  if (!step) {
    return null;
  }

  if (placement === "near-primary-cta") {
    return queryFirst(document, step.config.selectors.primaryCta);
  }

  return queryFirst(document, step.config.selectors.stepAnchor);
}

function buildMetaLine(text: string): HTMLElement {
  const line = document.createElement("span");
  line.textContent = text;
  return line;
}

function formatTime(timestamp: number): string {
  if (!timestamp) {
    return "--:--:--";
  }

  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
