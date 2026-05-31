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
export FEATHERLESS_API_KEY=...
export EXTENSION_DIST=/absolute/path/to/extension/dist
export COACH_API_URL=http://127.0.0.1:8787
export RUNNER_OUTPUT_DIR=artifacts/browser-runs
export LLM_API_URL=https://api.featherless.ai/v1/chat/completions
export LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

Live runs refuse to submit purchases. `s8_confirm` is treated as an observation boundary, not a submission step.

If `EXTENSION_DIST` is unset, the runner now auto-detects a local `extension/dist` build in this repo.

## Safety Breakers

`run_batch.py` classifies failures into:

- `selector`: selector drift or missing expected UI
- `backend`: backend timeout or connection failure
- `page`: live page load or unclassified browser failure

The result JSON includes `failures`, `failure_log`, and `circuit_breaker` so failed batches can be excluded or debugged before metrics are reported.

## LLM Persona Driver

`llm_persona.py` drives the simulated customer with an OpenAI-compatible chat endpoint. The default local path is Featherless:

- persona briefing + seeded overlay
- current step snapshot and visible price context
- recent decision history
- strict JSON action schema with runner-side fallback to the existing persona policy

Default local runner settings:

- calculator URL: `https://www.uniqa.at/rechner/krankenversicherung/`
- LLM endpoint: `https://api.featherless.ai/v1/chat/completions`
- model fallback: `Qwen/Qwen2.5-7B-Instruct`
- optional attribution headers: `LLM_HTTP_REFERER`, `LLM_APP_TITLE`

Each trace stores:

- `run_mode`
- `instrumentation_mode`
- `llm_decisions`
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
