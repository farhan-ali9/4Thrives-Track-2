# Browser Runner

Playwright sessions for baseline (no extension) vs coach (extension + runtime API) on the live UNIQA calculator.

## Modes

| Mode | Purpose |
|------|---------|
| `mock` | Deterministic traces for unit tests |
| `validation` | Small live smoke batch with screenshots |
| `bulk` | Evaluation batch after validation |

Execution modes: `baseline` (telemetry shim only) or `coach` (loads extension, posts runtime outcome).

## Environment

Set in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXTENSION_DIST` | `./extension/dist` | Built extension for coach mode |
| `COACH_API_URL` | `http://127.0.0.1:8787` | Runtime API |
| `RUNNER_OUTPUT_DIR` | `artifacts/browser-runs` | Trace output |
| `LLM_PROVIDER` | `local` | `local` (Ollama) or `remote` (Featherless) |
| `LLM_API_URL` | Ollama or Featherless URL | Persona LLM endpoint |
| `LLM_MODEL` | `qwen2.5:3b-instruct` | Persona model |
| `RUNNER_HEADLESS` | `0` | Set `1` for headless bulk |

Optional tuning: `LLM_TIMEOUT_S`, `LLM_MAX_ATTEMPTS`, `LLM_RETRY_BACKOFF_S`, `RUNNER_LOG_LEVEL`.

## Outcome rules

- In-scope Start/Optimal journeys reaching `s8_confirm` → `converted_online` (observation boundary; no form submit).
- Hospital, other persons, Opt. Plus/Premium → `submitted_advisor_lead`.
- Early exit → `abandoned`.

Patch mislabeled traces: `python3 scripts/patch_s8_trace_outcomes.py <trace-dirs...>`

## Key modules

- `run_batch.py` — persona matrix scheduling + circuit breakers
- `run_session.py` — live browser loop
- `llm_persona.py` — LLM persona driver with policy fallback
- `persona_policy.py` — rule-based fallback + outcome classification
- `live_page.py` — step detection + rich page context for the LLM

## Trace contents

Each session JSON includes `events`, `llm_decisions`, `artifacts` (screenshots/DOM), `coach_render_log` (coach mode), and `terminal_outcome`.
