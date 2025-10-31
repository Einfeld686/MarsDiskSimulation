# SiO psat auto-selector + HKL flux checks

## Case highlights
- Case A (tabulated): `psat_model_resolved="tabulated"` because the grain-equilibrium temperature (T_req=1222.6 K) sits inside the 1200–5000 K table span. (A,B)=(13.613, 17850), valid_K_active=[1200, 5000], α=7.0×10⁻³, μ=4.40849×10⁻² kg·mol⁻¹.
- Case B (local-fit): `psat_model_resolved="clausius(local-fit)"`; T_req=989.7 K lies 210 K below the tabulated window, so the IMEX run fitted local Clausius coefficients around the lower edge (metadata captured in `scans/psat_provenance.json`). valid_K_active=[1200, 1500], α, μ identical to Case A.
- Case C (clausius baseline): `psat_model_resolved="clausius(baseline)"` because no table path was supplied. T_req=1397.3 K, (A,B)=(13.613, 17850), valid_K_active=[1270, 1600], α=7.0×10⁻³, μ=4.40849×10⁻² kg·mol⁻¹.

## HKL scan summary (T=1500–6000 K, ΔT=50 K)
- All three cases share finite, non-negative fluxes with strictly monotonic growth (see `scans/hkl_assertions.json`).
- The flux ladder spans 2.7×10⁻⁴–1.14×10⁵ kg·m⁻²·s⁻¹ with no spikes or negative steps; `hkl_scan_case_*.csv` holds the detailed samples.

## Artifacts of interest
- Run configs & summaries: `runs/case_*/run_config.json`, `runs/case_*/summary.json`
- Time-series diagnostics: `runs/case_*/series/run.parquet`
- Mass budget logs: `runs/case_*/checks/mass_budget.csv`
- HKL scan data + assertions: `scans/hkl_scan_case_*.csv`, `scans/hkl_assertions.json`
- Auto-selector provenance digest: `scans/psat_provenance.json`
- pytest log & JUnit XML: `logs/pytest_sio.log`, `logs/pytest_sio.xml`
- Command logs: `logs/run.log`, `logs/make_table.log`, `logs/scan_hkl.log`
