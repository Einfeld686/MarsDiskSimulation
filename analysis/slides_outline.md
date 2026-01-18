このファイルは、`analysis/thesis/introduction.md` と `analysis/thesis/methods.md` を可視化するためのスライド骨格を定義する。数式は `analysis/equations.md`、詳細実装は `analysis/overview.md` を唯一のソースとし、ここではスライド単位の目的と参照先のみを保持する。

## 構成方針

- **S01–S07**: `introduction.md` の背景・目的・主要物理過程を可視化
- **S08–S11**: `methods.md` の数値手法・設定・検証を可視化
- **S12**: まとめと今後

聴衆に応じて S08–S11（手法詳細）を省略または追加可能。

---

## スライドセット（12 枚構成）

| slide_id | title | source_section | type | goal | key_points | eq_refs | fig_refs | run_refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 火星衛星 Phobos・Deimos の謎 | intro §1.1 | framing | 2つの衛星の起源問題と仮説を一目で示す | 捕獲 vs 巨大衝突仮説の対比表; 軌道特性（ほぼ円軌道、赤道面）が巨大衝突を示唆; Rosenblatt 2011, [@CanupSalmon2018_SciAdv4_eaar6887]| - | - | - |
| S02 | 巨大衝突と Gas-poor 円盤 | intro §1.2-1.3 | background | gas-poor 前提の根拠を整理する | intro §1.2 の Mermaid フロー図を転用; Hyodo+2017/2018 の蒸気比≲数%; TL2003 が適用外の理由 | - | - | RUN_MARS_GASPOOR_v01 |
| S03 | 研究目的と主要出力 | intro §2 | goal | シミュレーションで何を計算するかを明示 | 4つの物理過程リスト; 主要出力テーブル（Ṁ_out, M_loss, PSD, a_blow）; 2年間の質量損失履歴 | - | - | RUN_TEMP_SUPPLY_SWEEP_v01 |
| S04 | 放射圧ブローアウト | intro §3.1 | physics | β と a_blow の定義とパラメータ依存性 | β 式を図示; β > 0.5 → 脱出; T_M, ⟨Q_pr⟩, ρ の影響; Burns+1979, [@StrubbeChiang2006_ApJ648_652]| E.013,E.014 | FIG_BETA_SERIES_01 | RUN_TEMP_DRIVER_v01 |
| S05 | 衝突カスケード | intro §3.2 | physics | Smoluchowski 方程式と衝突寿命の概要 | Smoluchowski 式の直感的説明; K_ij（断面積×速度）と Y_kij（破片分配）; t_coll = 1/(Ωτ) | E.006,E.010 | - | RUN_WAVY_PSD_v01 |
| S06 | 昇華と自遮蔽 | intro §3.3-3.4 | physics | 高温環境での質量損失と光学的厚さの効果 | HKL 式と p_sat; gas-poor では P_gas ≈ 0; Σ_surf ≤ Σ_{τ=1} クリップ | E.015,E.016,E.017,E.018 | FIG_SHIELDING_SERIES_01 | - |
| S07 | 物理過程の相互作用 | intro §4 | model | 全体フローを俯瞰図で示す | intro §4 の ASCII 図をビジュアル化した Mermaid flowchart; 衝突→供給→相判定→シンク→収支の流れ | - | - | - |
| S08 | 数値手法: IMEX + PSD グリッド | methods §1-3 | methods | IMEX-BDF(1) と対数ビン設計 | 陰的（損失）/陽的（生成）分離; Δt ≤ 0.1 t_coll; n_bins=40, s∈[1μm,3m] | E.010,E.011 | - | - |
| S09 | カーネル・放射・遮蔽 | methods §4-6 | methods | 衝突強度と放射圧テーブルの設計 | Q_D* の速度外挿（LS09）; ⟨Q_pr⟩ テーブル補間; Φ(τ) テーブルとクリップ | E.024,E.026 | - | - |
| S10 | 温度・相・供給 | methods §7-9 | methods | 温度ドライバと供給経路の設定 | slab 冷却モデル T∝t^(-1/3); deep_mixing + t_mix_orbits; ε_mix パラメータ | E.027,E.042,E.043 | FIG_SUPPLY_SURFACE | RUN_TEMP_SUPPLY_SWEEP_v01 |
| S11 | 検証と実行 | methods §10-11 | verification | 検証手順と代表コマンド | DocSync + doc-tests; mass_budget 誤差 ≤ 0.5%; run-recipes 参照 | E.011 | - | RUN_TEMP_SUPPLY_SWEEP_v01 |
| S12 | まとめと今後 | intro §6 | discussion | 研究の位置づけと限界・展望 | 質問への回答（M_loss, 輸送量, 時間スケール）; MMX への期待; 未実装物理 | - | - | - |

---

## 凡例

- **source_section**: 参照元のセクション（intro = introduction.md, methods = methods.md）
- **type**: framing / background / goal / physics / model / methods / verification / discussion
- **eq_refs**: analysis/equations.md の E.xxx
- **fig_refs**: analysis/figures_catalog.md の FIG_*
- **run_refs**: analysis/run_catalog.md の RUN_*

---

## 派生スライド（オプション）

| slide_id | title | purpose | insert_after |
| --- | --- | --- | --- |
| S07a | 供給輸送モード (direct) | run_sweep 既定（direct）の外観（physics_flow.md §5.1 を転用） | S07 |
| S10a | パラメータスイープ結果 | temp_supply_sweep の M_loss ヒートマップ | S10 |
| S11a | τ≈1 維持条件 | evaluate_tau_supply.py の成功判定ロジック | S11 |

---

## メモ

- このファイルは手編集のみ（自動生成禁止）。増やす場合も既存 ID を変えずに S13 以降または派生スライド（S07a 等）を追加する。
- eq_refs は必ず `analysis/equations.md` の E.xxx のみを列挙し、式を再掲しない。
- fig_refs/run_refs は `analysis/figures_catalog.md` / `analysis/run_catalog.md` と 1:1 対応させる。
- introduction.md と methods.md の該当節を notes に明示し、読む順番の誘導に使う。
