# Sublimation Sink Call Graph (0D)
<!-- sink_token_sync: `sinks.mode=sublimation` `sinks.mode=none` `sinks.mode="none"` `sinks.sub_params` `mass_lost_by_sinks=0` `mass_lost_by_sinks` `M_sink_dot` `sink_flux_surface` `SinkOptions` `SinkOptions(enable_sublimation: bool = False, sub_params: SublimationParams = SublimationParams(), enable_gas_drag: bool = False, rho_g: float = 0.0)` `SinkTimescaleResult(t_sink=None, ...)` `SublimationParams(**cfg.sinks.sub_params.model_dump())` `SurfaceStepResult(sigma_surf: float, outflux: float, sink_flux: float)` `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]` `[marsdisk/physics/sinks.py#gas_drag_timescale [L70–L80]]` `[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]` `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]` `[marsdisk/physics/sinks.py#gas_drag_timescale [L70–L80]]` `[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]` `adds the sink term only when` `integrates sublimation/drag sinks;` `loss += 1/t_sink` `sink_flux` `sink_flux = sigma_new / t_sink` `surface.step_surface(..., t_sink=t_sink_current, ...)` `step_surface(..., tau: float | None = None, t_sink: float | None = None, sigma_tau1: float | None = None) -> SurfaceStepResult` `step_surface_density_S1(..., t_sink: float | None = None, ...) -> SurfaceStepResult` `t_sink` `t_sink=None` `total_sink_timescale` `total_sink_timescale(T: float, rho_p: float, Omega: float, opts: SinkOptions, *, s_ref: float = 1e-6) -> SinkTimescaleResult` `が 0 を返し、タイムスケールは登録されず “no active sinks” ログとともに` `と SurfaceStepResult(sigma_surf: float, outflux: float, sink_flux: float) に対応し、` `を計算し、sinks.mode に応じて昇華/drag を integrates（sinks.mode=none なら adds the sink term only when に該当せず no active sinks で t_sink=None -> 0 を返す）。主要関数は` `を算出する（[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]], [marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]）。` `を算出する（[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]], [marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]）。` -->
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。

## Key Interfaces

<!-- Required anchors for sinks_callgraph_documented check:
     marsdisk/run_zero_d.py#run_zero_d [L242–L4419], marsdisk/physics/surface.py#step_surface [L189–L221],
     marsdisk/physics/sinks.py#total_sink_timescale [L83–L160], marsdisk/physics/sublimation.py#mass_flux_hkl [L606–L662] -->

