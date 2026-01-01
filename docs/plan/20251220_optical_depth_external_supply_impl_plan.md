# 実装プラン：光学的厚さと定常外部供給（0D / run_zero_d）

## 目的
光学的厚さ τ を表層モデルの適用限界として扱い、τ=1 クリップを「停止判定」に置き換える。外部供給は μ を「1公転で初期表層の10%」に固定し、`epsilon_mix` と分離して定常供給を実装する。

## 要件
- 初期 `Sigma_surf0` を `tau0_target` と `kappa_eff0` から決定できること。
- `kappa_eff0` は `tau_field` で選んだ τ に `tau0_target` を代入して `Phi` を評価し、`kappa_eff0 = Phi(tau0_target) * kappa_surf0`（E.017）で固定すること。
- `tau_los` が `tau_stop` を超過したら停止し、`Sigma_surf` のクリップは行わないこと。
- μの定義を固定（1公転で初期表層の10%）し、`epsilon_mix` と混同しないこと。
- 既存の式（E.015–E.017, E.016, E.027）を流用し、新規物理式は導入しないこと。
- `series` と `summary` に必要診断を出力すること。
- 出力列名は既存仕様に合わせ、`tau_los_mars` と `Sigma_tau1` を使う（`Sigma_tau1_los` は導入しない）。
- 定常供給は既存の供給ゲート（相/ステップ0遅延/液相ブロック等）を維持し、その範囲内でのみ有効とする。
- `optical_depth` の有効化と `init_tau1.scale_to_tau1` は排他とし、同時指定は設定エラーにする。
- ドキュメント（`analysis/methods.md` など）に「τ=1 クリップは旧挙動、現行は停止判定」と明記して整合させる。

## 対象範囲
- In: 0D `run_zero_d` 初期化・遮蔽・供給・停止条件・診断出力・テスト
- Out: 1D拡張、温度スケール/τフィードバック/有限リザーバ、深部混合モデルの新規拡張

## デフォルト化と非推奨方針（重要）
この文書の方式（optical_depth + mu_orbit10pct + τ停止判定）を**0Dのデフォルト**とする。外部供給のデフォルト参照は `docs/plan/20251220_optical_depth_external_supply_impl_plan.md` と `~/.codex/plans/marsdisk-tau-sweep-phi-off.md` に限定し、それ以外の外部供給スイッチは**非推奨・削除候補**として扱い、互換性目的でのみ残す。

### デフォルトとして採用する挙動
- `optical_depth` を有効化し、初期 `Sigma_surf0` を `tau0_target` と `kappa_eff0` から決める。
- 表層の頭打ち/クリップは行わず、`tau_los > tau_stop * (1 + tau_stop_tol)` で停止する。
- 供給は `mu_orbit10pct` を基準とする定常供給のみ（`epsilon_mix` と明確に分離）。
- 供給ゲートは相判定やステップ遅延など既存の最小ゲートのみ許容。

### 非推奨として扱う機能（互換性維持のため当面残す）
- `supply.feedback.*`（τフィードバック）
- `supply.transport.*`（deep_mixing など）
- `supply.headroom_policy`（頭打ち/クリップ）
- `supply.temperature.*`（温度スケール）
- `supply.reservoir.*`（有限リザーバ）
- `init_tau1.scale_to_tau1`（`optical_depth` と排他のため、既定では使わない）
- `supply.mode` の非 `const` 設定、および `supply.injection` / `supply.injection.velocity` の**非デフォルト値**（現時点では完全廃止せず、非デフォルト使用時のみ警告）

### 移行の指針
- 旧モードを使っている設定は、`optical_depth` + `mu_orbit10pct` に置き換える。
- 供給量が過大になりやすいケースでは、`tau_stop` を超えた時点で終了する前提で運用する。
- どうしても旧モードを維持する場合は「感度試験・比較用」と明記し、デフォルト系と混同しない。

## 主要ファイル
- `marsdisk/run_zero_d.py`
- `marsdisk/schema.py`
- `marsdisk/physics/supply.py`
- `marsdisk/physics/surface.py`
- `marsdisk/physics/shielding.py`
- `marsdisk/runtime/helpers.py`
- `marsdisk/io/writer.py`
- `marsdisk/io/diagnostics.py`
- `tests/`

## スキーマ/APIの変更点
- `optical_depth.tau0_target`, `tau_stop`, `tau_stop_tol`, `tau_field` を追加（既定は `tau_los` 固定）。
- `supply.const.mu_orbit10pct`, `orbit_fraction_at_mu1` を追加（新しい供給パラメータはこの名称に限定）。
- `supply.mixing.mu`（`epsilon_mix` エイリアス）は廃止し、設定キーとしては受け付けない。
- 旧 μ（E.027a 相当）は診断・ツール側の導出値としてのみ保持し、設定に使わない。
- `optical_depth` は新設で維持し、既存 `init_tau1` とは統合しない（互換性のため `init_tau1` は残す）。
- `optical_depth` と `init_tau1.scale_to_tau1` の同時指定は検証でエラーにする。
- `out/<run_id>/summary.json` に `stop_reason`, `stop_tau_los` を追加。
- 外部供給は本方式へ一本化し、旧系（feedback/transport/headroom/temperature/reservoir 等）は段階的に非推奨化→削除する。

