from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from compare_modes import load_traces
from metrics import compare_dropoff_reduction, compute_metrics


def _read_batch_summary(path: Path) -> dict[str, Any]:
    summary_path = path / "batch-summary.json"
    if not summary_path.exists():
        return {"circuit_breaker": None, "failure_log": [], "failures": {}}
    return json.loads(summary_path.read_text())


def _fmt_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_number(value: float | int) -> str:
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _write_svg_bar_chart(
    *,
    title: str,
    rows: list[tuple[str, float, float]],
    left_label: str,
    right_label: str,
    output: Path,
) -> None:
    width = 780
    row_height = 56
    margin_left = 220
    margin_right = 40
    margin_top = 56
    bar_width = (width - margin_left - margin_right - 18) // 2
    height = margin_top + row_height * len(rows) + 24
    max_value = max([1.0, *[max(left, right) for _, left, right in rows]])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#10203d}.label{font-size:14px}.title{font-size:20px;font-weight:700}.legend{font-size:12px}.value{font-size:12px;font-weight:700}</style>',
        f'<text class="title" x="{margin_left}" y="30">{html.escape(title)}</text>',
        f'<rect x="{margin_left}" y="38" width="14" height="14" fill="#7aa6ff" rx="3"/>',
        f'<text class="legend" x="{margin_left + 22}" y="50">{html.escape(left_label)}</text>',
        f'<rect x="{margin_left + 120}" y="38" width="14" height="14" fill="#0e699b" rx="3"/>',
        f'<text class="legend" x="{margin_left + 142}" y="50">{html.escape(right_label)}</text>',
    ]
    for index, (label, left, right) in enumerate(rows):
        y = margin_top + index * row_height
        left_w = 0 if max_value == 0 else (left / max_value) * bar_width
        right_w = 0 if max_value == 0 else (right / max_value) * bar_width
        lines.extend([
            f'<text class="label" x="20" y="{y + 22}">{html.escape(label)}</text>',
            f'<rect x="{margin_left}" y="{y + 6}" width="{left_w:.2f}" height="16" fill="#7aa6ff" rx="4"/>',
            f'<text class="value" x="{margin_left + left_w + 8:.2f}" y="{y + 19}">{html.escape(_fmt_number(left))}</text>',
            f'<rect x="{margin_left + bar_width + 18}" y="{y + 6}" width="{right_w:.2f}" height="16" fill="#0e699b" rx="4"/>',
            f'<text class="value" x="{margin_left + bar_width + 26 + right_w:.2f}" y="{y + 19}">{html.escape(_fmt_number(right))}</text>',
        ])
    lines.append("</svg>")
    output.write_text("\n".join(lines), encoding="utf-8")


def _summary_markdown(
    *,
    baseline_metrics: dict[str, Any],
    coach_metrics: dict[str, Any],
    delta: dict[str, Any],
    baseline_batch: dict[str, Any],
    coach_batch: dict[str, Any],
) -> str:
    lines = [
        "# Bulk Run Summary",
        "",
        "## Baseline",
        "",
        f"- Sessions: {baseline_metrics['sessions']}",
        f"- Online conversion: {_fmt_percent(baseline_metrics['online_conversion_rate'])}",
        f"- Advisor lead submission: {_fmt_percent(baseline_metrics['advisor_lead_submission_rate'])}",
        f"- Abandonment: {_fmt_percent(baseline_metrics['abandonment_rate'])}",
        f"- Failures: {json.dumps(baseline_batch.get('failures', {}), sort_keys=True)}",
        "",
        "## Coach",
        "",
        f"- Sessions: {coach_metrics['sessions']}",
        f"- Online conversion: {_fmt_percent(coach_metrics['online_conversion_rate'])}",
        f"- Advisor lead submission: {_fmt_percent(coach_metrics['advisor_lead_submission_rate'])}",
        f"- Abandonment: {_fmt_percent(coach_metrics['abandonment_rate'])}",
        f"- Popup render rate: {_fmt_percent(coach_metrics['popup_render_rate'])}",
        f"- Popup CTA / dismiss: {coach_metrics['popup_cta_count']} / {coach_metrics['popup_dismiss_count']}",
        f"- Failures: {json.dumps(coach_batch.get('failures', {}), sort_keys=True)}",
        "",
        "## Delta",
        "",
        f"- Conversion uplift: {_fmt_percent(delta['conversion_rate_uplift'])}",
        f"- Advisor lead uplift: {_fmt_percent(delta['advisor_lead_submission_uplift'])}",
        f"- Abandonment reduction: {_fmt_percent(delta['abandonment_reduction'])}",
        f"- S4 dropoff reduction: {delta['s4_dropoff_reduction']}",
        f"- S5 dropoff reduction: {delta['s5_dropoff_reduction']}",
        f"- S7 dropoff reduction: {delta['s7_dropoff_reduction']}",
    ]
    return "\n".join(lines) + "\n"


