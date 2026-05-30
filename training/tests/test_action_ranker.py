from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("action_ranker", ROOT / "training" / "action_ranker.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class ActionRankerTests(unittest.TestCase):
    def test_load_and_predict_top_candidate_for_step(self):
        model = {"model_type": "frequency_action_ranker", "ranking_by_step": {"s4_initial_price": [["trust_reassurance", 3], ["price_transparency", 1]]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranker.json"
            path.write_text(json.dumps(model))
            loaded = module.load_ranker(path)
        self.assertEqual(module.predict_action(loaded, step_id="s4_initial_price"), "trust_reassurance")

    def test_unknown_step_returns_no_prediction(self):
        model = {"model_type": "frequency_action_ranker", "ranking_by_step": {}}
        self.assertIsNone(module.predict_action(model, step_id="s1_coverage_scope"))


if __name__ == "__main__":
    unittest.main()
