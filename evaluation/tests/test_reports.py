from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evaluation"))
spec = importlib.util.spec_from_file_location("reports", ROOT / "evaluation" / "reports.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def test_comparison_markdown_contains_delta(self):
        text = module.comparison_markdown(baseline={"sessions": 1, "online_conversion_rate": 0.0}, treatment={"sessions": 1, "online_conversion_rate": 1.0}, delta={"conversion_rate_uplift": 1.0})
        self.assertIn("# Evaluation Comparison", text)
        self.assertIn("conversion_rate_uplift", text)


if __name__ == "__main__":
    unittest.main()
