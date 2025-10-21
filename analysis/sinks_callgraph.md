# Sublimation Sink Call Graph (0D)
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。

## Key Interfaces

- `[marsdisk/physics/sublimation.py#PSAT_TABLE_BUFFER_DEFAULT_K [L37]]` `SublimationParams(mode: str = "logistic", psat_model: str = "clausius", alpha_evap: float = 0.007, mu: float = 0.0440849, A: Optional[float] = 13.613, B: Optional[float] = 17850.0, valid_K: Optional[Tuple[float, float]] = (1270.0, 1600.0), psat_table_path: Optional[pathlib.Path] = None, T_sub: float = 1300.0, s_ref: float = 1e-6, eta_instant: float = 0.1, dT: float = 50.0, P_gas: float = 0.0)`  
  Dataclass copied into runtime parameters. `run_zero_d` builds the instance via `SublimationParams(**cfg.sinks.sub_params.model_dump())` (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).

- `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]` `SinkOptions(enable_sublimation: bool = False, sub_params: SublimationParams = SublimationParams(), enable_gas_drag: bool = False, rho_g: float = 0.0)`  
  Bundles YAML switches for sublimation and gas drag before the sink-time calculation.

- `[marsdisk/physics/sinks.py#gas_drag_timescale [L70–L80]]` `gas_drag_timescale(s: float, rho_p: float, rho_g: float, c_s: float = 500.0) -> float`  
  Provides the optional drag contribution used inside `total_sink_timescale`.

- `[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]` `total_sink_timescale(T: float, rho_p: float, Omega: float, opts: SinkOptions, *, s_ref: float = 1e-6) -> SinkTimescaleResult`  
  Evaluates active sinks, returning the minimum lifetime (`logger` message at `[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]` confirms the value). When no sinks are active it returns `None` and skips the sink term.

- `[marsdisk/physics/surface.py#SurfaceStepResult [L77–L93]]` `SurfaceStepResult(sigma_surf: float, outflux: float, sink_flux: float)`  
  Holds the implicit-step output; `sink_flux` is the in-surface sink rate set by `t_sink`.

- `[marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]]` `step_surface_density_S1(..., t_sink: float | None = None, ...) -> SurfaceStepResult`  
  Performs the IMEX step. The sink term enters the combined loss rate (`loss += 1/t_sink`, lines `139–143`) and the returned `sink_flux = sigma_new / t_sink` (line `152`).

- `[marsdisk/physics/surface.py#step_surface [L185–L208]]` `step_surface(..., tau: float | None = None, t_sink: float | None = None, sigma_tau1: float | None = None) -> SurfaceStepResult`  
  Convenience wrapper used in the 0D loop; injects Wyatt collisions before forwarding to `step_surface_density_S1`.

- `[marsdisk/run.py#run_zero_d [L426–L1362]]` `run_zero_d(cfg: Config, *, enforce_mass_budget: bool = False) -> None`  
  Orchestrates the 0D evolution,再評価モード (`numerics.eval_per_step=true`) では各ステップの冒頭で⟨Q_pr⟩・`a_blow` と HKL 侵食を更新し、`total_sink_timescale` の結果を IMEX 表層ステップへ渡す。粒径侵食の反映は `psd.apply_uniform_size_drift` により面密度へ折り込まれる。

<!-- AUTOGEN:CALLGRAPH START -->
```mermaid
flowchart TD
    run_zero_d["run_zero_d<br/>marsdisk/run.py"]
    step_surface["step_surface<br/>marsdisk/physics/surface.py"]
    total_sink_timescale["total_sink_timescale<br/>marsdisk/physics/sinks.py"]
    mass_flux_hkl["mass_flux_hkl<br/>marsdisk/physics/sublimation.py"]
    s_sink_from_timescale["s_sink_from_timescale<br/>marsdisk/physics/sublimation.py"]
    step_surface_density["step_surface_density_S1<br/>marsdisk/physics/surface.py"]
    run_zero_d -->|mode='sublimation' で有効化| total_sink_timescale
    run_zero_d -->|t_sink を渡す (None でシンク無効)| step_surface
    step_surface -->|Wyatt 衝突後に委譲| step_surface_density
    total_sink_timescale -->|返値 t_sink / None| step_surface
    total_sink_timescale -->|HK ルート (蒸発率)| mass_flux_hkl
    mass_flux_hkl -->|即時蒸発サイズ s_sink| s_sink_from_timescale
    s_sink_from_timescale -->|τ_sink を再構成| total_sink_timescale
    step_surface -->|outflux / sink_flux を返却| run_zero_d
```
<!-- AUTOGEN:CALLGRAPH END -->

