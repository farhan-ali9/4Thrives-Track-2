from __future__ import annotations

import importlib.util
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

    def test_parse_modes_rejects_unknown_mode(self):
        with self.assertRaises(Exception):
            module._parse_modes("baseline,nope")


if __name__ == "__main__":
    unittest.main()
