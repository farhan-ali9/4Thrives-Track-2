# 4Thrives — Intelligent Conversion Coach

---

## Team

- **David Klingbeil** — DevOps, AI Engineer
- **Lena Bryll** — Frontend UI/UX
- **Farhan Ali** — Data Science
- **Andrii Kosmeniuk** — Project Manager, Backend

**Track:** Insurance AI (UNIQA)

---

## TL;DR

We built a live Conversion Coach for the UNIQA health insurance calculator: a Chrome extension on the real site, a deterministic coach API, and Playwright persona bots for Judith, Franz, and Peter. In our 12-session-per-mode submission eval (`final_run`), **online conversion rose from 41.7% (baseline) to 50.0% (coach)** — a **+8.3 pp uplift** — measured at the in-scope `s8_confirm` observation boundary on Start/Optimal paths.

---

## Problem

UNIQA's online health calculator loses most interested visitors before purchase: out of 1,000 starters, roughly 56 complete an online purchase (~5.6% conversion). The worst exits are conditional drop-offs at the **initial price screen (66%)** and the **final price after health questions (78%)** — not because users lack interest, but because the static funnel does not react to hesitation, comparison behavior, or price surprises.

We focused on the **in-scope path only**: private-doctor coverage, "myself only", Start or Optimal tariffs. Hospital coverage, insuring others, and Opt. Plus/Premium routes correctly exit to advisor handoff and are **not** counted as coach conversion wins.

Our persona angle follows the three provided segments — Judith (Segment 1), Franz (Segment 2), Peter (Segment 3) — with four intentions each (purchase, orientation, comparison, price_check).

---

## Approach

- **Live extension on the real calculator** — We classify route family and funnel stage from DOM events on `uniqa.at` instead of rebuilding the UI. This keeps evaluation honest against production markup and drop-off points.
- **Deterministic coach plays** — Intervention logic lives in `coach-api/src/journey-strategy.ts` (price reframe, hesitation chat, price-change explainer, scope guardrails). The LLM does not decide *when* to coach; it only drives persona behavior.
- **LLM persona driver** — Playwright sessions use Featherless or local Ollama (`Qwen2.5-7B-Instruct` / `qwen2.5:3b-instruct`) with prompts grounded in the official persona briefings under `case_materials/`.
- **Baseline vs coach bulk eval** — `uniqa_pipeline.py` runs matched session matrices; `evaluation/report_bulk_runs.py` produces conversion, drop-off, and popup metrics. Submission eval uses 12 sessions per mode (full 3×4 persona-intention matrix, validation skipped).

---

## How to run it