## HK Boundary → `ds/dt` diagnostics

1. `fragments.s_sub_boundary` (`[marsdisk/physics/fragments.py#s_sub_boundary [L101–L164]]`) still evaluates the Hertz–Knudsen limit by combining the grey-body temperature with `s_sink_from_timescale`. The helper is retained for analyses and potential post-processing hooks but is no longer invoked when choosing the PSD floor inside `run_zero_d`.
2. Runtimeでは `psd.apply_uniform_size_drift` が `ds/dt` を PSD バケットへ直接適用し、質量欠損を `mass_lost_sublimation_step` や `dSigma_dt_sublimation` に反映する一方で床粒径を `\max(s_{\min,\mathrm{cfg}}, s_{\mathrm{blow}})` に固定する（`[marsdisk/physics/psd.py#apply_uniform_size_drift [L149–L264]]`）。任意フラグ `sizes.evolve_min_size=true` を指定すると、従来通り `psd.evolve_min_size` で診断用 `s_min_evolved` を追跡できる。
3. For backward compatibility `compute_s_min_F2` now returns the blow-out size and raises a deprecation warning (`[marsdisk/physics/fragments.py#compute_s_min_F2 [L167–L198]]`), aligning auxiliary utilities with the updated floor definition.

## 0D Loop Call Order (t<sub>sink</sub> Propagation)

1. **Initialise radiation and PSD** – `run_zero_d` resolves the Mars-facing temperature (`T_M_source`) and `radiation.blowout_radius` before constructing the PSD (`[marsdisk/run.py#run_zero_d [L426–L1362]]`). Shielding tables are loaded when configured, yielding `phi_tau_fn` for later use (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).
2. **Set the PSD floor** – `run_zero_d` evaluates `a_blow` eachステップで再評価し `s_min_effective = max(cfg.sizes.s_min, a_blow)` を適用する (`[marsdisk/run.py#run_zero_d [L426–L1362]]`)。この値が `psd.update_psd_state` の床となり、`s_min_components` には `config`,`blowout`,`effective` のみが記録される。
3. **Instantiate sink physics** – `SinkOptions` bundles the YAML switches before the time-scale calculation (`[marsdisk/run.py#run_zero_d [L426–L1362]]`, `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]`).
4. **Evaluate `t_sink`** – `cfg.sinks.mode == "none"` forces `t_sink = None`. Otherwise `sinks.total_sink_timescale(T_M, rho_used, Omega, sink_opts)` を各ステップで呼び出して能動シンクを走査する (`[marsdisk/run.py#run_zero_d [L426–L1362]]`)。HK フラックスがゼロの場合は `s_sink_from_timescale` が 0 を返し、タイムスケールは登録されず “no active sinks” ログとともに `None` が返る (`[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]`)。
5. **Advance the surface layer** – Each step calls `surface.step_surface(..., t_sink=t_sink, ...)` (`[marsdisk/run.py#run_zero_d [L426–L1362]]`). `step_surface_density_S1` adds the sink term only when `t_sink` is finite; passing `None` keeps the IMEX loss operator identical to the blow-out-only case and forces `sink_flux_surface = 0.0` (`[marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]]`).
6. **Accumulate diagnostics** – Outflux and sink-loss tallies convert to Mars masses and flow into both parquet and summary outputs (`[marsdisk/run.py#run_zero_d [L426–L1362]]`). `mass_lost_by_sinks` and the cumulative `M_sink_cum` therefore rise exclusively when `t_sink` was finite in that step.

