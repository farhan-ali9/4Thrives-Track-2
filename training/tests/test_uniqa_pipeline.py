from __future__ import annotations

import importlib.util
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
        self.assertEqual(args.evaluation_runner_mode, "validation")

    def test_leonardo_submit_print_only(self):
        parser = module.build_parser()
        args = parser.parse_args(["leonardo-submit", "--job", "validate", "--print-only"])
        result = args.func(args)
        self.assertFalse(result["submitted"])
        self.assertIn("sbatch", result["command"][0])

    def test_leonardo_submit_supports_full_loop_jobs(self):
        parser = module.build_parser()
        for job_name in ("validate-vllm", "bulk-vllm", "build-datasets", "evaluate"):
            args = parser.parse_args(["leonardo-submit", "--job", job_name, "--print-only"])
            result = args.func(args)
            self.assertFalse(result["submitted"])
            self.assertTrue(result["command"][1].endswith(".sh"))


if __name__ == "__main__":
    unittest.main()
