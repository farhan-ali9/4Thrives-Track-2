import type { CoachAction, CoachPlacement, ResolvedStep } from "@/shared/contracts";
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

export class DomInjector {
  private readonly host: HTMLDivElement;
  private readonly shadowRootRef: ShadowRoot;
  private readonly layer: HTMLDivElement;
  private currentStep: ResolvedStep | null = null;
  private activeActions = new Map<string, CoachAction>();
  private impressed = new Set<string>();

  constructor(private readonly onInteraction: (interaction: CoachInteraction) => void) {
    this.host = document.createElement("div");
    this.host.id = ROOT_ID;
    this.shadowRootRef = this.host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLES;
    this.layer = document.createElement("div");
    this.layer.className = "layer";
    this.shadowRootRef.append(style, this.layer);
    document.body.appendChild(this.host);

    window.addEventListener("scroll", this.reposition, { passive: true });
    window.addEventListener("resize", this.reposition);
  }

  clear(): void {
    this.activeActions.clear();
    this.layer.replaceChildren();
  }

  render(actions: CoachAction[], step: ResolvedStep | null): CoachAction[] {
    this.currentStep = step;
    this.layer.replaceChildren();
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
      if (!(node instanceof HTMLElement)) {
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
