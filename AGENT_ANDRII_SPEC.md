# AGENT_ANDRII_SPEC.md

## Agent

Andrii

## Role

Browser Runner + Personas + Replay + Leonardo Training/Evaluation

## Coordination Rule

Before making changes, read `AGENT_COORDINATION.md`.

When starting work:
- update the Agent-Andrii section in `AGENT_COORDINATION.md`
- write which files you will edit
- write your start time and short plan

When completing work:
- update the Agent-Andrii section in `AGENT_COORDINATION.md`
- write which files you completed
- write your last update time
- add notes for David and Farhan if your work affects them

Do not edit files owned by David or Farhan unless agreed first.

---

# Main Goal

Build the evaluation and training pipeline around real-system traces.

This includes:
- automated browser sessions against the live UNIQA calculator
- personas that act through the real browser
- replay tools
- evaluation metrics
- trace-to-dataset pipeline
- Leonardo batch execution plan
- first action-ranking training workflow after traces exist

The runner should use the real extension and real backend where possible.

---

# Owned Files

Andrii owns:

```text
browser-runner/*
runner/*
personas/*
replay/*
training/*
evaluation/*
leonardo/*
scripts/run_*.sh
scripts/slurm_*.sh
notebooks/*
docs/evaluation/*
docs/training/*
AGENT_COORDINATION.md
```

Andrii should avoid:

```text
extension/*
extension/src/*
extension/tests/*
coach-api/*
backend/*
api/*
server/*
database/*
prisma/*
migrations/*
```

---

# Main Evaluation Modes

The evaluation pipeline must compare three modes:

```text
1. Baseline: no coach intervention
2. Legacy/rule-based coach: backend rule policy
3. Trainable mode: sequence-based action ranker, when available
```

For hackathon demo, at minimum compare:

```text
baseline vs rule-based coach
```

---

# Persona Definitions

Implement persona action policies for:

```text
Franz
Judith
Peter
```

## Franz

Behavior:
```text
online-affine
fast moving
comparison-focused
price sensitive at final price
curious about Opt. Plus/Premium
responds well to transparency, speed, and market comparison
```

Key test cases:
```text
clicks Premium once
navigates back
compares Start vs Optimal
hesitates at final price
```

## Judith

Behavior:
```text
rising hybrid
researches online
needs reassurance
trust-sensitive
may abandon when final price is higher than initial price
responds well to trust signals and transparent explanations
```

Key test cases:
```text
dwells on initial price
hovers cancel at final price
needs price-change explanation
```

## Peter

Behavior:
```text
service-affine
overwhelmed early
low complexity tolerance
needs simple next step
responds best to simplification
```

Key test cases:
```text
pauses early
struggles with choices
needs guidance before price page
```

---

# Persona Intentions

Each persona should support intentions:

```text
purchase
orientation
comparison
price_check
```

These intentions should affect:
- dwell time
- click behavior
- likelihood to continue
- likelihood to abandon
- reaction to intervention

---

# Browser Runner Requirements

Use Playwright or equivalent.

Each session should:

```text
1. Launch Chromium/Chrome with the extension loaded.
2. Open the live UNIQA calculator.
3. Assign persona and intention.
4. Drive real browser actions.
5. Wait for real page transitions.
6. Let the extension detect steps.
7. Let the backend return interventions.
8. Observe rendered coach cards.
9. React to coach cards based on persona policy.
10. End with converted_online, abandoned, or advisor_handoff.
11. Store run metadata and trace reference.
```

---

# Runner Metadata

Every run must include:

```text
runner_id
experiment_id
persona_id
persona_variant_id
intention
seed
extension_build_id
page_map_version
backend_url
model_version_or_policy
site_timestamp
leonardo_job_id
```

---

# Safe Live-Site Rules

Do not overload the real website.

Implement:

```text
low-concurrency validation mode
bulk mode with capped concurrency
randomized think time
circuit breaker on repeated selector failures
circuit breaker on repeated backend failures
circuit breaker on repeated page load failures
```

Never submit a real purchase unless a safe test path is explicitly approved.

---

# Run Modes

## Validation Mode

Purpose:
Check that extension + backend + runner work on the real site.

Settings:

```text
low concurrency
few sessions
screenshots/logs enabled
slow interactions
stop on selector drift
```

## Bulk Evaluation Mode

Purpose:
Generate many traces.

Settings:

```text
bounded concurrency
jittered delays
fixed experiment ID
trace export enabled
automatic failure summary
```

---

# Replay Requirements

Build replay tools that can read stored session traces from backend export or local JSON.

Replay should show:

```text
session timeline
step transitions
events
decision points
candidate actions
chosen intervention
impressions
CTA/dismiss events
terminal outcome
```

