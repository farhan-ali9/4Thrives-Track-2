from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("run_session", ROOT / "browser-runner" / "run_session.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["run_session"] = module
spec.loader.exec_module(module)


class MockRunnerTests(unittest.TestCase):
    def test_mock_runner_starts_one_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = module.BrowserRunConfig(output_dir=tmp_path)
            trace = module.run_mock_session(persona_id="franz", intention="purchase", experiment_id="test", seed=1, config=config)
            self.assertTrue(trace["session_id"].startswith("sess_"))
            self.assertTrue(trace["events"])
            self.assertIn(trace["terminal_outcome"], {"converted_online", "abandoned", "submitted_advisor_lead"})
            self.assertIn("runtime_trace", trace)
            self.assertIn("coach_render_log", trace)
            path = module.write_trace(trace, tmp_path)
            self.assertTrue(path.exists())

    def test_out_of_scope_live_elements_end_as_advisor_handoff(self):
        for element_key in ("hospital", "both", "other_persons"):
            self.assertEqual(module._terminal_outcome_for_element(element_key), "submitted_advisor_lead")
        self.assertIsNone(module._terminal_outcome_for_element("at_doctor"))
        self.assertIsNone(module._terminal_outcome_for_element("opt_plus"))
        self.assertIsNone(module._terminal_outcome_for_element("premium"))

    def test_coach_interaction_mode_is_deterministic(self):
        decision = module.PersonaDecision(
            step_id="s4_initial_price",
            action="select_optimal",
            reasoning="test",
            dwell_ms=900,
            llm_model="test",
            latency_ms=0,
            fallback_used=True,
            prompt_hash="stable_hash",
            candidate_set=[],
            overlay=SimpleNamespace(
                price_sensitivity=1,
                trust_friction=1,
                privacy_friction=1,
                impatience=1,
                tariff_curiosity=1,
                coach_receptiveness=1.25,
            ),
            step_context={},
        )

        self.assertEqual(module._coach_interaction_mode(decision), "cta")


if __name__ == "__main__":
    unittest.main()
