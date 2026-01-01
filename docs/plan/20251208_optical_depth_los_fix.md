# 光学的厚さ（τ=1）を火星視線方向に合わせる修正計画

## 背景と課題
- 現行の `Sigma_tau1=1/κ_eff` は面直（上から見た）光学深さを用いており、火星中心からの視線（放射圧の作用線）に沿った減衰を扱っていない。
- 放射圧フラックスや `tau_gate` 判定、表層クリップが「面直の τ」で評価されているため、火星方向の遮蔽が過小・過大評価され、`Sigma_surf` のクリップも目的とずれる。
- 0D 実装全体で τ の意味が混在しており、`analysis/equations.md` と I/O カラムの定義も「面直」前提のままになっている。

## 目的・スコープ
- 火星視線方向の光路長を定義し、`tau_los_mars`（放射圧の LOS 光学深さ）と `tau_vert`（面直衝突用）を区別して扱う。
- シールド計算・表層クリップ・`tau_gate`・出力カラムを `tau_los_mars` 基準へ再配線する。
- スキーマ/YAML に LOS 幾何を外出しし、ガス貧ディスクの既定値（面直=LOS 近似）を維持しつつ、感度掃引で係数を調整できるようにする。
- 0D ドライバと既存テストを破壊しない範囲で実施し、1D 拡散 (C5) は今回は対象外。

## 作業フェーズ
1) **幾何と設定の追加**
   - `schema.py`/YAML に LOS 幾何用パラメータを追加（例: `shielding.los_geometry: {"mode": "aspect_ratio_factor", "h_over_r": ..., "path_multiplier": ...}`）。既定は 1.0 で従来挙動を温存。
   - `analysis/equations.md` へ τ の定義を「面直 τ_vert」「火星 LOS τ_los_mars」に分けて明文化し、換算式 (E.#) を追記。

2) **コードの経路分離**
   - `marsdisk/run.py` と `marsdisk/physics_step.py` で `tau_vert = kappa_surf * Sigma_surf` を維持しつつ、LOS 用に `tau_los_mars = tau_vert * f_los(r, h_over_r, …)` を計算。
   - `shielding.apply_shielding` の τ を LOS 前提に切り替え、返す `Sigma_tau1` を `Sigma_tau1_los` として扱う（案B）。`surface.step_surface` や `collisions_smol.step_collisions_smol_0d` へのクリップ渡しも LOS 版に合わせる。代案として、Φ 計算は従来の τ_vert で行い、`Sigma_tau1_los = Sigma_tau1_vert / f_los` と後段で縮める案Aも検討。
   - Wyatt 衝突寿命など衝突関連の τ は `tau_vert` を使い続けるよう引数名を明示する。

3) **I/O と診断の整理**
   - `writer.py` の必須カラムに `tau_vert`, `tau_los_mars`, `Sigma_tau1_los`, `phi_los` を追加し、既存 `Sigma_tau1` を後方互換エイリアスにする。
   - 既存の `tau` ログをどちらに割り当てるか決め、互換性のために `tau_vert` を残すか `tau_los_mars` を主要列に昇格させる。
   - `analysis/overview.md`/`assumption_trace.md` で列の意味を更新。`μ = (dotΣ_prod t_blow)/Σ_tau1` は「LOS の Σ_tau1_los を使う」と明示する。

4) **テスト追加と更新（期待値を修正）**
   - `los_factor>1` で必ずしも `Sigma_tau1_los` が縮むとは限らない（Φ(τ_los) 低下で κ_eff が下がると Σ_tau1 は増えることもある）。テストは「LOS を伸ばすと κ_eff/β_eff や `M_out_dot` が減少する」ことを確認するように組む。
   - もし Σ_tau1_los の縮小自体を保証したい場合は案A（`Sigma_tau1_los = Sigma_tau1_vert / f_los`）を採用し、その挙動をテストにする。
   - `tests/integration/test_phase3_surface_blowout.py` を `Sigma_tau1_active` の基準を LOS に合わせて期待値更新。`tau_gate` が `tau_los_mars` を使うことも単体で確認できるとなお良い。

