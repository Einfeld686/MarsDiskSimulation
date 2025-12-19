# τクリップと供給ゲートの現状と課題（follow-up）

> 作成日: 2025-12-19  
> 区分: 調査メモ（τクリップ + 深部→表層混合の挙動整理）

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](../../analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](../../analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### 用語定義

本ドキュメントで使用される主な用語を以下に定義します：

| 用語 | 意味 | 参考式 |
|------|------|--------|
| $\Sigma_{\tau=1}$ (`sigma_tau1`) | 光学的深さ τ = 1 となる臨界面密度。$\kappa_{\rm eff}^{-1}$ として計算される | (E.016), (E.017) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。表層がτ=1を超えないための「余裕」。供給ゲートの開閉を決定する主要パラメータ | (E.031) |
| **τクリップ** | 表層面密度 $\Sigma_{\rm surf}$ が $\Sigma_{\tau=1}$ を超えないよう制限する処理 | (E.016), (E.017) |
| **供給ゲート (supply gate)** | headroom に応じて深部→表層への供給をオン/オフする制御機構 | — |
| `prod_subblow_area_rate` | ブローアウト未満に破砕で供給される面積率 $\dot{\Sigma}^{(<a_{\rm blow})}_{\rm prod}$ | (E.027), (E.035) |
| `supply_rate_applied` | headroom クリップ後に実際に表層へ適用された供給率 | — |
| **shielding.mode** | 遮蔽モード。`psitau`=Φテーブル適用、`fixed_tau1`=固定τ=1、`off`=無効 | [schema.py#Shielding](../../marsdisk/schema.py) |
| **shielding.fixed_tau1_sigma** | `fixed_tau1` モード時に使用する $\Sigma_{\tau=1}$ の固定値。`auto` で自動決定 | — |
| **deep_mixing** | 深部→表層の物質輸送モード。`t_mix_orbits` で混合時定数を指定 | [supply.py](../../marsdisk/physics/supply.py) |
| **hard gate** | headroom がゼロの場合に供給を完全遮断する現行ゲート方式（soft gate は未実装） | — |
| $\Phi(\tau)$ | 自遮蔽係数（放射輸送補正）。光学的に厚い層での吸収低減を近似 | (E.015), (E.017) |
| **init_tau1.scale_to_tau1** | 初期 $\Sigma_{\rm surf}$ を $\Sigma_{\tau=1}$ 以下にクランプするオプション | — |

### ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・振り返りを管理します。本メモは **τクリップと供給ゲートの現状整理および deep_mixing 挙動**に関する調査結果と対応方針をまとめたものです。

関連ドキュメント：
- [20251216_temp_supply_sigma_tau1_headroom.md](./20251216_temp_supply_sigma_tau1_headroom.md) — Σ_τ1 固定による供給クリップ事象の初回報告

---

## 背景
- 0D temp_supply_sweep 系で、`shielding.fixed_tau1_sigma=auto` と初期 Σ_surf がほぼ Σ_τ=1 に揃えられ、headroom ≈ 0 となるケースが多発。
- deep_mixing + hard headroom gate では headroom=0 だと供給が全量遮断され、`prod_subblow_area_rate` / `supply_rate_applied` が ほぼ 0 に張り付く。
- 直近の短時間テスト（`dt_init=0.5 s`, `t_end=5e-4 yr`, deep_mixing, t_mix_orbits=0.1）でも headroom=0 のまま供給 99.9% がブロックされ、M_out_dot は滑らかになる以前の問題だった。

## 現状（実装サマリ）
- τクリップ: `shielding.mode=psitau` かつ `fixed_tau1_sigma=auto` → κ_eff 逆数で Σ_τ=1 を決め、`init_tau1.scale_to_tau1` ありなら初期 Σ_surf をそこへクランプ。[marsdisk/run.py:2290–2345]
- 供給ゲート: Smol 側で headroom (=Σ_τ=1−Σ_surf) を dt で割った prod_cap と比較し、超過分をカット。[marsdisk/physics/collisions_smol.py:308–352]
- deep mixing: `supply.transport.mode=deep_mixing` で deep→surface を headroom で制限。`headroom_gate` は `"hard"` のみ実装・選択肢なし。

## 課題
1. 初期 headroom が 0 に近いと、混合時定数をどう設定しても供給が通らず、「律速」の設計意図を検証できない。
2. τクリップ値（Σ_τ=1）が自動決定かつ初期 Σ_surf と同値になりやすく、ユーザが「深部からじわじわ上がる」シナリオを作りにくい。
3. hard gate しかないため、わずかな headroom でも急峻にオン/オフし、M_out_dot のギザギザ原因を分離できない。

## 挙動の妥当性メモ
- **なぜ τ≲1 を見たいか**  
  放射圧ブローアウト層は「上端が光学的に薄い（τ≲1）」ことを仮定していて、Φ(τ) テーブルも τ→1 付近で外向きフラックスが最大になる描像に合わせている。表層をそれ以上厚くすると、放射圧が効かず outflux を過大評価する危険があるため、Σ_τ=1 を上限にした headroom 管理は物理的に安全側の選択。
- **const でも毎ステップ監視する理由**  
  const 供給は物理的には一定でも、実効レートは「raw const × ε_mix × 温度・フィードバック倍率」を時刻依存で掛ける。さらに headroom/dt を超えた分はシンクに逃がさず供給そのものを抑える設計にし、質量保存と τ≲1 を同時に守るために毎ステップで監視している。
- **現状の問題点**  
  “安全側” に振った結果、headroom=0 では供給が長時間ゼロになり、律速シナリオの比較ができない。安全性は保たれるが、パラメトリックスタディには向かない設定になりがち。

## 対応案
- **headroom を作る**（優先度高）
  - `shielding.fixed_tau1_sigma` を明示的に大きめ（例: 3e4 など）に設定し、`surface.init_policy=none` と `surface.sigma_surf_init_override` を Σ_τ=1 より十分小さく置く。
  - `init_tau1.scale_to_tau1=false` を一時的に試し、初期 Σ_surf をユーザ指定優先にする。
- **ソフト化・平滑化**
  - deep mixing の `t_mix_orbits` を 1–10 orbit 程度に引き上げ、供給を緩やかに表層へ戻す（headroom が確保されている前提）。
  - hard gate しかない点は仕様上の限界なので、将来的に soft gate 実装を検討（headroom に滑らかな係数を掛けるだけでも可）。
- **検証手順**
  - 上記設定で短区間（数時間〜数日相当）を再実行し、`prod_subblow_area_rate` / `supply_rate_applied` / `tau` を同プロットで確認。
  - headroom=0 が連続する割合をログ/summary で確認し、連続ブロック >90% なら警告を出す。

## すぐやるタスク（提案）
- [ ] 深層→表層律速のデモ用プリセットを追加（薄い初期 Σ + ゆるい τクリップ + deep_mixing）。
- [ ] run 設定サンプルに「headroom を意図的に確保する方法」を明記。
- [x] hard gate での連続ブロック率を summary に出すフックを追加（既存ログの警告を補完）。

## 参考

### 関連ドキュメント
- 先行メモ: [20251216_temp_supply_sigma_tau1_headroom.md](./20251216_temp_supply_sigma_tau1_headroom.md)（Sigma_tau1 固定で供給が長時間ゼロになった事例）
- 物理式の詳細: [analysis/equations.md](../../analysis/equations.md)
- シミュレーション実行方法: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- AI向け利用ガイド: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### コード参照
| 機能 | ファイル | 行範囲 |
|------|----------|--------|
| headroom クリップ実装 | [collisions_smol.py](../../marsdisk/physics/collisions_smol.py) | L308–352 |
| τ=1 初期化・自動決定 | [run.py](../../marsdisk/run.py) | L2290–2345 |
| deep_mixing 供給制御 | [supply.py](../../marsdisk/physics/supply.py) | `split_supply_with_deep_buffer()` |
| 遮蔽モード定義 | [schema.py](../../marsdisk/schema.py) | `Shielding` クラス |