## 実装タスク
[x] `run_zero_d` / `supply` / `surface` / `collisions_smol` の τ=1 クリップ/ヘッドルーム箇所を洗い出し、置換点を確定。
[x] `schema.py` に `optical_depth` と `mu_orbit10pct` を追加し、`epsilon_mix` と衝突しない検証を実装（`supply.mixing.mu` を受け付けない）。
[x] `optical_depth` と `init_tau1.scale_to_tau1` の排他チェックをスキーマで実装。
[x] `tau0_target` と `kappa_eff0`（遮蔽・LOS含む）から `Sigma_surf0` を計算し初期化へ統合。
[x] `kappa_eff0` の評価は `tau_field` で選んだ τ に `tau0_target` を代入して `Phi` を計算し、`kappa_eff0 = Phi * kappa_surf0` に固定する。
[x] μ→`dotSigma_prod`→`R_base` の定義を実装（`dotSigma_prod = mu * orbit_fraction_at_mu1 * Sigma_surf0 / T_orb`）。
[x] 表層更新時の τ=1 クリップを撤廃し、`Sigma_tau1` は診断用のみ保持。
[x] 更新後に `tau_los > tau_stop * (1 + tol)` を判定し停止、`stop_reason="tau_exceeded"` と最終 `tau_los` を記録。
[x] 時系列出力に `tau_los_mars`, `kappa_surf`, `phi_used`, `kappa_eff`, `Sigma_tau1`, `Sigma_surf0`, `mu_orbit10pct`, `epsilon_mix`, `dotSigma_prod` を追加（列名は既存仕様に合わせる）。
[x] `out/<run_id>/summary.json` に `stop_reason`, `stop_tau_los` を追加。
[x] `tools/derive_supply_rate` など旧 μ を扱う箇所を「診断用導出値」と明示し、設定キーとの混同が起きないよう更新。
[x] テスト追加（μスケール、停止条件）と既存テスト（ヘッドルーム/遮蔽/質量収支）の更新。
[ ] `analysis/methods.md` と関連ドキュメントの「Σ_tau1 でクリップ」記述を「停止判定」へ更新し、旧挙動は注記として残す。
[ ] 外部供給の旧モードを段階的に非推奨化（警告→エラー）し、新方式をデフォルトに切り替える移行手順を明記する。
[ ] 非推奨項目（feedback/transport/headroom/temperature/reservoir/scale_to_tau1）を明示し、ドキュメントの既定例を全て新方式へ切り替える。

## テスト・検証
- `pytest tests/integration/test_supply_headroom_policy.py`
- `pytest tests/integration/test_radiation_shielding_logging.py`
- `pytest tests/integration/test_surface_outflux_wavy.py`
- `pytest tests/integration/test_mass_conservation.py`
- `python -m marsdisk.run --config configs/base.yml`
- `out/checks/mass_budget.csv` の `error_percent < 0.5%` を確認

## リスク・エッジケース
- `kappa_eff` が非有限のとき `Sigma_tau1` が無効になり停止判定が空振りする可能性。
- クリップ削除により既存挙動・テストが破綻する可能性。
- deep_mixing/reservoir などの既存モードとの非互換が出る可能性。
- 旧 μ（E.027a）を参照するツール・ドキュメントが混同を招く可能性。

## 未決事項

## 議論メモ（2025-12-21）
- 透過率 10% を閾値にするため、停止条件は `tau_los > tau_stop * (1 + tol)` に合わせて `tau_stop=ln(10)=2.302585092994046`、`tau_stop_tol=1.0e-6` とする方針。
- 既存の `tau_stop=1.0` ケース（temp_supply_sweep 等）は `tau_exceeded` で数十〜百秒で停止していたため、閾値更新により停止時刻が後ろに伸びる見込み。
- 停止判定の動作確認（`out/20251221-1449_tau_stop_check__edaaa5b04__seed123`）では `stop_reason="tau_exceeded"`、`stop_tau_los=2.3057`、`early_stop_time_s=8.379e3`（約 2.33 時間）。`tau_stop=2.302585...` と `tau_stop_tol=1e-6` を反映して閾値超過で停止。
- 供給ゲートは相判定に連動し、`phase_state="solid"` かつ `liquid_dominated` でない場合のみ供給を許可（グローバル1ステップ遅延あり）。液体優勢では衝突カスケードもブロック。
- 0D の `tau_los` は角度分解ではなくスカラー診断で、`tau_los = kappa * Sigma * los_factor`（`los_factor` は `h_over_r` と `path_multiplier` から決まる）。垂直構造は明示的に解かない。
- 初期 `Sigma_surf0` は `optical_depth.tau0_target` と `kappa_eff0` から決まり、`mu_orbit10pct` は「表層の何割を1公転で供給するか」のスケールであって、内側円盤総質量の10%を表層に割り当てる意味ではない。
- 検証ランの例（`r_in=1.0 R_Mars`, `r_out=2.7 R_Mars`）では、面積 `2.27024e14 m^2`、`Sigma_surf0=10088.9 kg/m^2`、表層質量 `2.29e18 kg`（`3.57e-6 M_Mars`）。
- 垂直厚みは衝突カーネルのスケールハイト `H = H_factor * i * r` でのみ表現（例: `i=0.05`, `r=1.85 R_Mars` で `H≈3.14e5 m`）。`i0=0` はエラーにならないが `H` は最小値にクランプされ、衝突率が過大になりうる。

