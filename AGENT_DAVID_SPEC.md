# AGENT_DAVID_SPEC.md

## Agent

David

## Role

Chrome Extension + Live UNIQA Page Detection

## Coordination Rule

Before making changes, read `AGENT_COORDINATION.md`.

When starting work:
- update the Agent-David section in `AGENT_COORDINATION.md`
- write which files you will edit
- write your start time and short plan

When completing work:
- update the Agent-David section in `AGENT_COORDINATION.md`
- write which files you completed
- write your last update time
- add notes for Farhan and Andrii if your work affects them

Do not edit files owned by Farhan or Andrii unless agreed first.

---

# Main Goal

Build and stabilize the Chrome extension side of the UNIQA Conversion Coach.

The extension must run on the live UNIQA calculator page, detect the current journey step, collect behavioral events, send normalized events to the backend, receive coach actions, and render the coach message on the page.

The extension should stay thin:

```text
detect page state
collect browser events
send telemetry to backend
render backend response
```

The extension should not contain the main coach decision logic.

---

# Owned Files

David owns:

```text
extension/*
extension/src/*
extension/tests/*
extension/manifest.json
extension/package.json
docs/extension/*
AGENT_COORDINATION.md
```

David should avoid:

```text
coach-api/*
backend/*
database/*
training/*
evaluation/*
leonardo/*
browser-runner/*
replay/*
ops-console/*
```

---

# Functional Requirements

## 1. Step Detection

The extension must detect the live UNIQA calculator steps.

Required step IDs:

```text
s1_coverage_scope
s2_for_whom
s3_quote_basics
s4_initial_price
s5_add_ons
s6_personal_medical_data
s7_final_price
s8_confirm
```

Minimum stable detection required for demo:

```text
s1_coverage_scope
s2_for_whom
s4_initial_price
s5_add_ons
s7_final_price
```

Important:
Step 7 final price is critical and must be enabled once selectors are verified.

---

## 2. Scope Detection Signals

The extension must detect and send events for out-of-scope choices:

```text
hospital path
other persons
Opt. Plus
Premium
```

These choices are not conversion targets. They must be sent to the backend so Farhan's backend can return advisor handoff actions.

The extension should not decide final business logic, but it may label raw interaction intent as:

```json
{
  "intent": "out_of_scope_path"
}
```

or:

```json
{
  "intent": "out_of_scope_tariff"
}
```

---

## 3. Behavioral Event Tracking

Track browser/user signals:

```text
click
change
input
focus
blur
pointerenter on price elements
pointerenter on cancel/back elements
scroll direction
inactivity after 30 seconds
step enter
step leave
price changed
coach impression
coach CTA click
coach dismiss
```

Each event should include:

```json
{
  "event_id": "evt_...",
  "session_id": "sess_...",
  "ts": 1710000000000,
  "pageStepId": "s4_initial_price",
  "coachStepId": "s4_initial_price",
  "type": "inactivity",
  "elementKey": "inactivity_timer",
  "value": {},
  "derivedContext": {}
}
```

---

## 4. Derived Context Extraction

Where possible, extract:

```text
selected tariff
visible price
price delta
selected add-ons
field completion
validation error count
age band
social insurance provider code
session duration
```

Do not collect personally identifiable real user data. Keep context anonymous or bucketed.

Examples:
- age should be converted into age band, not stored as exact birth date
- selected tariff is okay
- visible price is okay
- form completion percentage is okay
- exact name, email, phone, address must not be stored

---

## 5. Backend Communication

The extension must send messages to the backend or background service worker.

Expected local extension message flow:

```text
content script
→ background/service worker
→ backend API
→ background/service worker
→ content script
→ render action
```

Every response from the background/backend must be safe:

```json
{
  "actions": []
}
```

Never assume `response.actions` exists. Always use safe fallback:

```js
const actions = response?.actions || [];
```

---

## 6. Coach Rendering

Render backend actions as coach cards.

The action object has this format:

```json
{
  "id": "action_123",
  "kind": "price_transparency",
  "placement": "bottom-toast",
  "title": "Still deciding?",
  "body": "Your final price reflects your selected coverage and personal details. You can still complete Start or Optimal fully online.",
  "ctaLabel": "Continue",
  "dismissible": true
}
```

Supported placements:

```text
bottom-toast
near-primary-cta
inline-top-of-step
```

Minimum required:
- `bottom-toast`

Stretch:
- `near-primary-cta`
- `inline-top-of-step`

---

# Implementation Steps

## Step 1 — Check Extension Boot

Make sure:
- `manifest.json` is valid
- content script loads on `https://www.uniqa.at/*`
- background/service worker is registered
- content script can initialize a session
- no runtime error occurs if backend is unavailable

Acceptance:
- extension loads successfully in `chrome://extensions`
- no immediate console crash
- content script receives a `sessionId`

---

## Step 2 — Stabilize Page Map

Verify selectors for:

```text
coverage choice
insured person choice
initial price table
tariff buttons
add-ons
final price
checkout/confirm
```

Acceptance:
- extension resolves the correct `pageStepId`
- logs step enter events
- logs step leave events

---

## Step 3 — Add Event Collection

Implement tracking for:
- clicks
- changes
- inactivity
- hover on price/cancel
- scroll/back behavior

Acceptance:
- interactions generate events
- events include step ID and derived context
- no raw sensitive fields are stored

---

## Step 4 — Render Coach Actions

Render action cards returned by backend.

Acceptance:
- extension renders at least one test action
- CTA click emits `coach_cta`
- dismiss emits `coach_dismiss`
- impression emits `coach_impression`

---

## Step 5 — Smoke Test Live Calculator

Create/update smoke tests.

Acceptance:
- test opens UNIQA calculator
- extension loads
- at least one step is detected
- at least one event is sent
- at least one mock coach action can render

---

# Deliverables

David should deliver:

```text
1. Working Chrome extension on live UNIQA calculator
2. Stable step detection for core in-scope journey
3. Event collection for user behavior signals
4. Coach card rendering
5. Smoke test or manual test notes
6. Notes in AGENT_COORDINATION.md
```

---

# Acceptance Criteria

David's work is complete when:

```text
extension loads without errors
session initialization works
events are sent to backend/background
Step 4 initial price is detected
Step 7 final price is detected or documented as pending selector verification
out-of-scope clicks are detected
coach card can be rendered
CTA/dismiss/impression events are logged
```

---

# Handoff To Farhan

Provide Farhan with:

```text
actual event payload examples
step IDs emitted by extension
derivedContext fields emitted by extension
required backend response format
any selector/page-map limitations
```

---

# Handoff To Andrii

Provide Andrii with:

```text
how to load the extension in Playwright
extension build path
steps that are currently stable
known selector failures
example session logs
```

---

# Do Not Do

Do not:
- implement the main intervention policy inside the extension
- store personal user data
- submit a real purchase
- edit backend database schemas
- edit training or Leonardo scripts
- make coach messages dependent only on hardcoded extension logic

---

# Final Success Statement

David's work enables the real UNIQA website to become observable and interactive for the Conversion Coach. The extension detects real user behavior, sends clean telemetry, and renders coach interventions returned by the backend.
