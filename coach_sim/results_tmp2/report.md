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
| baseline |   3.6% | - |  15.4% |  81.0% | - | - |
| coach:minimal |  12.9% | +9.3 pp |  15.4% |  71.8% |  50.8% |  49.2% |
| coach:balanced |  13.0% | +9.5 pp |  15.4% |  71.6% |  58.8% |  41.2% |
| coach:aggressive |  15.3% | +11.8 pp |  15.6% |  69.0% |  59.7% |  40.3% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   3.4% |   9.2% |   9.6% |  12.2% |
| judith |  30.0% |   5.4% |  21.2% |  21.0% |  24.0% |
| peter |  20.0% |   1.2% |   9.6% |   9.6% |  10.2% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  70.6% |  47.6% |  47.4% |  44.1% |
| s5_add_ons | 24% |  26.0% |  22.7% |  21.7% |  16.2% |
| s7_final_price | 78% |  77.9% |  56.8% |  57.4% |  56.4% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   3.3% |  20.1% |  76.6% | - | - | - |
| coach:minimal |  13.3% |  20.1% |  66.6% | 1184/642 |  54.2% |  45.8% |
| coach:balanced |  13.4% |  20.1% |  66.5% | 1655/1017 |  61.5% |  38.5% |
| coach:aggressive |  15.5% |  20.4% |  64.1% | 2899/1810 |  62.4% |  37.6% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
