# UNIQA Conversion Coach

> AI-Guided Conversion Flow — Lumos Hackathon 2026, Insurance AI Track

A real-time intervention coach that watches behavioural signals inside the UNIQA online health-insurance calculator and fires targeted nudges at the exact moment a user is about to abandon — validated across 10,000 journeys on the Leonardo HPC cluster.

**Baseline: 5.6% online conversion → Coach: 21.2% — 3.8× uplift**

---

## Results at a Glance

| Persona | Funnel share | Baseline | Balanced Coach | Uplift |
|---------|-------------|----------|----------------|--------|
| Franz — Online Affine | 50% | 6.2% | 20.8% | +3.4× |
| Judith — Rising Hybrid | 30% | 5.0% | 23.8% | +4.8× |
| Peter — Service Affine | 20% | 5.2% | 18.4% | +3.5× |
| **Weighted average** | 100% | **5.6%** | **21.2%** | **+3.8×** |

Critical step drop-off reduction:

| Step | Baseline | Coach | Reduction |
|------|----------|-------|-----------|
| S4 Initial Price (66% target) | 66.6% | 48.1% | −18.5 pp |
| S5 Add-ons (24% target) | 26.4% | 17.1% | −9.3 pp |
| S7 Final Price (78% target) | 75.2% | 44.8% | **−30.4 pp** |

Validated hypotheses: [HYPOTHESES.md](HYPOTHESES.md) — Full report: [REPORT.md](REPORT.md)

---

## Quickstart

**No API key needed — runs fully locally:**

```bash
git clone https://github.com/farhan-ali9/4Thrives-Track-2.git
cd 4Thrives-Track-2
git checkout Farhan-Branch
pip install -r requirements.txt
pip install -e .
python -m streamlit run streamlit_app/app.py
```

Open **http://localhost:8501**

### With LLM persona bots (optional)

```bash
cp .env.example .env
# Add FEATHERLESS_API_KEY=your_key_here to .env
python -m streamlit run streamlit_app/app.py
```

Get a free key at [featherless.ai](https://featherless.ai). Without a key, the rule-based simulator runs as fallback — the demo never breaks.

---

## What It Does

UNIQA's calculator converts at 5.6% online. Out of 1,000 people who start, only 56 buy. The biggest drops:

- **S4 (Initial Price):** 66% leave when they see EUR 68/month without context
- **S7 (Final Price):** 78% leave when the personalised premium is higher than the estimate

The Coach detects hesitation signals and fires one targeted intervention at the right moment:

```
[S4] Franz sees EUR 68/month — dwells 45s — hovers Cancel
[COACH] Detected: PRICE_FIXATION + CANCEL_INTENT
[COACH] "At EUR 68/month, Optimal is in the lower third of Austrian private-doctor tariffs."
[S4] Franz selects Optimal → continues

[S7] Franz sees EUR 74.82 — 3 hovers on Cancel — 25s inactivity
[COACH] Detected: PRICE_GAP_SHOCK + CANCEL_INTENT
[COACH] "Your final price includes your health profile. Transparent — complete online now."
[S7] Franz confirms → CONVERTED
```

---

## Architecture

```
Behavioural Signals          Detection Layer          Decision Layer
─────────────────            ───────────────          ──────────────
Dwell time              →    LONG_DWELL          →    trust_signal
Price hover             →    PRICE_FIXATION      →    price_reframe
Cancel hover            →    CANCEL_INTENT       →    market_comparison
Back navigation         →    BACK_NAV            →    tariff_route_explainer
Inactivity              →    PRICE_GAP_SHOCK     →    price_gap_transparency
Tariff click OOS        →    OUT_OF_SCOPE_TARIFF →    ADVISOR_ROUTE (no coaching)
Hospital / other path   →    OUT_OF_SCOPE_PATH   →    ADVISOR_ROUTE (no coaching)
```

**Scope boundary strictly enforced:** The Coach only intervenes on the online-purchasable path (Start / Optimal, "myself only"). Hospital, other persons, Opt.Plus, and Premium paths route to advisor — no coaching, not counted as conversion.

---

## Components

| File | What it does |
|------|-------------|
| `coach_sim/signals.py` | 8 raw behavioural signal types |
| `coach_sim/detector.py` | Signals → decision events |
| `coach_sim/coach.py` | Event → intervention (3 policies: minimal / balanced / aggressive) |
| `coach_sim/adaptive_coach.py` | Thompson Sampling — learns best intervention per step×persona |
| `coach_sim/personas.py` | Franz, Judith, Peter — calibrated to UNIQA spec |
| `coach_sim/llm_persona.py` | LLM-backed persona bots via Featherless AI API |
| `coach_sim/abandonment.py` | Classifies why each user stopped + UNIQA product suggestion |
| `coach_sim/run_cluster.py` | Parallel simulation — runs unchanged on Leonardo HPC via SLURM |
| `coach_sim/run_learning.py` | Persistent learning loop — saves `learned_policy.json` |
| `streamlit_app/app.py` | 5-tab demo dashboard |
| `cluster_job.sh` | SLURM script — ran on Leonardo (Job 43143976, ExitCode 0) |

---

## CLI Commands

```bash
# Single batch simulation
python -m coach_sim.run_sim --runs 1000 --policy balanced --out results/

# Self-learning coach (saves learned_policy.json)
python -m coach_sim.run_learning --iterations 10

# Cluster-scale parallel simulation (local)
python -m coach_sim.run_cluster --runs 5000 --workers 8

# Before/after demo for Franz (log output)
python -m coach_sim.demo
```

---

## Leonardo HPC Cluster

The same simulation code runs on the Leonardo HPC cluster (CINECA) via SLURM. Job 43143976 completed successfully (ExitCode 0, runtime 3s for 10,000 journeys across 8 cores).

```bash
ssh a08trc04@login.leonardo.cineca.it
git clone https://github.com/farhan-ali9/4Thrives-Track-2.git
cd 4Thrives-Track-2 && git checkout Farhan-Branch
module load python/3.11 && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
sbatch cluster_job.sh          # account: euhpc_d30_031
squeue -u a08trc04             # monitor
```

Results land in `coach_sim/results/cluster/cluster_raw.csv` and are automatically loaded in the Streamlit Results Dashboard.

---

## Streamlit Dashboard Tabs

| Tab | What you see |
|-----|-------------|
| **Live demo** | Side-by-side baseline vs coached journey — auto-finds seed where baseline abandons and coached converts. Also shows out-of-scope routing demo. |
| **Results dashboard** | Conversion metrics, per-persona breakdown, ROI estimate, sensitivity analysis, abandonment classifier |
| **LLM persona** | Run a journey with an LLM-backed persona bot (requires API key) |
| **Self-learning** | Train Thompson Sampling adaptive coach, view learning curve |
| **Cluster simulation** | Run parallel simulation, train adaptive policy from results |

---

## What's Needed to Run

| Requirement | Needed for |
|------------|------------|
| Python 3.10+ | Everything |
| `pip install -r requirements.txt` | Everything |
| `FEATHERLESS_API_KEY` in `.env` | LLM persona tab only — optional |
| Leonardo SSH access | Re-running cluster job — results already in repo |

No database, no Docker, no Node.js required for the demo.

---

## License

MIT — see [LICENSE](LICENSE)
