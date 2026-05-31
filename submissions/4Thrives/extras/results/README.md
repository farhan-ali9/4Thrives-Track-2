# Submission Results

Frozen report from the `final_run` eval (12 baseline + 12 coach sessions).

Regenerate:

```bash
npm run pipeline:submission
```

Or rebuild the report from existing traces after patching outcomes:

```bash
python3 scripts/patch_s8_trace_outcomes.py artifacts/browser-runs/<baseline-dir> artifacts/browser-runs/<coach-dir>
python3 evaluation/report_bulk_runs.py --baseline ... --coach ... --output-dir artifacts/reports/final_run
cp -r artifacts/reports/final_run/* submissions/4Thrives/extras/results/
```

Open `index.html` for charts. Headline numbers live in `summary.md`.
