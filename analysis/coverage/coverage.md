# Coverage Snapshot

Baseline thresholds: function reference rate ≥ 70%, anchor consistency rate = 100%.

| Metric | Value | Target |
| --- | --- | --- |
| Function reference rate | 73.8% (48/65) | ≥ 70% |
| Anchor consistency rate | 100.0% (151/151) | = 100% |
| Equation unit coverage | 15.4% (4/26) | — |
| Sinks callgraph documented | No | run→surface→sinks→sublimation |

## Top Coverage Gaps
- marsdisk/analysis/beta_sampler.py#sample_beta_over_orbit [L217–L331]
- marsdisk/analysis/massloss_sampler.py#sample_mass_loss_one_orbit [L114–L263]
- marsdisk/io/tables.py#get_qpr_table_path [L356–L359]
