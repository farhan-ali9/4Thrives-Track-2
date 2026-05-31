# Browser Runner

Andrii-owned runner entry points for persona-driven UNIQA calculator sessions.

## Modes

- `mock`: deterministic local trace generation for unit tests and smoke checks only.
- `validation`: low-concurrency live browser sessions with screenshots and conservative circuit breakers.
- `bulk`: capped-concurrency trace generation after validation succeeds.

Execution modes inside live runs:

- `baseline`: no extension loaded, but a lightweight runner telemetry shim records comparable interaction events.
- `coach`: loads the UNIQA extension, waits for the popup lifecycle on each step, posts a single runtime outcome, and embeds runtime replay into the local trace.

## Live Requirements

Set these before live runs:

```bash
export EXTENSION_DIST=/absolute/path/to/extension/dist
export COACH_API_URL=http://127.0.0.1:8787
export RUNNER_OUTPUT_DIR=artifacts/browser-runs
export LLM_PROVIDER=local
export LLM_API_URL=http://localhost:11434/v1/chat/completions
export LLM_MODEL=qwen2.5:3b-instruct
export LLM_TIMEOUT_S=120
```

### Local model (Ollama)

Recommended on Apple Silicon (e.g. MacBook Air M3): run the persona model locally and
avoid remote timeouts.

1. Install and start Ollama: `brew install ollama` (or the desktop app), then `ollama serve`.
2. Pull the model: `ollama pull qwen2.5:3b-instruct`
3. Set the env block above (or copy from `.env.example`).

Optional: larger context for long persona briefings + rich page text. Create a Modelfile:

```
FROM qwen2.5:3b-instruct
PARAMETER num_ctx 8192
```

Then `ollama create uniqa-qwen3b -f Modelfile` and set `LLM_MODEL=uniqa-qwen3b`.

Pre-warm before a batch so the model stays loaded (first call is slow):

```bash
OLLAMA_KEEP_ALIVE=30m ollama serve
# or one warm-up request:
curl -s http://localhost:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:3b-instruct","messages":[{"role":"user","content":"ok"}]}'
```

To switch back to Featherless remotely, set `LLM_PROVIDER=remote`, point `LLM_API_URL`
at `https://api.featherless.ai/v1/chat/completions`, set `LLM_MODEL`, and export
`FEATHERLESS_API_KEY`.

### Rich page context

The persona is text-only. Instead of a screenshot, on each step the runner captures a
faithful text transcript of the screen via `capture_rich_context()` in `live_page.py`
and passes it to the model under `step_context.rich`:

- `headings` and the bounded visible `bodyText`
- `options`: the choices it can pick (with checked/disabled state)
- `tariffs`: tariff names, monthly prices, and whether each is available online
- `prices`: visible EUR amounts with their nearby labels
- `tooltips`: term explanations (e.g. the unfamiliar terms Judith hovers on)
- `validationMessages` and the `primaryCtaLabel`

### Endpoint resilience

The driver retries transient failures (`429`/`5xx`/network timeouts) with backoff.
For remote Featherless, it also sends a browser `User-Agent` (Cloudflare rejects the
default `Python-urllib` UA with a 403 `error code 1010`):

```bash
export LLM_USER_AGENT="Mozilla/5.0 ..."   # optional override of the default browser UA
export LLM_MAX_ATTEMPTS=3                  # transient-retry attempts per decision
export LLM_RETRY_BACKOFF_S=2               # base backoff seconds (grows per attempt)
export LLM_TIMEOUT_S=120                   # local Ollama first load can be slow
export RUNNER_LOG_LEVEL=INFO               # stderr progress logs during live runs
```

If the model is unavailable after retries, the decision falls back to the rule-based
persona policy (`fallback_used: true` with low `latency_ms` in the trace).

Live runs refuse to submit purchases. `s8_confirm` is treated as an observation boundary, not a submission step.

If `EXTENSION_DIST` is unset, the runner now auto-detects a local `extension/dist` build in this repo.

## Safety Breakers

`run_batch.py` classifies failures into:

- `selector`: selector drift or missing expected UI
- `backend`: backend timeout or connection failure
- `page`: live page load or unclassified browser failure

The result JSON includes `failures`, `failure_log`, and `circuit_breaker` so failed batches can be excluded or debugged before metrics are reported.

## LLM Persona Driver

`llm_persona.py` drives the simulated customer with an OpenAI-compatible chat endpoint
(Ollama locally, Featherless remotely):

- persona briefing + seeded overlay (overlay values are soft tendencies, not hard rules)
- a rich text transcript of the current screen (`step_context.rich`; see Rich page context)
- current step snapshot and visible price context
- the rendered coach popup text (when a coach card is present)
- recent decision history
- strict JSON action schema with runner-side fallback to the existing persona policy

The model decides everything in character: the step action, `dwell_ms` (how long this
person would read/deliberate), free-text `reasoning`, and `coach_interaction`. The coach
choice is driven by the popup's actual wording, not a deterministic hash roll:

- `cta` — click the coach call-to-action
- `dismiss` — actively close the coach card
- `ignore` — leave it untouched (also the default when no card is present, when the
  persona is abandoning, or when the LLM call fails and the policy fallback is used)

Default local runner settings:

- calculator URL: `https://www.uniqa.at/rechner/krankenversicherung/`
- LLM endpoint (local): `http://localhost:11434/v1/chat/completions`
- model (local): `qwen2.5:3b-instruct`
- optional attribution headers (remote only): `LLM_HTTP_REFERER`, `LLM_APP_TITLE`

Each trace stores:

- `run_mode`
- `instrumentation_mode`
- `llm_decisions` (including `coach_interaction` per decision)
- `artifacts`
- `shim_events`


## Runtime Client

`backend_client.py` wraps the clean runtime API used by coach-mode runs:

- `POST /api/runtime/outcome`
- `GET /api/runtime/sessions/:id`

The runner owns the trace artifact locally. Runtime replay is supplemental and lands in the trace as `runtime_trace`.


## Event Factory

`event_factory.py` builds canonical runner events for mock/live telemetry. It derives flags for:

- `tariff_click_oos`
- `path_oos`
- `inactivity`
- `price_hover`
- `cancel_hover`
- `scroll`
- `coach_cta_clicked`
- `coach_dismissed`
- `price_changed`
- `advisor_terminal`
