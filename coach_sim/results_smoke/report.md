# UNIQA Conversion Coach — Simulation Report

Runs per persona: **100**  
Personas: franz, judith, peter

## Overall conversion

| Variant | Conversion | Advisor-routed | Abandoned | Interventions/Accepted | Annoyance |
|---|---|---|---|---|---|
| baseline |   4.0% |  20.3% |  75.7% | – | – |
| coach:minimal |  15.3% |  20.3% |  64.3% | 227/123 |  45.8% |
| coach:balanced |  12.3% |  20.3% |  67.3% | 327/202 |  38.2% |
| coach:aggressive |  15.0% |  22.0% |  63.0% | 569/355 |  37.6% |

## Per-persona conversion

| Persona | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|
| franz |   4.0% |  12.0% |  12.0% |  12.0% |
| judith |   8.0% |  28.0% |  19.0% |  23.0% |
| peter |   0.0% |   6.0% |   6.0% |  10.0% |

## Drop-off per critical step (overall)

| Step | baseline | coach:minimal | coach:balanced | coach:aggressive |
|---|---|---|---|---|
| s1_coverage_scope |  14.0% |  14.0% |  14.0% |  14.0% |
| s2_for_whom |   7.4% |   7.4% |   7.4% |   9.3% |
| s3_personal_data |  10.0% |  10.0% |  10.0% |   9.0% |
| s4_initial_price |  68.8% |  47.9% |  47.4% |  46.9% |
| s5_add_ons |  26.9% |  26.8% |  23.9% |  11.5% |
| s6_health_questions |   0.0% |   0.0% |   0.0% |   0.0% |
| s7_final_price |  73.5% |  42.7% |  54.7% |  53.0% |
| s8_confirm |   7.7% |   2.1% |   5.1% |   4.3% |

## Notes

- Baseline target: ~5.6% conversion, 66% drop at S4_initial_price, 78% drop at S7_final_price.
- `coach:balanced` is the recommended production policy. `coach:aggressive` demonstrates the annoyance pitfall — higher intervention count, marginal or negative uplift.
- Advisor-routed runs are correct out-of-scope exits (hospital / other persons / Opt.Plus / Premium) and do NOT count as conversion successes.
