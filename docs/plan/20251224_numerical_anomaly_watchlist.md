# 数値異常リスクの洗い出しと検証案

**作成日**: 2025-12-24  
**ステータス**: 実装・検証済み（追加テスト設計中 / Windows 再現テスト待ち）  
**対象**: 1D セル並列化後の数値安定性（主に `marsdisk/run_one_d.py`）

---

## 目的

セル並列化によってスレッド同時実行が増えたため、数値異常（NaN/inf/負値、非決定性、キャッシュ破損）を誘発しそうな箇所を整理し、
**異常が起きていないか**を検証するためのテスト設計案をまとめる。

---

## 数値異常のリスク候補

1. **Qpr キャッシュのスレッド非安全性**
   - 対象: `marsdisk/physics/radiation.py` の `_QPR_CACHE`（`OrderedDict`）
   - 懸念: セル並列で `qpr_lookup` が同時に走ると、キャッシュ破損や値の取り違えが起きる可能性。`Q_pr` は `a_blow`, `β`, `kappa` に影響。
   - 対応: `_QPR_CACHE` の get/set/clear を lock で保護する。

2. **Q_D* キャッシュと速度クランプ統計の競合**
   - 対象: `marsdisk/physics/qstar.py` の `_QDSTAR_CACHE`, `_VEL_CLAMP_COUNTS`
   - 懸念: OrderedDict の更新が競合するとキャッシュが壊れる可能性。`Q_D*` の誤差は破砕しきい値や衝突生成量に波及。
   - 対応: `_QDSTAR_CACHE` と `_VEL_CLAMP_COUNTS` を lock で保護する。

3. **Numba 失敗フラグのグローバル共有**
   - 対象: `marsdisk/physics/collisions_smol.py` などの `_NUMBA_FAILED`
   - 懸念: 1セルの Numba 失敗で全体がフォールバックし、ループ中に数値経路が切り替わる。結果が非決定的に揺れる可能性。
   - 方針: 実装修正は保留し、Numba 有効/無効の結果差が許容内かを統合テストで監視する。

4. **PSD 負値/NaN の伝播**
   - 対象: `marsdisk/physics/collisions_smol.py` → `psd_state` 更新
   - 懸念: IMEX で負値が混入すると `kappa`, `tau`, `Q_pr` などに NaN が伝播。run_one_d は毎ステップで全PSDを正規化しないため、異常が長引く可能性。
   - 方針: `out/<run_id>/series/psd_hist.parquet` で `N_bin`, `Sigma_bin`, `Sigma_surf` の非負性・有限性を検査する。

5. **質量保存チェックが実質ゼロ差分になる設計**
   - 対象: `marsdisk/run_one_d.py` の `mass_remaining = mass_initial - mass_lost` 型の集計
   - 懸念: 実際の `Sigma_surf` から算出した質量との差分を見ていないため、数値誤差やリークが検知されにくい。
   - 方針: `mass_total_bins` と損失累積から実質質量を再計算し、0.5% 以内に収まるか検査する。

6. **集計順序の変更による微小誤差**
   - 対象: セル並列化後の `step_*_sum` の加算順序
   - 懸念: 並列化により浮動小数の加算順が変わり、非常に小さい誤差が発生。発散ではないが比較試験で差分が出る可能性。
   - 方針: 並列 ON/OFF の要約差を rtol=1e-5, atol=1e-10 で監視する。

7. **IMEX-BDF ループの非停止（NaN 質量誤差）**
   - 対象: `marsdisk/physics/smol.py` の `step_imex_bdf1_C3`
   - 懸念: `mass_err` が NaN/inf のとき `while True` が抜けず、テストがハングする可能性。
   - 方針: `mass_err` の有限性ガードや最大反復回数の導入を検討し、タイムアウト付きテストで検出する。

