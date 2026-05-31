# UNIQA Conversion Coach

Live Chrome extension + coach API + Playwright persona runner for baseline-vs-coach evaluation on the real UNIQA calculator.

**Submission:** [`submissions/4Thrives/`](submissions/4Thrives/) (report, hypotheses, results, demo guide)

## For hackathon judges

Bare minimum to see the product working locally. Precomputed eval metrics are in [`submissions/4Thrives/extras/results/`](submissions/4Thrives/extras/results/) — you do not need to run the pipeline to review our numbers.

### 1. One-time setup

```bash
npm install
python3 -m pip install -r requirements-pipeline.txt
python3 -m playwright install chromium
cp .env.example .env
```

Requires Node.js, Python 3, Docker (Postgres), and Chrome.

### 2. Ollama (default persona LLM)

Install [Ollama](https://ollama.com), then:

```bash
ollama serve
ollama pull qwen2.5:3b-instruct
```

`.env` already uses `LLM_PROVIDER=local` and `http://localhost:11434`. For cloud LLM instead, set `LLM_PROVIDER=remote` and the Featherless keys in `.env.example`.

Ollama is only required for **automated** persona runs; manual extension testing does not need it.

### 3. Start backend

Terminal A:

```bash
npm run db:up && npm run db:migrate
npm run dev:coach-api
```

Verify: `curl http://127.0.0.1:8787/healthz`

### 4. Load the Chrome extension

```bash
npm run build:extension
```

Chrome → **Extensions** → **Developer mode** → **Load unpacked** → select `extension/dist`.

Open the [UNIQA health calculator](https://www.uniqa.at/krankenversicherung/rechner) and walk through a Start or Optimal path (private doctor, myself only). Coach popups appear at funnel steps when the API is running.

**What you should see:** the extension detects funnel stage from the live page; the coach API returns deterministic intervention plays — the LLM does not decide *when* to coach.

## Automated evaluation (optional)

### How it works

Playwright opens real Chrome sessions on `uniqa.at`. Three personas (Judith, Franz, Peter) × four intentions run in **baseline** (no extension) and **coach** (extension loaded) modes. Session traces feed `evaluation/report_bulk_runs.py`, which produces conversion, drop-off, and popup charts.

### Why it takes a long time

- Real browser on the production site — not a mock UI
- An LLM call per persona decision step
- Submission minimum: **24 sessions** (12 baseline + 12 coach); full loop: 300+

Coach mode requires a built extension and a healthy coach API.

```bash
npm run pipeline:submission
```

Traces land in `artifacts/browser-runs/`; the report is copied to `submissions/4Thrives/extras/results/`.

Full validation + bulk:

```bash
npm run pipeline:local
```

Optional overrides: `LOCAL_VALIDATE_SESSIONS`, `LOCAL_BULK_SESSIONS`, `EXPERIMENT_PREFIX`.

**Regenerate report** from existing traces (s8 relabel, no rerun):

```bash
python3 scripts/patch_s8_trace_outcomes.py artifacts/browser-runs/local-bulk-baseline-* artifacts/browser-runs/local-bulk-coach-*
python3 evaluation/report_bulk_runs.py --baseline artifacts/browser-runs/<baseline-dir> --coach artifacts/browser-runs/<coach-dir> --output-dir artifacts/reports/final_run
cp -r artifacts/reports/final_run/* submissions/4Thrives/extras/results/
```

Online conversion in reports = in-scope journey reaching `s8_confirm` (Start/Optimal, private doctor, myself only). The runner observes but does not submit the Berateranfrage form.

## Repo layout

| Path | Role |
|------|------|
| `extension/` | Live funnel detection + coach UI on uniqa.at |
| `coach-api/` | Deterministic `/api/runtime/*` decision API |
| `browser-runner/` | Playwright personas (Judith, Franz, Peter) |
| `evaluation/` | Metrics + `report_bulk_runs.py` |
| `shared/` | Runtime contracts |

`admin-portal/` is legacy and not required for the MVP path.

## Developers

**API:** `POST /api/runtime/decide`, `POST /api/runtime/outcome`, `GET /api/runtime/sessions/:id`, `GET /healthz`

**Test:**

```bash
npm test
python3 -m unittest \
  browser-runner/tests/test_run_batch.py \
  evaluation/tests/test_metrics.py \
  evaluation/tests/test_report_bulk_runs.py
```

**Deploy:** Coach API on DigitalOcean — [Dockerfile](Dockerfile), [.do/app.yaml](.do/app.yaml)
