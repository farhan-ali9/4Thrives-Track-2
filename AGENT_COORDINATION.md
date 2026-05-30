# AGENT_COORDINATION.md

## Coordination Rule

Before making changes, read this file.

When starting work, update your section with:

* status
* files you will touch
* start time
* short plan

When completing work, update your section with:

* status
* completed files
* last update time
* notes for the next agent

Do not edit files owned by another agent unless agreed first.

---

# Current Agents

## Agent-David

Task: Chrome Extension + Live UNIQA Page Detection

Goal:
Build and stabilize the browser extension side of the system. The extension should detect UNIQA calculator steps, collect user interaction signals, render coach interventions, and send events to the backend.

Files:

* extension/*
* extension/src/*
* extension/tests/*
* extension/manifest.json
* extension/package.json
* docs/extension/*
* AGENT_COORDINATION.md

Responsibilities:

* Maintain UNIQA page-map / selector detection.
* Track real user/browser events:

  * clicks
  * hovers
  * dwell time
  * back navigation
  * inactivity
  * tariff selection
  * out-of-scope path selection
* Render coach cards / popups returned by the backend.
* Ensure Step 4 initial price and Step 7 final price are detectable.
* Ensure out-of-scope paths are detected:

  * hospital
  * other persons
  * Opt. Plus
  * Premium
* Add extension smoke tests where possible.

Do not edit:

* coach-api/*
* backend/*
* training/*
* leonardo/*
* replay/*
* ops-console/*

Status: Not started

Files currently being edited:

* none

Last update: TBD

Notes:
David owns the browser-side integration only. Backend decision logic should be mocked only if needed for local testing, but real backend API contracts belong to Farhan.

---

## Agent-Farhan

Task: Coach Backend + API + Telemetry Storage

Goal:
Build the backend that receives extension events, reconstructs session state, applies hard guardrails, selects/ranks interventions, logs exposures/outcomes, and provides trace data for replay and training.

Files:

* coach-api/*
* backend/*
* api/*
* server/*
* database/*
* prisma/*
* migrations/*
* docs/api/*
* docs/backend/*
* AGENT_COORDINATION.md

Responsibilities:

* Implement or update API endpoints:

  * POST /api/v2/events
  * POST /api/v2/inference
  * POST /api/v2/exposures
  * POST /api/v2/outcomes
  * GET /api/v2/sessions/:id
* Store canonical trace events.
* Store inference results.
* Store intervention exposures.
* Store terminal outcomes:

  * converted
  * abandoned
  * advisor_handoff
* Apply hard guardrails:

  * hospital → advisor handoff
  * other persons → advisor handoff
  * Opt. Plus / Premium → advisor handoff
  * Start / Optimal → online conversion path
* Implement first rule-based coach policy.
* Return intervention actions to the extension.
* Add backend tests for scope routing and intervention selection.

Do not edit:

* extension/*
* training/*
* leonardo/*
* browser-runner/*
* ops-console/* unless agreed

Status: Complete

Files completed:

* coach-api/prisma/schema.prisma — added SessionTraceEvent, ModelInferenceResult, InterventionExposure, JourneyOutcome models
* coach-api/prisma/migrations/20260530120000_add_telemetry/migration.sql — new migration for telemetry tables
* coach-api/src/repository.ts — extended CoachRepository interface + MemoryCoachRepository with v2 telemetry methods
* coach-api/src/prisma-repository.ts — implemented v2 methods in PrismaCoachRepository
* coach-api/src/guardrails.ts — hard deterministic guardrails (hospital, other persons, Opt. Plus, Premium → advisor_handoff)
* coach-api/src/session-state.ts — session state reconstruction from event history + risk scoring (0–100)
* coach-api/src/routes-v2.ts — all /api/v2/* route handlers
* coach-api/src/app.ts — v2 routes wired in
* coach-api/tests/routes-v2.test.ts — 37 tests for guardrails, intervention selection, scope routing, outcomes, exposures, session replay
* coach-api/vitest.config.ts — vitest workspace alias config

Test results: 45/45 passed (37 v2 tests + 5 policy engine + 3 existing app tests)

Last update: 2026-05-30T15:20:00Z

Notes:
Farhan owns the decision API and telemetry plane. The backend must be inspectable and should not become a pure LLM wrapper. Hard routing logic must remain deterministic.

Notes for David:
- v2 event schema: POST /api/v2/events expects { schema_version, event_id, session_id, ts, source, step_id, event_type, element_key, raw_value, derived_signals, derived_context, runner_metadata, privacy_level }
- derived_context should include selectedTariff, coverage, insuredPerson when known
- derived_signals should include path_oos:true or tariff_click_oos:true for OOS events
- POST /api/v2/events returns { ok: true, actions: CoachAction[] }
- v1 endpoint /api/v1/coach/evaluate still works for direct policy evaluation

Notes for Andrii:
- GET /api/v2/sessions/:id returns full trace { sessionId, events, decisions, exposures, outcome }
- Outcome values: converted_online | abandoned | advisor_handoff
- advisor_handoff does NOT count as online conversion
- Risk score (0–100) is stored with each inference result for evaluation

---

## Agent-Andrii

Task: Browser Runner + Replay + Leonardo Training/Evaluation

Goal:
Build the evaluation and training pipeline around real-system traces. This includes automated browser sessions, persona runners, trace replay, metrics, dataset building, and Leonardo batch execution.

Files:

* browser-runner/*
* runner/*
* personas/*
* replay/*
* training/*
* evaluation/*
* leonardo/*
* scripts/run_*.sh
* scripts/slurm_*.sh
* notebooks/*
* docs/evaluation/*
* docs/training/*
* AGENT_COORDINATION.md

Responsibilities:

* Build persona action policies:

  * Franz
  * Judith
  * Peter
  * persona variants
* Run browser sessions against the live UNIQA website with the extension loaded.
* Generate real-system traces through the extension and backend.
* Build replay tools for stored sessions.
* Compute evaluation metrics:

  * online conversion rate
  * drop-off reduction at Step 4
  * drop-off reduction at Step 7
  * advisor-routing correctness
  * intervention precision
  * annoyance rate
  * extension render success
  * step detection success
* Prepare Leonardo batch execution:

  * Slurm scripts
  * Pixi environment
  * Singularity/Apptainer notes
* Build training dataset from traces.
* Implement first action-ranking model only after traces are available.

Do not edit:

* extension/*
* coach-api/*
* backend/*
* database migrations unless agreed with Farhan

Status: Not started

Files currently being edited:

* none

Last update: TBD

Notes:
Andrii owns measurement and training. The runner should use the real extension and real backend where possible. Synthetic simulation can be used only for small unit-style testing, not as the primary proof.

---

# Shared Interfaces

These interfaces must be agreed before parallel implementation.

## Event Object

Owned by: Farhan
Used by: David, Andrii

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

## Inference Response Object

Owned by: Farhan
Used by: David

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

## Terminal Outcomes

Owned by: Farhan
Used by: Andrii

Allowed values:

* converted_online
* abandoned
* advisor_handoff

Important:
Advisor handoff is correct for out-of-scope paths but does not count as online conversion.

---

# Non-Overlapping Ownership Summary

| Agent  | Owns                                                   | Should Avoid                            |
| ------ | ------------------------------------------------------ | --------------------------------------- |
| David  | Extension, page detection, browser rendering           | Backend logic, model training           |
| Farhan | Backend API, telemetry, guardrails, inference response | Extension DOM work, Leonardo jobs       |
| Andrii | Runner, personas, replay, evaluation, training         | Extension internals, backend migrations |

---

# Final Product Integration

The three agents' work should combine into this final system:

1. David's extension observes the live UNIQA calculator and sends events.
2. Farhan's backend receives events, applies guardrails, and returns coach actions.
3. David's extension renders those actions on the page.
4. Andrii's runner executes persona sessions through the real site.
5. Farhan's backend stores traces and outcomes.
6. Andrii's evaluation pipeline compares:

   * no coach
   * rule-based coach
   * trainable coach
7. Final report shows conversion uplift, drop-off reduction, persona performance, and intervention quality.

---

# Shared Rule For All Agents

Do not make this a pure LLM-wrapper system.

The intelligence should be in:

* real behavior detection
* hard scope guardrails
* session reconstruction
* intervention policy
* trace-based evaluation
* persona-driven testing
* action ranking

An LLM may be used only for message wording, persona text generation, or optional model components.
