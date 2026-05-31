from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("live_page", ROOT / "browser-runner" / "live_page.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["live_page"] = module
spec.loader.exec_module(module)


class FakePage:
    def __init__(self, states):
        self.states = list(states)
        self.waits = []

    def evaluate(self, _script):
        if len(self.states) > 1:
            return self.states.pop(0)
        return self.states[0]

    def wait_for_timeout(self, timeout_ms):
        self.waits.append(timeout_ms)


class ExtensionStateTests(unittest.TestCase):
    def test_wait_for_extension_ready_uses_structured_state(self):
        page = FakePage(
            [
                {"rootAttached": False, "initialized": False, "apiState": None},
                {"rootAttached": True, "initialized": True, "apiState": "connected"},
            ]
        )

        self.assertTrue(module.wait_for_extension_ready(page, timeout_ms=1_000, settle_ms=0))
        self.assertEqual(page.waits, [150])

    def test_wait_for_coach_render_requires_rendered_card(self):
        page = FakePage(
            [
                {"cardCount": 0, "renderState": "idle", "actionable": False},
                {"cardCount": 1, "renderState": "rendered", "actionable": True},
            ]
        )

        self.assertTrue(module.wait_for_coach_render(page, timeout_ms=1_000, settle_ms=0))

    def test_wait_for_coach_cycle_accepts_rendered_popup_for_current_step(self):
        page = FakePage(
            [
                {"currentStepId": "s3_quote_basics", "decisionState": "pending", "requestFinishedAt": 0},
                {"currentStepId": "s4_initial_price", "decisionState": "rendered", "playId": "price_reframe", "requestFinishedAt": 2_000},
            ]
        )

        state = module.wait_for_coach_cycle(page, step_id="s4_initial_price", entered_at=1_000, timeout_ms=1_000, settle_ms=0)
        self.assertEqual(state["decisionState"], "rendered")
        self.assertEqual(state["playId"], "price_reframe")

    def test_wait_for_coach_cycle_accepts_empty_result_for_current_step(self):
        page = FakePage(
            [
                {"currentStepId": "s4_initial_price", "decisionState": "pending", "requestFinishedAt": 0},
                {"currentStepId": "s4_initial_price", "decisionState": "empty", "requestFinishedAt": 2_000},
            ]
        )

        state = module.wait_for_coach_cycle(page, step_id="s4_initial_price", entered_at=1_000, timeout_ms=1_000, settle_ms=0)
        self.assertEqual(state["decisionState"], "empty")


if __name__ == "__main__":
    unittest.main()
