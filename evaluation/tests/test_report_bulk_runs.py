from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evaluation"))
spec = importlib.util.spec_from_file_location("report_bulk_runs", ROOT / "evaluation" / "report_bulk_runs.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class BulkReportTests(unittest.TestCase):
    def test_write_bulk_report_emits_summary_and_svgs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_dir = tmp_path / "baseline"
            coach_dir = tmp_path / "coach"
            output_dir = tmp_path / "report"
            baseline_dir.mkdir()
            coach_dir.mkdir()

            (baseline_dir / "trace_1.json").write_text(json.dumps({
                "terminal_outcome": "abandoned",
                "metadata": {"persona_id": "franz", "intention": "purchase"},
                "events": [{"step_id": "s4_initial_price"}],
                "coach_render_log": [],
            }))
            (coach_dir / "trace_1.json").write_text(json.dumps({
                "terminal_outcome": "converted_online",
                "metadata": {"persona_id": "franz", "intention": "purchase"},
                "events": [
                    {"step_id": "s4_initial_price", "event_type": "coach_cta"},
                    {"step_id": "s8_confirm"},
                ],
                "coach_render_log": [{"step_id": "s4_initial_price", "decision_state": "rendered", "rendered": True}],
            }))
            (baseline_dir / "batch-summary.json").write_text(json.dumps({"failures": {"backend": 0, "page": 0, "selector": 0}}))
            (coach_dir / "batch-summary.json").write_text(json.dumps({"failures": {"backend": 1, "page": 0, "selector": 0}}))

            result = module.write_bulk_report(baseline_path=baseline_dir, coach_path=coach_dir, output_dir=output_dir)

            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "summary.md").exists())
            self.assertTrue((output_dir / "outcomes.svg").exists())
            self.assertTrue((output_dir / "dropoffs.svg").exists())
            self.assertTrue((output_dir / "popup_rendering.svg").exists())
            self.assertTrue((output_dir / "index.html").exists())
            self.assertEqual(result["output_dir"], str(output_dir))


if __name__ == "__main__":
    unittest.main()
