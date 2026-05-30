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

Status: Leonardo/Slurm/Apptainer execution assets implemented locally; coordination update ready to share

Files currently being edited:

* none

Completed files:

* browser-runner/README.md
* browser-runner/errors.py
* browser-runner/persona_policy.py
* browser-runner/playwright_config.py
* browser-runner/run_session.py
* browser-runner/run_batch.py
* browser-runner/tests/test_persona_policy.py
* browser-runner/tests/test_mock_runner.py
* browser-runner/tests/test_run_batch.py
* personas/franz.json
* personas/judith.json
* personas/peter.json
* personas/variants.json
* replay/render_timeline.py
* replay/replay_session.py
* replay/trace_store.py
* replay/validate_traces.py
* replay/tests/test_trace_store.py
* evaluation/metrics.py
* evaluation/compare_modes.py
* evaluation/reports.py
* evaluation/run_experiment.py
* evaluation/tests/test_metrics.py
* evaluation/tests/test_reports.py
* evaluation/tests/test_run_experiment.py
* training/build_dataset.py
* training/train_ranker.py
* training/evaluate_ranker.py
* training/tests/test_build_dataset.py
* training/quality_checks.py
* training/tests/test_quality_checks.py
* leonardo/README.md
* leonardo/env.example
* leonardo/apptainer.def
* leonardo/pixi.toml
* leonardo/slurm_browser_batch.sh
* leonardo/slurm_replay.sh
* leonardo/slurm_train.sh
* scripts/run_browser_validation.sh
* scripts/run_mock_evaluation.sh
* scripts/run_evaluation_experiment.sh
* scripts/slurm_browser_batch.sh
* scripts/slurm_replay.sh
* scripts/slurm_evaluation_experiment.sh
* scripts/slurm_train.sh
* docs/evaluation/README.md
* docs/training/README.md

Last update: 2026-05-30 15:38 CEST

Notes:
Andrii implemented the first local scaffold for persona policies, safe mock/live runner entry points, replay, metrics, trace-to-dataset, simple post-trace ranker training, Leonardo batch docs/scripts, and focused unit tests. Follow-up expansion added classified runner failures, batch `failure_log` and `circuit_breaker` summaries, explicit backend/selector failure tests, and metrics for advisor-routing correctness, conversion by intention, persona-step drop-off, intervention acceptance/dismiss/annoyance, precision/recall, selector drift, backend timeout, and inference latency. Trace validation slice added local/backend-export trace validation, validation CLI, markdown report generation, dataset quality checks, and tests for those gates. Experiment slice added `evaluation/run_experiment.py` plus `scripts/run_evaluation_experiment.sh` to create baseline/rule_based/trainable experiment folders, per-mode manifests, and a baseline-vs-rule report. Latest slice hardened Leonardo execution with `leonardo/env.example`, `leonardo/apptainer.def`, README Apptainer/Singularity notes, and root `scripts/slurm_*.sh` wrappers for browser batches, replay/dataset checks, evaluation experiments, and ranker training. Verified with `bash -n` over run/Slurm scripts, `python3 -m unittest discover -s browser-runner/tests -p 'test_*.py'`, `python3 -m unittest discover -s evaluation/tests -p 'test_*.py'`, `python3 -m unittest discover -s training/tests -p 'test_*.py'`, `python3 -m unittest discover -s replay/tests -p 'test_*.py'`, and experiment CLI smoke. David: live validation will need `EXTENSION_DIST` pointing at the built extension and stable live selectors/render signals; origin/david-branch remains coordination-only. Farhan: dataset builder expects trace events with `derived_context.intervention_kind`, `runner_metadata`, and terminal outcomes; origin/Farhan-Branch still matched the agents-spec commit at 15:35 CEST.

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