Replay should support debugging:

```text
why was this intervention selected?
was it shown successfully?
did the user accept or dismiss it?
what happened after?
```

---

# Metrics

Compute these metrics:

## Funnel Metrics

```text
online conversion rate
advisor handoff count
abandonment rate
S4 initial-price drop-off
S5 add-on drop-off
S7 final-price drop-off
drop-off reduction vs baseline
```

## Persona Metrics

```text
conversion by persona
conversion by intention
drop-off by persona and step
advisor handoff correctness by persona
performance gap between personas
```

## Intervention Metrics

```text
intervention count
intervention volume per session
impression-to-CTA rate
acceptance rate
dismiss rate
annoyance rate
intervention precision
intervention recall
```

## Operational Metrics

```text
extension render success rate
step detection success rate
selector drift rate
backend timeout rate
inference latency
trace completeness rate
```

---

# Dataset Building

Build training examples from real decision points.

Each training example should include:

```text
session_id
decision_id
trace_prefix
current_step_id
page_map_version
extension_version
model_version_or_baseline
candidate_set
guardrail_filtered_candidates
chosen_candidate
exposure_result
future_outcome_summary
runner_metadata
dataset_phase
```

Do not train on old simulator traces as the main source of evidence.

Synthetic traces may be used only for unit tests or rare edge cases.

---

# Model Training Path

Only start trainable model work after traces exist.

## Stage 1: Behavioral Imitation Bootstrap

Train on traces from:
```text
rule-based coach
curated exploratory policies
```

Goal:
```text
reproduce stable baseline behavior
validate trace-to-dataset pipeline
```

## Stage 2: Outcome-Aware Ranking

Add auxiliary labels:
```text
accepted_or_not
converted_later_or_not
annoyed_or_not
```

Goal:
```text
rank actions based on likely value, not only imitation
```

## Stage 3: Exploration-Informed Ranking

Use controlled exploration traces.

Goal:
```text
escape rule-policy bias
improve action ranking from real evidence
```

---

# Leonardo Execution

Prepare files for Leonardo execution.

Expected tools:

```text
SSH login nodes
Slurm jobs
Pixi for reproducible environment
Singularity/Apptainer for container compatibility
```

Create or document:

```text
Pixi environment
Slurm batch script for browser runs
Slurm batch script for replay/feature extraction
Slurm batch script for training
run instructions
environment variables
output directory conventions
```

---

# Suggested Folder Outputs

Create or maintain:

```text
browser-runner/
  run_session.py
  run_batch.py
  persona_policy.py
  playwright_config.py

personas/
  franz.json
  judith.json
  peter.json
  variants.json

replay/
  replay_session.py
  render_timeline.py

evaluation/
  metrics.py
  compare_modes.py
  reports.py

training/
  build_dataset.py
  train_ranker.py
  evaluate_ranker.py

leonardo/
  README.md
  pixi.toml
  slurm_browser_batch.sh
  slurm_replay.sh
  slurm_train.sh
```

---

# Tests

Add tests for:

```text
persona policy produces valid browser actions
runner can start one session in mock mode
runner handles backend timeout
runner handles missing selector
outcome classification works
metrics compute conversion correctly
advisor handoff does not count as conversion
replay loads a trace
dataset builder creates decision examples
```

---

# Deliverables

Andrii should deliver:

```text
1. Browser runner design and implementation
2. Persona action policies
3. Validation-mode run script
4. Bulk-evaluation run script
5. Replay tool
6. Metrics computation
7. Trace-to-dataset builder
8. Leonardo execution plan/scripts
9. Training workflow skeleton
10. Notes in AGENT_COORDINATION.md
```

---

# Acceptance Criteria

Andrii's work is complete when:

```text
one persona can run through a browser session
runner can load the extension
runner can talk to backend
run metadata is recorded
baseline vs coach mode can be compared
metrics report is generated
replay can inspect a stored trace
Leonardo scripts are documented or prepared
```

---

# Handoff From David Needed

Andrii needs:

```text
extension build path
how to load extension in Playwright
stable step IDs
known selector failures
page-map version
manual smoke test notes
```

---

# Handoff From Farhan Needed

Andrii needs:

```text
backend base URL
event/inference/outcome API contract
session replay endpoint
trace export format
model/policy version fields
metrics fields available
```

---

# Do Not Do

Do not:
- modify extension internals
- modify backend database migrations
- make old state-machine simulation the primary evidence
- run high-concurrency traffic without validation mode
- train a model before schema and traces are stable
- count advisor handoff as online conversion
```

---

# Final Success Statement

Andrii's work proves the system works. The runner generates real-site traces, replay explains behavior, metrics quantify conversion uplift, and the training pipeline turns those traces into future trainable coach models.
