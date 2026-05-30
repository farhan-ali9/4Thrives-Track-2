import type {
  ChatMessage,
  CoachAction,
  CoachApiStatus,
  CoachCta,
  CoachCtaType,
  CoachPlacement,
  ResolvedStep,
} from "@/shared/contracts";
import { queryFirst } from "@/shared/page-map";
import { createLogger } from "@/shared/logger";

const log = createLogger("dom-injector");

const ROOT_ID = "uniqa-conversion-coach-root";

const STYLES = `
  :host {
    all: initial;
  }

  .layer {
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 2147483646;
  }

  .status-wrap {
    bottom: 14px;
    display: grid;
    gap: 8px;
    left: 14px;
    max-width: min(300px, calc(100vw - 28px));
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
    box-shadow: 0 10px 24px rgba(7, 22, 58, 0.18);
    color: #ffffff;
    cursor: pointer;
    display: inline-flex;
    gap: 10px;
    justify-self: start;
    padding: 8px 12px;
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
    border-radius: 16px;
    box-shadow: 0 14px 36px rgba(7, 22, 58, 0.22);
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
    border-radius: 16px;
    box-shadow: 0 14px 36px rgba(7, 22, 58, 0.24);
    color: #ffffff;
    max-width: min(318px, calc(100vw - 32px));
    min-width: min(240px, calc(100vw - 32px));
    padding: 13px 14px 12px;
    pointer-events: auto;
    position: fixed;
  }

  .card[data-placement="bottom-toast"] {
    bottom: 88px;
    right: 16px;
  }

  .eyebrow {
    color: rgba(255, 255, 255, 0.76);
    display: block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
    text-transform: uppercase;
  }

  .title {
    display: block;
    font-size: 15px;
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: 5px;
  }

  .body {
    color: rgba(255, 255, 255, 0.92);
    display: block;
    font-size: 13px;
    line-height: 1.45;
    margin-bottom: 12px;
  }

  .actions {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .cta,
  .dismiss {
    appearance: none;
    border: 0;
    border-radius: 999px;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    padding: 8px 11px;
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
    bottom: 14px;
    pointer-events: auto;
    position: fixed;
    right: 14px;
    z-index: 2147483647;
  }

  .chat-launcher {
    align-items: center;
    appearance: none;
    background: #07163a;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 999px;
    box-shadow: 0 10px 26px rgba(7, 22, 58, 0.24);
    color: #ffffff;
    cursor: pointer;
    display: flex;
    font: inherit;
    font-size: 19px;
    font-weight: 800;
    height: 48px;
    justify-content: center;
    width: 48px;
  }

  .chat-panel {
    background: #ffffff;
    border: 1px solid rgba(7, 22, 58, 0.12);
    border-radius: 16px;
    box-shadow: 0 22px 58px rgba(7, 22, 58, 0.28);
    color: #10203d;
    display: flex;
    flex-direction: column;
    height: min(460px, calc(100vh - 32px));
    overflow: hidden;
    width: min(360px, calc(100vw - 28px));
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

  @media (max-width: 720px) {
    .status-wrap {
      bottom: 10px;
      left: 10px;
      max-width: calc(100vw - 76px);
    }

    .card {
      left: 10px !important;
      max-width: calc(100vw - 20px);
      right: auto !important;
    }

    .card[data-placement="bottom-toast"] {
      bottom: 72px;
    }

    .chat-dock {
      bottom: 10px;
      right: 10px;
    }
  }
`;

export interface CoachInteraction {
  action: CoachAction;
  cta: CoachCta | null;
  result?: PageActionResult;
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

interface PageActionResult {
  message: string;
  status: "success" | "fallback_chat" | "not_supported" | "target_missing";
  target: string | null;
  type: CoachCtaType | "dismiss";
}

interface CoachRenderState {
  activeActionIds: string[];
  actionable: boolean;
  apiState: CoachApiStatus["state"];
  cardCount: number;
  initialized: boolean;
  lastActionResult: PageActionResult | null;
  lastRenderAt: number;
  layoutFallback: string | null;
  placement: CoachPlacement | null;
  renderState: "bootstrapping" | "idle" | "rendered" | "actioning" | "error";
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
  private layoutFallback: string | null = null;
  private pendingChatPrompt = "";
  private selectedChatModel = this.chatModel;
  private renderState: CoachRenderState = {
    activeActionIds: [],
    actionable: false,
    apiState: "starting",
    cardCount: 0,
    initialized: false,
    lastActionResult: null,
    lastRenderAt: 0,
    layoutFallback: null,
    placement: null,
    renderState: "bootstrapping",
  };

