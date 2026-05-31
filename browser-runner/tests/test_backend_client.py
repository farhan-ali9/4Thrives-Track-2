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
    def test_outcome_payload_matches_runtime_contract(self):
        payload = module.normalize_outcome_payload({
            "sessionId": "sess_1",
            "routeFamily": "online_doctor",
            "terminalStage": "done",
            "outcome": "submitted_advisor_lead",
            "decidedAt": 123.0,
        })
        self.assertEqual(payload["sessionId"], "sess_1")
        self.assertEqual(payload["routeFamily"], "online_doctor")
        self.assertEqual(payload["terminalStage"], "done")
        self.assertEqual(payload["outcome"], "submitted_advisor_lead")
        self.assertEqual(payload["decidedAt"], 123)

    def test_invalid_outcome_rejected_before_backend_call(self):
        with self.assertRaises(ValueError):
            module.normalize_outcome_payload({"sessionId": "sess_1", "routeFamily": "online_doctor", "terminalStage": "done", "outcome": "converted", "decidedAt": 1})

    def test_client_routes_requests_to_runtime_endpoints(self):
        calls = []

        def transport(method, url, payload, timeout):
            calls.append((method, url, payload, timeout))
            return {"ok": True}

        client = module.RuntimeApiClient("http://backend.test/", timeout=3.5, transport=transport)
        client.post_outcome({
            "sessionId": "sess_1",
            "routeFamily": "online_doctor",
            "terminalStage": "done",
            "outcome": "abandoned",
            "decidedAt": 1,
        })
        client.fetch_session("sess_1")
        self.assertEqual([call[0] for call in calls], ["POST", "GET"])
        self.assertTrue(calls[0][1].endswith("/api/runtime/outcome"))
        self.assertTrue(calls[1][1].endswith("/api/runtime/sessions/sess_1"))

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
            parsed = module._urllib_transport("GET", "http://backend.test/api/runtime/sessions/sess_1", None, 3.0)
        finally:
            module.urlopen = original
        self.assertEqual(parsed, {"ok": True})


if __name__ == "__main__":
    unittest.main()
