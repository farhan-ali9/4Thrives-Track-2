# Demo Video Guide

**Status:** Link TBD — add to `REPORT.md` when uploaded.

Show one coached session per segment (Judith / Franz / Peter). Suggested coach moments: S4 price reframe, S5 hesitation chat, S7 price-change explainer.

```bash
npm run db:up && npm run db:migrate && npm run dev:coach-api && npm run build:extension
export RUNNER_HEADLESS=0
python3 browser-runner/run_session.py --persona judith --intention price_check --mode validation
python3 browser-runner/run_session.py --persona franz --intention comparison --mode validation
python3 browser-runner/run_session.py --persona peter --intention purchase --mode validation
```

Checklist: all three segments shown with visible coach intervention; link added to `REPORT.md`.
