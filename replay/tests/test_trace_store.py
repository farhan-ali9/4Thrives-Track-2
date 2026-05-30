from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("trace_store", ROOT / "replay" / "trace_store.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def valid_trace():
    metadata = {
        "runner_id": "andrii-browser-runner",
        "experiment_id": "exp",
        "persona_id": "franz",
        "intention": "purchase",
        "seed": 1,
        "backend_url": "http://127.0.0.1:8787",
        "model_version_or_policy": "rule-based",
    }
    return {
        "session_id": "sess_1",
        "terminal_outcome": "converted_online",
        "metadata": metadata,
        "events": [
            {
                "schema_version": "v1",
                "event_id": "evt_1",
                "session_id": "sess_1",
                "ts": 1,
                "source": "extension",
                "step_id": "s4_initial_price",
                "event_type": "inactivity",
                "element_key": "price_table",
                "raw_value": {},
                "derived_signals": {},
                "derived_context": {},
                "runner_metadata": metadata,
                "privacy_level": "anonymous",
            }
        ],
    }


def farhan_v2_trace():
    return {
        "session_id": "sess_backend",
        "events": [
            {
                "event_id": "evt_backend",
                "session_id": "sess_backend",
                "ts": 10,
                "step_id": "s4_initial_price",
                "event_type": "inactivity",
                "element_key": "price_table",
                "derived_signals": {},
                "derived_context": {},
                "privacy_level": "anonymous",
            }
        ],
        "decisions": [
            {
                "decision_id": "dec_1",
                "session_id": "sess_backend",
                "model_version": "rule_based_v1",
                "chosen_action_id": "price_transparency",
                "risk_score": 55,
                "guardrail_decisions": [],
                "latency_ms": 12,
                "created_at": "2026-05-30T12:00:00.000Z",
            }
        ],
        "exposures": [],
        "outcome": {"session_id": "sess_backend", "outcome": "converted_online"},
    }


class TraceStoreTests(unittest.TestCase):
    def test_valid_trace_has_no_errors(self):
        self.assertEqual(module.validate_trace(valid_trace()), [])

    def test_invalid_trace_reports_missing_fields(self):
        trace = valid_trace()
        del trace["events"][0]["event_id"]
        trace["terminal_outcome"] = "bad"
        errors = module.validate_trace(trace)
        self.assertTrue(any("event[0] missing fields" in error for error in errors))
        self.assertIn("missing or invalid terminal_outcome", errors)

    def test_farhan_v2_trace_is_normalized_for_replay(self):
        trace = module.normalize_trace(farhan_v2_trace())
        self.assertEqual(trace["terminal_outcome"], "converted_online")
        self.assertEqual(trace["events"][0]["schema_version"], "v1")
        self.assertEqual(trace["events"][0]["source"], "backend_export")
        self.assertEqual(module.validate_trace(trace), [])


if __name__ == "__main__":
    unittest.main()