5) **ドキュメントと同期**
   - `analysis/equations.md`/`overview.md`/`assumption_trace.md` を更新後、DocSyncAgent (`make analysis-sync`) → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を実行。
   - YAML サンプル（`configs/base.yml` や sweep 例）に新設定を追加し、既定値は互換モードで記録。

6) **検証・実行**
   - `python -m marsdisk.run --config configs/base.yml` で 0D 完走と `out/checks/mass_budget.csv` の誤差 <0.5% を確認。
   - 主要テスト (`pytest tests/unit/test_surface_outflux.py tests/integration/test_phase3_surface_blowout.py` など) を通し、`out/<run_id>/series/run.parquet` に LOS カラムが出力されているか目視確認。

## 非対象と留意点
- 1D 拡散（C5）や半径プロファイルへの LOS 拡張は今回は見送り、0D の線形光路補正に限定する。
- 光路長モデルの精緻化（例: 傾斜・巻き上げ・非等方散乱）は別プランで扱い、ここでは単純な幾何係数による縮約に留める。

## 設計上の補足（f_los の式と選択肢）
- 0D 幾何の近似として、火星からの光路長 ℓ ≃ `path_multiplier * r`、鉛直厚み 2H（H = h_over_r * r）を仮定すると `f_los = max(1, path_multiplier / h_over_r)` が素直。
- τ の扱いは次の2案のいずれかで整合を取る:
  - **案A（Σ_tau1 を直接縮める）**: `tau_vert` で Φ を計算し `Sigma_tau1_vert` を得た後、`Sigma_tau1_los = Sigma_tau1_vert / f_los` として表層クリップに使う。Σ_tau1 の縮小を保証する。
  - **案B（Φ の τ を LOS にする）**: `tau_los_mars` を `apply_shielding` に渡し、`kappa_eff_los` と `Sigma_tau1_los` を得てそのまま使う。Σ_tau1_los が増える場合もあるが、Φ が下がることで κ_eff/β_eff が減少し、結果としてブローアウトが抑制されることをテストで確認する。
- μ 定義、`tau_gate`、出力カラムの説明はいずれの案でも LOS 前提で統一する。
- **方向の使い分けを明記**: 垂直方向の物質輸送・衝突タイムスケールは鉛直 τ (`tau_vert`) を使い、放射圧の遮蔽・ゲート・クリップは視線方向 τ (`tau_los_mars`) を使う。ドキュメントにもこの役割分担を明記して混同を避ける。

## 実装フロー（案B 基準）
1. **スキーマ**: `schema.py` に `shielding.los_geometry` を追加（`h_over_r`, `path_multiplier`, `mode`）。デフォルトは 1.0 で互換維持。
2. **f_los 評価**: `run.py`/`physics_step.py` で `tau_vert` を算出後、`f_los` を用いて `tau_los_mars` を得るヘルパを新設（0D 近似式を埋め込む）。
3. **シールド入力の切替**: `shielding.apply_shielding` への τ を `tau_los_mars` に変更し、戻り値を `Sigma_tau1_los` として記録・伝搬する（`surface.step_surface`、`collisions_smol.step_collisions_smol_0d` の `sigma_tau1` に渡す）。
4. **Wyatt/衝突 τ の維持**: 衝突寿命や t_coll 用 τ は `tau_vert` のまま引数名で明示。
5. **I/O 拡張**: `writer.py` で `tau_vert`, `tau_los_mars`, `Sigma_tau1_los`, `phi_los` を出力。`Sigma_tau1` はエイリアスとして残す。
6. **テスト更新**: `tests/unit/test_surface_outflux.py`, `tests/integration/test_phase3_surface_blowout.py` を「los_factor>1 で κ_eff/β_eff・M_out_dot が減る」期待に合わせる。`tau_gate` が LOS を見ることもカバー。
7. **ドキュメント**: `analysis/equations.md` に τ_vert/τ_los と f_los 式を追記し、`overview.md`/`assumption_trace.md`/μ 定義を LOS 基準に更新。DocSync→doc-tests→evaluation_system の手順を実行。
