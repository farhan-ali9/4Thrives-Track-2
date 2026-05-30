from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from trace_store import normalize_trace, validate_trace


def fetch_session_trace(*, backend_url: str, session_id: str, timeout: float = 10.0) -> dict:
    url = f"{backend_url.rstrip('/')}/api/v2/sessions/{session_id}"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Backend returned HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach backend at {url}: {exc.reason}") from exc
    return normalize_trace(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one /api/v2/sessions/:id trace for replay/training")
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fail-on-invalid", action="store_true")
    args = parser.parse_args()
    trace = fetch_session_trace(backend_url=args.backend_url, session_id=args.session_id)
    errors = validate_trace(trace)
    if args.fail_on_invalid and errors:
        raise SystemExit("invalid trace: " + "; ".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2, sort_keys=True))
    print(json.dumps({"output": str(args.output), "session_id": trace.get("session_id"), "validation_errors": errors}, indent=2))


if __name__ == "__main__":
    main()
