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
- `optical_depth.tau0_target`, `tau_stop`, `tau_stop_tol`, `tau_field` を追加（既定は `tau_los` 固定、`tau_vertical` は v1 で扱わない）。
- `supply.const.mu_orbit10pct`, `orbit_fraction_at_mu1` を追加（新しい供給パラメータはこの名称に限定）。
- `supply.mixing.mu`（`epsilon_mix` エイリアス）は廃止し、設定キーとしては受け付けない。
- 旧 μ（E.027a 相当）は診断・ツール側の導出値としてのみ保持し、設定に使わない。
- `optical_depth` は新設で維持し、既存 `init_tau1` とは統合しない（互換性のため `init_tau1` は残す）。
- `optical_depth` と `init_tau1.scale_to_tau1` の同時指定は検証でエラーにする。
- `summary.json` に `stop_reason`, `stop_tau_los` を追加。
- 外部供給は本方式へ一本化し、旧系（feedback/transport/headroom 等）は段階的に非推奨化→削除する。

## 実装タスク
[x] `run_zero_d` / `supply` / `surface` / `collisions_smol` の τ=1 クリップ/ヘッドルーム箇所を洗い出し、置換点を確定。
[x] `schema.py` に `optical_depth` と `mu_orbit10pct` を追加し、`epsilon_mix` と衝突しない検証を実装（`supply.mixing.mu` を受け付けない）。
[x] `optical_depth` と `init_tau1.scale_to_tau1` の排他チェックをスキーマで実装。
[x] `tau0_target` と `kappa_eff0`（遮蔽・LOS含む）から `Sigma_surf0` を計算し初期化へ統合。
[x] `kappa_eff0` の評価は `tau_field` で選んだ τ に `tau0_target` を代入して `Phi` を計算し、`kappa_eff0 = Phi * kappa_surf0` に固定する。
[x] μ→`dotSigma_prod`→`R_base` の定義を実装（`dotSigma_prod = mu * orbit_fraction_at_mu1 * Sigma_surf0 / T_orb`）。
[ ] 表層更新時の τ=1 クリップを撤廃し、`Sigma_tau1` は診断用のみ保持。
[x] 更新後に `tau_los > tau_stop * (1 + tol)` を判定し停止、`stop_reason="tau_exceeded"` と最終 `tau_los` を記録。
[x] 時系列出力に `tau_los_mars`, `kappa_surf`, `phi_used`, `kappa_eff`, `Sigma_tau1`, `Sigma_surf0`, `mu_orbit10pct`, `epsilon_mix`, `dotSigma_prod` を追加（列名は既存仕様に合わせる）。
[x] `summary.json` に `stop_reason`, `stop_tau_los` を追加。
[x] `tools/derive_supply_rate` など旧 μ を扱う箇所を「診断用導出値」と明示し、設定キーとの混同が起きないよう更新。
[x] テスト追加（μスケール、停止条件）と既存テスト（ヘッドルーム/遮蔽/質量収支）の更新。
[ ] `analysis/methods.md` と関連ドキュメントの「Σ_tau1 でクリップ」記述を「停止判定」へ更新し、旧挙動は注記として残す。
[ ] 外部供給の旧モードを段階的に非推奨化（警告→エラー）し、新方式をデフォルトに切り替える移行手順を明記する。

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
