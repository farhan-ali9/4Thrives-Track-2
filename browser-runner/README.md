# Browser Runner

Andrii-owned runner entry points for persona-driven UNIQA calculator sessions.

## Modes

- `mock`: deterministic local trace generation for unit tests and smoke checks only.
- `validation`: low-concurrency live browser sessions with screenshots and conservative circuit breakers.
- `bulk`: capped-concurrency trace generation after validation succeeds.

## Live Requirements

Set these before live runs:

```bash
export EXTENSION_DIST=/absolute/path/to/extension/dist
export COACH_API_URL=https://coach-api-42il2.ondigitalocean.app/
export RUNNER_OUTPUT_DIR=artifacts/browser-runs
```

Live runs refuse to submit purchases. Real purchase submission needs an explicitly approved safe test path.

## Safety Breakers

`run_batch.py` classifies failures into:

- `selector`: selector drift or missing expected UI
- `backend`: backend timeout or connection failure
- `page`: live page load or unclassified browser failure

The result JSON includes `failures`, `failure_log`, and `circuit_breaker` so failed batches can be excluded or debugged before metrics are reported.


## Backend V2 Client

`backend_client.py` wraps Farhan's v2 API for runner-side telemetry and replay integration:

- `POST /api/v2/events`
- `POST /api/v2/inference`
- `POST /api/v2/exposures`
- `POST /api/v2/outcomes`
- `GET /api/v2/sessions/:id`

Payload normalizers default missing optional event fields to the agreed anonymous schema and reject invalid terminal outcomes before network calls.


## Event Factory

`event_factory.py` builds canonical v2 event payloads for mock/live runner telemetry. It mirrors David's extension payload shape and derives flags for:

- `tariff_click_oos`
- `path_oos`
- `inactivity`
- `price_hover`
- `cancel_hover`
- `scroll`
- `coach_cta_clicked`
- `coach_dismissed`
- `price_changed`
- `advisor_terminal`
