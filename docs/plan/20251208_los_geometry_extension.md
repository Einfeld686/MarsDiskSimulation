# 視線方向光路長を明示する拡張プラン

## 背景
- 現行の LOS τ は鉛直 τ を幾何係数 `f_los = max(1, path_multiplier/h_over_r)` でスケールする簡易モデル。火星までの視線距離や傾斜を直接扱っていない。
- 放射圧・遮蔽をより物理的に評価するには、光路長 ℓ を明示し、τ_los = κ Σ (ℓ / 2H) の形で距離依存を入れる必要がある。

## 目的
- 0D モデルでも「視線方向の距離」を明示的に扱えるようにし、f_los を距離・厚みから計算するパスを追加する。
- 既存の単純係数モードは互換のため残す。

## スコープ
- 0D LOS 幾何の強化に限定。1D 半径依存や傾斜分布の詳細モデルは別プラン。
- ドキュメント（analysis/equations.md ほか）と I/O 定義を更新。

## 作業ステップ
1) **スキーマ拡張**
   - `shielding.los_geometry.mode` に `distance_scaled` を追加。
   - パラメータ: `h_over_r`, `path_multiplier`, `use_radius` (r を光路に掛けるか)、将来拡張用の `inclination_deg` (未使用なら None)。
2) **f_los 計算の切替**
   - `run_zero_d.py/_resolve_los_factor` を拡張し、`mode=="distance_scaled"` の場合は `f_los = max(1, path_multiplier * r / (2 * H))` （H = h_over_r * r）を使用。
   - 既存 `aspect_ratio_factor` モードは現行の定数係数で維持。
3) **LOS τ 評価の更新**
   - `tau_los_mars = kappa_surf * Sigma_surf * f_los` として距離依存を反映（既存パスを置換）。
   - `phase_payload`/`tau_gate`/`Sigma_tau1` の計算は新しい τ_los を使う。
4) **I/O と検証**
   - 出力カラムに `f_los`（選択モードと値）を追加するか、`out/<run_id>/run_config.json` に記録する。
   - `writer` 定義と `evaluation_system.REQUIRED_SERIES_COLUMNS` を調整。
5) **テスト**
   - f_los が距離スケーリングすることをユニットテストで確認（例: r を倍にすると f_los も比例増）。
   - LOS τ を伸ばしたケースで κ_eff/M_out_dot が減少することを検証（既存の LOS テストを距離モードに拡張）。
6) **ドキュメント**
   - `analysis/equations.md` に `f_los` 距離スケール式を追記し、`overview.md`/`assumption_trace.md` で LOS τ の距離依存を明示。
   - DocSyncAgent → doc-tests → evaluation_system を実行。

## 非対象
- 半径方向の構造・傾斜分布・非等方散乱の詳細モデルは扱わない。
- 1D C5 拡散への適用は別プラン。
