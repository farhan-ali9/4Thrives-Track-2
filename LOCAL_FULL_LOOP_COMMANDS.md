# Local Full Loop Commands

This is the local-machine path for the simplified UNIQA live baseline/coach loop using Featherless as the LLM provider.

## 1. Install Dependencies

```bash
npm install
python3 -m pip install -r requirements-pipeline.txt
python3 -m playwright install chromium
```

## 2. Configure `.env`

```bash
cp .env.example .env
```

Set at minimum:

```bash
FEATHERLESS_API_KEY=...
VITE_FEATHERLESS_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
COACH_API_URL=http://127.0.0.1:8787
```

Optional but recommended for Featherless attribution:

```bash
LLM_HTTP_REFERER=http://localhost
LLM_APP_TITLE=UNIQA Conversion Coach Runner
```

## 3. Start Local Backend

Terminal A:

```bash
npm run db:up
npm run db:migrate
npm run dev:coach-api
```

Wait until the backend serves:

```bash
curl http://127.0.0.1:8787/healthz
```

## 4. Validate Before Bulk

Terminal B:

Baseline validation:

```bash
bash scripts/run_local_validation.sh baseline 12
```

Coach validation:

```bash
bash scripts/run_local_validation.sh coach 12
```

These commands source `.env`, rebuild the extension for coach mode, and fail fast if the local coach API is not healthy.

## 5. Run Bulk Collection

Baseline bulk:

```bash
bash scripts/run_local_bulk.sh baseline 300
```

Coach bulk:

```bash
bash scripts/run_local_bulk.sh coach 300
```

All raw traces land under:

```bash
artifacts/browser-runs
```

## 6. Build The Bulk Report

```bash
python3 evaluation/report_bulk_runs.py \
  --baseline artifacts/browser-runs/<experiment-prefix>/baseline-bulk \
  --coach artifacts/browser-runs/<experiment-prefix>/coach-bulk \
  --output-dir artifacts/reports/<experiment-prefix>
```

Outputs:

```bash
artifacts/reports/<experiment-prefix>/summary.json
artifacts/reports/<experiment-prefix>/summary.md
artifacts/reports/<experiment-prefix>/outcomes.svg
artifacts/reports/<experiment-prefix>/dropoffs.svg
artifacts/reports/<experiment-prefix>/popup_rendering.svg
artifacts/reports/<experiment-prefix>/index.html
```

## 7. One-Command Full Loop

If you want the full local pipeline in one command:

```bash
bash scripts/run_local_full_loop.sh
```

Optional overrides:

```bash
LOCAL_VALIDATE_SESSIONS=12 \
LOCAL_BULK_SESSIONS=300 \
EXPERIMENT_PREFIX=local-uniqa-run \
bash scripts/run_local_full_loop.sh
```

This command performs:

```bash
baseline validation
coach validation
baseline bulk
coach bulk
bulk report
```

and stores run-specific outputs under:

```bash
artifacts/browser-runs/<experiment-prefix>
artifacts/reports/<experiment-prefix>
```

## 8. Direct CLI Equivalents

```bash
./uniqa-pipeline validate-live --execution-mode baseline --sessions 12
./uniqa-pipeline validate-live --execution-mode coach --sessions 12
./uniqa-pipeline run-live --execution-mode baseline --sessions 300
./uniqa-pipeline run-live --execution-mode coach --sessions 300
./uniqa-pipeline local-full-loop --validate-sessions 12 --bulk-sessions 300
```

## Notes

- Coach mode requires a built `extension/dist` and a running coach API.
- The live runner never submits the final purchase. `s8_confirm` remains an observation boundary.
- Featherless is OpenAI-compatible at `https://api.featherless.ai/v1/chat/completions`, and its model catalog is available via `GET https://api.featherless.ai/v1/models`.