8. **PSD グリッドの非正値入力**
   - 対象: `marsdisk/physics/psd.py` の `update_psd_state`（`logspace`）
   - 懸念: `s_min <= 0` で NaN が生じ、`kappa/tau/Q_pr` が連鎖的に破綻する。
   - 方針: `schema.Sizes.s_min/s_max` の正値バリデーションを追加し、設定ロードで失敗させる。

9. **PSD 正規化の自動リセットが異常を隠蔽**
   - 対象: `marsdisk/physics/psd.py` の `sanitize_and_normalize_number`
   - 懸念: NaN/負値が混じった場合に無言で一様分布へ戻るため、異常を検知しにくい。
   - 方針: 警告/カウンタの導入で「リセットが起きた」ことを記録し、テストで捕捉する。

10. **カーネルの H_ij 極小化による dt 崩壊**
    - 対象: `marsdisk/physics/collide.py` の `compute_collision_kernel_C1`
    - 懸念: `H_ij` が極端に小さいとカーネルが巨大化し、`dt_eff` がほぼ 0 になって進行しない。
    - 方針: `H_fixed_over_a` に下限/警告を設け、テストで過小値の検知を確認する。

11. **Clausius P_sat の非物理温度入力**
    - 対象: `marsdisk/physics/sublimation.py` の `p_sat_clausius` / `mass_flux_hkl`
    - 懸念: `T <= 0` で `inf/NaN` が返り、`ds/dt` が暴走する可能性。
    - 方針: 非正の温度入力で例外を投げるか、ドライバ側で明示的に弾くテストを用意する。

12. **deep_mixing 供給の質量が保存チェックに入らない**
    - 対象: `marsdisk/physics/supply.py` の `split_supply_with_deep_buffer` と `run_one_d` の集計
    - 懸念: `sigma_deep` が `mass_total_bins` に反映されず、質量保存の再計算が破綻する。
    - 方針: `sigma_deep` を含めた再計算で 0.5% 以内になることを検査する。

13. **`_NUMBA_FAILED` のグローバル共有**
   - 対象: `marsdisk/io/tables.py`, `marsdisk/physics/radiation.py`
   - 懸念: 1 スレッドの numba 失敗で全体がフォールバックし、並列時の経路が不安定化。
   - 方針: numba 例外を人工的に起こし、フォールバック後の結果が安定するかテストする。

14. **供給 powerlaw の t<t0 での NaN/複素化**
   - 対象: `marsdisk/physics/supply.py` の `_rate_basic`
   - 懸念: `((t - t0) + eps) ** index` で `t < t0` かつ非整数指数の場合に NaN/複素数が出る可能性。
   - 方針: `t < t0` を 0 クリップするか例外化し、テストで挙動を固定化する。

15. **温度テーブルの NaN/負温度混入による供給率崩壊**
   - 対象: `marsdisk/physics/supply.py` の `_TemperatureTable.load` / `_temperature_factor`
   - 懸念: 温度テーブルに NaN/負値が混入しても無検知で `np.interp` に流れ、供給率が NaN/負値になり得る。
   - 方針: テーブル入力の有限性・正値検証を追加し、異常値は例外で止める。

16. **`solve_c_eq` の eps_model が NaN を返すケース**
   - 対象: `marsdisk/physics/dynamics.py` の `solve_c_eq`
   - 懸念: `eps_model` が NaN を返すと `c_new` が NaN 化し収束不能、ループが無駄に回る。
   - 方針: `eps` / `c_new` の有限性チェックを追加し、非有限なら例外。

17. **衝突カーネルの v_rel 非有限・負値未検査**
   - 対象: `marsdisk/physics/collide.py` の `compute_collision_kernel_C1`
   - 懸念: `v_rel` が NaN/負値でもカーネルを計算し、負の衝突率や NaN が混入する恐れ。
   - 方針: `v_rel` の有限性・非負を検査し、異常値で例外。