  constructor(
    private readonly onInteraction: (interaction: CoachInteraction) => void,
    private readonly onChatRequest: (request: ChatRequest) => Promise<ChatMessage> = async () => ({
      content: "Chat is unavailable in this environment.",
      role: "assistant",
    }),
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
    this.publishRenderState({
      initialized: true,
      renderState: "idle",
    });

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
    this.layoutFallback = null;
    this.publishRenderState({
      activeActionIds: [],
      actionable: false,
      cardCount: 0,
      lastRenderAt: Date.now(),
      layoutFallback: null,
      placement: null,
      renderState: "idle",
    });
  }

  render(actions: CoachAction[], step: ResolvedStep | null): CoachAction[] {
    this.currentStep = step;
    this.layer.replaceChildren(this.statusWrap);
    this.activeActions.clear();

    const displayed: CoachAction[] = [];
    for (const action of actions.slice(0, 1)) {
      const card = this.renderCard(action);
      this.activeActions.set(action.id, action);
      this.layer.appendChild(card);
      displayed.push(action);
    }

    this.reposition();
    this.publishRenderState({
      activeActionIds: displayed.map((action) => action.id),
      actionable: displayed.some((action) => Boolean(resolveCta(action))),
      cardCount: displayed.length,
      lastRenderAt: Date.now(),
      layoutFallback: this.layoutFallback,
      placement: displayed[0]?.placement ?? null,
      renderState: displayed.length > 0 ? "rendered" : "idle",
    });
    if (actions.length > displayed.length) {
      log.debug("Rendering one card at a time; extra actions deferred", {
        received: actions.length,
        rendered: displayed.length,
      });
    }
    const fresh = displayed.filter((action) => {
      if (this.impressed.has(action.id)) {
        return false;
      }
      this.impressed.add(action.id);
      return true;
    });
    if (fresh.length < displayed.length) {
      log.debug("Some rendered actions were already impressed this page load", {
        deduped: displayed.length - fresh.length,
      });
    }
    log.debug("Card mounted in shadow DOM", {
      cardCount: displayed.length,
      placement: displayed[0]?.placement ?? null,
      step: step?.pageStepId ?? null,
    });
    return fresh;
  }

