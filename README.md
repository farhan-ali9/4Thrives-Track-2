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

## Local Startup

Set environment variables from `.env.example`. The coach API and admin portal
use Postgres, and the local database container is exposed on host port `5433`.

1. Start the database:

```bash
npm run db:up
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/conversion_coach npm run db:migrate
```

2. Start the backend/API:

```bash
npm run dev:coach-api
```

The API listens on `http://127.0.0.1:8787`.

3. Start the admin portal:

```bash
npm run dev:admin
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8787`.

4. Build and load the extension:

```bash
npm run build:extension
```

Load `extension/dist` as an unpacked Chrome extension.

Useful database commands:

```bash
npm run db:logs
npm run db:down
npm run db:reset
```

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
```

`npm test` rebuilds the shared workspace first so the extension and backend
tests always execute against the current shared contracts/schema.

Live extension smoke:

```bash
cd extension
npm run test:live
```

## DigitalOcean Deployment

The production deployment runs the API/backend and the built admin SPA from the
same Docker image. The key file is:

- [Dockerfile](Dockerfile)

The Dockerfile already contains both the build and runtime commands:

- build stage:
  - installs dependencies with `npm ci`
  - builds `shared`, `coach-api`, and `admin-portal`
- runtime stage:
  - starts the API with `npm run start --workspace coach-api`

Build and run the container directly:

```bash
docker build -t uniqa-conversion-coach .
docker run --rm \
  -p 8080:8080 \
  -e DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/conversion_coach \
  -e SESSION_SECRET=replace-me \
  -e BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
  -e BOOTSTRAP_ADMIN_PASSWORD=admin \
  -e BOOTSTRAP_ADMIN_NAME="Conversion Coach Admin" \
  uniqa-conversion-coach
```

For DigitalOcean, create an App Platform app or container deployment from the
repo root and point it at this Dockerfile. Configure the managed Postgres
database as `DATABASE_URL` and set the bootstrap admin credentials as secrets.

After deployment, verify the health endpoint at `/healthz` and use the admin
portal to confirm the bootstrapped account can log in.

## Known Limitation

The verified live page map still covers steps 1-6. Steps `s7_final_price` and
`s8_confirm` remain disabled until the live UNIQA DOM for those screens is
re-verified and stable enough to support selectors without brittle assumptions.
