from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonDict = dict[str, Any]
Transport = Callable[[str, str, JsonDict | None, float], JsonDict]


class RuntimeApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeApiClient:
    backend_url: str
    timeout: float = 10.0
    transport: Transport | None = None

    def post_outcome(self, outcome: JsonDict) -> JsonDict:
        return self._request("POST", "/api/runtime/outcome", normalize_outcome_payload(outcome))

    def fetch_session(self, session_id: str) -> JsonDict:
        if not session_id:
            raise ValueError("session_id is required")
        return self._request("GET", f"/api/runtime/sessions/{session_id}", None)

    def _request(self, method: str, path: str, payload: JsonDict | None) -> JsonDict:
        if self.transport:
            return self.transport(method, self._url(path), payload, self.timeout)
        return _urllib_transport(method, self._url(path), payload, self.timeout)

    def _url(self, path: str) -> str:
        return f"{self.backend_url.rstrip('/')}{path}"


def normalize_outcome_payload(outcome: JsonDict) -> JsonDict:
    _require(outcome, ["sessionId", "routeFamily", "terminalStage", "outcome", "decidedAt"], "outcome")
    if outcome["outcome"] not in {"converted_online", "submitted_advisor_lead", "abandoned"}:
        raise ValueError("outcome must be converted_online, submitted_advisor_lead, or abandoned")
    return {
        "sessionId": outcome["sessionId"],
        "routeFamily": outcome["routeFamily"],
        "terminalStage": outcome["terminalStage"],
        "outcome": outcome["outcome"],
        "finalTariff": outcome.get("finalTariff"),
        "finalPriceMonthly": outcome.get("finalPriceMonthly"),
        "decidedAt": int(outcome["decidedAt"]),
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
        raise RuntimeApiError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeApiError(f"{method} {url} failed: {exc.reason}") from exc
    return json.loads(raw) if raw else {}
