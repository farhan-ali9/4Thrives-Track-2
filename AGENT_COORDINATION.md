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

Status: In progress

Files currently being edited:

* extension/src/background/coach-client.ts
* extension/src/background/orchestrator.ts
* extension/src/content/data-collector.ts
* extension/src/shared/extractors.ts
* extension/src/shared/uniqa-page-map.json
* extension/tests/data-collector.test.ts
* extension/tests/integration.test.ts
* extension/tests/fixtures/s7_final_price.html
* extension/tests/fixtures/s8_confirm.html
* extension/tests/live-smoke.spec.ts
* extension/tests/page-observer.test.ts
* extension/tests/step-matcher.test.ts
* AGENT_COORDINATION.md

Start time: 2026-05-30 15:06:07 CEST

Short plan:
* audit current extension behavior against the David spec
* stabilize UNIQA step and out-of-scope detection
* fill event/derived-context/rendering gaps and extend smoke coverage

Last update: 2026-05-30 15:49:35 CEST

Notes:
* Completed this pass:
  * switched the extension backend client to post canonical v2 event-ingestion payloads to `/api/v2/events` first, while preserving a legacy `/api/v1/coach/evaluate` fallback for older mocks/local servers
  * fixed a per-session event-ordering race in the extension background so concurrent observer events no longer overwrite each other
  * added session-duration extraction and corrected price-delta extraction against the previous visible price
  * tightened interaction tracking so focus/blur/pointerenter reset inactivity and button text can still classify out-of-scope path/tariff choices
  * added direct collector coverage for hospital/other-person out-of-scope choices plus `scroll` and `inactivity` events
  * added a live smoke that loads the built MV3 extension in Chromium against the real UNIQA calculator with a mock backend and verifies coach render plus stored `coach_impression`, `coach_cta`, and `coach_dismiss` events
  * enabled `s7_final_price` using live-verified selectors for the current UNIQA journey screen titled `Bisherige Versicherungen`
  * enabled `s8_confirm` against the current live terminal `Berateranfrage` screen because the live UNIQA flow now routes this persona path into advisor request rather than a simple online confirm page
  * fixed extractor realm-safety so field/value extraction works correctly for cross-realm DOMs in JSDOM fixtures as well as the live page
  * added observer-level coverage for `step_enter`, `step_leave`, and `price_changed`
  * added collector-level tests for out-of-scope hospital/other-person selection plus price/cancel hover capture
* Verification on 2026-05-30:
  * `cd extension && npm test`
  * `cd extension && npm run build`
  * `cd extension && npm run test:live`
  * all passed
* Stable live step detection verified today:
  * `s1_coverage_scope`
  * `s2_for_whom`
  * `s4_initial_price`
  * `s5_add_ons`
  * `s6_personal_medical_data`
  * `s7_final_price`
  * `s8_confirm`
* Step 7 status:
  * live verified and enabled
  * to reach it reliably in automation, Step 6 needed valid personal/medical data including a valid Austrian-style SV number and the full phone number with country code in the phone field
  * live selector anchor now uses:
    * text: `Bisherige Versicherungen`
    * `data-cy='insuranceInPast7Years'`
    * `data-cy='rejectedApplication'`
* Step 8 status:
  * live verified and enabled against the current terminal advisor-request screen
  * the current live sequence after Step 7 is:
    * medical-history questions
    * planned-treatment questions
    * `Berateranfrage` consultation-choice screen
  * live selector anchor now uses:
    * text: `Berateranfrage`
    * text: `Wo soll die Beratung bevorzugt stattfinden?`
    * `data-cy='consultationContact'`
* Remaining open area:
  * the current live site behavior does not show a straightforward online confirmation screen on this persona path, so Farhan and Andrii should treat the observed Step 8 screen in this branch as an advisor-handoff terminal state unless later backend rules say otherwise
* Notes for Farhan:
  * current extension/backend integration in this branch now prefers `POST /api/v2/events`
  * browser payload now follows the canonical snake_case event contract:
    * `schema_version`
    * `event_id`
    * `session_id`
    * `ts`
    * `source`
    * `step_id`
    * `event_type`
    * `element_key`
    * `raw_value`
    * `derived_signals`
    * `derived_context`
    * `runner_metadata`
    * `privacy_level`
  * legacy fallback to `POST /api/v1/coach/evaluate` is still present for older local mocks, but the primary path is now aligned with your `origin/Farhan-Branch`
  * live-stored event types now reliably include `step_enter`, `step_resolved`, `coach_impression`, `coach_cta`, and `coach_dismiss`
  * derived context emitted by the extension now includes `sessionDurationMs`, a corrected incremental `priceDelta`, Step 7 field-completion data, and Step 8 consultation-choice field-completion data
  * if backend terminal-outcome logic keys off steps, the current live `s8_confirm` detection should be interpreted as advisor handoff on this journey
  * example v2 event payload emitted by the extension:
    ```json
    {
      "schema_version": "v1",
      "event_id": "evt_step_enter",
      "session_id": "session_1",
      "ts": 1710000000000,
      "source": "extension",
      "step_id": "s4_initial_price",
      "event_type": "click",
      "element_key": "selectionbutton_2",
      "raw_value": {
        "intent": "out_of_scope_tariff",
        "option": "opt_plus"
      },
      "derived_signals": {
        "tariff_click_oos": true
      },
      "derived_context": {
        "selectedTariff": "optimal",
        "visiblePrice": 73.02,
        "priceDelta": 31.72,
        "sessionDurationMs": 1250
      },
      "runner_metadata": {},
      "privacy_level": "anonymous"
    }
    ```
  * expected safe response shape the extension handles:
    ```json
    {
      "actions": []
    }
    ```
* Notes for Andrii:
  * there is now a Playwright live smoke path that launches the built extension bundle in Chromium with `--load-extension`
  * stable live journey coverage now reaches the current terminal `Berateranfrage` screen
  * the live smoke contains the exact synthetic Step 6 inputs needed to advance into Step 7 and then answer the post-Step-7 medical questions with `nein`
  * if runner metrics distinguish online conversion from advisor handoff, this current live branch path should be counted as advisor handoff rather than online confirm
  * extension build path for runner loading: `extension/dist`
  * Chromium launch flags used in smoke coverage:
    * `--disable-extensions-except=/absolute/path/to/extension/dist`
    * `--load-extension=/absolute/path/to/extension/dist`
  * stable emitted step IDs currently observed live:
    * `s1_coverage_scope`
    * `s2_for_whom`
    * `s3_quote_basics`
    * `s4_initial_price`
    * `s5_add_ons`
    * `s6_personal_medical_data`
    * `s7_final_price`
    * `s8_confirm`
  * example session-log sequence from the extension-loaded smoke:
    * `step_enter`
    * `step_resolved`
    * `coach_impression`
    * `coach_cta`
    * `coach_dismiss`
* Branch check:
  * `origin/Farhan-Branch` now contains the v2 telemetry API and session replay work David should target
  * `origin/andrii-agent` now exists and shows active runner/trace orchestration progress
  * `origin/frontend` contains earlier extension/chat work and asset additions, but I did not see a newer backend interface change there that alters David’s current integration notes

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

Status: Not started

Files currently being edited:

* none

Last update: TBD

Notes:
Farhan owns the decision API and telemetry plane. The backend must be inspectable and should not become a pure LLM wrapper. Hard routing logic must remain deterministic.

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
