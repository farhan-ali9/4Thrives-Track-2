from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "browser-runner" / "persona_policy.py"
spec = importlib.util.spec_from_file_location("persona_policy", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["persona_policy"] = module
spec.loader.exec_module(module)


class PersonaPolicyTests(unittest.TestCase):
    def test_personas_have_all_intentions_and_valid_actions(self):
        personas = module.load_personas(ROOT / "personas")
        self.assertEqual(set(personas), {"franz", "judith", "peter"})
        for policy in personas.values():
            self.assertEqual(set(policy.intentions), module.VALID_INTENTIONS)
            action = policy.action_for_step(step_id="s4_initial_price", intention="price_check", intervention_kind="price_transparency", seed=7)
            self.assertIn(action["action"], {"continue", "abandon", "request_advisor", "explore_out_of_scope_then_back"})
            self.assertGreaterEqual(action["dwell_ms"], 250)

    def test_advisor_handoff_does_not_classify_as_conversion(self):
        outcome = module.classify_outcome([{"step_id": "s3_tariff_choice", "element_key": "premium"}])
        self.assertEqual(outcome, "advisor_handoff")

    def test_live_step_ids_and_aliases_are_supported(self):
        personas = module.load_personas(ROOT / "personas")
        action = personas["franz"].action_for_step(step_id="s3_tariff_choice", intention="comparison", seed=2)
        self.assertEqual(action["step_id"], "s3_quote_basics")
        self.assertEqual(module.ONLINE_STEPS, module.LIVE_UNIQA_STEPS)
        self.assertIn("s7_final_price", module.ONLINE_STEPS)
        self.assertIn("s8_confirm", module.ONLINE_STEPS)

    def test_current_live_s8_berateranfrage_counts_as_advisor_handoff(self):
        outcome = module.classify_outcome([
            {"step_id": "s8_confirm", "element_key": "consultationContact", "derived_context": {"screenTitle": "Berateranfrage"}}
        ])
        self.assertEqual(outcome, "advisor_handoff")

    def test_load_personas_ignores_appledouble_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "franz.json").write_text(json.dumps({
                "persona_id": "franz",
                "display_name": "Franz",
                "segment": "online-affine",
                "traits": [],
                "responds_to": [],
                "base_dwell_ms": 1000,
                "intentions": {
                    "purchase": {"continue_bias": 0.8, "abandon_bias": 0.1, "advisor_bias": 0.1, "dwell_multiplier": 1.0},
                    "orientation": {"continue_bias": 0.7, "abandon_bias": 0.2, "advisor_bias": 0.1, "dwell_multiplier": 1.0},
                    "comparison": {"continue_bias": 0.7, "abandon_bias": 0.2, "advisor_bias": 0.1, "dwell_multiplier": 1.0},
                    "price_check": {"continue_bias": 0.6, "abandon_bias": 0.3, "advisor_bias": 0.1, "dwell_multiplier": 1.0},
                },
            }))
            (root / "._franz.json").write_bytes(b"\x00\x05\x16\x07binary-sidecar")
            personas = module.load_personas(root)
            self.assertEqual(set(personas), {"franz"})


if __name__ == "__main__":
    unittest.main()
