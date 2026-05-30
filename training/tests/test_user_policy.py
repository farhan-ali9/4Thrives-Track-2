from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))
spec = importlib.util.spec_from_file_location("user_policy", ROOT / "training" / "user_policy.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["user_policy"] = module
spec.loader.exec_module(module)


class UserPolicyTests(unittest.TestCase):
    def test_predict_uses_most_specific_key_first(self):
        rows = [
            {
                "current_step_id": "s4_initial_price",
                "persona_id": "franz",
                "intention": "purchase",
                "run_mode": "coach",
                "chosen_action": "select_optimal",
            },
            {
                "current_step_id": "s4_initial_price",
                "persona_id": "franz",
                "intention": "purchase",
                "run_mode": "coach",
                "chosen_action": "select_optimal",
            },
            {
                "current_step_id": "s4_initial_price",
                "persona_id": "franz",
                "intention": "comparison",
                "run_mode": "baseline",
                "chosen_action": "select_start",
            },
        ]
        model = module.train_frequency_user_policy(rows)
        predicted = module.predict_user_action(
            model,
            {
                "current_step_id": "s4_initial_price",
                "persona_id": "franz",
                "intention": "purchase",
                "run_mode": "coach",
                "candidate_actions": ["select_start", "select_optimal"],
            },
        )
        self.assertEqual(predicted, "select_optimal")


if __name__ == "__main__":
    unittest.main()
