# UNIQA Conversion Coach

Simulation-based prototype for the UNIQA AI-Guided Conversion Flow track.

The project focuses on the measured hackathon scope:

- In scope: private-doctor path, "myself only", Start and Optimal tariffs.
- Out of scope: hospital/Sonderklasse, "other persons", Opt. Plus, Premium.
- Conversion metric: online purchase completion of Start or Optimal only.
- Advisor routing: valid clean exit for out-of-scope paths, not a conversion.

## What Is Included

- `coach_sim/`: reproducible state-machine simulator, persona bots, detection
  rules, coach decision policy, metrics, batch runner, and scripted demo.
- `streamlit_app/`: interactive dashboard for side-by-side journeys, batch
  results, persona profiles, scope, and case-material review.
- `case_materials/`: hackathon reference files used to ground the prototype.

## Run The Backend Simulation

```powershell
python -m coach_sim.run_sim --runs 500 --out coach_sim/results
python -m coach_sim.demo
```

The batch runner writes:

- `coach_sim/results/baseline.csv`
- `coach_sim/results/coach.csv`
- `coach_sim/results/report.md`

## Run The UI

```powershell
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Open the Streamlit URL, usually:

```text
http://localhost:8501
```

The UI works without an LLM key using the local rule-based persona simulator.
To enable LLM-backed personas, set `FEATHERLESS_API_KEY` in `.env`.

## Requirement Fit

This version is built for the recommended hackathon path:

- Option 1: state-machine simulation with log output.
- Option 2: Streamlit dashboard on top of the simulation backend.
- Three A/B policies: `minimal`, `balanced`, `aggressive`.
- Weighted evaluation using the brief's estimated funnel mix: Franz 50%,
  Judith 30%, Peter 20%.
- Intervention quality metrics: accepted suggestions as trigger precision,
  ignored suggestions as annoyance rate.
- Traceable logic: the Coach is deterministic Python; LLM-backed personas are
  optional and do not replace the detection/decision layer.

## Current Verified Result

Latest local run writes the full report to `coach_sim/results/report.md`.
The report includes weighted headline metrics, per-persona conversion,
critical-step drop-off reduction, requirement coverage, and a qualitative
before/after demo pointer.

These results are synthetic and reproducible from seeded persona simulations;
present them as prototype validation, not a production forecast.
