from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("metrics", ROOT / "evaluation" / "metrics.py")
metrics = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(metrics)


class MetricsTests(unittest.TestCase):
    def test_conversion_handoff_and_operational_metrics(self):
        traces = [
            {
                "terminal_outcome": "converted_online",
                "metadata": {"persona_id": "franz", "intention": "purchase"},
                "events": [
                    {"step_id": "s4_initial_price", "event_type": "cta_click", "derived_context": {"intervention_kind": "price_transparency", "eligible_for_intervention": True, "inference_latency_ms": 120}},
                    {"step_id": "s8_confirm"},
                ],
            },
            {
                "terminal_outcome": "submitted_advisor_lead",
                "metadata": {"persona_id": "peter", "intention": "orientation"},
                "events": [
                    {"step_id": "s3_quote_basics", "event_type": "out_of_scope_selected", "element_key": "premium"},
                    {"step_id": "s3_quote_basics", "event_type": "intervention_dismissed", "derived_context": {"intervention_kind": "advisor_handoff", "eligible_for_intervention": True}, "derived_signals": {"annoyed": True}},
                ],
                "coach_render_log": [{"step_id": "s3_quote_basics", "decision_state": "rendered", "rendered": True}],
            },
            {
                "terminal_outcome": "abandoned",
                "metadata": {"persona_id": "judith", "intention": "price_check"},
                "events": [
                    {"step_id": "s5_add_ons", "event_type": "selector_missing"},
                    {"step_id": "s5_add_ons", "event_type": "backend_timeout"},
                ],
                "coach_render_log": [{"step_id": "s5_add_ons", "decision_state": "timeout", "rendered": False}],
            },
        ]
        result = metrics.compute_metrics(traces)
        self.assertEqual(result["online_conversion_rate"], 1 / 3)
        self.assertEqual(result["advisor_lead_count"], 1)
        self.assertEqual(result["s5_addon_dropoff"], 1)
        self.assertEqual(result["advisor_routing_correctness"], 1.0)
        self.assertEqual(result["intervention_count"], 2)
        self.assertEqual(result["acceptance_rate"], 0.5)
        self.assertEqual(result["dismiss_rate"], 0.5)
        self.assertEqual(result["annoyance_rate"], 0.5)
        self.assertEqual(result["selector_drift_rate"], 1 / 3)
        self.assertEqual(result["backend_timeout_rate"], 1 / 3)
        self.assertEqual(result["inference_latency_ms_avg"], 120)
        self.assertEqual(result["conversion_by_intention"]["purchase"], 1.0)
        self.assertEqual(result["popup_render_rate"], 0.5)
        self.assertEqual(result["popup_timeout_count"], 1)

    def test_legacy_s5_step_alias_counts_for_dropoff(self):
        result = metrics.compute_metrics([
            {"terminal_outcome": "abandoned", "metadata": {"persona_id": "franz"}, "events": [{"step_id": "s5_addons"}]}
        ])
        self.assertEqual(result["s5_addon_dropoff"], 1)
        self.assertEqual(result["dropoff_by_persona_step"]["franz:s5_add_ons"], 1)

    def test_dropoff_reduction_delta(self):
        delta = metrics.compare_dropoff_reduction({"online_conversion_rate": 0.2, "s7_final_price_dropoff": 3}, {"online_conversion_rate": 0.5, "s7_final_price_dropoff": 1})
        self.assertAlmostEqual(delta["conversion_rate_uplift"], 0.3)
        self.assertEqual(delta["s7_dropoff_reduction"], 2)


if __name__ == "__main__":
    unittest.main()
