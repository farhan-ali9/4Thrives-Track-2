# AGENT_FARHAN_SPEC.md

## Agent

Farhan

## Role

Coach Backend + API + Telemetry Storage

## Coordination Rule

Before making changes, read `AGENT_COORDINATION.md`.

When starting work:
- update the Agent-Farhan section in `AGENT_COORDINATION.md`
- write which files you will edit
- write your start time and short plan

When completing work:
- update the Agent-Farhan section in `AGENT_COORDINATION.md`
- write which files you completed
- write your last update time
- add notes for David and Andrii if your work affects them

Do not edit files owned by David or Andrii unless agreed first.

---

# Main Goal

Build the coach backend that receives extension events, reconstructs session state, applies hard guardrails, selects/ranks coach interventions, logs exposures and outcomes, and exposes trace data for replay and training.

The backend is the decision and telemetry plane.

It should be inspectable, deterministic where necessary, and not a pure LLM wrapper.

---

# Owned Files

Farhan owns:

```text
coach-api/*
backend/*
api/*
server/*
database/*
prisma/*
migrations/*
docs/api/*
docs/backend/*
AGENT_COORDINATION.md
```

Farhan should avoid:

```text
extension/*
extension/src/*
extension/tests/*
browser-runner/*
runner/*
personas/*
training/*
evaluation/*
leonardo/*
replay/*
notebooks/*
```

---

# Core Backend Responsibilities

The backend must:

```text
receive browser events
store session traces
reconstruct session state
apply hard scope guardrails
rank or select coach actions
return actions to extension
log impressions, CTA clicks, dismissals, and outcomes
provide session replay data
```

---

# API Endpoints

Implement or specify these route families.

## 1. Event Ingestion

```http
POST /api/v2/events
```

Purpose:
Receive normalized events from the extension.

Request example:

```json
{
  "schema_version": "v1",
  "event_id": "evt_123",
  "session_id": "sess_123",
  "ts": 1710000000000,
  "source": "extension",
  "step_id": "s4_initial_price",
  "event_type": "inactivity",
  "element_key": "price_table",
  "raw_value": {},
  "derived_signals": {},
  "derived_context": {},
  "runner_metadata": {},
  "privacy_level": "anonymous"
}
```

Response example:

```json
{
  "ok": true,
  "actions": []
}
```

---

## 2. Inference

```http
POST /api/v2/inference
```

Purpose:
Rank or select coach actions at a decision point.

Response example:

```json
{
  "decision_id": "dec_123",
  "session_id": "sess_123",
  "actions": [
    {
      "id": "action_123",
      "kind": "price_transparency",
      "placement": "bottom-toast",
      "title": "Still deciding?",
      "body": "Your final price reflects your selected coverage and personal details. You can still complete Start or Optimal fully online.",
      "ctaLabel": "Continue",
      "dismissible": true
    }
  ]
}
```

---

## 3. Exposure Logging

```http
POST /api/v2/exposures
```

Purpose:
Record impression, render success, dismiss, and CTA events.

Required fields:

```text
exposure_id
session_id
decision_id
action_id
impression_ts
dismiss_ts
cta_ts
render_success
```

---

## 4. Outcome Logging

```http
POST /api/v2/outcomes
```

Purpose:
Record the terminal session outcome.

Allowed outcomes:

```text
converted_online
abandoned
advisor_handoff
```

Important:
Advisor handoff is correct for out-of-scope paths but does not count as online conversion.

---

## 5. Session Replay

```http
GET /api/v2/sessions/:id
```

Purpose:
Return full session trace, decisions, exposures, and outcome.

---

# Hard Guardrails

Hard guardrails must stay deterministic and outside the trainable model.

Rules:

```text
coverage = hospital → advisor_handoff
insured_person = other_persons → advisor_handoff
tariff = opt_plus → advisor_handoff
tariff = premium → advisor_handoff
coverage = private_doctor + insured_person = myself + tariff = start/optimal → online coaching allowed
```

Guardrail result examples:

```json
{
  "guardrail": "out_of_scope_advisor_tariff",
  "allowed_actions": ["advisor_handoff"],
  "blocked_actions": ["price_transparency", "market_comparison"]
}
```

---

# Intervention Catalog

Create or maintain an intervention catalog.

Required action kinds:

```text
no_action
price_transparency
trust_signal
simplified_explanation
market_comparison
online_alternative_explanation
save_progress
advisor_handoff
clear_next_step
```

