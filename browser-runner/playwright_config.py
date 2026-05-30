from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LIVE_UNIQA_URL = "https://www.uniqa.at/versicherung/gesundheit/private-krankenversicherung.html"


@dataclass(frozen=True)
class RunnerSafetyConfig:
    mode: str = "validation"
    max_sessions: int = 3
    concurrency: int = 1
    min_think_ms: int = 650
    max_think_ms: int = 2600
    selector_failure_limit: int = 3
    backend_failure_limit: int = 3
    page_failure_limit: int = 2
    allow_purchase_submit: bool = False
    screenshots: bool = True

    @classmethod
    def for_mode(cls, mode: str) -> "RunnerSafetyConfig":
        if mode == "bulk":
            return cls(mode="bulk", max_sessions=50, concurrency=3, min_think_ms=450, max_think_ms=2200, screenshots=False)
        if mode == "validation":
            return cls()
        if mode == "mock":
            return cls(mode="mock", max_sessions=3, concurrency=1, screenshots=False)
        raise ValueError(f"Unsupported run mode: {mode}")


@dataclass(frozen=True)
class BrowserRunConfig:
    site_url: str = LIVE_UNIQA_URL
    backend_url: str = "http://127.0.0.1:8787"
    extension_path: Path | None = None
    output_dir: Path = Path("artifacts/browser-runs")
    headless: bool = False
    page_map_version: str = "live-uniqa-v1"
    extension_build_id: str = "local"
    model_version_or_policy: str = "rule-based"

    @classmethod
    def from_env(cls) -> "BrowserRunConfig":
        extension = os.getenv("EXTENSION_DIST")
        return cls(
            site_url=os.getenv("UNIQA_CALCULATOR_URL", LIVE_UNIQA_URL),
            backend_url=os.getenv("COACH_API_URL", "http://127.0.0.1:8787"),
            extension_path=Path(extension).expanduser().resolve() if extension else None,
            output_dir=Path(os.getenv("RUNNER_OUTPUT_DIR", "artifacts/browser-runs")),
            headless=os.getenv("RUNNER_HEADLESS", "0") == "1",
            page_map_version=os.getenv("PAGE_MAP_VERSION", "live-uniqa-v1"),
            extension_build_id=os.getenv("EXTENSION_BUILD_ID", "local"),
            model_version_or_policy=os.getenv("MODEL_VERSION_OR_POLICY", "rule-based"),
        )
