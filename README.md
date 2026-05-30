# UNIQA Conversion Coach

Workspace for the live Chrome extension, the production rule-driven coach API,
the admin portal, and the original simulator/demo assets.

## Packages

- `extension/`: Chrome extension that detects funnel state on the live UNIQA calculator and requests hints from the remote coach API.
- `coach-api/`: Fastify + Prisma backend for coach evaluation, admin auth, policy versioning, and static serving of the admin SPA.
- `admin-portal/`: React/Vite admin UI for policy settings, intervention copy, rules, and version restore.
- `shared/`: Shared contracts, policy schema, and seeded default policy.
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

Set environment variables from `.env.example`. For the coach API and admin
portal, you need a Postgres database.

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

Run the admin portal in standalone Vite mode:

```bash
npm run dev:admin
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8787`.

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

- `POST /api/v1/coach/evaluate`
- `POST /api/v1/admin/login`
- `POST /api/v1/admin/logout`
- `GET /api/v1/admin/me`
- `GET /api/v1/admin/policy`
- `PUT /api/v1/admin/policy`
- `GET /api/v1/admin/policies`
- `POST /api/v1/admin/policies/:id/restore`
- `GET /healthz`

Important behavior:

- The extension no longer falls back to a local mock engine.
- Coach failures return `source: "remote_error"` with an empty `actions` array.
- Policy versions are append-only snapshots stored in Postgres.
- The bootstrap admin account is created or updated from environment variables
  on startup.

## Build And Test

```bash
npm run build
npm test
python -m unittest browser-runner/tests/test_llm_persona.py training/tests/test_build_live_datasets.py training/tests/test_user_policy.py training/tests/test_uniqa_pipeline.py
```

`npm test` rebuilds the shared workspace first so the extension and backend
tests always execute against the current shared contracts/schema.

Live extension smoke:

```bash
cd extension
npm run test:live
```

## Live Simulation CLI

The repo now exposes one CLI for live simulation, dataset building, training, evaluation, and optional Leonardo submission:

```bash
./uniqa-pipeline validate-live --execution-mode baseline
./uniqa-pipeline validate-live --execution-mode coach
./uniqa-pipeline run-live --execution-mode coach --sessions 300
./uniqa-pipeline local-full-loop --validate-sessions 12 --bulk-sessions 300
./uniqa-pipeline build-datasets --traces artifacts/browser-runs
./uniqa-pipeline train-user-policy
./uniqa-pipeline train-coach-ranker
./uniqa-pipeline evaluate --runner-mode validation
```

Trace files now include runner-owned LLM decision logs, per-step screenshots and DOM snapshots, and a normalized `run_mode` / `instrumentation_mode` split so baseline and coached sessions can be used together.

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

## Known Limitation

The verified live page map still covers steps 1-6. Steps `s7_final_price` and
`s8_confirm` remain disabled until the live UNIQA DOM for those screens is
re-verified and stable enough to support selectors without brittle assumptions.
