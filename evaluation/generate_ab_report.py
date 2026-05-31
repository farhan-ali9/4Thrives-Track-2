"""Generate a rich A/B comparison report: baseline (no coach) vs treatment (with coach).

Usage:
    python evaluation/generate_ab_report.py \
        --baseline artifacts/browser-runs/exp/baseline \
        --treatment artifacts/browser-runs/exp/coach \
        --output-dir artifacts/ab-reports/exp \
        --experiment exp-name
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT / "browser-runner"))

from compare_modes import load_traces
from metrics import compare_dropoff_reduction, compute_metrics


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _delta_sign(value: float) -> str:
    if value > 0:
        return f"+{value * 100:.1f}pp"
    if value < 0:
        return f"{value * 100:.1f}pp"
    return "0.0pp"


def _row(label: str, baseline: float, treatment: float, higher_is_better: bool = True) -> str:
    delta = treatment - baseline
    arrow = ""
    if abs(delta) > 0.001:
        improved = (delta > 0) == higher_is_better
        arrow = " ✓" if improved else " ✗"
    return f"| {label} | {_pct(baseline)} | {_pct(treatment)} | {_delta_sign(delta)}{arrow} |"


def _count_row(label: str, baseline: int, treatment: int, higher_is_better: bool = False) -> str:
    delta = treatment - baseline
    arrow = ""
    if delta != 0:
        improved = (delta > 0) == higher_is_better
        arrow = " ✓" if improved else " ✗"
    sign = "+" if delta > 0 else ""
    return f"| {label} | {baseline} | {treatment} | {sign}{delta}{arrow} |"


def build_markdown(
    *,
    experiment: str,
    baseline: dict,
    treatment: dict,
    delta: dict,
    baseline_count: int,
    treatment_count: int,
) -> str:
    lines: list[str] = []

    lines += [
        f"# UNIQA Conversion Coach — A/B Report",
        f"",
        f"**Experiment:** `{experiment}`  ",
        f"**Baseline sessions:** {baseline_count} (no coach)  ",
        f"**Treatment sessions:** {treatment_count} (with coach extension)  ",
        f"",
        f"---",
        f"",
        f"## Conversion & Abandonment",
        f"",
        f"| Metric | Baseline | Coach | Delta |",
        f"|--------|----------|-------|-------|",
        _row("Online conversion rate", baseline["online_conversion_rate"], treatment["online_conversion_rate"], higher_is_better=True),
        _row("Abandonment rate", baseline["abandonment_rate"], treatment["abandonment_rate"], higher_is_better=False),
        f"",
        f"## Drop-off by Step",
        f"",
        f"| Step | Baseline drop-offs | Coach drop-offs | Delta |",
        f"|------|--------------------|-----------------|-------|",
        _count_row("s4 — Initial price", baseline["s4_initial_price_dropoff"], treatment["s4_initial_price_dropoff"], higher_is_better=False),
        _count_row("s5 — Add-ons", baseline["s5_addon_dropoff"], treatment["s5_addon_dropoff"], higher_is_better=False),
        _count_row("s7 — Final price", baseline["s7_final_price_dropoff"], treatment["s7_final_price_dropoff"], higher_is_better=False),
        f"",
        f"## Coach Intervention Quality",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Interventions triggered | {treatment.get('intervention_count', 0)} |",
        f"| Acceptance rate | {_pct(treatment.get('acceptance_rate', 0.0))} |",
        f"| Dismiss rate | {_pct(treatment.get('dismiss_rate', 0.0))} |",
        f"| Annoyance rate | {_pct(treatment.get('annoyance_rate', 0.0))} |",
        f"| Impression → CTA rate | {_pct(treatment.get('impression_to_cta_rate', 0.0))} |",
        f"| Intervention precision | {_pct(treatment.get('intervention_precision', 0.0))} |",
        f"",
        f"## Conversion by Persona",
        f"",
        f"| Persona | Baseline | Coach | Delta |",
        f"|---------|----------|-------|-------|",
    ]

    personas = sorted(set(list(baseline.get("conversion_by_persona", {}).keys()) + list(treatment.get("conversion_by_persona", {}).keys())))
    for persona in personas:
        b = baseline.get("conversion_by_persona", {}).get(persona, 0.0)
        t = treatment.get("conversion_by_persona", {}).get(persona, 0.0)
        lines.append(_row(persona, b, t, higher_is_better=True))

    lines += [
        f"",
        f"## Conversion by Intention",
        f"",
        f"| Intention | Baseline | Coach | Delta |",
        f"|-----------|----------|-------|-------|",
    ]

    intentions = sorted(set(list(baseline.get("conversion_by_intention", {}).keys()) + list(treatment.get("conversion_by_intention", {}).keys())))
    for intention in intentions:
        b = baseline.get("conversion_by_intention", {}).get(intention, 0.0)
        t = treatment.get("conversion_by_intention", {}).get(intention, 0.0)
        lines.append(_row(intention, b, t, higher_is_better=True))

    lines += [
        f"",
        f"## Technical Health",
        f"",
        f"| Metric | Baseline | Coach |",
        f"|--------|----------|-------|",
        f"| Trace completeness | {_pct(baseline.get('trace_completeness_rate', 0.0))} | {_pct(treatment.get('trace_completeness_rate', 0.0))} |",
        f"| Step detection success | {_pct(baseline.get('step_detection_success_rate', 0.0))} | {_pct(treatment.get('step_detection_success_rate', 0.0))} |",
        f"| Selector drift rate | {_pct(baseline.get('selector_drift_rate', 0.0))} | {_pct(treatment.get('selector_drift_rate', 0.0))} |",
        f"| Backend timeout rate | {_pct(baseline.get('backend_timeout_rate', 0.0))} | {_pct(treatment.get('backend_timeout_rate', 0.0))} |",
        f"| Avg inference latency | — | {treatment.get('inference_latency_ms_avg', 0.0):.0f} ms |",
        f"| Advisor routing correctness | {_pct(baseline.get('advisor_routing_correctness', 1.0))} | {_pct(treatment.get('advisor_routing_correctness', 1.0))} |",
        f"",
        f"## Summary Delta",
        f"",
        f"| | |",
        f"|--|--|",
        f"| Conversion rate uplift | **{_delta_sign(delta.get('conversion_rate_uplift', 0.0))}** |",
        f"| s4 drop-off reduction | {delta.get('s4_dropoff_reduction', 0)} sessions |",
        f"| s5 drop-off reduction | {delta.get('s5_dropoff_reduction', 0)} sessions |",
        f"| s7 drop-off reduction | {delta.get('s7_dropoff_reduction', 0)} sessions |",
        f"",
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A/B comparison report")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline trace dir or JSON")
    parser.add_argument("--treatment", type=Path, required=True, help="Coach trace dir or JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for reports")
    parser.add_argument("--experiment", default="ab-experiment", help="Experiment identifier")
    args = parser.parse_args()

    baseline_traces = load_traces(args.baseline)
    treatment_traces = load_traces(args.treatment)

    if not baseline_traces:
        print(f"WARNING: No baseline traces found in {args.baseline}", file=sys.stderr)
    if not treatment_traces:
        print(f"WARNING: No treatment traces found in {args.treatment}", file=sys.stderr)

    baseline = compute_metrics(baseline_traces)
    treatment = compute_metrics(treatment_traces)
    delta = compare_dropoff_reduction(baseline, treatment)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "experiment": args.experiment,
        "baseline": baseline,
        "treatment": treatment,
        "delta": delta,
    }

    json_path = args.output_dir / "comparison.json"
    md_path = args.output_dir / "comparison.md"

    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))

    md = build_markdown(
        experiment=args.experiment,
        baseline=baseline,
        treatment=treatment,
        delta=delta,
        baseline_count=len(baseline_traces),
        treatment_count=len(treatment_traces),
    )
    md_path.write_text(md)

    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, indent=2))
    print()
    print(md)


if __name__ == "__main__":
    main()
