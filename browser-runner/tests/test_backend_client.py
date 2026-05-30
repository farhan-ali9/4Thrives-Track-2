from __future__ import annotations

import gzip
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from email.message import Message

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("backend_client", ROOT / "browser-runner" / "backend_client.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["backend_client"] = module
spec.loader.exec_module(module)


class BackendClientTests(unittest.TestCase):
    def test_event_payload_defaults_match_farhan_v2_contract(self):
        payload = module.normalize_event_payload({
            "event_id": "evt_1",
            "session_id": "sess_1",
            "ts": 123.0,
            "event_type": "inactivity",
        })
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["source"], "browser-runner")
        self.assertEqual(payload["privacy_level"], "anonymous")
        self.assertEqual(payload["raw_value"], {})
        self.assertEqual(payload["ts"], 123)

    def test_invalid_outcome_rejected_before_backend_call(self):
        with self.assertRaises(ValueError):
            module.normalize_outcome_payload({"session_id": "sess_1", "outcome": "converted"})

    def test_client_routes_requests_to_v2_endpoints(self):
        calls = []

        def transport(method, url, payload, timeout):
            calls.append((method, url, payload, timeout))
            return {"ok": True}

        client = module.CoachApiClient("http://backend.test/", timeout=3.5, transport=transport)
        client.post_event({"event_id": "evt_1", "session_id": "sess_1", "ts": 1, "event_type": "click"})
        client.request_inference("sess_1")
        client.post_exposure({"exposure_id": "exp_1", "session_id": "sess_1", "decision_id": "dec_1", "action_id": "action_1"})
        client.post_outcome({"session_id": "sess_1", "outcome": "abandoned"})
        client.fetch_session("sess_1")
        self.assertEqual([call[0] for call in calls], ["POST", "POST", "POST", "POST", "GET"])
        self.assertTrue(calls[0][1].endswith("/api/v2/events"))
        self.assertTrue(calls[1][1].endswith("/api/v2/inference"))
        self.assertTrue(calls[2][1].endswith("/api/v2/exposures"))
        self.assertTrue(calls[3][1].endswith("/api/v2/outcomes"))
        self.assertTrue(calls[4][1].endswith("/api/v2/sessions/sess_1"))

    def test_gzip_response_is_decoded(self):
        payload = gzip.compress(b'{"ok":true}')

        class FakeResponse:
            def __init__(self):
                self.headers = Message()
                self.headers["Content-Encoding"] = "gzip"
                self.headers["Content-Type"] = "application/json; charset=utf-8"

            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original = module.urlopen
        module.urlopen = lambda request, timeout=0: FakeResponse()
        try:
            parsed = module._urllib_transport("GET", "http://backend.test/api/v2/sessions/sess_1", None, 3.0)
        finally:
            module.urlopen = original
        self.assertEqual(parsed, {"ok": True})


if __name__ == "__main__":
    unittest.main()
