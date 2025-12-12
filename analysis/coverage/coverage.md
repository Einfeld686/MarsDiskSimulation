# Coverage Snapshot

Baseline thresholds: function reference rate ≥ 70%, anchor consistency rate = 100%.

| Metric | Value | Target |
| --- | --- | --- |
| Function reference rate | 81.0% (64/79) | ≥ 70% |
| Anchor consistency rate | 100.0% (162/162) | = 100% |
| Equation unit coverage | 94.3% (33/35) | — |
| Sinks callgraph documented | Yes | run→surface→sinks→sublimation |

## Top Coverage Gaps
- marsdisk/physics/psd.py#evolve_min_size [L267–L356]
- marsdisk/physics/qstar.py#compute_q_d_star_array [L56–L79]
- marsdisk/physics/smol.py#number_density_to_psd_state [L91–L143]
