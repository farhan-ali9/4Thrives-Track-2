from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))
spec = importlib.util.spec_from_file_location("build_live_datasets", ROOT / "training" / "build_live_datasets.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["build_live_datasets"] = module
spec.loader.exec_module(module)


class BuildLiveDatasetsTests(unittest.TestCase):
    def test_builds_user_and_coach_datasets(self):
        trace = {
            "session_id": "sess_1",
            "run_mode": "coach",
            "metadata": {"persona_id": "franz", "intention": "purchase", "seed": 1, "run_mode": "coach", "llm_model": "model"},
            "terminal_outcome": "advisor_handoff",
            "llm_decisions": [
                {
                    "decision_id": "lld_1",
                    "step_id": "s4_initial_price",
                    "action": "select_optimal",
                    "candidate_set": ["select_optimal", "abandon"],
                    "fallback_used": False,
                    "prompt_hash": "abc",
                    "step_context": {"visiblePrice": 68.14},
                    "history": [],
                    "llm_model": "model",
                }
            ],
            "events": [
                {
                    "event_id": "evt_1",
                    "session_id": "sess_1",
                    "ts": 1,
                    "step_id": "s4_initial_price",
                    "event_type": "coach_impression",
                    "element_key": "price_transparency",
                    "raw_value": {},
                    "derived_signals": {},
                    "derived_context": {"intervention_kind": "price_transparency"},
                    "runner_metadata": {"page_map_version": "v1", "extension_build_id": "ext", "model_version_or_policy": "rule"},
                    "privacy_level": "anonymous",
                    "schema_version": "v1",
                    "source": "browser-runner",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            traces_path = tmp_path / "traces.json"
            traces_path.write_text(json.dumps([trace]))
            user_output = tmp_path / "user.jsonl"
            coach_output = tmp_path / "coach.jsonl"
            summary = module.build_live_datasets(
                traces_path=traces_path,
                user_output=user_output,
                coach_output=coach_output,
                user_dataset_phase="user_phase",
                coach_dataset_phase="coach_phase",
            )
            self.assertEqual(summary["user_policy_examples"], 1)
            self.assertEqual(summary["coach_ranking_examples"], 1)
            self.assertTrue(user_output.exists())
            self.assertTrue(coach_output.exists())

    def test_bootstraps_rule_based_coach_examples_when_backend_trace_is_empty(self):
        trace = {
            "session_id": "sess_1",
            "run_mode": "coach",
            "metadata": {
                "page_map_version": "v1",
                "extension_build_id": "ext",
                "model_version_or_policy": "rule-based",
                "run_mode": "coach",
            },
            "terminal_outcome": "advisor_handoff",
            "events": [],
            "decisions": [],
            "exposures": [],
            "llm_decisions": [
                {"decision_id": "lld_1", "step_id": "s1_coverage_scope", "action": "at_doctor"},
                {"decision_id": "lld_2", "step_id": "s4_initial_price", "action": "select_optimal"},
                {"decision_id": "lld_3", "step_id": "s7_final_price", "action": "request_advisor"},
            ],
        }
        examples = module.build_coach_ranking_examples(trace, "coach_phase")
        self.assertEqual(len(examples), 2)
        self.assertEqual([row["current_step_id"] for row in examples], ["s4_initial_price", "s7_final_price"])
        self.assertEqual({row["chosen_candidate"] for row in examples}, {"price_transparency"})
        self.assertEqual({row["exposure_result"] for row in examples}, {"not_recorded"})


if __name__ == "__main__":
    unittest.main()
