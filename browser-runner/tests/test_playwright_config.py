from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("playwright_config", ROOT / "browser-runner" / "playwright_config.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["playwright_config"] = module
spec.loader.exec_module(module)


class BrowserRunConfigTests(unittest.TestCase):
    def test_defaults_use_featherless_endpoint(self):
        with patch.dict(os.environ, {}, clear=True):
            config = module.BrowserRunConfig.from_env()
        self.assertEqual(config.llm_api_url, module.FEATHERLESS_CHAT_COMPLETIONS_URL)
        self.assertEqual(config.llm_model, module.DEFAULT_FEATHERLESS_MODEL)

    def test_vite_featherless_model_feeds_runner_model(self):
        with patch.dict(os.environ, {"VITE_FEATHERLESS_MODEL": "provider/custom-model"}, clear=True):
            config = module.BrowserRunConfig.from_env()
        self.assertEqual(config.llm_model, "provider/custom-model")


if __name__ == "__main__":
    unittest.main()