18. **サイズドリフト再ビンで全ゼロ化が無警告**
   - 対象: `marsdisk/physics/psd.py` の `apply_uniform_size_drift`
   - 懸念: 再ビン結果が全ゼロの場合に無警告で元 PSD 維持となり、`ds/dt` の異常が隠れる。
   - 方針: `np.allclose(new_number, 0.0)` で警告を出し、診断指標に記録する。

19. **PSD→数密度変換の mass_density_raw=0/NaN 無警告**
   - 対象: `marsdisk/physics/smol.py` の `psd_state_to_number_density`
   - 懸念: `mass_density_raw <= 0` で N_k をゼロ化するが無警告のため、質量喪失に気づけない。
   - 方針: 0/非有限を検出した場合に警告・診断を記録する。

20. **Σ(r) 正規化の特異点（p≈2 & r_out≈r_in）**
   - 対象: `marsdisk/physics/initfields.py` の `sigma_from_Minner`
   - 懸念: `log(r_out/r_in)` や `r_out^(2-p) - r_in^(2-p)` が極小化し、Σが発散する恐れ。
   - 方針: `r_out/r_in` の下限や `|p-2|` 近傍での警告/例外を追加する。

21. **`omega_kepler`/`v_kepler` の r<=0 未検査**
   - 対象: `marsdisk/grid.py` の `omega_kepler`, `v_kepler`
   - 懸念: `r<=0` で NaN/inf が返り、時間刻みや衝突率計算が破綻する可能性。
   - 方針: `r>0` の検証を追加し、異常値は例外で止める。

22. **C5 のトーマス法で対角 0 によるゼロ除算**
   - 対象: `marsdisk/physics/viscosity.py` の `_solve_tridiagonal`
   - 懸念: `bc[i-1]=0` でゼロ除算が発生し NaN を生成、拡散結果が破綻。
   - 方針: 対角の下限・例外化、もしくはガード付き分岐を導入する。

23. **`tau` が NaN の場合の衝突項無効化**
   - 対象: `marsdisk/physics/surface.py` の `_safe_tcoll`
   - 懸念: `tau=np.nan` で `t_coll` が NaN となり衝突項が無言で無効化される可能性。
   - 方針: `tau` の有限性を検査し、非有限時は警告/例外とする。

24. **供給テーブルの欠損セルが NaN を伝播**
   - 対象: `marsdisk/physics/supply.py` の `_TableData.load`
   - 懸念: t×r グリッドに欠損があると補間値が NaN になり供給率が破綻する。
   - 方針: グリッドの完全性（欠損・非有限）をロード時に検査し、異常は例外。

25. **Φ(τ,ω0,g) テーブルの未検証入力**
   - 対象: `marsdisk/io/tables.py` の `PhiTable.from_frame`
   - 懸念: 欠損・非有限・次元不足の Φ テーブルで補間が NaN 化する恐れ。
   - 方針: テーブルの完全性・次元数（各軸>=2）を検査し、異常は例外。

26. **e0/i0 の非有限・不正値**
   - 対象: `marsdisk/schema.py` の `Dynamics`
   - 懸念: `e0>=1` や `i0<0` が混入すると `v_rel` 計算が例外化・破綻する。
   - 方針: スキーマで e0/i0 の範囲・有限性を検証し、構成時に失敗させる。

27. **sublimation_min で温度未指定**
   - 対象: `marsdisk/physics/psd.py` の `evolve_min_size`
   - 懸念: `T=None` で `mass_flux_hkl` のガードにより例外化する可能性。
   - 方針: T 未指定はスキップ扱いとして警告し、診断値を保持する。

28. **負の Σ_surf による τ の負値化**
   - 対象: `marsdisk/run_one_d.py` の τ 計算ブロック
   - 懸念: `sigma_val<0` で `tau_los` が負になり、衝突・ゲート判定が崩れる。
   - 方針: 非有限/負の Σ_surf は 0 へクランプし、警告を出す。

---

## テスト設計案（異常検知）

