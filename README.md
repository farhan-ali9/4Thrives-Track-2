# UNIQA Conversion Coach

Workspace for the live Chrome extension, the deterministic runtime API,
and the live browser runner used for baseline-vs-coach bulk runs.

## Packages

- `extension/`: Chrome extension that classifies the live UNIQA calculator into route families and stages, then renders one runtime decision at a time.
- `coach-api/`: Fastify + Prisma backend exposing the clean runtime endpoints for decisions, outcomes, and session replay.
- `admin-portal/`: Legacy admin UI kept in the workspace but no longer required by the MVP runtime.
- `shared/`: Shared runtime contracts used by the extension and runtime API.
- `coach_sim/`: Simulation backend used for the hackathon demo and synthetic evaluation.
- `streamlit_app/`: Streamlit demo UI for the simulator.

## Install

```bash
npm install
```

Python/Streamlit tooling remains separate:

```bash
python -m pip install -r streamlit_app/requirements.txt
```

For the live browser pipeline:

```bash
python3 -m pip install -r requirements-pipeline.txt
python3 -m playwright install chromium
```

## Local Development

Set environment variables from `.env.example`. For the coach API runtime you
need a Postgres database.

Start the local Postgres database:

```bash
npm run db:up
npm run db:migrate
```

Useful database commands:

```bash
npm run db:logs
npm run db:down
npm run db:reset
```

Start the backend:

```bash
npm run dev:coach-api
```

Build the extension:

```bash
npm run build:extension
```

Load `extension/dist` as an unpacked Chrome extension.

The extension manifest is generated at build time and always includes:

- `https://www.uniqa.at/*`
- `http://127.0.0.1:8787/*`
- the configured `VITE_COACH_API_ORIGIN`
- any comma-separated `VITE_COACH_API_EXTRA_ORIGINS`

## Backend/API

Public routes:

- `POST /api/runtime/decide`
- `POST /api/runtime/outcome`
- `GET /api/runtime/sessions/:id`
- `GET /healthz`

Important behavior:

- The extension owns session state and sends compact journey snapshots.
- The runtime returns at most one deterministic conversion play per request.
- Postgres is used as a telemetry sink for snapshots, decisions, and outcomes.
- The old policy/admin runtime is no longer part of the MVP request path.

## Build And Test

```bash
npm run build
npm test
python3 -m unittest \
  browser-runner/tests/test_backend_client.py \
  browser-runner/tests/test_live_page_extension_state.py \
  browser-runner/tests/test_mock_runner.py \
  browser-runner/tests/test_run_batch.py \
  training/tests/test_uniqa_pipeline.py \
  evaluation/tests/test_metrics.py \
  evaluation/tests/test_report_bulk_runs.py
```

`npm test` rebuilds the shared workspace first so the extension and backend
tests always execute against the current shared contracts/schema.

Live extension smoke:

```bash
cd extension
npm run test:live
```

## Live Simulation CLI

The active CLI is intentionally small and only supports live baseline/coach runs plus offline artifact reporting:

```bash
./uniqa-pipeline validate-live --execution-mode baseline
./uniqa-pipeline validate-live --execution-mode coach
./uniqa-pipeline run-live --execution-mode coach --sessions 300
./uniqa-pipeline local-full-loop --validate-sessions 12 --bulk-sessions 300
python3 evaluation/report_bulk_runs.py \
  --baseline artifacts/browser-runs/<run>/baseline-bulk \
  --coach artifacts/browser-runs/<run>/coach-bulk \
  --output-dir artifacts/reports/<run>
```

Trace files now include runner-owned `events`, `llm_decisions`, per-step screenshots and DOM snapshots, `runtime_trace` for coach sessions, and `coach_render_log` so popup timing can be audited offline.

The local-machine workflow is now the primary path:

- Set `FEATHERLESS_API_KEY` in `.env`.
- Start the local DB and coach API.
- Run [LOCAL_FULL_LOOP_COMMANDS.md](/Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2/LOCAL_FULL_LOOP_COMMANDS.md) for the exact command sequence.
- For a single command, use `bash scripts/run_local_full_loop.sh` or `npm run pipeline:local`.

Featherless is used as the default runner-side LLM provider via its OpenAI-compatible endpoint at [https://api.featherless.ai/v1/chat/completions](https://api.featherless.ai/v1/chat/completions). The model list is available at [https://api.featherless.ai/v1/models](https://api.featherless.ai/v1/models).

## DigitalOcean Deployment

Files added for deployment:

- [Dockerfile](/Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2/Dockerfile)
- [.do/app.yaml](/Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2/.do/app.yaml)
- [coach-api/prisma/migrations/20260530111500_init/migration.sql](/Users/davidklingbeil2/Documents/Hackathon/Uniqa_hackathon/4Thrives-Track-2/coach-api/prisma/migrations/20260530111500_init/migration.sql)

The App Platform template expects:

- a Docker build from the repo root
- one web service serving both the API and built admin SPA
- one managed Postgres database exposed to the service as `DATABASE_URL`
- runtime secrets for `SESSION_SECRET` and bootstrap admin credentials

Update `.do/app.yaml` with the real GitHub repo before deploying.

## Reporting Outputs

`evaluation/report_bulk_runs.py` writes:

- `summary.json`
- `summary.md`
- `outcomes.svg`
- `dropoffs.svg`
- `popup_rendering.svg`
- `index.html`