def write_bulk_report(*, baseline_path: Path, coach_path: Path, output_dir: Path) -> dict[str, Any]:
    baseline_metrics = compute_metrics(load_traces(baseline_path))
    coach_metrics = compute_metrics(load_traces(coach_path))
    baseline_batch = _read_batch_summary(baseline_path)
    coach_batch = _read_batch_summary(coach_path)
    delta = {
        **compare_dropoff_reduction(baseline_metrics, coach_metrics),
        "advisor_lead_submission_uplift": coach_metrics["advisor_lead_submission_rate"] - baseline_metrics["advisor_lead_submission_rate"],
        "abandonment_reduction": baseline_metrics["abandonment_rate"] - coach_metrics["abandonment_rate"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    outcomes_svg = output_dir / "outcomes.svg"
    dropoffs_svg = output_dir / "dropoffs.svg"
    popup_svg = output_dir / "popup_rendering.svg"
    index_html = output_dir / "index.html"

    summary_payload = {
        "baseline": {
            "batch": baseline_batch,
            "metrics": baseline_metrics,
        },
        "coach": {
            "batch": coach_batch,
            "metrics": coach_metrics,
        },
        "delta": delta,
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")
    summary_md.write_text(
        _summary_markdown(
            baseline_metrics=baseline_metrics,
            coach_metrics=coach_metrics,
            delta=delta,
            baseline_batch=baseline_batch,
            coach_batch=coach_batch,
        ),
        encoding="utf-8",
    )

    _write_svg_bar_chart(
        title="Outcomes",
        rows=[
            ("Online conversion rate", baseline_metrics["online_conversion_rate"], coach_metrics["online_conversion_rate"]),
            ("Advisor lead submission rate", baseline_metrics["advisor_lead_submission_rate"], coach_metrics["advisor_lead_submission_rate"]),
            ("Abandonment rate", baseline_metrics["abandonment_rate"], coach_metrics["abandonment_rate"]),
        ],
        left_label="Baseline",
        right_label="Coach",
        output=outcomes_svg,
    )
    _write_svg_bar_chart(
        title="Price-Step Dropoffs",
        rows=[
            ("S4 initial price", float(baseline_metrics["s4_initial_price_dropoff"]), float(coach_metrics["s4_initial_price_dropoff"])),
            ("S5 add-ons", float(baseline_metrics["s5_addon_dropoff"]), float(coach_metrics["s5_addon_dropoff"])),
            ("S7 final price", float(baseline_metrics["s7_final_price_dropoff"]), float(coach_metrics["s7_final_price_dropoff"])),
        ],
        left_label="Baseline",
        right_label="Coach",
        output=dropoffs_svg,
    )
    _write_svg_bar_chart(
        title="Coach Popup Performance",
        rows=[
            ("Popup render rate", 0.0, coach_metrics["popup_render_rate"]),
            ("Popup CTA count", 0.0, float(coach_metrics["popup_cta_count"])),
            ("Popup dismiss count", 0.0, float(coach_metrics["popup_dismiss_count"])),
        ],
        left_label="Baseline",
        right_label="Coach",
        output=popup_svg,
    )

    index_html.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html lang=\"en\">",
                "<head><meta charset=\"utf-8\"><title>UNIQA Bulk Report</title></head>",
                "<body style=\"font-family:Arial,sans-serif;padding:24px;color:#10203d\">",
                "<h1>UNIQA Bulk Report</h1>",
                "<ul>",
                '<li><a href="summary.json">summary.json</a></li>',
                '<li><a href="summary.md">summary.md</a></li>',
                '<li><a href="outcomes.svg">outcomes.svg</a></li>',
                '<li><a href="dropoffs.svg">dropoffs.svg</a></li>',
                '<li><a href="popup_rendering.svg">popup_rendering.svg</a></li>',
                "</ul>",
                "</body>",
                "</html>",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "baseline_dir": str(baseline_path),
        "coach_dir": str(coach_path),
        "output_dir": str(output_dir),
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a simple baseline-vs-coach bulk-run report")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--coach", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_bulk_report(baseline_path=args.baseline, coach_path=args.coach, output_dir=args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
