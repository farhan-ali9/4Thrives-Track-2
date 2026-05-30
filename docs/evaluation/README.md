# Evaluation Pipeline

The evaluation pipeline compares baseline, rule-based coach, and trainable coach modes from stored session traces. Trainable mode loads a frequency action-ranker model and uses its top prediction as the intervention for each step with learned rankings.

Before reporting metrics, validate traces:

```bash
python replay/validate_traces.py artifacts/browser-runs --fail-on-invalid
```

Metrics currently implemented in `evaluation/metrics.py`:

- online conversion rate
- advisor handoff count
- abandonment rate
- S4, S5, and S7 drop-off counts
- drop-off reduction versus baseline
- conversion by persona and intention
- drop-off by persona and step
- advisor-routing correctness for out-of-scope paths
- intervention volume, impression-to-CTA rate, acceptance rate, dismiss rate, annoyance rate
- intervention precision and recall from eligible decision points
- extension render success rate
- step detection success rate
- selector drift rate
- backend timeout rate
- average inference latency
- trace completeness rate


Run a full baseline, rule-based, and trainable experiment layout after training a ranker:

```bash
bash scripts/run_evaluation_experiment.sh
```

This writes:

```text
artifacts/evaluation-experiments/latest/
  baseline/*.json
  rule_based/*.json
  trainable/*.json
  experiment_manifest.json
  baseline_vs_rule_based.md
  baseline_vs_trainable.md
```

Use `TRAINABLE_RANKER_MODEL=artifacts/training/frequency-ranker.json` to point evaluation at a trained model. The runner fails fast if trainable mode is requested without a model file.

Compare modes:

```bash
python evaluation/compare_modes.py --baseline artifacts/baseline --treatment artifacts/rule-based
```

Write a markdown report:

```bash
python evaluation/reports.py --baseline artifacts/baseline --treatment artifacts/rule-based --output artifacts/evaluation/report.md
```

Batch runner summaries include circuit-breaker state and should be checked before treating a run as valid evaluation evidence.


Live step IDs currently aligned with David's extension smoke:

- `s1_coverage_scope`
- `s2_for_whom`
- `s3_quote_basics`
- `s4_initial_price`
- `s5_add_ons`
- `s6_personal_medical_data`
- `s7_final_price`
- `s8_confirm`

On the current live journey, David observed `s8_confirm` as a `Berateranfrage` advisor-request terminal screen. Evaluation should count that path as `advisor_handoff`, not online conversion, when the event context or element indicates the consultation screen.
