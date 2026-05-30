# UNIQA Conversion Coach — Simulation Report

Runs per persona: **200**  
Personas: franz, judith, peter

## Overall conversion

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Annoyance |
|---|---|---|---|---|---|
| baseline |   3.3% |  20.5% |  76.2% | – | – |
| coach:minimal |  35.7% |  20.5% |  43.8% | 542/295 |  45.6% |
| coach:balanced |  40.2% |  20.5% |  39.3% | 817/504 |  38.3% |
| coach:aggressive |  38.8% |  20.7% |  40.5% | 1280/772 |  39.7% |

## Per-persona conversion

| Persona | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|
| franz |   4.0% |  27.5% |  28.5% |  38.0% |
| judith |   5.0% |  51.0% |  62.5% |  55.0% |
| peter |   1.0% |  28.5% |  29.5% |  23.5% |

## Drop-off per critical step (overall)

| Step | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|
| s1_coverage_scope |  13.0% |  13.0% |  13.0% |  13.0% |
| s2_for_whom |   8.6% |   8.6% |   8.6% |   8.8% |
| s3_personal_data |  11.1% |   8.6% |   4.4% |   3.6% |
| s4_initial_price |  69.3% |  26.4% |  26.1% |  21.4% |
| s5_add_ons |  24.6% |  13.7% |   8.0% |   8.3% |
| s6_health_questions |   0.0% |   0.0% |   0.0% |   0.0% |
| s7_final_price |  77.6% |  20.6% |  21.3% |  27.5% |
| s8_confirm |   9.1% |   2.7% |   1.2% |   2.9% |

## Notes

- Baseline target: ~5.6% conversion, 66% drop at S4_initial_price, 78% drop at S7_final_price.
- `coach:balanced` is the recommended production policy. `coach:aggressive` demonstrates the annoyance pitfall — higher intervention count, marginal or negative uplift.
- Advisor-routed runs are correct out-of-scope exits (hospital / other persons / Opt.Plus / Premium) and do NOT count as conversion successes.
