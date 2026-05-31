from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


class UniqaPipelineLocalLlmTests(unittest.TestCase):
    def test_is_local_llm_endpoint_when_provider_local(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "local", "LLM_API_URL": "https://api.featherless.ai/v1/chat/completions"}, clear=False):
            self.assertTrue(module._is_local_llm_endpoint())

    def test_is_local_llm_endpoint_for_localhost_url(self):
        with patch.dict(os.environ, {"LLM_API_URL": "http://localhost:11434/v1/chat/completions"}, clear=False):
            os.environ.pop("LLM_PROVIDER", None)
            self.assertTrue(module._is_local_llm_endpoint())

    def test_is_local_llm_endpoint_for_loopback_url(self):
        with patch.dict(os.environ, {"LLM_API_URL": "http://127.0.0.1:11434/v1/chat/completions"}, clear=False):
            os.environ.pop("LLM_PROVIDER", None)
            self.assertTrue(module._is_local_llm_endpoint())

    def test_is_local_llm_endpoint_false_for_featherless(self):
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "remote", "LLM_API_URL": "https://api.featherless.ai/v1/chat/completions"},
            clear=False,
        ):
            self.assertFalse(module._is_local_llm_endpoint())

    def test_local_ollama_models_url(self):
        with patch.dict(os.environ, {"LLM_API_URL": "http://localhost:11434/v1/chat/completions"}, clear=False):
            self.assertEqual(module._local_ollama_models_url(), "http://localhost:11434/v1/models")


if __name__ == "__main__":
    unittest.main()
