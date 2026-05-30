from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

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
            self.assertIn(trace["terminal_outcome"], {"converted_online", "abandoned", "advisor_handoff"})
            path = module.write_trace(trace, tmp_path)
            self.assertTrue(path.exists())

    def test_out_of_scope_live_elements_end_as_advisor_handoff(self):
        for element_key in ("hospital", "other_persons", "opt_plus", "premium"):
            self.assertEqual(module._terminal_outcome_for_element(element_key), "advisor_handoff")
        self.assertIsNone(module._terminal_outcome_for_element("at_doctor"))


if __name__ == "__main__":
    unittest.main()