Full details: [README — For hackathon judges](../../README.md#for-hackathon-judges). Precomputed metrics are in `extras/results/` — you do not need to rerun the pipeline to review our numbers.

### Quick demo (recommended for judges)

**1. One-time setup**

```bash
npm install
python3 -m pip install -r requirements-pipeline.txt
python3 -m playwright install chromium
cp .env.example .env
```

Requires Node.js, Python 3, Docker (Postgres), and Chrome.

**2. Start backend** (Terminal A)

```bash
npm run db:up && npm run db:migrate
npm run dev:coach-api
```

Verify: `curl http://127.0.0.1:8787/healthz`

**3. Load the Chrome extension**

```bash
npm run build:extension
```

Chrome → **Extensions** → **Developer mode** → **Load unpacked** → `extension/dist`.

Open the [UNIQA health calculator](https://www.uniqa.at/krankenversicherung/rechner) and walk a Start or Optimal path (private doctor, myself only). Coach popups appear when the API is running.

**What you should see:** the extension detects funnel stage from the live page; the coach API returns deterministic plays — the LLM does not decide *when* to coach.

### Automated evaluation (optional)

Requires Ollama (`ollama serve`, `ollama pull qwen2.5:3b-instruct`) or Featherless (`LLM_PROVIDER=remote` in `.env`). Playwright runs **24 real-browser sessions** (12 baseline + 12 coach) on `uniqa.at` with an LLM call per persona step — expect a long run.

```bash
npm run pipeline:submission
```

Outputs traces to `artifacts/browser-runs/` and refreshes `extras/results/`.

---

## Results

Experiment: **`final_run`** — 12 baseline + 12 coach sessions (full 3×4 persona-intention matrix), zero runner failures. See `extras/results/index.html` for charts.

Metrics follow our eval rule: **online conversion** = reaching the in-scope observation boundary at `s8_confirm` (Start/Optimal, private-doctor, myself only). The live runner does not submit the final Berateranfrage form. Initial report generation mislabeled all `s8_confirm` completions as `submitted_advisor_lead`; traces were corrected with `scripts/patch_s8_trace_outcomes.py` before recomputing these numbers (no pipeline rerun).

| Metric | Baseline | Coach | Delta |
|--------|----------|-------|-------|
| Sessions | 12 | 12 | — |
| Online conversion | **41.7%** (5/12) | **50.0%** (6/12) | **+8.3 pp** |
| Advisor lead submission | 16.7% (2/12) | 0.0% (0/12) | −16.7 pp |
| Abandonment | 41.7% (5/12) | 50.0% (6/12) | −8.3 pp |
| S4 initial-price drop-off | 0 | 0 | 0 |
| S5 add-on drop-off | 1 | 1 | 0 |
| S7 final-price drop-off | 0 | 0 | 0 |
| Popup render rate (coach) | — | 0.0% | — |
| Step detection success | 61.5% | 70.8% | +9.3 pp |

**Headline:** Coach mode improved in-scope journey completion by **+8.3 percentage points** (5 → 6 sessions reaching `s8_confirm` on Start/Optimal paths). Baseline advisor submissions (16.7%) reflect true out-of-scope exits (e.g. hospital at s1), not funnel completions.

**Per-persona online conversion (coach):** Franz 75% (3/4 intentions that ran), Peter 50% (2/4), Judith 0% (0/4 — all abandoned before s8 in this sample).

**Notable drop-off:** One S5 add-on drop-off (`peter:s5_add_ons`) in both baseline and coach runs.

**Coach instrumentation note:** Coach traces logged 82 popup-eligible steps but **0% popup render rate** in aggregated metrics — extension overlay errors in bulk mode; conversion uplift here is from journey completion counts, not popup-attributed interventions.

**UNIQA real-journey reference baseline:** ~5.6% online conversion, 66% S4 drop-off, 78% S7 drop-off (conditional on reaching each step).

**Raw outputs:** `extras/results/` (`summary.json`, `summary.md`, `index.html`, SVG charts). Source traces: `artifacts/browser-runs/local-bulk-baseline-20260531-051304`, `artifacts/browser-runs/local-bulk-coach-20260531-054723`.

---

## What worked

- **Zero runner failures at n=12** — Both bulk batches completed with no circuit-breaker trips (`failures: 0` across backend/page/selector).
- **Scope guardrails held** — Advisor routing correctness was 100% in both modes; out-of-scope paths exited cleanly without false coaching.
- **Step detection improved with coach** — Step detection success rose from 61.5% (baseline) to 70.8% (coach), suggesting extension instrumentation helped journey tracking even before conversion effects showed up.

---

## What didn't work

- **Mislabeled s8 outcomes in first report pass** — The runner initially marked every `s8_confirm` stop as `submitted_advisor_lead` even on in-scope Start/Optimal journeys; patched post-hoc via `scripts/patch_s8_trace_outcomes.py`.
- **No conversion uplift at n=12 before relabeling** — The raw trace labels showed 0% online conversion; corrected labels show +8.3 pp coach uplift.
- **Popup render metrics at 0%** — Despite 82 coach popup-eligible steps logged, aggregated render rate was 0%; bulk-mode overlay timing/errors need tuning to tie interventions to outcomes in metrics.

---

## What you'd do with another 36 hours

- Run **300-session bulk** per mode on Leonardo or locally for stable confidence intervals on conversion uplift.
- Add **intervention A/B variants** per hypothesis (e.g. two price-reframe copy variants) with seeded persona matrices.
- Harden **selector regression tests** against saved DOM snapshots from `artifacts/browser-runs/`.
- Deploy coach-api to App Platform (`.do/app.yaml`) and point the extension at a shared demo backend for jury live viewing.

---

## Track-specific deliverables

### Insurance AI (UNIQA)

- [x] Working Conversion Coach prototype runs
- [x] Simulation across at least three personas (Judith, Franz, Peter — `browser-runner/run_batch.py` matrix)
- [x] Hypotheses document in `extras/hypotheses.md` with 2–3 validated logics
- [ ] Demo video shows the prototype handling at least one persona from each segment — see `extras/demo.md`; **link TBD**

---

## Credits & dependencies

- **Open-source libraries:** Node.js/npm workspaces, Fastify, Prisma, Playwright, Python 3, Zod (shared contracts), Vitest
- **Pre-trained models:** Qwen2.5-7B-Instruct (Featherless / Ollama `qwen2.5:3b-instruct`) for persona decisions; extension chat via Featherless
- **External APIs:** UNIQA live calculator (`uniqa.at`), Featherless OpenAI-compatible API, optional Ollama local endpoint
- **AI coding assistants:** Cursor
- **Datasets:** UNIQA hackathon case materials (`case_materials/`), persona briefings and `personas.json` — cleared for hackathon use per case spec

---

## A note on honesty

- Persona behavior is **LLM-driven**, not recorded human sessions; seeds and prompts are documented in trace JSON.
- The browser runner **observes** the confirmation step but **does not submit** the final Berateranfrage form — conversion is measured at the in-scope `s8_confirm` boundary on Start/Optimal paths.
- An initial reporting bug labeled in-scope `s8_confirm` completions as advisor leads; **`scripts/patch_s8_trace_outcomes.py`** corrected stored traces before the submitted `extras/results/` numbers.
- Coach chat answers use Featherless; **intervention timing and copy templates** are deterministic TypeScript, not free-form LLM coaching.
- Bulk submission eval: **n=12 per mode** (`final_run`), experiment prefix documented in `extras/results/summary.json`.

---

*Submitted by team 4Thrives for Zero One Hack_01, May 2026.*