- [marsdisk/physics/sublimation.py#mass_flux_hkl [L606–L662]] / `[marsdisk/physics/sublimation.py#SublimationParams [L55–L134]]`: `SublimationParams(...)` と HKL パラメータ群。`run_zero_d` は YAML `sinks.sub_params` から `SublimationParams(**cfg.sinks.sub_params.model_dump())` を構築する。
- [marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]] / `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]`: `SinkOptions` と `total_sink_timescale`。`sinks.mode="none"` では `SinkTimescaleResult(t_sink=None, ...)` を返し、昇華・gas drag の有効化時のみ最短寿命を採用する。
- [marsdisk/physics/surface.py#step_surface [L221–L253]] / `[marsdisk/physics/surface.py#SurfaceStepResult [L89–L105]]`: `SurfaceStepResult` / `step_surface_density_S1`。`t_sink` が有限のときのみ `loss += 1/t_sink` と `sink_flux = sigma_new / t_sink` を適用する。
- `[marsdisk/physics/surface.py#step_surface [L221–L253]]` `step_surface`。Wyatt 衝突寿命を挿入してから `step_surface_density_S1` へ委譲するラッパー。
- `[marsdisk/physics/collisions_smol.py#step_collisions_smol_0d [L726–L1133]]` `step_collisions_smol_0d`。Smol 経路で `t_sink` と `ds_dt_val` を受け取り、表層以外でも昇華・追加シンクを適用する。
- `[marsdisk/physics/phase.py#hydro_escape_timescale [L594–L623]]` `hydro_escape_timescale`。蒸気相でのみ有効になる水素逸脱スケールを返し、ブローアウトと同時には作動しない。
- [marsdisk/run_zero_d.py#run_zero_d [L270–L4828]] / `[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]`: 0D 本体での sink オプション解決と "no active sinks" 分岐。
- `[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]` 表層 ODE・Smol 経路で `t_sink` と `ds_dt_val` を配分し、`sink_flux_surface` や水素逸脱の累積を計算するループ。

## I/O とトグルの対応
- `sinks.mode=none` → `total_sink_timescale` を呼ばず `t_sink=None` を強制し、`mass_lost_by_sinks` は終始 0。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
- `sinks.mode=sublimation` → HKL 由来の `t_sink` が有効化され、`sink_flux_surface` と `mass_lost_by_sinks` が増分を持つ。`sublimation_location` が `surface` / `smol` / `both` を切り替え、Smol 経路にも `t_sink` と `ds_dt_val` が伝搬する。[marsdisk/physics/sublimation.py#SublimationParams [L55–L134]][marsdisk/physics/sinks.py#SinkOptions [L35–L45]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/physics/collisions_smol.py#step_collisions_smol_0d [L726–L1133]]
- `sub_params.mass_conserving=true` の場合、昇華 ds/dt は粒径のみを縮小し、blowout サイズを跨いだ分だけをブローアウト損失へ振替える（`M_sink_dot` は 0 を維持）。false で従来どおり昇華シンクとして質量減算。[marsdisk/physics/collisions_smol.py#step_collisions_smol_0d [L726–L1133]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
- `hydro_escape.enable=true` かつ相が vapor のときだけ水素逸脱スケールを使用し、ブローアウトとは排他的に選択される。[marsdisk/physics/phase.py#hydro_escape_timescale [L594–L623]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]

<!-- AUTOGEN:CALLGRAPH START -->
```mermaid
flowchart TD
    run_zero_d["run_zero_d<br/>marsdisk/run.py"]
    total_sink_timescale["total_sink_timescale<br/>marsdisk/physics/sinks.py"]
    mass_flux_hkl["mass_flux_hkl<br/>marsdisk/physics/sublimation.py"]
    s_sink_from_timescale["s_sink_from_timescale<br/>marsdisk/physics/sublimation.py"]
    step_surface["step_surface<br/>marsdisk/physics/surface.py"]
    step_surface_density["step_surface_density_S1<br/>marsdisk/physics/surface.py"]
    smol_step["step_collisions_smol_0d<br/>marsdisk/physics/collisions_smol.py"]
    hydro_escape["hydro_escape_timescale<br/>marsdisk/physics/phase.py"]
    run_zero_d -->|mode='sublimation' で有効化| total_sink_timescale
    run_zero_d -->|vapor 相で選択| hydro_escape
    run_zero_d -->|t_sink / ds_dt を配布| step_surface
    run_zero_d -->|t_sink / ds_dt を配布| smol_step
    step_surface -->|Wyatt 衝突後に委譲| step_surface_density
    total_sink_timescale -->|返値 t_sink / None| step_surface
    total_sink_timescale -->|返値 t_sink / None| smol_step
    hydro_escape -->|vapor 相のみ t_sink| step_surface
    total_sink_timescale -->|HK ルート (蒸発率)| mass_flux_hkl
    mass_flux_hkl -->|即時蒸発サイズ s_sink| s_sink_from_timescale
    s_sink_from_timescale -->|τ_sink を再構成| total_sink_timescale
    step_surface -->|outflux / sink_flux を返却| run_zero_d
    smol_step -->|outflux / sink_flux / mass_error| run_zero_d
```
<!-- AUTOGEN:CALLGRAPH END -->

## HK Boundary → `ds/dt` diagnostics

1. `fragments.s_sub_boundary` は灰色体温度と `s_sink_from_timescale` を用いた HKL 境界を計算するが、床粒径の決定には使わない（診断用のみ）。[marsdisk/physics/fragments.py#s_sub_boundary [L148–L214]]
2. Runtimeでは `psd.apply_uniform_size_drift` が `ds/dt` を PSD バケットへ反映し、欠損を `mass_lost_sublimation_step` と `dSigma_dt_sublimation` に出力しつつ床粒径は `max(s_min_cfg, a_blow)` を維持する。[marsdisk/physics/psd.py#apply_uniform_size_drift [L373–L502]]
3. `compute_s_min_F2` は現在ブローアウトサイズのみ返し、警告を発する互換用ヘルパー。[marsdisk/physics/fragments.py#s_sub_boundary [L148–L214]]

## 0D Loop Call Order (t<sub>sink</sub> Propagation)

1. **Initialise radiation and PSD** – `run_zero_d` 解法の冒頭で温度・⟨Q_pr⟩・`a_blow` を決定し PSD を構築。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
2. **Set the PSD floor** – 各ステップで `s_min_effective = max(cfg.sizes.s_min, a_blow, s_min_floor_dynamic)` を更新し、床情報を `s_min_components` に記録。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
3. **Instantiate sink physics** – YAML `sinks` を `SinkOptions` へ束ね、昇華/drag の有効・無効と `sublimation_location` を反映。[marsdisk/physics/sinks.py#SinkOptions [L35–L45]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
4. **Evaluate `t_sink`** – `sinks.mode="none"` では `t_sink=None` を強制し、そうでなければ `total_sink_timescale` で最短寿命を取得。`hydro_escape` が vapor 相で選択されるとブローアウトと排他的に `t_sink` を置換。[marsdisk/physics/phase.py#hydro_escape_timescale [L594–L623]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
5. **Advance the surface/Smol layers** – `surface.step_surface(..., t_sink=t_sink_current, ...)` で表層 IMEX を進めつつ、`sublimation_location` が `smol`/`both` なら `collisions_smol.step_collisions_smol_0d(..., t_sink=t_sink_current, ds_dt_val=...)` にも同じ `t_sink` を渡す。[marsdisk/physics/surface.py#step_surface [L221–L253]][marsdisk/physics/collisions_smol.py#step_collisions_smol_0d [L726–L1133]][marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
6. **Accumulate diagnostics** – `mass_lost_by_sinks` と `M_sink_cum` は `sink_flux_surface` が有限だったステップのみ増え、`M_hydro_cum` は水素逸脱を選択したステップでのみ加算される。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]

The blow-out and sink channels therefore remain disentangled even when additional sinks are disabled at the schema level.

## YAML → Schema → Runtime Switch Tracking

```
sinks.mode (YAML)
   │
   ▼
schema.Sinks.mode  ([marsdisk/schema.py#Surface [L855–L870]])
   │
   ▼
cfg.sinks.mode in run_zero_d  ([marsdisk/run_zero_d.py#run_zero_d [L270–L4828]])
   ├─ "none"  ──► t_sink = None ──► surface.step_surface_density_S1(t_sink=None)
   └─ "sublimation" ──► total_sink_timescale(...) ──► surface.step_surface_density_S1 / collisions_smol(t_sink>0)
```

Additional flags `enable_sublimation`, `enable_gas_drag`, `rho_g`, and `sublimation_location` follow the same path: YAML (`configs/base.yml`) → `schema.Sinks` validation → `SinkOptions` → `total_sink_timescale` → surface/Smol 配置。Gas drag only engages when both the switch and density are positive ([marsdisk/physics/sinks.py#SinkOptions [L35–L45]]).

## Output Columns and Provenance

- **Time-series parquet** – 各ステップのフラックスと β/床診断を記録。`mass_lost_by_sinks` は `sink_flux_surface` の累積で、`mass_lost_sublimation_step` は HKL 由来の部分だけを抜き出す。Smol ルートでの `mass_loss_rate_sublimation` もここに合算される。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/physics/psd.py#apply_uniform_size_drift [L373–L502]][marsdisk/physics/collisions_smol.py#step_collisions_smol_0d [L726–L1133]][marsdisk/io/writer.py#write_parquet [L24–L369]]
- 追加で `dt_over_t_blow`（`Δt / t_{\rm blow}`，無次元）と `fast_blowout_factor`（`1 - \exp(-Δt / t_{\rm blow})`，無次元）が出力され、時間ステップがブローアウト頻度に対して十分細かいか、および補正が適用されたかを判定できる。`case_status ≠ "blowout"` の行では `fast_blowout_factor` と旧互換カラム `fast_blowout_ratio` が 0.0 に設定される点に注意する。`fast_blowout_flag_gt3` / `fast_blowout_flag_gt10` は `dt/t_{\rm blow}` が 3 / 10 を超える場合に `true` になり、`fast_blowout_corrected` は補正が実際に乗算されたステップのみ `true` になる。既定では `io.correct_fast_blowout=false` のため補正は適用されず、列は診断目的で保持される。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/io/writer.py#write_parquet [L24–L369]]
- **Summary JSON** – 累積損失、β診断、`s_min_components`、温度ソース、`M_hydro_cum` を集計。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]
- **Mass-budget checks** – `checks/mass_budget.csv` に質量保存ログを逐次書き出し。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]][marsdisk/io/writer.py#write_parquet [L24–L369]]
- **Run configuration** – HKL/psat パラメータや β 定数を `run_config.json` に記録。[marsdisk/run_zero_d.py#run_zero_d [L270–L4828]]

These artefacts document whether the sink term participated, how the effective grain size was chosen, and how the resulting β values compared with the global threshold.
