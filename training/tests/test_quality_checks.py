from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("quality_checks", ROOT / "training" / "quality_checks.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class QualityChecksTests(unittest.TestCase):
    def test_valid_dataset_row(self):
        row = {
            "session_id": "sess_1",
            "decision_id": "evt_2",
            "trace_prefix": [{"event_id": "evt_1"}],
            "current_step_id": "s4_initial_price",
            "page_map_version": "v1",
            "extension_version": "ext",
            "model_version_or_baseline": "rule",
            "candidate_set": ["price_transparency"],
            "guardrail_filtered_candidates": ["price_transparency"],
            "chosen_candidate": "price_transparency",
            "exposure_result": "shown",
            "future_outcome_summary": "converted_online",
            "runner_metadata": {},
            "dataset_phase": "test",
        }
        summary = module.check_dataset([row])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["rows"], 1)

    def test_invalid_candidate_is_reported(self):
        row = {field: None for field in module.REQUIRED_DATASET_FIELDS}
        row.update({"candidate_set": ["a"], "guardrail_filtered_candidates": ["b"], "chosen_candidate": "b", "trace_prefix": []})
        summary = module.check_dataset([row])
        self.assertFalse(summary["valid"])
        self.assertIn("row[0] chosen_candidate not in candidate_set", summary["errors"])

    def test_empty_dataset_is_reported(self):
        summary = module.check_dataset([])
        self.assertFalse(summary["valid"])
        self.assertIn("dataset is empty", summary["errors"])


if __name__ == "__main__":
    unittest.main()