### 1) キャッシュ競合の再現テスト（ユニット）
- **目的**: Qpr/Q_D* のキャッシュ破損や値のぶれ検知
- **案**:
  - `ThreadPoolExecutor` で `radiation.qpr_lookup` と `qstar.compute_q_d_star_array` を同時に多数回呼ぶ。
  - 同一入力に対する出力が一致し続けることを確認。
  - 例外や NaN が出たら失敗（`atol=1e-12` の一致を要求）。

### 2) 並列 ON/OFF の再現性比較（統合）
- **目的**: セル並列が数値を壊していないことの確認
- **案**:
  - 同一設定で `MARSDISK_CELL_PARALLEL=0` と `1` を実行。
  - `out/<run_id>/summary.json` の `M_loss`, `M_out_cum`, `mass_budget_max_error_percent` を比較。
  - 許容差: `rtol=1e-5`, `atol=1e-10`（短時間テスト）。

### 3) PSD 非負性チェック（統合）
- **目的**: PSD の負値・NaN 混入検知
- **案**:
  - 出力 `out/<run_id>/series/psd_hist.parquet` を読み込み、`N_bin`, `Sigma_bin`, `Sigma_surf` の負値・NaN を検査。
  - 異常があれば失敗（負値は `-1e-12` 未満を NG）。

### 4) “実質質量”による保存則再計算（統合）
- **目的**: 出力上の質量保存が破れていないか検知
- **案**:
  - `Sigma_surf` と幾何面積からステップごとの実質質量を再計算。
  - `dSigma_dt_total * smol_dt_eff` を質量変化の推定として用い、実質質量の差分と 0.5% 以内で整合するかを確認。

### 5) Numba フォールバックの影響検証（統合）
- **目的**: `_NUMBA_FAILED` による経路切り替えの影響把握
- **案**:
  - `MARSDISK_DISABLE_NUMBA=1` で実行した結果と通常実行結果を比較。
  - 主要指標が `rtol=1e-5`, `atol=1e-10` の範囲内かを確認。

### 6) 並列加算順序差の監視（回帰）
- **目的**: 微小誤差を許容範囲に抑えているか確認
- **案**:
  - 並列 ON/OFF の `out/<run_id>/series/run.parquet` で `prod_subblow_area_rate`, `M_out_dot` の平均との差を比較。
  - 差分が閾値を超えた場合は警告扱い。

### 7) IMEX ループ非停止の検出（ユニット）
- **目的**: NaN 質量誤差でのハングを検出
- **案**:
  - `compute_mass_budget_error_C4` を `np.nan` を返すスタブに差し替えた上で `step_imex_bdf1_C3` を実行。
  - `multiprocessing` でプロセス分離し、一定時間で終了しない場合は失敗とする（タイムアウト 1–2 秒）。
  - 期待: ガード導入後は例外で終了する。

### 8) PSD グリッドの正値バリデーション（ユニット）
- **目的**: `s_min <= 0` が構成時に弾かれることを確認
- **案**:
  - `load_config` で `sizes.s_min=0`/`-1` の設定を読み込み、`ConfigurationError` になることを確認。
  - `s_min >= s_max` の既存チェックと併せて検証する。

### 9) PSD 正規化リセットの検知（ユニット）
- **目的**: 異常 PSD が自動リセットされたことを可視化
- **案**:
  - `sanitize_and_normalize_number` に警告/カウンタを追加し、NaN を含む PSD を渡して警告が出ることを確認。
  - 監視指標（例: `psd_sanitize_reset_count`）が 1 以上になることを期待。

### 10) H_ij 極小による dt 崩壊の監視（統合）
- **目的**: `H_fixed_over_a` 極小での dt 退化を検出
- **案**:
  - `dynamics.kernel_H_mode=fixed` かつ `H_fixed_over_a=1e-12` などで短時間 run を実行。
  - `smol_dt_eff` の最小値が極端に小さい場合は警告/失敗扱い（閾値例: `1e-15`）。

