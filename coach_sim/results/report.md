# UNIQA Conversion Coach - Simulation Report

Runs per persona: **2000**  
Personas: franz, judith, peter  
Official funnel mix used for weighted headline: **franz 50%, judith 30%, peter 20%**

## Requirement coverage

| Track requirement | How this prototype satisfies it |
|---|---|
| Conversion Coach detection + decision layer | `detector.py` turns dwell time, back navigation, repeated changes, inactivity, price hover, cancel hover, and out-of-scope selections into events; `coach.py` maps those events to interventions. |
| Three runnable personas | `personas.py` implements Judith, Franz, and Peter with segment-specific purchase intent, trust threshold, price sensitivity, OOS curiosity, and dwell behavior. |
| Same persona set and same seeds | Baseline and coached journeys use identical `persona:seed:index` seeds. |
| At least three intervention variants | `minimal`, `balanced`, and `aggressive` are evaluated side by side. |
| Evaluation metrics | Conversion uplift, per-persona conversion, per-step drop-off, advisor exits, trigger precision, and annoyance rate. |
| Scope boundary | Only Start/Optimal online purchase sets `converted=True`; hospital, other persons, Opt. Plus, and Premium are advisor exits, not conversions. |

## Weighted headline - official funnel mix

| Variant | Online conversion | Uplift vs baseline | Advisor-routed OOS | Abandoned | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   5.4% | - |   2.3% |  92.3% | - | - |
| coach:minimal |  18.6% | +13.2 pp |   2.3% |  79.2% |  72.9% |  27.1% |
| coach:balanced |  20.7% | +15.4 pp |   2.3% |  77.0% |  77.1% |  22.9% |
| coach:aggressive |  23.1% | +17.7 pp |   2.4% |  74.6% |  68.6% |  31.4% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   5.0% |  17.4% |  17.2% |  16.5% |
| judith |  30.0% |   6.2% |  22.4% |  26.4% |  32.6% |
| peter |  20.0% |   5.2% |  15.5% |  21.2% |  25.1% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  66.7% |  50.0% |  49.3% |  44.1% |
| s5_add_ons | 24% |  21.9% |  19.4% |  17.2% |  11.9% |
| s7_final_price | 78% |  78.1% |  51.9% |  48.5% |  52.4% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   5.5% |   2.8% |  91.8% | - | - | - |
| coach:minimal |  18.5% |   2.8% |  78.8% | 5197/3870 |  74.5% |  25.5% |
| coach:balanced |  21.6% |   2.8% |  75.6% | 8648/6869 |  79.4% |  20.6% |
| coach:aggressive |  24.7% |   2.9% |  72.4% | 15327/11178 |  72.9% |  27.1% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
