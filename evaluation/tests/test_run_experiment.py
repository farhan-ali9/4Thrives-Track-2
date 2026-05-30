from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("run_experiment", ROOT / "evaluation" / "run_experiment.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["run_experiment"] = module
spec.loader.exec_module(module)


class RunExperimentTests(unittest.TestCase):
    def test_baseline_rule_experiment_writes_manifest_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = module.run_experiment(
                experiment_id="test-exp",
                runner_mode="mock",
                sessions_per_mode=2,
                output_root=Path(tmp),
                evaluation_modes=("baseline", "rule_based"),
            )
            self.assertTrue(Path(result["manifest_path"]).exists())
            self.assertTrue((Path(tmp) / "baseline").is_dir())
            self.assertTrue((Path(tmp) / "rule_based").is_dir())
            self.assertTrue(Path(result["report"]["output"]).exists())
            self.assertEqual(len(result["evaluation_modes"]), 2)

    def test_trainable_experiment_writes_trainable_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "ranker.json"
            model_path.write_text(json.dumps({
                "model_type": "frequency_action_ranker",
                "ranking_by_step": {"s4_initial_price": [["trust_reassurance", 2]], "s7_final_price": [["price_transparency", 1]]},
            }))
            result = module.run_experiment(
                experiment_id="test-exp",
                runner_mode="mock",
                sessions_per_mode=2,
                output_root=root / "experiment",
                evaluation_modes=("baseline", "rule_based", "trainable"),
                trainable_model=model_path,
            )
            self.assertTrue((root / "experiment" / "trainable").is_dir())
            self.assertTrue(Path(result["reports"]["baseline_vs_trainable"]["output"]).exists())
            self.assertEqual(len(result["evaluation_modes"]), 3)

    def test_trainable_mode_requires_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                module.run_experiment(
                    experiment_id="test-exp",
                    runner_mode="mock",
                    sessions_per_mode=1,
                    output_root=Path(tmp),
                    evaluation_modes=("trainable",),
                    trainable_model=Path(tmp) / "missing.json",
                )

    def test_parse_modes_rejects_unknown_mode(self):
        with self.assertRaises(Exception):
            module._parse_modes("baseline,nope")


if __name__ == "__main__":
    unittest.main()
