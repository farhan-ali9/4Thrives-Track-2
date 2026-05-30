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
| baseline |   4.8% | - |   7.1% |  88.1% | - | - |
| coach:minimal |  13.4% | +8.6 pp |   7.1% |  79.5% |  53.5% |  46.5% |
| coach:balanced |  14.2% | +9.5 pp |   7.1% |  78.7% |  58.3% |  41.7% |
| coach:aggressive |  16.3% | +11.5 pp |   7.3% |  76.4% |  57.9% |  42.1% |

## Per-persona conversion

| Persona | Funnel share | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| franz |  50.0% |   4.7% |   9.7% |  10.1% |  12.0% |
| judith |  30.0% |   5.8% |  19.9% |  22.2% |  26.5% |
| peter |  20.0% |   3.5% |  12.8% |  12.7% |  11.7% |

## Critical-step drop-off - weighted view

| Step | Brief anchor | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|---|
| s4_initial_price | 66% |  66.2% |  49.5% |  49.3% |  46.8% |
| s5_add_ons | 24% |  25.6% |  21.6% |  20.1% |  17.6% |
| s7_final_price | 78% |  77.6% |  61.2% |  60.7% |  59.4% |

## Unweighted diagnostic view

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Trigger precision | Annoyance |
|---|---|---|---|---|---|---|
| baseline |   4.7% |   9.4% |  85.9% | - | - | - |
| coach:minimal |  14.1% |   9.4% |  76.5% | 3083/1745 |  56.6% |  43.4% |
| coach:balanced |  15.0% |   9.4% |  75.6% | 4039/2457 |  60.8% |  39.2% |
| coach:aggressive |  16.7% |   9.6% |  73.7% | 6859/4163 |  60.7% |  39.3% |

## Qualitative before/after demo

Run `python -m coach_sim.demo` for the required side-by-side Franz journey. The baseline run abandons after exploring an advisor-only tariff; the coached run explains the route, selects Optimal, completes the in-scope steps, and converts online.

## Notes

- Real UNIQA anchor: about 5.6% online conversion, 66% Step 4 drop-off, 24% Step 5 drop-off, and 78% Step 7 drop-off.
- The weighted headline uses the brief's online funnel mix: 50% Franz, 30% Judith, 20% Peter. The unweighted view is kept as a debugging fairness check.
- `coach:balanced` is the recommended policy because it improves conversion while keeping intervention volume capped. `coach:aggressive` is intentionally included to show the annoyance-risk tradeoff.
- Advisor-routed runs are correct out-of-scope exits and do not count as conversion successes.
