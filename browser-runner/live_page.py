from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

PAGE_MAP_PATH = Path(__file__).resolve().parents[1] / "extension" / "src" / "shared" / "uniqa-page-map.json"
PAGE_MAP = json.loads(PAGE_MAP_PATH.read_text(encoding="utf-8"))


def enabled_page_map() -> list[dict[str, Any]]:
    return [entry for entry in PAGE_MAP if entry.get("enabled")]


def detect_step(page: Any) -> dict[str, Any] | None:
    entries = enabled_page_map()
    step_id = page.evaluate(
        """
        (entries) => {
          const normalize = (value) => (value ?? "").replace(/\\s+/g, " ").trim().toLowerCase();
          const docText = normalize(document.body?.innerText || document.body?.textContent || "");
          for (const entry of entries) {
            const requiredText = entry.match.requiredText ?? [];
            const requiredSelectorsAll = entry.match.requiredSelectorsAll ?? [];
            const requiredSelectorsAny = entry.match.requiredSelectorsAny ?? [];
            const matchesText = requiredText.every((needle) => docText.includes(normalize(needle)));
            const matchesAll = requiredSelectorsAll.every((selector) => document.querySelector(selector));
            const matchesAny = requiredSelectorsAny.length === 0 || requiredSelectorsAny.some((selector) => document.querySelector(selector));
            if (matchesText && matchesAll && matchesAny) {
              return entry.pageStepId;
            }
          }
          return null;
        }
        """,
        entries,
    )
    if not step_id:
        return None
    for entry in entries:
        if entry["pageStepId"] == step_id:
            return entry
    return None


