from __future__ import annotations


class RunnerFailure(Exception):
    """Base class for classified runner failures."""


class SelectorFailure(RunnerFailure):
    """Raised when the live page selectors drift or expected UI is missing."""


class BackendFailure(RunnerFailure):
    """Raised when the coach backend is unavailable or times out."""


class PageLoadFailure(RunnerFailure):
    """Raised when the live UNIQA page cannot be loaded reliably."""
