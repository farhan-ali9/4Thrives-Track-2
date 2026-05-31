from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LIVE_UNIQA_URL = "https://www.uniqa.at/rechner/krankenversicherung/"
DEFAULT_FEATHERLESS_CHAT_URL = "https://api.featherless.ai/v1/chat/completions"
DEFAULT_FEATHERLESS_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def _default_extension_path() -> Path | None:
    built_extension = Path(__file__).resolve().parents[1] / "extension" / "dist"
    if built_extension.exists():
        return built_extension
    return None


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
    coach_settle_ms: int = 750
    coach_overlay_timeout_ms: int = 2_500
    post_action_settle_ms: int = 600
    coach_read_ms: int = 450

    @classmethod
    def for_mode(cls, mode: str) -> "RunnerSafetyConfig":
        if mode == "bulk":
            return cls(
                mode="bulk",
                max_sessions=600,
                concurrency=3,
                min_think_ms=450,
                max_think_ms=2200,
                screenshots=False,
                coach_settle_ms=400,
                coach_overlay_timeout_ms=1_200,
                post_action_settle_ms=300,
                coach_read_ms=250,
            )
        if mode == "validation":
            return cls(max_sessions=12)
        if mode == "mock":
            return cls(
                mode="mock",
                max_sessions=3,
                concurrency=1,
                screenshots=False,
                coach_settle_ms=0,
                coach_overlay_timeout_ms=0,
                post_action_settle_ms=0,
                coach_read_ms=0,
            )
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
    execution_mode: str = "coach"
    llm_api_url: str = DEFAULT_FEATHERLESS_CHAT_URL
    llm_model: str = DEFAULT_FEATHERLESS_MODEL
    llm_temperature: float = 0.2
    llm_timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "BrowserRunConfig":
        extension = os.getenv("EXTENSION_DIST")
        resolved_extension = Path(extension).expanduser().resolve() if extension else _default_extension_path()
        execution_mode = os.getenv("RUNNER_EXECUTION_MODE", "coach")
        model = os.getenv("LLM_MODEL") or os.getenv("LLM_DEFAULT_MODEL") or os.getenv("VITE_FEATHERLESS_MODEL") or DEFAULT_FEATHERLESS_MODEL
        return cls(
            site_url=os.getenv("UNIQA_CALCULATOR_URL", LIVE_UNIQA_URL),
            backend_url=os.getenv("COACH_API_URL", "http://127.0.0.1:8787"),
            extension_path=resolved_extension,
            output_dir=Path(os.getenv("RUNNER_OUTPUT_DIR", "artifacts/browser-runs")),
            headless=os.getenv("RUNNER_HEADLESS", "0") == "1",
            page_map_version=os.getenv("PAGE_MAP_VERSION", "live-uniqa-v1"),
            extension_build_id=os.getenv("EXTENSION_BUILD_ID", "local"),
            execution_mode=execution_mode,
            llm_api_url=os.getenv("LLM_API_URL") or os.getenv("LLM_GATEWAY_URL") or DEFAULT_FEATHERLESS_CHAT_URL,
            llm_model=model,
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
        )
