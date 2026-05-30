# UNIQA Conversion Coach — Streamlit Demo

Beautiful interactive UI on top of the `coach_sim` simulation backend.

## Run

```
python -m pip install -r streamlit_app/requirements.txt
copy .env.example .env
streamlit run streamlit_app/app.py
```

Open the URL Streamlit prints (default http://localhost:8501).

## Optional LLM setup

The app runs without an LLM key using the local rule-based persona simulator.
For LLM-backed persona decisions, open `.env` in the project root and set:

```
FEATHERLESS_API_KEY=rc_your_real_key_here
LLM_DEFAULT_MODEL=MihaiPopa-1/Qwen-3-0.6B-Claude-4.7-Opus-Distilled
```

If `.env` is missing or the key is still a placeholder, only the LLM persona
run falls back to local rules; the dashboard and batch simulator still work.

## What it shows

- **Live journey** tab: side-by-side replay of one persona running the
  funnel with vs. without the Coach. Step-by-step animation, intervention
  popups, and final outcome.
- **Batch results** tab: run N journeys per persona for baseline +
  selected coach policy. Conversion cards, per-persona table, per-step
  drop-off chart, intervention/annoyance stats.
- **Personas** tab: profile cards for Judith, Franz, Peter with
  parameters and segment context.
- **Scope** tab: the hard scope boundary from the brief, in-scope vs
  out-of-scope at a glance.

The UI is read-only on top of `coach_sim`; all logic lives in the
Python package and can be swapped for LLM-backed personas later.
