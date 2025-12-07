# Sublimation Sink Call Graph (0D)
<!-- sink_token_sync: `sinks.mode=sublimation` `sinks.mode=none` `sinks.mode="none"` `sinks.sub_params` `mass_lost_by_sinks=0` `mass_lost_by_sinks` `sink_flux_surface` `SinkOptions` `SinkOptions(enable_sublimation: bool = False, sub_params: SublimationParams = SublimationParams(), enable_gas_drag: bool = False, rho_g: float = 0.0)` `SinkTimescaleResult(t_sink=None, ...)` `SublimationParams(**cfg.sinks.sub_params.model_dump())` `SurfaceStepResult(sigma_surf: float, outflux: float, sink_flux: float)` `[marsdisk/physics/sinks.py#SinkOptions [L35–L45]]` `[marsdisk/physics/sinks.py#gas_drag_timescale [L70–L80]]` `[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]` `[marsdisk/physics/sinks.py:83–160]` `adds the sink term only when` `integrates sublimation/drag sinks;` `loss += 1/t_sink` `sink_flux` `sink_flux = sigma_new / t_sink` `surface.step_surface(..., t_sink=t_sink_current, ...)` `step_surface(..., tau: float | None = None, t_sink: float | None = None, sigma_tau1: float | None = None) -> SurfaceStepResult` `step_surface_density_S1(..., t_sink: float | None = None, ...) -> SurfaceStepResult` `t_sink` `t_sink=None` `total_sink_timescale` `total_sink_timescale(T: float, rho_p: float, Omega: float, opts: SinkOptions, *, s_ref: float = 1e-6) -> SinkTimescaleResult` `が 0 を返し、タイムスケールは登録されず “no active sinks” ログとともに` `と SurfaceStepResult(sigma_surf: float, outflux: float, sink_flux: float) に対応し、` `を計算し、sinks.mode に応じて昇華/drag を integrates（sinks.mode=none なら adds the sink term only when に該当せず no active sinks で t_sink=None -> 0 を返す）。主要関数は` `を算出する（[marsdisk/physics/sinks.py:83–160], [marsdisk/run.py:1447–1463]）。` -->
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。

## Key Interfaces

- `[marsdisk/physics/sublimation.py:54–120]` `SublimationParams(...)` と HKL パラメータ群。`run_zero_d` は YAML `sinks.sub_params` から `SublimationParams(**cfg.sinks.sub_params.model_dump())` を構築する。
- `[marsdisk/physics/sinks.py:83–160]` `SinkOptions` と `total_sink_timescale`。`sinks.mode="none"` では `SinkTimescaleResult(t_sink=None, ...)` を返し、昇華/drag スイッチが立つと最短寿命を計算する。
- `[marsdisk/physics/surface.py:81–95]` `SurfaceStepResult` / `step_surface_density_S1`。`t_sink` が有限のときのみ `loss += 1/t_sink` と `sink_flux = sigma_new / t_sink` を適用する。
- `[marsdisk/physics/surface.py:190–219]` `step_surface`。Wyatt 衝突寿命を挿入してから `step_surface_density_S1` へ委譲するラッパー。
- `[marsdisk/run.py:1447–1463]` 0D 本体での `t_sink` 解決と “no active sinks” 分岐。
- `[marsdisk/run.py:1654–1683]` `surface.step_surface(..., t_sink=t_sink_current, ...)` を呼び出し、`sink_flux_surface` を積分するループ。

## I/O とトグルの対応
- `sinks.mode=none` → `total_sink_timescale` を呼ばず `t_sink=None` を強制し、`mass_lost_by_sinks` は終始 0。[marsdisk/run.py:1447–1455][marsdisk/run.py:2120–2185]
- `sinks.mode=sublimation` → HKL 由来の `t_sink` が有効化され、`sink_flux_surface` と `mass_lost_by_sinks` が増分を持つ。[marsdisk/physics/sublimation.py:54–120][marsdisk/physics/sinks.py:83–160][marsdisk/run.py:1456–1463][marsdisk/run.py:1654–1683][marsdisk/run.py:2120–2185]

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
    step_surface -->|Strubbe–Chiang 衝突後に委譲| step_surface_density
    total_sink_timescale -->|返値 t_sink / None| step_surface
    total_sink_timescale -->|HK ルート (蒸発率)| mass_flux_hkl
    mass_flux_hkl -->|即時蒸発サイズ s_sink| s_sink_from_timescale
    s_sink_from_timescale -->|τ_sink を再構成| total_sink_timescale
    step_surface -->|outflux / sink_flux を返却| run_zero_d
