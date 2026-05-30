from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "replay"))
spec = importlib.util.spec_from_file_location("build_dataset", ROOT / "training" / "build_dataset.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class BuildDatasetTests(unittest.TestCase):
    def test_build_examples_from_inline_decision_point(self):
        trace = {
            "session_id": "sess_1",
            "terminal_outcome": "converted_online",
            "metadata": {"persona_id": "franz"},
            "events": [
                {"event_id": "evt_1", "step_id": "s4_initial_price", "derived_context": {"intervention_kind": "price_transparency"}, "runner_metadata": {"page_map_version": "v1", "extension_build_id": "ext", "model_version_or_policy": "rule"}},
            ],
        }
        examples = module.build_examples(trace, "test")
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["chosen_candidate"], "price_transparency")
        self.assertEqual(examples[0]["future_outcome_summary"], "converted_online")

    def test_build_examples_from_backend_decision_and_exposure(self):
        trace = {
            "session_id": "sess_backend",
            "terminal_outcome": "advisor_handoff",
            "events": [{"event_id": "evt_1", "session_id": "sess_backend", "ts": 1, "step_id": "s3_tariff_choice", "event_type": "out_of_scope_selected", "element_key": "premium", "derived_signals": {}, "derived_context": {}, "privacy_level": "anonymous"}],
            "decisions": [{"decision_id": "dec_1", "session_id": "sess_backend", "model_version": "rule_based_v1", "chosen_action_id": "advisor_handoff", "risk_score": 80, "guardrail_decisions": [{"outcome": "advisor_handoff"}], "latency_ms": 5}],
            "exposures": [{"exposure_id": "exp_1", "session_id": "sess_backend", "decision_id": "dec_1", "action_id": "advisor_handoff", "impression_ts": 2, "dismiss_ts": None, "cta_ts": 3, "render_success": True}],
        }
        examples = module.build_examples(trace, "test")
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["decision_id"], "dec_1")
        self.assertEqual(examples[0]["chosen_candidate"], "advisor_handoff")
        self.assertEqual(examples[0]["exposure_result"], "cta")
        self.assertIn("advisor_handoff", examples[0]["guardrail_filtered_candidates"])


if __name__ == "__main__":
    unittest.main()
