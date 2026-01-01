# PSD 正規化ガードレール検討メモ

> **文書種別**: 検討メモ（Diátaxis: Explanation）

本文書は、粒径分布（PSD）の数値オーバーフロー問題とその対策を検討するメモです。**火星月形成円盤シミュレーション**（[analysis/overview.md](file://analysis/overview.md)）のコンテキストで、PSD 状態変数の不安定化がシミュレーション全体に波及する問題の原因と対策を整理します。

---

## 用語定義

| 用語 | 説明 | 関連コード・式 |
|------|------|----------------|
| **PSD** (Particle Size Distribution) | 粒径分布。各サイズビンの粒子個数 `number` を保持する状態辞書 `psd_state` で表現 | [psd.py#update_psd_state](file://marsdisk/physics/psd.py#L43-L131) |
| **κ (kappa)** | 質量不透明度 [m² kg⁻¹]。PSD から面積/質量比として計算 | [psd.py#compute_kappa](file://marsdisk/physics/psd.py#L134-L159), (E.015) |
| **κ_eff** | 有効不透明度。自遮蔽係数 Φ を掛けた補正後の κ | [shielding.py#effective_kappa](file://marsdisk/physics/shielding.py#L81-L120), (E.015) |
| **Σ_τ=1** | 光学深度 τ=1 となる表層面密度 [kg m⁻²]。κ_eff の逆数 | [shielding.py#sigma_tau1](file://marsdisk/physics/shielding.py#L123-L130), (E.016) |
| **τ** | 光学深度（無次元）。遮蔽判断やクリップに使用 | (E.017), [glossary.md](file://analysis/glossary.md) |
| **wavy PSD** | 衝突カスケードで生じる波状の粒径分布パターン | [equations.md#E.010](file://analysis/equations.md) |

> **参考**: 用語の詳細は [analysis/glossary.md](file://analysis/glossary.md) を参照してください。

---

## 関連するコードと式

- **PSD 状態管理**: `psd_state` 辞書は `sizes`, `widths`, `number`, `rho` 等を保持し、[update_psd_state](file://marsdisk/physics/psd.py#L43-L131) で初期化・更新
- **不透明度計算**: [compute_kappa](file://marsdisk/physics/psd.py#L134-L159) は `number` 配列から質量不透明度を算出
  ```
  κ = ∫ π s² n(s) ds / ∫ (4/3) π ρ s³ n(s) ds
  ```
- **自遮蔽と τ=1 クリップ**: (E.015)–(E.017) で定義される遮蔽処理。κ_eff = Φ(τ) κ_surf から Σ_τ=1 = 1/κ_eff を算出
- **サイズドリフト**: [apply_uniform_size_drift](file://marsdisk/physics/psd.py#L283-L398) で昇華による粒径縮小を処理

---

## 背景と課題
- `T5000_mu1p0_phi20` 実行で `psd_state.number` が 1e279〜1e308 に膨張し、t≈5.58584e6 s に全ビン 0 へリセット。その後 κ_surf→κ_eff が 2e-13 付近まで崩落し、`Sigma_tau1≈5e12` で τ が立たなくなった。
- Φテーブル（phi_const_0p20）や Planck Q_pr/温度は原因でない（テスト済み）。崩壊は `number` のオーバーフロー→ゼロ化が直接のトリガ。
- `compute_kappa` は `number` をそのまま面積・質量比に使うため、`number` が壊れると κ がゼロ付近に落ちて Σ_tau1 が暴走する。

## どのタイミングで正規化するか（案）
1. **各PSD更新直後**: 供給・破砕・サイズドリフト `apply_uniform_size_drift` の各ループ終了時に、`number` の桁崩れを検査し質量整合でリスケール。閾値（例: max(number)>1e50, 非有限）を超えたときのみ発火する軽量ガード。
2. **周期サニティチェック**: Nステップごと（10^3–10^4目安）に総質量と number の範囲を確認し、異常時のみ正規化。大規模ランでの負荷抑制策。

## 何を基準に正規化するか（案）
- **表層質量整合**: 現在の `Sigma_surf` とビン幅・ρから期待質量を計算し、その比で `number` をスケーリング（質量保存との整合が取りやすい）。
- **質量分率ベース**: `number` の代わりに質量分率で保持し、κ計算時に面積/質量へ変換。API変更が大きいので段階導入が必要。
- **クリップ併用**: 上限（例: 1e50）と下限（0未満→0）を設定し、発火時に警告を残す。下限は `KAPPA_MIN` に対応する Σ_tau1 から逆算してもよい。

## psd_hist の扱い
- 現状は `psd_state.number` をそのまま `N_bin` として書き出しており、解析時に桁外れ・全ゼロが混入する。
- 改善案: `N_bin` を質量分率またはビン面密度 `Sigma_bin`（kg/m^2）に換算して出力し、数密度そのものはデバッグ用に別カラムへ分離。単位を明示する。

## 実装優先順位（提案）
1. コア処理に「`number` 異常時の質量整合スケーリング＋クリップ」を追加（供給・破砕・サイズドリフト後）。
2. psd_hist の出力を質量分率/Σ_bin に変更し、number 生値を直接解析に使わないようにする。
3. 必要なら周期サニティチェックや閾値設定をチューニングし、負荷と安定性のバランスを取る。

## 補足（テストで確認したこと）
- Φテーブルはゼロ化せず、κ_eff=0.2κ 程度を維持（テーブル外 τ でも同様）。
- 通常の PSD（1e-6–3 m, q=3.5）や極端な大径単峰でも `compute_kappa` は 1e-12 まで落ちない。
- κ=2e-13 だと Σ_tau1 >1e12 になり、ヘッドルーム無限大で τ が立たないことを再現済み。

---

## 参考資料

### 関連ドキュメント

- [analysis/equations.md](file://analysis/equations.md): 物理式の唯一の定義源（特に E.015–E.017 が関連）
- [analysis/overview.md](file://analysis/overview.md): モジュール責務とデータフローの概要
- [analysis/glossary.md](file://analysis/glossary.md): 用語定義と命名規約
- [analysis/physics_flow.md](file://analysis/physics_flow.md): 物理処理フローの mermaid 図

### 関連コード

| ファイル | 関数 | 役割 |
|----------|------|------|
| [marsdisk/physics/psd.py](file://marsdisk/physics/psd.py) | `update_psd_state` | 三勾配 PSD の初期化・更新 |
| [marsdisk/physics/psd.py](file://marsdisk/physics/psd.py) | `compute_kappa` | 質量不透明度 κ の算出 |
| [marsdisk/physics/psd.py](file://marsdisk/physics/psd.py) | `apply_uniform_size_drift` | 昇華による粒径縮小処理 |
| [marsdisk/physics/shielding.py](file://marsdisk/physics/shielding.py) | `effective_kappa` | 有効不透明度 κ_eff の計算 |
| [marsdisk/physics/shielding.py](file://marsdisk/physics/shielding.py) | `sigma_tau1` | Σ_τ=1 の算出 |

### 関連テスト

- [tests/integration/test_psd_kappa.py](file://tests/integration/test_psd_kappa.py): `compute_kappa` の単体テスト
- [tests/integration/test_opacity_guardrails.py](file://tests/integration/test_opacity_guardrails.py): 不透明度ガードレールのテスト

