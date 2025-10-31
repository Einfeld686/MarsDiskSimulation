# RC Suite Summary

## Step Status
- rc_scan_ast.py: OK
- rc_scan_docs.py: OK
- rc_compare.py: OK
- rc_root_cause_probe.py: OK
- rc_anchor_suggestions.py: OK

## Coverage
- Function reference rate: 43.3% (26/60)
- Top gaps:
  - `marsdisk/io/tables.py`:287 `load_phi_table`
  - `marsdisk/io/writer.py`:109 `write_summary`
  - `marsdisk/io/writer.py`:120 `write_run_config`
  - `marsdisk/io/writer.py`:128 `write_mass_budget`
  - `marsdisk/physics/collide.py`:18 `compute_collision_kernel_C1`

## Artefacts
- reports/ast_symbols.json
- reports/doc_refs.json
- reports/coverage.json
- reports/coverage_report.md
- reports/root_cause_probe.md
- reports/suggestions_index.json
- reports/summary.md

Generated suggestions reside under `suggestions/`.