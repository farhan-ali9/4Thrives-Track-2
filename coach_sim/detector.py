"""Rule-based detection layer: per-step Signal stream -> typed events."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .signals import Signal, SignalKind


class Event(str, Enum):
    LONG_DWELL = "long_dwell"
    BACK_NAV = "back_nav"
    REPEATED_CHANGE = "repeated_change"
    CANCEL_INTENT = "cancel_intent"          # cancel hover + inactivity
    PRICE_FIXATION = "price_fixation"        # price hover + long dwell
    OUT_OF_SCOPE_TARIFF = "oos_tariff"       # clicked Opt.Plus / Premium
    OUT_OF_SCOPE_PATH = "oos_path"           # picked hospital / other persons
    PRICE_GAP_SHOCK = "price_gap_shock"      # final > initial
    NONE = "none"


@dataclass
class DetectorConfig:
    long_dwell_seconds: float = 25.0
    price_fixation_seconds: float = 15.0   # lower threshold — price hover is a stronger signal
    price_gap_eur_threshold: float = 3.0


class Detector:
    def __init__(self, config: DetectorConfig | None = None):
        self.cfg = config or DetectorConfig()

    def detect(self, signals: list[Signal], *,
               initial_price: float | None = None,
               final_price: float | None = None) -> list[Event]:
        events: list[Event] = []
        kinds = [s.kind for s in signals]
        dwell = next((s.value for s in signals if s.kind == SignalKind.DWELL), 0.0)

        if SignalKind.PATH_OOS in kinds:
            events.append(Event.OUT_OF_SCOPE_PATH)
        if SignalKind.TARIFF_CLICK_OOS in kinds:
            events.append(Event.OUT_OF_SCOPE_TARIFF)
        if SignalKind.BACK_NAV in kinds or SignalKind.SCROLL_BACK in kinds:
            events.append(Event.BACK_NAV)
        if SignalKind.REPEATED_CHANGE in kinds:
            events.append(Event.REPEATED_CHANGE)
        if dwell >= self.cfg.long_dwell_seconds:
            events.append(Event.LONG_DWELL)
        if SignalKind.PRICE_HOVER in kinds and dwell >= self.cfg.price_fixation_seconds:
            events.append(Event.PRICE_FIXATION)
        if SignalKind.CANCEL_HOVER in kinds or SignalKind.INACTIVITY in kinds:
            events.append(Event.CANCEL_INTENT)
        if (initial_price is not None and final_price is not None
                and final_price - initial_price >= self.cfg.price_gap_eur_threshold):
            events.append(Event.PRICE_GAP_SHOCK)

        return events or [Event.NONE]