from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("uniqa_pipeline", ROOT / "uniqa_pipeline.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["uniqa_pipeline"] = module
spec.loader.exec_module(module)


def json_line(row: dict) -> str:
    import json

    return json.dumps(row) + "\n"


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

    def test_local_full_parser_defaults_to_small_validation_run(self):
        with patch.dict(os.environ, {}, clear=True):
            parser = module.build_parser()
            args = parser.parse_args(["local-full"])
        self.assertEqual(args.runner_mode, "validation")
        self.assertEqual(args.persona_runs, 1)
        self.assertIsNone(args.baseline_sessions)
        self.assertIsNone(args.coach_sessions)

    def test_local_full_skips_coach_training_for_empty_coach_dataset(self):
        parser = module.build_parser()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"FEATHERLESS_API_KEY": "rc_test"}, clear=True):
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text("FEATHERLESS_API_KEY=rc_test\n")
            output_root = root / "out"

            def fake_batch(**kwargs):
                return {"traces": [f"{kwargs['execution_mode']}.json"], "failures": {}}

            def fake_build_live_datasets(*, traces_path, user_output, coach_output, user_dataset_phase, coach_dataset_phase):
                user_output.parent.mkdir(parents=True, exist_ok=True)
                coach_output.parent.mkdir(parents=True, exist_ok=True)
                user_output.write_text(
                    json_line({
                        "session_id": "sess_1",
                        "decision_id": "lld_1",
                        "trace_prefix": [],
                        "current_step_id": "s1_coverage_scope",
                        "persona_id": "franz",
                        "intention": "purchase",
                        "seed": 1,
                        "run_mode": "baseline",
                        "llm_model": "fake",
                        "candidate_actions": ["at_doctor"],
                        "chosen_action": "at_doctor",
                        "future_outcome_summary": "abandoned",
                        "runner_metadata": {},
                        "dataset_phase": "test",
                    })
                )
                coach_output.write_text("")
                return {"traces": 1, "user_policy_examples": 1, "coach_ranking_examples": 0}

            def fake_overview(*, traces_dir, output_root):
                output_root.mkdir(parents=True, exist_ok=True)
                (output_root / "overview.json").write_text("{}")
                (output_root / "overview.md").write_text("# Overview\n")
                return {"baseline": {"sessions": 1}, "coach": {"sessions": 1}, "delta": {}}

            args = parser.parse_args([
                "local-full",
                "--env-file",
                str(env_path),
                "--output-root",
                str(output_root),
                "--skip-evaluate",
            ])
            with patch.object(module, "_run_live_batch", side_effect=fake_batch), patch.object(module, "build_live_datasets", side_effect=fake_build_live_datasets), patch.object(module, "_write_local_overview", side_effect=fake_overview):
                result = args.func(args)

            self.assertTrue(result["training"]["coach_ranker"]["skipped"])
            self.assertTrue((output_root / "pipeline_summary.json").exists())
            self.assertTrue((output_root / "overview.md").exists())

    def test_persona_runs_expands_to_full_matrix(self):
        self.assertEqual(module._session_count(explicit_sessions=None, persona_runs=2), 24)
        self.assertEqual(module._session_count(explicit_sessions=5, persona_runs=2), 5)

    def test_env_loader_maps_featherless_model_to_runner_model(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join([
                    "FEATHERLESS_API_KEY=rc_test",
                    "VITE_FEATHERLESS_MODEL=provider/custom-model",
                ])
            )
            loaded = module.load_env_file(env_path)
            self.assertEqual(loaded["FEATHERLESS_API_KEY"], "rc_test")
            self.assertEqual(os.environ["LLM_API_URL"], module.FEATHERLESS_CHAT_COMPLETIONS_URL)
            self.assertEqual(os.environ["LLM_MODEL"], "provider/custom-model")


if __name__ == "__main__":
    unittest.main()
