# UNIQA Conversion Coach - Simulation Report

Runs per persona: **500**  
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
| baseline |   5.6% | - |   2.5% |  91.8% | - | - |
| coach:minimal |  18.3% | +12.6 pp |   2.5% |  79.2% |  78.0% |  22.0% |
| coach:balanced |  21.2% | +15.6 pp |   2.5% |  76.2% |  81.0% |  19.0% |
| coach:aggressive |  22.4% | +16.8 pp |   2.7% |  75.0% |  73.6% |  26.4% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   6.2% |  21.0% |  20.8% |  19.4% |
| judith |  30.0% |   5.0% |  16.4% |  23.8% |  27.2% |
| peter |  20.0% |   5.2% |  14.2% |  18.4% |  22.8% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  66.6% |  48.7% |  48.1% |  40.7% |
| s5_add_ons | 24% |  26.4% |  22.4% |  17.1% |  11.0% |
| s7_final_price | 78% |  75.2% |  49.3% |  44.8% |  53.2% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   5.5% |   3.1% |  91.4% | - | - | - |
| coach:minimal |  17.2% |   3.1% |  79.7% | 1253/966 |  77.1% |  22.9% |
| coach:balanced |  21.0% |   3.1% |  75.9% | 2206/1806 |  81.9% |  18.1% |
| coach:aggressive |  23.1% |   3.3% |  73.5% | 3840/2925 |  76.2% |  23.8% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