## 違和感/確認ポイント
- `tau_stop` を透過率ベース（`ln(10)`）にする妥当性と、デフォルト値としての採用是非。
- `los_factor`（幾何補正）と `i`/`H` の関係が切り離されている点の扱い（モデル上の独立仮定として保持するか検討）。
- `Sigma_surf0` で初期質量が上書きされる挙動を、ユーザー向けに明示する必要があるか。

## 数式と状況の詳細（外部向け整理）
### 0Dモデルの前提
- 0Dは「r_in〜r_out の環を面平均した表層」を解くモデルで、角度依存の視線方向を分解しているわけではない。
- 光学的厚さはスカラー診断で、停止判定もこのスカラーで行う。

### 光学的厚さの定義
- LOS補正: `los_factor = max(path_multiplier / h_over_r, 1.0)`
- 視線方向（LOS）: `tau_los = kappa_surf * Sigma_surf * los_factor`
- 停止条件: `tau_los > tau_stop * (1 + tau_stop_tol)`
- 停止判定で使う係数: `kappa_for_stop = kappa_eff (finiteなら) / kappa_surf (fallback)`

### 初期表層密度の決定（optical_depth有効時）
- `kappa_eff0 = Phi(tau0_target) * kappa_surf0`（Phiは遮蔽テーブル）
- `Sigma_surf0 = tau0_target / (kappa_eff0 * los_factor)`
- `optical_depth` 有効時は `surface.sigma_surf_init_override` より `Sigma_surf0` を優先する。

### 供給スケール（mu_orbit10pct）
- `T_orb = 2*pi / Omega`、`Omega = sqrt(G*M_Mars / r^3)`
- `dotSigma_prod = mu_orbit10pct * orbit_fraction_at_mu1 * Sigma_surf0 / T_orb`
- `supply.const.prod_area_rate_kg_m2_s = dotSigma_prod / epsilon_mix`
- ここでの「10%」は *表層の何割を1公転で供給するか* の意味であり、内側円盤総質量の10%を表層に割り当てる意味ではない。

### 表層質量（環の総質量）
- 面積: `A = pi * (r_out^2 - r_in^2)`
- 表層質量: `M_surface = Sigma_surf0 * A`
- `optical_depth` 有効時は `initial.mass_total` が `M_surface / M_Mars` に置き換えられる。

### 相判定による供給・衝突のゲート
- 供給許可: `allow_supply_step = (step_no > 0) and (phase_state == "solid") and not liquid_dominated`
- 衝突: `liquid_dominated` では衝突カスケードがブロックされる。
- 昇華: `liquid_dominated` かつ `allow_liquid_hkl=false` のとき昇華をブロック。

### 垂直厚み（幾何H）について
- 衝突カーネル用のスケールハイト: `H = H_factor * i * r`（`kernel_H_mode="ia"`）
- これは衝突率の計算に使うだけで、`tau_los` の計算には直接使わない。
- `i0=0` はエラーにならないが `H` は最小値でクランプされ、衝突率が過大になりうる。

### 具体例（検証ランの数値）
- 対象: `out/20251221-1449_tau_stop_check__edaaa5b04__seed123`
- `r_in=1.0 R_Mars`, `r_out=2.7 R_Mars` -> `A=2.27024e14 m^2`
- `Sigma_surf0=10088.9 kg/m^2`, `kappa_eff0=9.9119e-05` -> `tau_los(t0) ~ 1.0`
- 表層質量: `M_surface=2.29e18 kg = 3.57e-6 M_Mars`
- 停止判定: `tau_stop=ln(10)=2.302585...`, `tau_stop_tol=1e-6` -> `threshold=2.302587...`
  実測 `stop_tau_los=2.3057`, `early_stop_time_s=8.379e3 s (~2.33 h)`
- スケールハイト例: `i=0.05`, `r=1.85 R_Mars` -> `H ~ 3.14e5 m`（2Hなら約 6.3e5 m）
