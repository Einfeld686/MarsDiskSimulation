# フェーズ5 事前リサーチメモ

フェーズ5では「昇華のみ / 衝突のみ」を選択的に実行し、2本のサブランを同一初期条件から分岐させて比較出力する。既存コードのフック位置と安全に切り替えるための要点を以下に整理する。

## 1. 切替点（single process hooks）
- ラン全体のモード決定は `run_zero_d` 冒頭で `process.primary` と `modes.single_process` を突き合わせて `primary_process`, `enforce_sublimation_only`, `enforce_collisions_only`, `collisions_active` を確定している。[marsdisk/run.py:441–508]
- 昇華の `ds/dt` と PSD 床の更新は `ds_dt_val`、`psd.apply_uniform_size_drift`、`s_min_floor_dynamic` の計算経路に集約されており、`sublimation_active` フラグで完全に分岐できる。[marsdisk/run.py:918–1016][marsdisk/physics/psd.py:30–220]
- 追加シンクは `sink_opts = SinkOptions(...)` → `sinks.total_sink_timescale` → `surface.step_surface(..., t_sink=...)` という流れで計算され、`sink_opts.enable_sublimation` をFalseにすると昇華源の `components["sublimation"]` が `None` になる。[marsdisk/run.py:872–1047][marsdisk/physics/sinks.py:34–160]
- 衝突寄与は `collisions_active` で包まれ、`surface.step_surface` の呼び出しを完全にスキップできる。Wyatt 型 `t_coll` は `surface.step_surface(..., tau=tau_for_coll)` が `tau` を `surface.wyatt_tcoll_S1` に渡す仕組みなので、ここをバイパスすれば Σ_surf も更新されない。[marsdisk/run.py:1184–1336][marsdisk/physics/surface.py:1–217]
- ブローアウトや速い補正（`_fast_blowout_correction_factor`）も `collisions_active` と `enable_blowout_step` の論理にぶら下がっているため、衝突を止めれば自動的に無効化できる。[marsdisk/run.py:1072–1360]

## 2. s_min と初期条件の共有
- 初期 PSD の決定は `psd.update_psd_state` → `psd.compute_kappa` → `initfields.surf_sigma_init` の順で行われ、`psd_state`/`sigma_surf_reference` が run 内の唯一の真値になる。`rng_seed` も `_resolve_seed` で決定しており、`np.random.default_rng(seed)` が使い回されるので、初期オブジェクトをディープコピーすれば決定論的に再利用できる。[marsdisk/run.py:652–807][marsdisk/run.py:509–520]
- `psd_state["s_min"]` や `s_min_components` が in-place で更新される点に注意。比較ランナーではコピーを取ってから各サブランに渡し、終了後は破壊して構わない。

## 3. 時間グリッドと2年スパン・比較モード
- 時間積分区間は `_resolve_time_grid` が直列で決定しており、`numerics.t_end_years`／`t_end_orbits` のいずれかが必須。`scope.analysis_years` がセットされると `cfg.numerics.t_end_years` が未設定時にデフォルト値（2年）が書き戻される。[marsdisk/run.py:223–312][marsdisk/run.py:461–499]
- 比較モードで2年スパンを強制したい場合は、サブラン用 `Config` を複製→`cfg.numerics.t_end_years = duration_years` で上書きすれば `_resolve_time_grid` が一貫した `dt`/`n_steps` を返す。
- 比較設定は `phase5.compare.mode_a/mode_b` と `label_a/label_b` を持ち、 `_prepare_phase5_variants` で正規化した2本のモード（昇華のみ・衝突のみなど）を同一初期条件から実行する。[marsdisk/run.py:205–248][marsdisk/run.py:2232–2406]

## 4. 出力とメタデータの拡張点
- タイムシリーズは `records` を `writer.write_parquet(.../series/run.parquet)` に流し込むだけであり、列を追加するには `record` 辞書へ `variant` 等を差し込むだけで済む。PSDhisto/diagnostics も同じ構造で列追加が可能。[marsdisk/run.py:1508–1643][marsdisk/io/writer.py:24–220]
- 集計は `summary` 辞書（`M_loss` など）と `run_config` JSON で保持されているので、`phase5.compare` や `variant` をそのままぶら下げれば互換を壊さない。[marsdisk/run.py:1678–1874]
- `mass_budget` は `budget_entry` を `writer.write_mass_budget(.../checks/mass_budget.csv)` へ送るだけなので、比較ランの row メタを付与する余地がある。[marsdisk/run.py:1640–1765]

## 5. 放射源・太陽無効化の確認
- `radiation_field` は `radiation.source`／`use_mars_rp`／`use_solar_rp` の組で決まり、太陽放射圧が要求されても gas-poor campagne では `logger.info` を吐いて無効化している。`rp_blowout_enabled` も `mars_rp_enabled_cfg` に掛かる。[marsdisk/run.py:466–520][marsdisk/run.py:666–720]

## 6. 検証・質量保存ログ
- `mass_budget` には `mass_initial`, `mass_remaining`, `mass_lost`, `mass_diff`, `error_percent`（許容 0.5%）が蓄積され、超過時は `MassBudgetViolationError` を投げる。ゼロ寄与（例: 昇華量0）もここで確認できる。比較結果が2行出力される `orbit_rollup.csv` も `writer.write_orbit_rollup` が担当。[marsdisk/run.py:1608–1778][marsdisk/run.py:1360–1435]

## 7. リスク/考慮点
- `collisions_active` が False でも `sink_opts.enable_sublimation` が True だと Σ_surf 更新はスキップされるが `mass_budget` は 0 のまま。単一モードで「無効側がゼロ寄与」を検証する場合は `M_loss_cum` / `M_sink_cum` の蓄積ロジックにも variant 情報を差し込む必要がある。[marsdisk/run.py:1287–1342]
- 初期 `Config` をコピーする際、`pydantic` モデルは `copy(deep=True)` を使わないと `Path` などが共有されてしまう。比較ラン実装では pydantic の `model_copy`（v1: `.copy(deep=True)`）を使うこと。
