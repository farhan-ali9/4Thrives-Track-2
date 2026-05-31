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

    def test_fallback_yields_ignore_coach_interaction(self):
        driver = module.LLMPersonaDriver(model="fake-model", api_url="http://127.0.0.1:9")
        driver._call_llm = lambda messages: None  # type: ignore[method-assign]
        decision = driver.decide(
            persona_id="judith",
            intention="purchase",
            step_id="s4_initial_price",
            seed=5,
            step_context={"visiblePrice": 70.0},
            history=[],
            coach_interaction_seen=False,
            coach_card_text="We can explain this price for you.",
            coach_present=True,
        )
        self.assertTrue(decision.fallback_used)
        self.assertEqual(decision.coach_interaction, "ignore")

    def test_coach_interaction_is_parsed_when_card_present(self):
        driver = module.LLMPersonaDriver(model="fake-model", api_url="http://127.0.0.1:9")
        driver._call_llm = lambda messages: {  # type: ignore[method-assign]
            "action": "select_optimal",
            "reasoning": "This explanation feels helpful.",
            "dwell_ms": 4200,
            "coach_interaction": "cta",
        }
        decision = driver.decide(
            persona_id="judith",
            intention="purchase",
            step_id="s4_initial_price",
            seed=2,
            step_context={"visiblePrice": 70.0},
            history=[],
            coach_interaction_seen=False,
            coach_card_text="We can explain this price for you.",
            coach_present=True,
        )
        self.assertFalse(decision.fallback_used)
        self.assertEqual(decision.coach_interaction, "cta")

    def test_coach_interaction_defaults_to_ignore_without_card(self):
        driver = module.LLMPersonaDriver(model="fake-model", api_url="http://127.0.0.1:9")
        driver._call_llm = lambda messages: {  # type: ignore[method-assign]
            "action": "select_optimal",
            "reasoning": "No popup is shown.",
            "dwell_ms": 3000,
            "coach_interaction": "cta",
        }
        decision = driver.decide(
            persona_id="judith",
            intention="purchase",
            step_id="s4_initial_price",
            seed=2,
            step_context={"visiblePrice": 70.0},
            history=[],
            coach_interaction_seen=False,
            coach_present=False,
        )
        self.assertEqual(decision.coach_interaction, "ignore")

    def test_user_prompt_is_plain_text_and_includes_rich_context(self):
        driver = module.LLMPersonaDriver(model="fake-model", api_url="http://127.0.0.1:9")
        captured: dict[str, object] = {}

        def fake_call(messages):
            captured["messages"] = messages
            return {"action": "select_optimal", "reasoning": "ok", "dwell_ms": 2000, "coach_interaction": "ignore"}

        driver._call_llm = fake_call  # type: ignore[method-assign]
        rich = {
            "headings": ["Voraussichtliche Prämie"],
            "tariffs": [{"name": "Optimal", "monthly_price": "70,50", "online_eligible": True}],
            "tooltips": ["Heilbehelfe sind medizinische Hilfsmittel."],
        }
        driver.decide(
            persona_id="judith",
            intention="purchase",
            step_id="s4_initial_price",
            seed=2,
            step_context={"visiblePrice": 70.0, "rich": rich},
            history=[],
            coach_interaction_seen=False,
        )
        user_message = captured["messages"][1]  # type: ignore[index]
        self.assertIsInstance(user_message["content"], str)
        self.assertIn("Heilbehelfe", user_message["content"])
        self.assertIn("online_eligible", user_message["content"])

    def test_parse_json_content_strips_markdown_fence(self):
        parsed = module._parse_json_content('```json\n{"action": "continue"}\n```')
        self.assertEqual(parsed, {"action": "continue"})


if __name__ == "__main__":
    unittest.main()
