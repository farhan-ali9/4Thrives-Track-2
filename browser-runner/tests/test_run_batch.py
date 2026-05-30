from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("run_batch", ROOT / "browser-runner" / "run_batch.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class RunBatchSafetyTests(unittest.TestCase):
    def test_backend_timeout_trips_backend_circuit_breaker(self):
        def failing_runner(persona_id, intention, experiment_id, seed, config, safety):
            raise module.BackendFailure("backend timed out")

        with tempfile.TemporaryDirectory() as tmp:
            result = module.run_batch(mode="mock", experiment_id="test", sessions=5, output_dir=Path(tmp), runner=failing_runner)
        self.assertEqual(result["failures"]["backend"], 3)
        self.assertEqual(result["circuit_breaker"], "backend_failure_limit")
        self.assertEqual(result["failure_log"][0]["failure_type"], "backend")

    def test_missing_selector_trips_selector_circuit_breaker(self):
        def failing_runner(persona_id, intention, experiment_id, seed, config, safety):
            raise module.SelectorFailure("selector missing")

        with tempfile.TemporaryDirectory() as tmp:
            result = module.run_batch(mode="mock", experiment_id="test", sessions=5, output_dir=Path(tmp), runner=failing_runner)
        self.assertEqual(result["failures"]["selector"], 3)
        self.assertEqual(result["circuit_breaker"], "selector_failure_limit")


if __name__ == "__main__":
    unittest.main()
