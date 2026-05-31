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

    def test_hash_roll_helper_is_removed(self):
        self.assertFalse(hasattr(module, "_coach_interaction_mode"))

    def test_coach_interaction_follows_llm_decision(self):
        for mode in ("cta", "dismiss"):
            page = _FakeCoachPage(overlay_text="Helpful coach card")
            decision = _make_decision(coach_interaction=mode)
            result = module._try_coach_interaction(page, decision, read_ms=10)
            self.assertEqual(result, mode)
            self.assertEqual(page.clicked_mode, mode)

    def test_coach_interaction_ignore_clicks_nothing(self):
        page = _FakeCoachPage(overlay_text="Helpful coach card")
        decision = _make_decision(coach_interaction="ignore")
        result = module._try_coach_interaction(page, decision, read_ms=10)
        self.assertIsNone(result)
        self.assertIsNone(page.clicked_mode)
        self.assertEqual(page.text_reads, 0)

    def test_coach_interaction_skips_when_no_card_visible(self):
        page = _FakeCoachPage(overlay_text="")
        decision = _make_decision(coach_interaction="cta")
        result = module._try_coach_interaction(page, decision, read_ms=10)
        self.assertIsNone(result)
        self.assertIsNone(page.clicked_mode)


class _FakeCoachPage:
    def __init__(self, *, overlay_text: str) -> None:
        self.overlay_text = overlay_text
        self.clicked_mode = None
        self.text_reads = 0
        self.waits: list[int] = []

    def evaluate(self, script, arg=None):
        if arg is None:
            self.text_reads += 1
            return self.overlay_text
        self.clicked_mode = arg
        return None

    def wait_for_timeout(self, ms):
        self.waits.append(ms)


def _make_decision(*, coach_interaction: str) -> "object":
    return module.PersonaDecision(
        step_id="s4_initial_price",
        action="select_optimal",
        reasoning="test",
        dwell_ms=900,
        llm_model="test",
        latency_ms=0,
        fallback_used=False,
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
        coach_interaction=coach_interaction,
    )


if __name__ == "__main__":
    unittest.main()