### 11) P_sat 入力温度のガード（ユニット）
- **目的**: `T <= 0` の入力で異常値が出ないことを確認
- **案**:
  - `p_sat_clausius` / `mass_flux_hkl` を `T=0` または `T<0` で呼び、例外が発生することを確認。
  - `tempdriver` のテーブルで非有限値が存在するときに例外が出ることも併せて確認する。

### 12) deep_mixing の質量再計算（統合）
- **目的**: 深層リザーバを含めた質量保存の監視
- **案**:
  - `supply.transport.mode=deep_mixing` + `t_mix_orbits` 大きめで run。
  - `mass_total_bins + sigma_deep * area + losses` の総量が一定であることを確認（0.5% 以内）。

### 13) `_NUMBA_FAILED` グローバル影響の検証（ユニット/統合）
- **目的**: numba 失敗が並列実行で非決定性を生まないか確認
- **案**:
  - numba 補間関数を一度だけ例外を投げるスタブに差し替え、並列 `qpr_lookup_array` を実行。
  - その後の結果が NumPy フォールバックと一致し、`NaN` が混入しないことを確認。

### 14) powerlaw 供給の t<t0 での NaN 防止（ユニット）
- **目的**: `t<t0` で指数が非整数でも NaN/複素化しないことの確認
- **案**:
  - `index=0.5` と `t<t0` を与え、例外 or 0 クリップの挙動を固定化。

### 15) 温度テーブルの NaN/負値検出（ユニット）
- **目的**: 異常テーブル入力が供給率へ伝播しないことの確認
- **案**:
  - NaN/負温度を含むテーブルを読み込ませ、例外が出ることを確認。

### 16) `solve_c_eq` の NaN 防止（ユニット）
- **目的**: `eps_model` が NaN を返した際に即時停止することを確認
- **案**:
  - `eps_model=lambda _: np.nan` で呼び出し、例外が発生することを確認。

### 17) 衝突カーネルの v_rel 異常値検出（ユニット）
- **目的**: `v_rel` の非有限・負値が例外で止まることの確認
- **案**:
  - `v_rel=-1` または `np.nan` で `compute_collision_kernel_C1` を呼び、例外を確認。

### 18) サイズドリフト再ビンの全ゼロ化警告（ユニット）
- **目的**: 再ビンが全ゼロになったとき警告/診断が出ることの確認
- **案**:
  - 全ビンが `floor` に吸収される条件で `apply_uniform_size_drift` を実行し、警告を確認。

### 19) PSD→数密度変換のゼロ質量検知（ユニット）
- **目的**: `mass_density_raw<=0` が警告されることの確認
- **案**:
  - `number=0` の PSD を与え、警告/診断が出ることを確認。

### 20) Σ(r) 正規化の特異点ガード（ユニット）
- **目的**: `p≈2` かつ `r_out≈r_in` で発散しないことの確認
- **案**:
  - `p_index=2±1e-12`、`r_out/r_in→1` の設定で例外/警告が出ることを確認。

### 21) r<=0 の軌道関数ガード（ユニット）
- **目的**: `omega_kepler`/`v_kepler` が不正入力で例外になることの確認
- **案**:
  - `r=0` / `r<0` で例外を確認。

### 22) C5 トーマス法の対角 0 ガード（ユニット）
- **目的**: 対角 0 で NaN を出さずに停止することの確認
- **案**:
  - `diag=0` が起きる入力を構成し、例外/警告を確認。

### 23) `tau` の NaN 検出（ユニット）
- **目的**: `tau=np.nan` が衝突項を無言で無効化しないことの確認
- **案**:
  - `_safe_tcoll(Omega, np.nan)` で警告/例外が出ることを確認。

### 24) 供給テーブル欠損セル検出（ユニット）
- **目的**: t×r 欠損が NaN 伝播しないことの確認
- **案**:
  - 欠損を含む `t,r,rate` テーブルを読み込み、例外を確認。

