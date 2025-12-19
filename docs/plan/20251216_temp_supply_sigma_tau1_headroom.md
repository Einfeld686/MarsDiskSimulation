# temp_supply_sweep: Sigma_tau1 による供給クリップ事象まとめ

> **作成日**: 2025-12-16  
> **状況**: 共有メモ（原因整理＋対応方針）

---

## 背景：本プロジェクトについて

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](../../analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](../../analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](../../analysis/run-recipes.md)

### 用語定義

| 用語 | 意味 | 参考式 |
|------|------|--------|
| $\Sigma_{\tau=1}$ (`sigma_tau1`) | 光学的深さ τ = 1 となる臨界面密度。$\kappa_{\rm eff}^{-1}$ として計算される | (E.016), (E.017) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。表層がτ=1を超えないための「余裕」 | (E.031) |
| `prod_subblow_area_rate` | ブローアウト未満に破砕で供給される面積率 $\dot{\Sigma}^{(<a_{\rm blow})}_{\rm prod}$ | (E.027), (E.035) |
| **shielding.mode** | 遮蔽モード。`psitau`=Φテーブル適用、`fixed_tau1`=固定τ=1、`off`=無効 | [schema.py#Shielding](../../marsdisk/schema.py) |
| $\Phi(\tau)$ | 自遮蔽係数（放射輸送補正）。光学的に厚い層での吸収低減を近似 | (E.015), (E.017) |

### 本ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・振り返りを管理します。本メモは **temp_supply_sweep スイープ実行中に発生した供給クリップ現象**の調査結果と対応方針をまとめたものです。

---

## 何が起きたか
- 対象: `/Volumes/KIOXIA/marsdisk_out/temp_supply_sweep/20251212-222756__36a427291__seed599704065/T6000_mu1p0_phi20`
- 現象: `prod_subblow_area_rate` が
  - 実行開始〜約260 s のみ ~1.0e-2 kg m^-2 s^-1 で立ち上がり、
  - その後 3.4e6 s（約39.4日）まで 0 に張り付く。
  - 3.40544e6 s で `mass_lost_surface_solid_marsRP_step` が 1.07e-5 M_Mars 増え、`Sigma_surf` が 0 → 0.075 kg/m^2 へリセットされた直後に供給が再開（~3.7e-3 kg m^-2 s^-1）。以降は正のまま推移。
- 供給レートの実効値が跳ねるのは raw const (=3.0e-3) ではなく、温度スケール（T=6000 K → ~3.33）、フィードバックスケール（初期 ~1.0, 再開時 ~0.42）が乗算されているため。

## 原因（推定）
- `shielding.mode=fixed_tau1` かつ `shielding.fixed_tau1_sigma=30000` により、開始直後に `Sigma_surf` が Στ=1 上限へ達し headroom=0 になる。
- Smol 側で headroom に応じて供給をクリップする実装があり、`sigma_tau1` が効いていると `prod_subblow_area_rate` を 0 に落とす。[marsdisk/physics/collisions_smol.py:308–352]
- 3.4e6 s 時点で表層質量が Mars RP ブローアウトで一気に失われ、`Sigma_surf` がほぼ 0 になったことで headroom が復活し、供給が再び通る。
- これはスクリプトの想定（const 供給）ではなく、`Sigma_tau1` を固定・小さくしたことによるクリップが支配している。

## 影響
- 供給ゼロの期間が長く、`prod_subblow_area_rate` の平均値・プロットが「初期スパイク＋再開時ジャンプ」に見える。
- run_config の `effective_prod_rate_kg_m2_s` には raw const×epsilon_mix の値が記録されるが、時系列では headroom 依存で大きく乖離する。
- 評価スクリプト（例: `evaluate_tau_supply.py`）を回しても、供給維持条件を満たしにくい。

## 対応案
- スクリプト側で headroom を確保する設定を既定にする:
  - `shielding.fixed_tau1_sigma` を大きくするか `auto/auto_max` をデフォルトに戻す。
  - `init_tau1.scale_to_tau1=true` を常に付与し、初期 Σ を Στ=1 以下にクランプ。
- 供給スケールのばらつきを抑える:
  - 一定供給を確認したい run では `SUPPLY_TEMP_ENABLED=0` `SUPPLY_FEEDBACK_ENABLED=0` を推奨（環境変数）。
  - それでも温度スケールを使う場合は `supply.temperature.cap` の確認とログ出力を強制。
- ログ強化:
  - 実効供給（raw×epsilon_mix×temperature×feedback）と headroom (=Sigma_tau1 - Sigma_surf) を冒頭で echo。
  - `Sigma_tau1` と `init_tau1.scale_to_tau1` の採用値を run_config かコンソールに明示。

## 直近タスク（提案）
- [x] `run_temp_supply_sweep.sh` のデフォルトを `SHIELDING_SIGMA=auto`, `INIT_SCALE_TO_TAU1=true` に戻す。
- [ ] 温度・フィードバックをオフにするデモ用のプリセット（環境変数例示）を README に追記。
- [x] 供給クリップが起きた場合に警告を出す（`prod_subblow_area_rate_raw>0 && prod_subblow_area_rate==0` が一定連続したら warn）。
- [ ] 本事象の経緯を `docs/plan/README.md` から本メモにリンク。

## 今回の修正（2025-12-13）
- `run.parquet` に `supply_rate_nominal/scaled/applied` と `supply_headroom`・`supply_clip_factor` を追加し、`summary.json`/`run_config.json` で headroom・clip_factor の min/median/max と「scaled>0 なのに applied==0 だった時間割合」を追跡できるようにした。
- 連続して `supply_rate_scaled>0` かつ `applied==0` が続くと warn を出し、ログに time・Sigma_surf・Sigma_tau1・headroom・温度/フィードバックスケールを必ず含める。初期 headroom も起動時に一行でログ出力する。
- `run_temp_supply_sweep.sh` のデフォルトで温度スケールを無効化し（feedback は従来どおり off）、起動時に有効な倍率・遮蔽設定を echo。クイックプロットに supply 内訳と headroom/clip factor を載せ、summary の clip 時間割合をタイトルに含めた。
## 参考
- 対象 run: `/Volumes/KIOXIA/marsdisk_out/temp_supply_sweep/20251212-222756__36a427291__seed599704065/T6000_mu1p0_phi20`
- 実装ヘッドルーム判定: [marsdisk/physics/collisions_smol.py:308–352]
- Στ=1 固定の適用箇所: [marsdisk/run.py:2290–2345]
