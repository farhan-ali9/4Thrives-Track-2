# UNIQA Conversion Coach — Simulation Backend

Python implementation of the AI-Guided Conversion Flow track (Option 1
from the brief: state-machine simulation + persona bots + coach logic +
log output).

Scope lock (matches the track brief):
- In scope: private-doctor path, "myself only", Start & Optimal tariffs.
- Out of scope (auto-route to advisor, no coaching): hospital, other
  persons, Opt. Plus, Premium.
- Conversion = online purchase of Start or Optimal.
- Baseline to beat: ~5.6% conversion, with 66% drop at initial price
  (Step 4) and 78% drop at final price (Step 7).

## Layout

```
coach_sim/
  journey.py      # 15-step state machine for the in-scope path
  signals.py      # behavioral signal types emitted per step
  personas.py     # Judith / Franz / Peter persona bots (rule-based,
                  # parameters from personas.json)
  detector.py     # rule-based signal -> event detection
  coach.py        # decision policy: event -> intervention, with
                  # 3 interchangeable variants for A/B testing
  sim.py          # single-journey runner
  run_sim.py      # batch runner: baseline vs coach, all personas
  metrics.py      # conversion / drop-off / annoyance aggregation
  demo.py         # scripted Franz before/after transcript (the brief
                  # example) for live demo
```

## Run

```
python -m coach_sim.run_sim --runs 500 --out coach_sim/results
python -m coach_sim.demo
```

Outputs `baseline.csv`, `coach.csv`, and `report.md` under the chosen
output directory.

## Replacing the rule-based bots with LLM personas

`personas.PersonaBot.decide()` is the only hook to swap. Feed it the
full markdown briefing from `insurance-uniqa/persona_*.md` plus the
current state description and parse `{action, dwell_seconds, signals}`
from the response. Keep seeds identical between baseline and coach runs
for a fair comparison (the runner already does this).