def derive_context(page: Any, entry: dict[str, Any], base_context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = page.evaluate(
        """
        ({ entry, baseContext }) => {
          const queryFirst = (selectors) => {
            for (const selector of selectors || []) {
              const node = document.querySelector(selector);
              if (node) return node;
            }
            return null;
          };
          const queryAll = (selectors) => {
            const seen = new Set();
            const elements = [];
            for (const selector of selectors || []) {
              for (const node of Array.from(document.querySelectorAll(selector))) {
                if (!seen.has(node)) {
                  seen.add(node);
                  elements.push(node);
                }
              }
            }
            return elements;
          };
          const readText = (node) => (node?.innerText || node?.textContent || "").replace(/\\s+/g, " ").trim();
          const parseEuro = (text) => {
            const match = text.match(/(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?)\\s*EUR/i);
            if (!match) return null;
            return Number(match[1].replace(/\\./g, "").replace(",", "."));
          };
          const parseRelevantPrice = (text) => {
            const patterns = [
              /Unser Angebot[^0-9]*(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?)\\s*EUR/iu,
              /Voraussichtliche Prämie[^0-9]*(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?)\\s*EUR/iu,
            ];
            for (const pattern of patterns) {
              const match = text.match(pattern);
              if (match) return Number(match[1].replace(/\\./g, "").replace(",", "."));
            }
            return null;
          };
          const selectedTariff = () => {
            const pressed = document.querySelector("[aria-pressed='true'][aria-label^='Wählen ']");
            if (pressed?.getAttribute("aria-label")) return pressed.getAttribute("aria-label").replace(/^Wählen\\s+/i, "").trim().toLowerCase();
            const selected = document.querySelector("[data-selected='true'][aria-label^='Wählen ']");
            if (selected?.getAttribute("aria-label")) return selected.getAttribute("aria-label").replace(/^Wählen\\s+/i, "").trim().toLowerCase();
            return null;
          };
          const selectedAddOns = (selectors) => {
            const values = [];
            for (const node of queryAll(selectors)) {
              if (!(node instanceof HTMLInputElement) || node.type !== "checkbox" || !node.checked) continue;
              const label = node.closest("label");
              const text = readText(label) || readText(node.parentElement) || node.getAttribute("aria-label") || "selected_add_on";
              values.push(text.toLowerCase());
            }
            return values;
          };
          const fieldCompletion = (selectors) => {
            const fields = queryAll(selectors);
            if (!fields.length) return null;
            let completed = 0;
            for (const field of fields) {
              if (field instanceof HTMLInputElement) {
                if (field.type === "checkbox" || field.type === "radio") {
                  if (field.checked) completed += 1;
                } else if (field.value.trim()) {
                  completed += 1;
                }
              } else if (field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
                if (field.value.trim()) completed += 1;
              } else if (readText(field)) {
                completed += 1;
              }
            }
            return Number((completed / fields.length).toFixed(2));
          };

          const derived = { ...baseContext };
          for (const extractor of entry.extractors || []) {
            const selectors = extractor.selectors || [];
            if (extractor.kind === "selectedTariff") {
              derived.selectedTariff = selectedTariff();
            } else if (extractor.kind === "selectedAddOns") {
              derived.selectedAddOns = selectedAddOns(selectors);
            } else if (extractor.kind === "fieldCompletion") {
              derived.fieldCompletion = fieldCompletion(selectors);
            } else if (extractor.kind === "validationErrorCount") {
              derived.validationErrorCount = document.querySelectorAll("[aria-invalid='true'], input:invalid, select:invalid, textarea:invalid").length;
            } else if (extractor.kind === "visiblePrice") {
              let value = null;
              for (const node of queryAll(selectors)) {
                const text = readText(node);
                value = parseRelevantPrice(text) ?? parseEuro(text);
                if (value !== null) break;
              }
              derived.visiblePrice = value;
            } else if (extractor.kind === "priceDelta") {
              let value = null;
              for (const node of queryAll(selectors)) {
                const text = readText(node);
                value = parseRelevantPrice(text) ?? parseEuro(text);
                if (value !== null) break;
              }
              if (value !== null && baseContext?.visiblePrice !== undefined && baseContext.visiblePrice !== null) {
                derived.priceDelta = Number((value - baseContext.visiblePrice).toFixed(2));
              } else if (value !== null) {
                derived.priceDelta = null;
              }
            } else if (extractor.kind === "sessionTiming") {
              const now = Date.now();
              if (!window.__uniqaRunnerSessionStartedAt) window.__uniqaRunnerSessionStartedAt = now;
              derived.sessionDurationMs = Math.max(0, now - window.__uniqaRunnerSessionStartedAt);
            } else if (extractor.kind === "socialInsuranceProvider") {
              const node = queryFirst(selectors);
              const value = readText(node);
              derived.socialInsuranceProviderCode = value === "ÖGK" ? "ogk" : null;
            } else if (extractor.kind === "ageBandFromDate") {
              const node = queryFirst(selectors);
              const value = node instanceof HTMLInputElement ? node.value : readText(node);
              derived.ageBand = value || null;
            }
          }
          derived.screenTitle = readText(document.querySelector("h1")) || readText(document.querySelector("[data-cy='consultationContact']")) || null;
          if ((derived.screenTitle || "").toLowerCase().includes("berateranfrage")) {
            derived.terminalScreen = "advisor_handoff";
          }
          return derived;
        }
        """,
        {"entry": entry, "baseContext": base_context or {}},
    )
    return context or {}


def capture_rich_context(page: Any) -> dict[str, Any]:
    """Capture a bounded, human-readable text transcript of the current screen.

    This is what the persona "reads" in place of a screenshot: headings, the
    visible body text, the choices it can make, tariff names/prices and whether
    each is available online, visible prices, term tooltips, and validation
    messages.
    """
    try:
        rich = page.evaluate(
            """
            () => {
              const MAX_BODY = 3500;
              const norm = (v) => (v == null ? "" : String(v)).replace(/\\s+/g, " ").trim();
              const visible = (el) => {
                if (!(el instanceof Element)) return false;
                const rects = el.getClientRects();
                if (!rects.length && !el.offsetWidth && !el.offsetHeight) return false;
                const style = window.getComputedStyle(el);
                return style.visibility !== "hidden" && style.display !== "none";
              };
              const textOf = (el) => norm(el && (el.innerText || el.textContent));

              const headings = [];
              for (const el of Array.from(document.querySelectorAll("h1, h2, legend"))) {
                if (visible(el)) { const t = textOf(el); if (t) headings.push(t); }
              }

              const region = document.querySelector("form")
                || document.querySelector("main")
                || document.querySelector("[role=main]")
                || document.body;
              let bodyText = norm(region && region.innerText);
              let bodyTruncated = false;
              if (bodyText.length > MAX_BODY) { bodyText = bodyText.slice(0, MAX_BODY); bodyTruncated = true; }

              const options = [];
              const seen = new Set();
              const optionSelectors = "label, [role=radio], [role=checkbox], button, [data-cy='nextStepButton'], [data-cy='backButton']";
              for (const el of Array.from(document.querySelectorAll(optionSelectors))) {
                if (!visible(el)) continue;
                const t = textOf(el) || norm(el.getAttribute("aria-label"));
                if (!t || t.length > 120) continue;
                const key = t.toLowerCase();
                if (seen.has(key)) continue;
                seen.add(key);
                const input = el.querySelector ? el.querySelector("input") : null;
                const role = el.getAttribute("role");
                const kind = role || el.tagName.toLowerCase();
                const checked = el.getAttribute("aria-checked") === "true" || Boolean(input && input.checked);
                const disabled = el.hasAttribute("disabled")
                  || el.getAttribute("aria-disabled") === "true"
                  || Boolean(input && input.disabled);
                options.push({ text: t, kind, checked: Boolean(checked), disabled: Boolean(disabled) });
                if (options.length >= 40) break;
              }

              const tariffs = [];
              for (const btn of Array.from(document.querySelectorAll("[aria-label^='Wählen ']"))) {
                const name = norm((btn.getAttribute("aria-label") || "").replace(/^Wählen\\s+/i, ""));
                if (!name) continue;
                let scope = btn.closest("th, td, [role=columnheader], li, article, div");
                let priceText = "";
                for (let i = 0; i < 4 && scope; i++) {
                  const m = textOf(scope).match(/(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?)\\s*EUR/i);
                  if (m) { priceText = m[1]; break; }
                  scope = scope.parentElement;
                }
                const onlineEligible = !/opt\\.?\\s*plus|premium/i.test(name);
                tariffs.push({ name, monthly_price: priceText || null, online_eligible: onlineEligible });
              }

              const prices = [];
              const bodyForPrice = textOf(region);
              const priceRe = /([A-Za-zÄÖÜäöüß .]{0,40}?)(\\d{1,3}(?:\\.\\d{3})*(?:,\\d{2})?)\\s*EUR/g;
              let pm; let pc = 0;
              while ((pm = priceRe.exec(bodyForPrice)) !== null && pc < 12) {
                prices.push({ label: norm(pm[1]), amount: pm[2] + " EUR" });
                pc++;
              }

              const tooltips = [];
              for (const el of Array.from(document.querySelectorAll("[role=tooltip], [data-cy*='tooltip'], [title]"))) {
                const t = textOf(el) || norm(el.getAttribute("title"));
                if (t && t.length <= 240 && !tooltips.includes(t)) tooltips.push(t);
                if (tooltips.length >= 15) break;
              }

              const validationMessages = [];
              for (const el of Array.from(document.querySelectorAll("[role=alert], [aria-invalid='true']"))) {
                if (!visible(el)) continue;
                const t = textOf(el) || norm(el.getAttribute("aria-label"));
                if (t) validationMessages.push(t.slice(0, 160));
                if (validationMessages.length >= 10) break;
              }

              const cta = document.querySelector("[data-cy='nextStepButton']");
              const primaryCtaLabel = cta ? (textOf(cta) || norm(cta.getAttribute("aria-label"))) : null;

              return { headings, bodyText, bodyTruncated, options, tariffs, prices, tooltips, validationMessages, primaryCtaLabel };
            }
            """
        )
    except Exception:
        return {}
    return rich or {}


def install_runner_shim(page: Any, *, preferred_session_id: str | None = None) -> None:
    serialized_session = json.dumps(preferred_session_id)
    script = """
        (() => {{
          const preferredSessionId = __PREFERRED_SESSION_ID__;
          window.__UNIQA_PREFERRED_SESSION_ID = preferredSessionId || undefined;
          window.__uniqaRunnerSessionStartedAt = Date.now();
          window.__uniqaRunnerTelemetry = {{ events: [] }};
          const pushEvent = (type, target, extra = {{}}) => {{
            const element = target instanceof Element ? target.closest("button, input, textarea, select, [role='button'], [role='radio'], [role='checkbox']") || target : null;
            const payload = {{
              ts: Date.now(),
              type,
              tag: element?.tagName?.toLowerCase() || null,
              dataCy: element?.getAttribute?.("data-cy") || null,
              ariaLabel: element?.getAttribute?.("aria-label") || null,
              text: (element?.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 80),
              ...extra,
            }};
            window.__uniqaRunnerTelemetry.events.push(payload);
          }};
          document.addEventListener("click", (event) => pushEvent("click", event.target), true);
          document.addEventListener("change", (event) => pushEvent("change", event.target), true);
          document.addEventListener("input", (event) => pushEvent("input", event.target), true);
          document.addEventListener("pointerenter", (event) => pushEvent("pointerenter", event.target), true);
        }})();
        """.replace("__PREFERRED_SESSION_ID__", serialized_session)
    page.add_init_script(
        script,
    )


def read_runner_shim(page: Any) -> list[dict[str, Any]]:
    return page.evaluate("() => window.__uniqaRunnerTelemetry?.events ?? []")


def read_extension_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const root = document.querySelector("#uniqa-conversion-coach-root");
          const state = window.__UNIQA_COACH_STATE__ || {};
          const numberOrZero = (value) => {
            const parsed = Number(value ?? 0);
            return Number.isFinite(parsed) ? parsed : 0;
          };
          return {
            activeActionIds: state.activeActionIds || [],
            actionable: Boolean(state.actionable),
            apiState: state.apiState || root?.dataset?.apiState || null,
            cardCount: Number(state.cardCount ?? root?.dataset?.cardCount ?? 0),
            currentStepId: state.currentStepId || root?.dataset?.currentStepId || null,
            decisionState: state.decisionState || root?.dataset?.decisionState || "idle",
            initialized: Boolean(state.initialized || root),
            lastActionResult: state.lastActionResult || null,
            lastRenderAt: Number(state.lastRenderAt ?? root?.dataset?.lastRenderAt ?? 0),
            playId: state.playId || root?.dataset?.playId || null,
            requestFinishedAt: numberOrZero(state.requestFinishedAt ?? root?.dataset?.requestFinishedAt),
            requestStartedAt: numberOrZero(state.requestStartedAt ?? root?.dataset?.requestStartedAt),
            layoutFallback: state.layoutFallback || root?.dataset?.layoutFallback || null,
            renderState: state.renderState || root?.dataset?.renderState || null,
            rootAttached: Boolean(root?.shadowRoot),
          };
        }
        """
    )


def wait_for_extension_ready(page: Any, *, timeout_ms: int = 10_000, settle_ms: int = 150) -> bool:
    started = time.time()
    while (time.time() - started) * 1000 < timeout_ms:
        try:
            state = read_extension_state(page)
            if state.get("rootAttached") and state.get("initialized") and state.get("apiState") in {"starting", "connected", "error"}:
                if settle_ms > 0:
                    page.wait_for_timeout(settle_ms)
                return True
        except Exception:
            pass
        page.wait_for_timeout(150)
    return False


def wait_for_coach_render(
    page: Any,
    *,
    timeout_ms: int,
    settle_ms: int = 0,
    require_actionable: bool = True,
) -> bool:
    if timeout_ms <= 0:
        return False
    started = time.time()
    while (time.time() - started) * 1000 < timeout_ms:
        try:
            state = read_extension_state(page)
            has_card = state.get("cardCount", 0) > 0 and state.get("renderState") == "rendered"
            is_actionable = bool(state.get("actionable")) or not require_actionable
            if has_card and is_actionable:
                if settle_ms > 0:
                    page.wait_for_timeout(settle_ms)
                return True
        except Exception:
            pass
        page.wait_for_timeout(150)
    return False


def wait_for_coach_cycle(
    page: Any,
    *,
    step_id: str,
    entered_at: int,
    timeout_ms: int,
    settle_ms: int = 0,
) -> dict[str, Any] | None:
    if timeout_ms <= 0:
        return None
    started = time.time()
    while (time.time() - started) * 1000 < timeout_ms:
        try:
            state = read_extension_state(page)
            if state.get("currentStepId") != step_id:
                page.wait_for_timeout(150)
                continue
            if int(state.get("requestFinishedAt", 0) or 0) < entered_at:
                page.wait_for_timeout(150)
                continue
            if state.get("decisionState") in {"rendered", "empty", "error"}:
                if settle_ms > 0:
                    page.wait_for_timeout(settle_ms)
                return state
        except Exception:
            pass
        page.wait_for_timeout(150)
    return None


def dismiss_cookie_banner(page: Any) -> None:
    buttons = [
        page.get_by_role("button", name="Alle ablehnen außer technisch notwendige Cookies"),
        page.get_by_role("button", name=re.compile("alle ablehnen", re.IGNORECASE)),
    ]
    for button in buttons:
        try:
            if button.is_visible(timeout=1_000):
                button.click(force=True)
                return
        except Exception:
            continue
    try:
        clicked = page.evaluate(
            """
            () => {
              const buttons = Array.from(document.querySelectorAll("unext-cookie-banner button, .cc__buttons button, button"));
              const target = buttons.find((button) => {
                const text = (button.textContent || "").replace(/\\s+/g, " ").trim().toLowerCase();
                return text.includes("ablehnen") || text.includes("technisch notwendige");
              });
              if (target instanceof HTMLButtonElement) {
                target.click();
                return true;
              }
              return false;
            }
            """
        )
        if clicked:
            page.wait_for_timeout(750)
            return
    except Exception:
        pass
    try:
        page.evaluate(
            """
            () => {
              const banner = document.querySelector("unext-cookie-banner");
              if (banner) {
                banner.remove();
              }
              document.querySelectorAll(".cc__backdrop, .cc__modal, .cc-window").forEach((node) => node.remove());
            }
            """
        )
        page.wait_for_timeout(250)
    except Exception:
        pass


def generate_sv(day: int, month: int, year: int) -> str:
    yy = str(year)[-2:]
    dd = f"{day:02d}"
    mm = f"{month:02d}"
    birth = f"{dd}{mm}{yy}"
    for serial in range(100, 1000):
        digits = [int(char) for char in f"{serial:03d}{birth}"]
        checksum = (3 * digits[0] + 7 * digits[1] + 9 * digits[2] + 5 * digits[3] + 8 * digits[4] + 4 * digits[5] + 2 * digits[6] + digits[7] + 6 * digits[8]) % 11
        if checksum != 10:
            return f"{serial:03d}{checksum}{birth}"
    raise RuntimeError("Unable to generate a valid SV number")


def choose_no_for_question_group(page: Any, data_cy: str) -> None:
    group = page.locator(f"[data-cy='{data_cy}']")
    no_input = group.locator("label").filter(has_text=re.compile("^nein$", re.IGNORECASE)).locator("input")
    if no_input.count() > 0:
        no_input.first.check(force=True)
        return
    radio_inputs = group.locator("input[type='radio']")
    count = radio_inputs.count()
    if count == 0:
        raise RuntimeError(f"No radio inputs found for question group {data_cy}")
    radio_inputs.nth(count - 1).check(force=True)
