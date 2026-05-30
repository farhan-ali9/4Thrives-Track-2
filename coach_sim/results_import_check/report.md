# UNIQA Conversion Coach - Simulation Report

Runs per persona: **50**  
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
| baseline |   8.4% | - |   2.2% |  90.0% | - | - |
| coach:minimal |  17.8% | +9.4 pp |   2.2% |  80.0% |  52.0% |  48.0% |
| coach:balanced |  16.6% | +8.2 pp |   2.2% |  82.0% |  58.2% |  41.8% |
| coach:aggressive |  17.8% | +9.4 pp |   2.6% |  80.0% |  55.4% |  44.6% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   8.0% |  14.0% |  14.0% |  20.0% |
| judith |  30.0% |  12.0% |  20.0% |  16.0% |  18.0% |
| peter |  20.0% |   4.0% |  24.0% |  24.0% |  12.0% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  67.0% |  56.5% |  55.8% |  54.1% |
| s5_add_ons | 24% |  26.9% |  27.1% |  25.6% |   9.8% |
| s7_final_price | 78% |  65.0% |  42.4% |  46.8% |  55.8% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   8.0% |   2.7% |  89.3% | - | - | - |
| coach:minimal |  19.3% |   2.7% |  78.0% | 171/97 |  56.7% |  43.3% |
| coach:balanced |  18.0% |   2.7% |  79.3% | 225/139 |  61.8% |  38.2% |
| coach:aggressive |  16.7% |   3.3% |  80.0% | 366/212 |  57.9% |  42.1% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