```
<!-- AUTOGEN:CALLGRAPH END -->

## HK Boundary → `ds/dt` diagnostics

1. `fragments.s_sub_boundary` は灰色体温度と `s_sink_from_timescale` を用いた HKL 境界を計算するが、床粒径の決定には使わない（診断用のみ）。[marsdisk/physics/fragments.py:142–164]
2. Runtimeでは `psd.apply_uniform_size_drift` が `ds/dt` を PSD バケットへ反映し、欠損を `mass_lost_sublimation_step` と `dSigma_dt_sublimation` に出力しつつ床粒径は `max(s_min_cfg, a_blow)` を維持する。[marsdisk/physics/psd.py:149–264]
3. `compute_s_min_F2` は現在ブローアウトサイズのみ返し、警告を発する互換用ヘルパー。[marsdisk/physics/fragments.py:167–198]

## 0D Loop Call Order (t<sub>sink</sub> Propagation)

1. **Initialise radiation and PSD** – `run_zero_d` 解法の冒頭で温度・⟨Q_pr⟩・`a_blow` を決定し PSD を構築。[marsdisk/run.py:850–1100]
2. **Set the PSD floor** – 各ステップで `s_min_effective = max(cfg.sizes.s_min, a_blow, s_min_floor_dynamic)` を更新し、床情報を `s_min_components` に記録。[marsdisk/run.py:1340–1434]
3. **Instantiate sink physics** – YAML `sinks` を `SinkOptions` へ束ね、昇華/drag の有効・無効を反映。[marsdisk/physics/sinks.py:83–160][marsdisk/run.py:1447–1463]
4. **Evaluate `t_sink`** – `sinks.mode="none"` では `t_sink=None` を強制し、そうでなければ `total_sink_timescale` で最短寿命を取得。[marsdisk/run.py:1447–1463]
5. **Advance the surface layer** – `surface.step_surface(..., t_sink=t_sink_current, ...)` で IMEX ステップを進め、`sink_flux_surface` を積分。[marsdisk/physics/surface.py:81–95][marsdisk/physics/surface.py:190–219][marsdisk/run.py:1654–1683]
6. **Accumulate diagnostics** – `mass_lost_by_sinks` と `M_sink_cum` は `sink_flux_surface` が有限だったステップのみ増える。[marsdisk/run.py:2120–2185]

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

- **Time-series parquet** – 各ステップのフラックスと β/床診断を記録。`mass_lost_by_sinks` は `sink_flux_surface` の累積で、`mass_lost_sublimation_step` は HKL 由来の部分だけを抜き出す。[marsdisk/run.py:1654–1683][marsdisk/run.py:2120–2185][marsdisk/physics/psd.py:149–264][marsdisk/io/writer.py:24–162]
- 追加で `dt_over_t_blow`（`Δt / t_{\rm blow}`，無次元）と `fast_blowout_factor`（`1 - \exp(-Δt / t_{\rm blow})`，無次元）が出力され、時間ステップがブローアウト頻度に対して十分細かいか、および補正が適用されたかを判定できる。`case_status \neq "blowout"` の行では `fast_blowout_factor` と旧互換カラム `fast_blowout_ratio` が 0.0 に設定される点に注意する。`fast_blowout_flag_gt3` / `fast_blowout_flag_gt10` は `dt/t_{\rm blow}` が 3 / 10 を超える場合に `true` になり、`fast_blowout_corrected` は補正が実際に乗算されたステップのみ `true` になる。既定では `io.correct_fast_blowout=false` のため補正は適用されず、列は診断目的で保持される（`[marsdisk/run.py#run_zero_d [L426–L1362]]`, `[marsdisk/io/writer.py#write_parquet [L24–L162]]`）。
- **Summary JSON** – 累積損失、β診断、`s_min_components`、温度ソースなどを集計。[marsdisk/run.py:2270–2387]
- **Mass-budget checks** – `checks/mass_budget.csv` に質量保存ログを逐次書き出し。[marsdisk/run.py:1330–1357][marsdisk/io/writer.py:191–193]
- **Run configuration** – HKL/psat パラメータや β 定数を `run_config.json` に記録。[marsdisk/run.py:1477–1547]

These artefacts document whether the sink term participated, how the effective grain size was chosen, and how the resulting β values compared with the global threshold.
