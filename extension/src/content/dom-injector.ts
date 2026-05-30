import type {
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
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
`;

export interface CoachInteraction {
  action: CoachAction;
  type: "coach_cta" | "coach_dismiss";
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
  private currentStep: ResolvedStep | null = null;
  private activeActions = new Map<string, CoachAction>();
  private impressed = new Set<string>();
  private expanded = false;
  private lastStatusKey: string | null = null;
  private statusLogs: VisibleLogEntry[] = [];

  constructor(private readonly onInteraction: (interaction: CoachInteraction) => void) {
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
    this.shadowRootRef.append(style, this.layer);
    document.body.appendChild(this.host);

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