### 25) Φ テーブルの完全性検証（ユニット）
- **目的**: 欠損・次元不足の Φ テーブルを拒否することを確認
- **案**:
  - 不完全な `(tau,w0,g,Phi)` を `PhiTable.from_frame` に渡し、例外を確認。

### 26) e0/i0 の範囲検証（ユニット）
- **目的**: e0/i0 の不正値が構成時に弾かれることを確認
- **案**:
  - `e0>=1` / `e0<0` / `i0<0` の `Dynamics` を生成し、`ValidationError` を確認。

### 27) sublimation_min の温度未指定ガード（ユニット）
- **目的**: `T=None` が例外化せず安全にスキップされることを確認
- **案**:
  - `evolve_min_size(..., model="sublimation_min", T=None)` で元値が返ることを確認。

### 28) Σ_surf クランプ動作（ユニット）
- **目的**: 非有限・負の Σ_surf が 0 にクランプされることを確認
- **案**:
  - 内部ヘルパを直接呼び出し、負値/NaN が 0 になることを確認。

---

## 追記メモ

- セル並列の再現性テストのみ **Windows/.cmd 実行**を前提とする。
- それ以外のテスト設計は OS 非依存を想定。
- 既存のテスト設計に追加する場合は、`FORCE_STREAMING_OFF=1` を用いて I/O を簡略化する。

---

## テスト実行結果（ローカル）

- **実行日**: 2025-12-24
- **コマンド**: `pytest tests/unit/test_numerical_anomaly_watchlist_additional.py tests/integration/test_deep_mixing_mass_budget.py`
- **結果**: 7 passed, 1 warning
- **警告**: `TableWarning`（numba 補間失敗 → NumPy フォールバック）を 1 件確認
- **実行日**: 2025-12-24
- **コマンド**: `pytest tests/unit/test_numerical_anomaly_watchlist_additional.py`
- **結果**: 19 passed
- **警告**: なし
- **実行日**: 2025-12-24
- **コマンド**: `pytest tests/unit/test_numerical_anomaly_watchlist_additional.py`
- **結果**: 24 passed
- **警告**: なし
- **実行日**: 2025-12-24
- **コマンド**: `pytest tests/integration`
- **結果**: 199 passed, 3 skipped, 62 warnings
- **警告**: DeprecationWarning（供給設定の非デフォルトに関する既知警告）

---

## 完了チェックリスト

- [x] リスク候補の妥当性を再確認し、不要・重複がないか整理する
- [x] 各リスクの対応方針（修正/回避/許容）を決定する
- [x] キャッシュ競合（Qpr/Q_D*）の対策有無を確定する
- [x] テスト設計案の許容差・判定基準を明確化する
- [x] ユニットテスト（キャッシュ競合）と統合テスト（Numbaフォールバック）を追加する
- [x] 統合テスト（並列ON/OFF、PSD非負性、質量再計算）を追加する
- [x] 追加リスク（7–13）のテスト設計を追記する
- [x] IMEX ループ非停止の検出テストを実装する
- [x] PSD グリッド正値バリデーションのテストを実装する
- [x] PSD 正規化リセット検知のテストを実装する
- [x] H_ij 極小による dt 崩壊の監視テストを実装する
- [x] P_sat 入力温度ガードのテストを実装する
- [x] deep_mixing の質量再計算テストを実装する
- [x] `_NUMBA_FAILED` グローバル影響テストを実装する
- [ ] `out/<run_id>/summary.json` と質量保存ログの差分を確認し、許容範囲内であることを確認する
- [x] 追加リスク（14–23）の方針を確定する
- [x] 追加リスク（14–23）のテスト設計を確定する
- [x] 追加リスク（24–28）の方針を確定する
- [x] 追加リスク（24–28）のテスト設計を確定する
- [x] 追加リスク（24–28）のガード実装を行う
- [x] 追加リスク（24–28）のテスト実装を行う
