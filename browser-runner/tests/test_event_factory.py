from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser-runner"))
spec = importlib.util.spec_from_file_location("event_factory", ROOT / "browser-runner" / "event_factory.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules["event_factory"] = module
spec.loader.exec_module(module)


class EventFactoryTests(unittest.TestCase):
    def test_out_of_scope_tariff_payload_matches_v2_shape(self):
        event = module.make_runner_event(
            session_id="session_1",
            event_id="evt_1",
            ts=1710000000000,
            event_type="click",
            step_id="s4_initial_price",
            element_key="selectionbutton_2",
            raw_value={"intent": "out_of_scope_tariff", "option": "opt_plus"},
            derived_context={"selectedTariff": "optimal", "visiblePrice": 73.02, "priceDelta": 31.72},
        )
        self.assertEqual(event["schema_version"], "v1")
        self.assertEqual(event["source"], "browser-runner")
        self.assertTrue(event["derived_signals"]["tariff_click_oos"])
        self.assertTrue(event["derived_signals"]["path_oos"])
        self.assertTrue(event["derived_signals"]["price_changed"])
        self.assertEqual(event["privacy_level"], "anonymous")

    def test_step_aliases_are_canonicalized(self):
        event = module.make_step_event(session_id="session_1", step_id="s3_tariff_choice")
        self.assertEqual(event["step_id"], "s3_quote_basics")
        self.assertEqual(event["element_key"], "s3_quote_basics")

    def test_coach_events_emit_expected_signals(self):
        dismiss = module.make_coach_event(session_id="session_1", step_id="s4_initial_price", event_type="coach_dismiss", decision_id="dec_1", action_id="action_1")
        cta = module.make_coach_event(session_id="session_1", step_id="s4_initial_price", event_type="coach_cta", decision_id="dec_1", action_id="action_1")
        self.assertTrue(dismiss["derived_signals"]["coach_dismissed"])
        self.assertTrue(cta["derived_signals"]["coach_cta_clicked"])
        self.assertEqual(cta["raw_value"]["decision_id"], "dec_1")

    def test_pointer_and_inactivity_signals(self):
        price_hover = module.derive_signal_flags(event_type="pointerenter", element_key="price", raw_value={"target": "price"})
        idle = module.derive_signal_flags(event_type="inactivity", element_key="inactivity_timer", raw_value={"idleMs": 30000})
        self.assertTrue(price_hover["price_hover"])
        self.assertTrue(idle["inactivity"])


if __name__ == "__main__":
    unittest.main()
