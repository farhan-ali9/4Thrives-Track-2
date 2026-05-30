from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("llm_persona", ROOT / "browser-runner" / "llm_persona.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["llm_persona"] = module
spec.loader.exec_module(module)


class LLMPersonaTests(unittest.TestCase):
    def test_overlay_stays_within_expected_bounds(self):
        overlay = module.generate_overlay("judith", "price_check", 7)
        for value in overlay.__dict__.values():
            self.assertGreaterEqual(value, 0.55)
            self.assertLessEqual(value, 1.45)

    def test_driver_falls_back_when_llm_returns_invalid_action(self):
        driver = module.LLMPersonaDriver(model="fake-model", api_url="http://127.0.0.1:9")
        driver._call_llm = lambda messages: {"action": "not_allowed"}  # type: ignore[method-assign]
        decision = driver.decide(
            persona_id="franz",
            intention="purchase",
            step_id="s4_initial_price",
            seed=3,
            step_context={"visiblePrice": 68.14},
            history=[],
            coach_interaction_seen=False,
        )
        self.assertTrue(decision.fallback_used)
        self.assertIn(decision.action, module.ALLOWED_ACTIONS_BY_STEP["s4_initial_price"])


if __name__ == "__main__":
    unittest.main()
