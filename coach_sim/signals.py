"""Behavioral signals emitted by persona bots and consumed by the detector.

Signals are intentionally low-level (what the UI would observe in a real
browser). The detector turns streams of these into typed Coach events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SignalKind(str, Enum):
    DWELL = "dwell"                    # seconds spent on the step
    SCROLL_BACK = "scroll_back"        # scrolled upward / toward previous content
    BACK_NAV = "back_nav"              # used browser back / "previous" CTA
    REPEATED_CHANGE = "repeated_change"  # changed the same input >=2 times
    PRICE_HOVER = "price_hover"        # hovered over a price cell
    CANCEL_HOVER = "cancel_hover"      # hovered over close / cancel
    TARIFF_CLICK_OOS = "tariff_click_oos"   # clicked Opt.Plus / Premium
    PATH_OOS = "path_oos"              # selected hospital / other persons
    INACTIVITY = "inactivity"          # >30s no input


@dataclass
class Signal:
    kind: SignalKind
    value: float = 0.0                 # seconds, count, etc.
    note: str = ""


@dataclass
class StepObservation:
    """Everything the journey records for one step visit."""
    step_id: str
    persona_id: str
    action: str                        # e.g. "continue", "select_optimal", "abandon"
    dwell_seconds: float
    signals: list[Signal] = field(default_factory=list)
    intervention_shown: Optional[str] = None
    intervention_accepted: Optional[bool] = None
    detected_events: list[str] = field(default_factory=list)
    screen_title: str = ""
    screen_description: str = ""
    phase: str = ""
