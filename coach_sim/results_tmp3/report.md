# UNIQA Conversion Coach - Simulation Report

Runs per persona: **1000**  
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
| baseline |   4.7% | - |   7.1% |  88.2% | - | - |
| coach:minimal |  12.9% | +8.2 pp |   7.1% |  80.0% |  53.3% |  46.7% |
| coach:balanced |  13.7% | +9.0 pp |   7.1% |  79.2% |  58.2% |  41.8% |
| coach:aggressive |  15.9% | +11.3 pp |   7.3% |  76.8% |  57.9% |  42.1% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   4.7% |   9.4% |   9.5% |  11.8% |
| judith |  30.0% |   5.4% |  19.1% |  21.6% |  25.8% |
| peter |  20.0% |   3.5% |  12.3% |  12.2% |  11.4% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  66.0% |  49.3% |  49.1% |  46.4% |
| s5_add_ons | 24% |  25.5% |  21.5% |  20.1% |  17.8% |
| s7_final_price | 78% |  77.6% |  61.3% |  60.7% |  59.3% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   4.5% |   9.4% |  86.1% | - | - | - |
| coach:minimal |  13.6% |   9.4% |  77.0% | 3032/1711 |  56.4% |  43.6% |
| coach:balanced |  14.4% |   9.4% |  76.2% | 3991/2424 |  60.7% |  39.3% |
| coach:aggressive |  16.3% |   9.6% |  74.1% | 6784/4116 |  60.7% |  39.3% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