Each catalog item should include:

```text
action_id
kind
title
body
ctaLabel
placement
persona_fit
step_fit
cooldown_seconds
max_per_session
enabled
```

---

# Rule-Based Coach Policy v1

Before a trainable model exists, implement a rule-based policy.

Decision inputs:

```text
current step
derived context
recent events
dwell time
hover cancel
back navigation
tariff switches
selected tariff
selected coverage
insured person
persona metadata if provided by runner
intervention history
```

Example rules:

```text
Step 4 + inactivity + in scope → price_transparency or market_comparison
Step 4 + clicked Premium/Opt Plus → online_alternative_explanation or advisor_handoff depending context
Step 5 + repeated add-on toggles → simplified_explanation
Step 7 + long dwell/hover cancel → price_transparency
Judith + price page → trust_signal
Franz + final price → price_transparency or market_comparison
Peter + early complexity → simplified_explanation
Out-of-scope path → advisor_handoff
```

---

# Session State Reconstruction

The backend must keep session state from event history.

Track at least:

```text
session_id
current_step_id
coverage
insured_person
selected_tariff
selected_addons
visible_price
price_delta
recent_event_window
intervention_count
last_intervention_ts
advisor_routed
converted
abandoned
```

---

# Cooldown And Budget Rules

Prevent annoying interventions.

Required:

```text
max 3 interventions per session
minimum 30 seconds between interventions
do not repeat same intervention kind twice in a row
do not show intervention if risk is too low
always allow no_action
```

---

# Risk Score

Implement a simple risk score.

Inputs:

```text
long dwell time
back navigation
tariff switching
add-on toggling
hover on cancel
price page
final price page
persona sensitivity
```

Output:

```text
0-29 low
30-59 medium
60-79 high
80-100 critical
```

The risk score should be logged with each inference result.

---

# Data Storage

Store these canonical objects:

## session_trace_event

```text
schema_version
event_id
session_id
ts
source
step_id
event_type
element_key
raw_value
derived_signals
derived_context
runner_metadata
privacy_level
```

## model_inference_result

```text
decision_id
session_id
model_version
experiment_id
candidate_set_version
chosen_action_id
ranked_candidates
guardrail_decisions
latency_ms
risk_score
```

## intervention_exposure

```text
exposure_id
session_id
decision_id
action_id
impression_ts
dismiss_ts
cta_ts
render_success
```

## journey_outcome

```text
session_id
outcome
terminal_step_id
advisor_routed
converted
abandoned
ended_at
final_tariff
final_visible_price
price_delta
```

---

# Tests

Add tests for:

```text
event ingestion accepts valid event
event ingestion rejects malformed event
hospital routes to advisor
other persons routes to advisor
Opt. Plus routes to advisor
Premium routes to advisor
Start/Optimal remain online-coachable
cooldown prevents repeated nudges
budget prevents too many interventions
Step 4 can trigger price intervention
Step 7 can trigger final-price intervention
advisor_handoff does not count as conversion
```

---

# Deliverables

Farhan should deliver:

```text
1. Backend API endpoints
2. Session event storage
3. Rule-based coach policy v1
4. Hard guardrail implementation
5. Intervention catalog
6. Exposure/outcome logging
7. Session replay endpoint
8. API documentation
9. Tests for routing and intervention selection
10. Notes in AGENT_COORDINATION.md
```

---

# Acceptance Criteria

Farhan's work is complete when:

```text
extension can initialize session through backend
extension can send events
backend returns valid actions array every time
out-of-scope paths return advisor handoff
in-scope hesitation can return coach intervention
events, decisions, exposures, and outcomes are stored
session replay returns complete trace
tests pass
```

---

# Handoff To David

Provide David with:

```text
backend base URL
exact endpoint paths
request/response examples
action response schema
error response schema
local dev instructions
mock mode instructions
```

---

# Handoff To Andrii

Provide Andrii with:

```text
session replay API
trace export format
outcome schema
experiment/model version fields
dataset extraction instructions
metrics fields available from backend
```

---

# Do Not Do

Do not:
- put DOM selectors in backend
- edit extension page-map
- edit browser runner scripts
- train model before trace schema is stable
- make advisor handoff count as online conversion
- use LLM as the only decision engine

---

# Final Success Statement

Farhan's work provides the central coach platform. It receives real extension events, applies deterministic guardrails, returns coach actions, and stores replayable traces that Andrii can use for evaluation and training.
