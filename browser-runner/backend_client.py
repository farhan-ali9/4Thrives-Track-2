from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonDict = dict[str, Any]
Transport = Callable[[str, str, JsonDict | None, float], JsonDict]


class CoachApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class CoachApiClient:
    backend_url: str
    timeout: float = 10.0
    transport: Transport | None = None

    def post_event(self, event: JsonDict) -> JsonDict:
        return self._request("POST", "/api/v2/events", normalize_event_payload(event))

    def request_inference(self, session_id: str) -> JsonDict:
        return self._request("POST", "/api/v2/inference", {"session_id": session_id})

    def post_exposure(self, exposure: JsonDict) -> JsonDict:
        return self._request("POST", "/api/v2/exposures", normalize_exposure_payload(exposure))

    def post_outcome(self, outcome: JsonDict) -> JsonDict:
        return self._request("POST", "/api/v2/outcomes", normalize_outcome_payload(outcome))

    def fetch_session(self, session_id: str) -> JsonDict:
        return self._request("GET", f"/api/v2/sessions/{session_id}", None)

    def _request(self, method: str, path: str, payload: JsonDict | None) -> JsonDict:
        if self.transport:
            return self.transport(method, self._url(path), payload, self.timeout)
        return _urllib_transport(method, self._url(path), payload, self.timeout)

    def _url(self, path: str) -> str:
        return f"{self.backend_url.rstrip('/')}{path}"


def normalize_event_payload(event: JsonDict) -> JsonDict:
    required = ["event_id", "session_id", "ts", "event_type"]
    _require(event, required, "event")
    return {
        "schema_version": event.get("schema_version", "v1"),
        "event_id": event["event_id"],
        "session_id": event["session_id"],
        "ts": int(event["ts"]),
        "source": event.get("source", "browser-runner"),
        "step_id": event.get("step_id"),
        "event_type": event["event_type"],
        "element_key": event.get("element_key"),
        "raw_value": event.get("raw_value") or {},
        "derived_signals": event.get("derived_signals") or {},
        "derived_context": event.get("derived_context") or {},
        "runner_metadata": event.get("runner_metadata") or {},
        "privacy_level": event.get("privacy_level", "anonymous"),
    }


def normalize_exposure_payload(exposure: JsonDict) -> JsonDict:
    _require(exposure, ["exposure_id", "session_id", "decision_id", "action_id"], "exposure")
    return {
        "exposure_id": exposure["exposure_id"],
        "session_id": exposure["session_id"],
        "decision_id": exposure["decision_id"],
        "action_id": exposure["action_id"],
        "impression_ts": exposure.get("impression_ts"),
        "dismiss_ts": exposure.get("dismiss_ts"),
        "cta_ts": exposure.get("cta_ts"),
        "render_success": exposure.get("render_success", True),
    }


def normalize_outcome_payload(outcome: JsonDict) -> JsonDict:
    _require(outcome, ["session_id", "outcome"], "outcome")
    if outcome["outcome"] not in {"converted_online", "abandoned", "advisor_handoff"}:
        raise ValueError("outcome must be converted_online, abandoned, or advisor_handoff")
    return {
        "session_id": outcome["session_id"],
        "outcome": outcome["outcome"],
        "terminal_step_id": outcome.get("terminal_step_id"),
        "ended_at": outcome.get("ended_at"),
        "final_tariff": outcome.get("final_tariff"),
        "final_visible_price": outcome.get("final_visible_price"),
        "price_delta": outcome.get("price_delta"),
    }


def _require(payload: JsonDict, fields: list[str], label: str) -> None:
    missing = [field for field in fields if payload.get(field) in (None, "")]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")


def _urllib_transport(method: str, url: str, payload: JsonDict | None, timeout: float) -> JsonDict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw_bytes = gzip.decompress(raw_bytes)
            charset = response.headers.get_content_charset("utf-8")
            raw = raw_bytes.decode(charset)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CoachApiError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise CoachApiError(f"{method} {url} failed: {exc.reason}") from exc
    return json.loads(raw) if raw else {}