  updateStatus(status: CoachApiStatus): void {
    this.statusPill.dataset.state = status.state;
    this.statusMessage.textContent = status.message;
    this.publishRenderState({
      apiState: status.state,
      renderState: status.state === "error" ? "error" : this.renderState.renderState,
    });
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

    const ctaAction = resolveCta(action);
    if (ctaAction) {
      const cta = document.createElement("button");
      cta.className = "cta";
      cta.dataset.actionTarget = ctaAction.target ?? "";
      cta.dataset.actionType = ctaAction.type;
      cta.type = "button";
      cta.textContent = ctaAction.label;
      cta.addEventListener("click", () => {
        void (async () => {
          this.publishRenderState({ renderState: "actioning" });
          const result = await this.executeCta(action, ctaAction);
          this.publishRenderState({
            lastActionResult: result,
            renderState: this.activeActions.size > 0 ? "rendered" : "idle",
          });
          this.onInteraction({ action, cta: ctaAction, result, type: "coach_cta" });
        })();
      });
      actions.appendChild(cta);
    }

    if (action.dismissible) {
      const dismiss = document.createElement("button");
      dismiss.className = "dismiss";
      dismiss.type = "button";
      dismiss.textContent = "Schließen";
      dismiss.addEventListener("click", () => {
        this.onInteraction({
          action,
          cta: null,
          result: {
            message: "Dismissed coach card",
            status: "success",
            target: action.id,
            type: "dismiss",
          },
          type: "coach_dismiss",
        });
        card.remove();
        this.activeActions.delete(action.id);
        this.publishRenderState({
          activeActionIds: Array.from(this.activeActions.keys()),
          actionable: Array.from(this.activeActions.values()).some((active) => Boolean(resolveCta(active))),
          cardCount: this.activeActions.size,
          lastActionResult: {
            message: "Dismissed coach card",
            status: "success",
            target: action.id,
            type: "dismiss",
          },
          lastRenderAt: Date.now(),
          renderState: this.activeActions.size > 0 ? "rendered" : "idle",
        });
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
    input.value = this.pendingChatPrompt;
    const send = document.createElement("button");
    send.className = "chat-send";
    send.disabled = this.chatLoading;
    send.textContent = this.chatLoading ? "..." : "Send";
    send.type = "submit";
    form.append(input, send);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.pendingChatPrompt = "";
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

  private async executeCta(action: CoachAction, cta: CoachCta): Promise<PageActionResult> {
    const result = this.executePageAction(cta);
    if (result.status === "success") {
      this.addLogMessage(result.message);
      return result;
    }

    const prompt = cta.prompt ?? fallbackPrompt(action, result);
    this.openChat(prompt);
    const fallbackResult: PageActionResult = {
      ...result,
      status: "fallback_chat",
      message: `${result.message}; opened coach chat`,
    };
    this.addLogMessage(fallbackResult.message);
    return fallbackResult;
  }

  private executePageAction(cta: CoachCta): PageActionResult {
    if (cta.type === "open_chat" || cta.type === "save_progress") {
      this.openChat(cta.prompt);
      return {
        message: "Opened coach chat",
        status: "success",
        target: cta.target,
        type: cta.type,
      };
    }

    if (cta.type === "advisor_handoff") {
      const anchor = this.findStepAnchor();
      if (anchor instanceof HTMLElement) {
        anchor.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      this.openChat(cta.prompt);
      return {
        message: "Opened advisor guidance",
        status: "success",
        target: cta.target,
        type: cta.type,
      };
    }

    if (cta.type === "select_tariff") {
      const target = this.findTariffTarget(cta.target);
      if (!target) {
        return {
          message: "Could not find tariff target",
          status: "target_missing",
          target: cta.target,
          type: cta.type,
        };
      }
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.click();
      return {
        message: `Selected ${cta.target ?? "tariff"}`,
        status: "success",
        target: cta.target,
        type: cta.type,
      };
    }

    if (cta.type === "continue") {
      const target = queryFirst(document, this.currentStep?.config.selectors.primaryCta ?? []);
      if (!(target instanceof HTMLElement)) {
        return {
          message: "Could not find primary CTA",
          status: "target_missing",
          target: cta.target,
          type: cta.type,
        };
      }
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.click();
      return {
        message: "Clicked primary CTA",
        status: "success",
        target: cta.target,
        type: cta.type,
      };
    }

    if (cta.type === "focus_field") {
      const target = this.findFocusableTarget(cta.target);
      if (!target) {
        return {
          message: "Could not find a field to focus",
          status: "target_missing",
          target: cta.target,
          type: cta.type,
        };
      }
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.focus({ preventScroll: true });
      return {
        message: "Focused the relevant page area",
        status: "success",
        target: cta.target,
        type: cta.type,
      };
    }

    return {
      message: "CTA type is not supported by this page",
      status: "not_supported",
      target: cta.target,
      type: cta.type,
    };
  }

  private findFocusableTarget(target: string | null): HTMLElement | null {
    if (target && target !== "step_anchor") {
      const direct = document.querySelector(target);
      if (direct instanceof HTMLElement) {
        return direct;
      }
    }

    const incomplete = document.querySelector(
      "input:not([type='hidden']):not(:disabled):not([readonly]), textarea:not(:disabled), select:not(:disabled)",
    );
    if (incomplete instanceof HTMLElement) {
      return incomplete;
    }
    const anchor = this.findStepAnchor();
    return anchor instanceof HTMLElement ? anchor : null;
  }

  private findStepAnchor(): Element | null {
    return queryFirst(document, this.currentStep?.config.selectors.stepAnchor ?? []);
  }

  private findTariffTarget(target: string | null): HTMLElement | null {
    const normalized = (target ?? "optimal").toLowerCase();
    const selectorsByTarget: Record<string, string[]> = {
      optimal: ["[aria-label='Wählen Optimal']", "[data-cy='selectionButton_1']"],
      opt_plus: ["[aria-label='Wählen Opt. Plus']", "[data-cy='selectionButton_2']"],
      premium: ["[aria-label='Wählen Premium']", "[data-cy='selectionButton_3']"],
      start: ["[aria-label='Wählen Start']", "[data-cy='selectionButton_0']"],
    };
    return queryFirst(document, selectorsByTarget[normalized] ?? [target ?? ""]) as HTMLElement | null;
  }

  private openChat(prompt: string | null): void {
    this.pendingChatPrompt = prompt ?? "";
    this.chatOpen = true;
    this.renderChat();
  }

  private readonly reposition = (): void => {
    this.layoutFallback = null;
    for (const node of Array.from(this.layer.children)) {
      if (!(node instanceof HTMLElement) || node === this.statusWrap) {
        continue;
      }

      const placement = (node.dataset.placement as CoachPlacement | undefined) ?? "bottom-toast";
      if (placement === "bottom-toast") {
        node.style.bottom = this.chatOpen ? "88px" : "72px";
        node.style.left = "auto";
        node.style.right = "16px";
        node.style.top = "auto";
        continue;
      }

      const anchor = resolveAnchor(this.currentStep, placement);
      if (!anchor) {
        node.style.top = "16px";
        node.style.left = "16px";
        this.layoutFallback = "missing_anchor";
        log.warn("Anchor not found for placement; using top-left fallback", {
          placement,
          step: this.currentStep?.pageStepId ?? null,
        });
        continue;
      }

      const rect = anchor.getBoundingClientRect();
      const width = Math.max(node.offsetWidth, 300);
      const height = Math.max(node.offsetHeight, 120);
      const left = Math.max(16, Math.min(rect.left, window.innerWidth - width - 16));
      let top =
        placement === "near-primary-cta"
          ? rect.top - height - 10
          : rect.top + 8;
      if (top < 16 && placement === "near-primary-cta") {
        top = rect.bottom + 10;
        this.layoutFallback = "flipped_below_anchor";
      }
      if (top + height > window.innerHeight - 16) {
        top = Math.max(16, window.innerHeight - height - 16);
        this.layoutFallback = this.layoutFallback ?? "clamped_to_viewport";
      }
      node.style.left = `${left}px`;
      node.style.top = `${top}px`;
    }
    this.publishRenderState({ layoutFallback: this.layoutFallback });
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

  private publishRenderState(update: Partial<CoachRenderState>): void {
    this.renderState = {
      ...this.renderState,
      ...update,
    };
    this.host.dataset.renderState = this.renderState.renderState;
    this.host.dataset.apiState = this.renderState.apiState;
    this.host.dataset.cardCount = String(this.renderState.cardCount);
    this.host.dataset.actionable = String(this.renderState.actionable);
    this.host.dataset.activeActions = this.renderState.activeActionIds.join(",");
    this.host.dataset.lastRenderAt = String(this.renderState.lastRenderAt);
    this.host.dataset.layoutFallback = this.renderState.layoutFallback ?? "";
    (
      window as Window & {
        __UNIQA_COACH_STATE__?: CoachRenderState;
      }
    ).__UNIQA_COACH_STATE__ = { ...this.renderState };
  }
}

function resolveCta(action: CoachAction): CoachCta | null {
  if (action.cta) {
    return action.cta;
  }
  if (!action.ctaLabel) {
    return null;
  }
  return {
    label: action.ctaLabel,
    prompt: null,
    target: "primary_cta",
    telemetryKey: action.id,
    type: "open_chat",
  };
}

function fallbackPrompt(action: CoachAction, result: PageActionResult): string {
  return [
    `The coach action "${action.title}" could not run automatically.`,
    result.message,
    "Explain the next best step for this calculator page.",
  ].join(" ");
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