The blow-out and sink channels therefore remain disentangled even when additional sinks are disabled at the schema level.

## YAML → Schema → Runtime Switch Tracking

```
sinks.mode (YAML)
   │
   ▼
schema.Sinks.mode  ([marsdisk/schema.py#QStar [L202–L204]])
   │
   ▼
cfg.sinks.mode in run_zero_d  ([marsdisk/run.py#run_zero_d [L426–L1362]])
   ├─ "none"  ──► t_sink = None ──► surface.step_surface_density_S1(t_sink=None)
   └─ "sublimation" ──► total_sink_timescale(...) ──► surface.step_surface_density_S1(t_sink>0)
```

Additional flags `enable_sublimation`, `enable_gas_drag`, and `rho_g` follow the same path: YAML (`configs/base.yml`) → `schema.Sinks` validation → `SinkOptions` → `total_sink_timescale`. Gas drag only engages when both the switch and density are positive (`[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]`).

## Output Columns and Provenance

- **Time-series parquet** – each step appends a record with the split diagnostics (`[marsdisk/run.py#run_zero_d [L426–L1362]]`):  
  - `mass_lost_by_blowout` integrates the radiation channel (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).  
  - `mass_lost_by_sinks` integrates sublimation/drag sinks; `mass_lost_sublimation_step` isolates the HKL erosion within that step (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).  
  - `dSigma_dt_sublimation` and `ds_dt_sublimation` capture the applied size-drift diagnostics (`[marsdisk/physics/psd.py#apply_uniform_size_drift [L149–L264]]`).  
  - `beta_at_smin_config` / `beta_at_smin_effective` / `beta_threshold` track the active blow-out regime (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).  
  The DataFrame is written through `writer.write_parquet` (`[marsdisk/run.py#run_zero_d [L426–L1362]]`, `[marsdisk/io/writer.py#write_parquet [L24–L162]]`). `orbit_rollup.csv` summarises orbit-integrated losses when `numerics.orbit_rollup=true`.
- 追加で `dt_over_t_blow`（`Δt / t_{\rm blow}`，無次元）と `fast_blowout_factor`（`1 - \exp(-Δt / t_{\rm blow})`，無次元）が出力され、時間ステップがブローアウト頻度に対して十分細かいか、および補正が適用されたかを判定できる。`case_status \neq "blowout"` の行では `fast_blowout_factor` と旧互換カラム `fast_blowout_ratio` が 0.0 に設定される点に注意する。`fast_blowout_flag_gt3` / `fast_blowout_flag_gt10` は `dt/t_{\rm blow}` が 3 / 10 を超える場合に `true` になり、`fast_blowout_corrected` は補正が実際に乗算されたステップのみ `true` になる。既定では `io.correct_fast_blowout=false` のため補正は適用されず、列は診断目的で保持される（`[marsdisk/run.py#run_zero_d [L426–L1362]]`, `[marsdisk/io/writer.py#write_parquet [L24–L162]]`）。
- **Summary JSON** – `run_zero_d` records the cumulative loss, beta diagnostics, `s_min_components`, and temperature source (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).  
- **Mass-budget checks** – conservation diagnostics accumulate per step and are flushed to `out/checks/mass_budget.csv` via `writer.write_mass_budget` (`[marsdisk/run.py#run_zero_d [L426–L1362]]`, `[marsdisk/run.py#run_zero_d [L426–L1362]]`).  
- **Run configuration** – `out/run_config.json` now embeds a `sublimation_provenance` block summarising the HKL formula, selected `psat_model`, SiO defaults (`alpha_evap`, `mu`, `A`, `B`), ambient pressure, validity window, and any tabulated path alongside the β constants (`[marsdisk/run.py#run_zero_d [L426–L1362]]`).

These artefacts document whether the sink term participated, how the effective grain size was chosen, and how the resulting β values compared with the global threshold.
