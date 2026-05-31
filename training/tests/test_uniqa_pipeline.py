from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("uniqa_pipeline", ROOT / "uniqa_pipeline.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["uniqa_pipeline"] = module
spec.loader.exec_module(module)


class UniqaPipelineParserTests(unittest.TestCase):
    def test_validate_live_defaults(self):
        parser = module.build_parser()
        args = parser.parse_args(["validate-live"])
        self.assertEqual(args.execution_mode, "baseline")
        self.assertEqual(args.sessions, 12)

    def test_local_full_loop_defaults(self):
        parser = module.build_parser()
        args = parser.parse_args(["local-full-loop"])
        self.assertEqual(args.validate_sessions, 12)
        self.assertEqual(args.bulk_sessions, 300)
        self.assertEqual(args.experiment_prefix, "local-full-loop")

    def test_run_live_defaults_to_coach_mode(self):
        parser = module.build_parser()
        args = parser.parse_args(["run-live"])
        self.assertEqual(args.execution_mode, "coach")
        self.assertEqual(args.sessions, 300)

    def test_removed_training_commands_are_not_exposed(self):
        parser = module.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["train-coach-ranker"])


if __name__ == "__main__":
    unittest.main()
