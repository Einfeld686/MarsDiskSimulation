# 外部供給スイープ導入メモ（run_temp_supply_sweep.sh）

> 目的: `scripts/research/run_temp_supply_sweep.sh` で新しい外部供給（temp_supply 系）を回す際に必要な環境変数・モード・注意点を 1 枚にまとめる。  
> 対象: temp_supply スイープの実行担当者（CI/手元どちらも）

---

## 背景と目的

本スクリプトは**火星月形成円盤**モデルにおける**外部質量供給**のパラメータ感度試験を自動化します。巨大衝突後の円盤に外部から物質が供給される状況をシミュレートし、光学的厚さ $\tau$ が $\tau=1$ を超えないよう遮蔽条件を適用しながら時間発展を追跡します。

### この文書で扱う物理
- **放射圧による質量損失（ブローアウト）**: 小粒径ダストは放射圧で系外へ吹き飛ばされる（式 [E.013](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E013), [E.014](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E014)）
- **外部供給（supply）**: 衝突破砕や外部起源で新たに粒子が注入されるモデル（式 [E.027](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E027)）
- **光学的遮蔽（shielding）**: 表層が $\tau=1$ を超えると供給がクリップされる（式 [E.015–E.017](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E015)）

詳細な数式定義は [`analysis/equations.md`](file:///Users/daichi/marsshearingsheet/analysis/equations.md) を参照してください。

---

## 主要用語の定義

| 用語 | 記号 | 意味 | 参照 |
|------|------|------|------|
| **光学深度** | $\tau$ | 表層の光学的厚さ。$\tau=1$ が遮蔽閾値 | [glossary](file:///Users/daichi/marsshearingsheet/analysis/glossary.md) |
| **表層面密度** | $\Sigma_{\rm surf}$ | 表層の質量面密度 [kg m⁻²] | E.007, E.025 |
| **τ=1 面密度** | $\Sigma_{\tau=1}$ | $\tau=1$ となる面密度上限 = $1/\kappa_{\rm eff}$ | E.016 |
| **混合効率** | $\epsilon_{\rm mix}$ | 供給率に乗じるスケール係数（0–1） | E.027 |
| **ヘッドルーム** | headroom | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$：追加供給可能な余地 | スクリプト内定義 |
| **吹き飛びサイズ** | $s_{\rm blow}$ | $\beta \geq 0.5$ となる粒径 [m] | E.014 |
| **放射圧比** | $\beta$ | 放射圧/重力比；0.5 超で粒子が脱出 | E.013 |
| **温度スケール** | temp_scale | 温度依存で供給率を調整する係数 | `supply.temperature.*` |
| **τ フィードバック** | feedback | $\tau$ 目標値に近づけるよう供給を制御 | `supply.feedback.*` |
| **深層混合** | deep_mixing | 供給を即座に表層へ入れず保留層を経由 | `supply.transport.mode` |

---

## 関連コードとスキーマ

| モジュール | 役割 |
|------------|------|
| [marsdisk/physics/supply.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/supply.py) | 外部供給率の計算（`get_prod_area_rate`, `_rate_basic`） |
| [marsdisk/physics/shielding.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/shielding.py) | 遮蔽と $\Sigma_{\tau=1}$ クリップ |
| [marsdisk/schema.py](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py) | YAML 設定のバリデーション（`Supply`, `Shielding` クラス） |
| [marsdisk/run.py](file:///Users/daichi/marsshearingsheet/marsdisk/run.py) | メイン実行ループ `run_zero_d` |

---

## 必須の前提・入力
- **ベース設定**: `BASE_CONFIG`（既定 `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`）を基準に環境変数で上書きする。
- **温度テーブル**: `data/mars_temperature_T{T}p0K.csv` が存在していること（T_LIST に合わせて 2000/4000/6000K を用意）。
- **遮蔽**: 既定は `shielding.mode=off`（Φ=1）。テーブルを使う場合のみ `shielding.table_path` を明示する。
- **出力ルート**: `OUT_ROOT` 未指定なら `out/`、外付け SSD があれば `/Volumes/KIOXIA/marsdisk_out` を既定にする。書き込み権限を確認。
- **仮想環境**: `.venv` が無ければ自動生成し、`requirements.txt` で依存を入れる前提。pyarrow 必須。

## 外部供給に関わる主要環境変数
- **供給モード/強度**:  
  - `SUPPLY_MODE`（既定 `const`）  
  - `SUPPLY_MU_ORBIT10PCT`（`mu_orbit10pct`）  
  - `SUPPLY_ORBIT_FRACTION`（`orbit_fraction_at_mu1`）  
  - `EPS_LIST` は epsilon_mix スイープ。実効レートは `mu_orbit10pct`×`orbit_fraction_at_mu1`×Σ_refで決まる。
- **遮蔽/初期化**:  
  - `SHIELDING_MODE`（既定 `off`）、`SHIELDING_SIGMA`（`fixed_tau1` 用）、`SHIELDING_AUTO_MAX_MARGIN`（既定 0.05）  
  - `TAU_LIST` または `OPTICAL_TAU0_TARGET` で初期 τ を指定。
- **リザーバ/フィードバック/温度スケール（オプション）**:  
  - `SUPPLY_RESERVOIR_M` 空で無効、指定時は `SUPPLY_RESERVOIR_MODE`（hard_stop/taper）、`SUPPLY_RESERVOIR_TAPER` を併用。  
  - `SUPPLY_FEEDBACK_ENABLED`=1 で τ フィードバック ON（target/gain/response/min/max/tau_field/initial を併せて設定）。  
  - `SUPPLY_TEMP_ENABLED`=1 で温度スケール ON（mode=scale/table、ref_K/exp/scale_at_reference/floor/cap、table_* を必要に応じて指定）。
- **注入レンジ・輸送・速度**:  
  - `SUPPLY_INJECTION_MODE`（min_bin/powerlaw_bins）、`SUPPLY_INJECTION_Q`、`SUPPLY_INJECTION_SMIN/SMAX`。  
  - `SUPPLY_TRANSPORT_MODE`（既定 deep_mixing）、`SUPPLY_TRANSPORT_TMIX_ORBITS`（既定 50）または `SUPPLY_DEEP_TMIX_ORBITS` エイリアス。  
  - `SUPPLY_TRANSPORT_HEADROOM`（hard/soft）でゲートを切替。  
  - `SUPPLY_VEL_MODE`（fixed_ei/inherit/factor）と e/i/factor/blend/weight で注入速度を制御。
- **ストリーミング/進捗**:  
  - `ENABLE_PROGRESS`（TTY で既定 ON）、`STREAM_MEM_GB`（io.streaming.memory_limit_gb）、`STREAM_STEP_INTERVAL`（step_flush_interval）を上書き可能。
- **評価フック**: `EVAL`=1 で `scripts/research/evaluate_tau_supply.py` を各ケース後に実行し、`checks/tau_supply_eval.json` を残す。

## 実行フロー上の注意点
- スクリプト内で必ず `--override supply.enabled=true` を付与するので、ベース設定が supply 無効でも外部供給が有効化される前提。  
- `run_temp_supply_sweep.sh` は `numerics.dt_init=20` を固定で上書きする。dt/t_blow が粗いケースでブローアウト補正やサブステップを使う場合はベース設定側で設定する。  
- deep_mixing を使うと headroom ゲート (`supply.transport.headroom_gate`) による遮断が起きやすい。`transport.t_mix_orbits` を必ず正に設定し、初期 τ は `optical_depth.tau0_target` で管理することを推奨。  
- 温度テーブルや（必要な場合のみ）遮蔽テーブルのパスを変えた場合、`run_config.json` に記録された path を確認して再現性を確保する。  
- 生成物は `out/temp_supply_sweep/<ts>__<sha>__seed<batch>/T{T}_eps{EPS}_tau{TAU}/` 配下に `series/run.parquet`, `summary.json`, `checks/`（mass_budget, オプションで tau_supply_eval）, `plots/*.png` が出る。ディスク容量を事前確認すること。

## 典型的な起動例
```bash
OUT_ROOT=/Volumes/KIOXIA/marsdisk_out \
SUPPLY_MU_ORBIT10PCT=1.0 SUPPLY_MODE=const \
SUPPLY_FEEDBACK_ENABLED=1 SUPPLY_FEEDBACK_TARGET=0.8 SUPPLY_FEEDBACK_GAIN=0.8 \
SUPPLY_TEMP_ENABLED=1 SUPPLY_TEMP_MODE=scale SUPPLY_TEMP_REF_K=1800 SUPPLY_TEMP_EXP=1.5 \
ENABLE_PROGRESS=1 EVAL=1 \
scripts/research/run_temp_supply_sweep.sh
```
上記は温度スケールと τ フィードバックを同時に有効化し、外付け SSD へ出力する例。プログレスバーは TTY のときのみ表示される。

---

## 出力ファイルの見方

各ケースの出力ディレクトリには以下のファイルが生成されます：

| ファイル | 内容 | 確認ポイント |
|----------|------|--------------|
| `series/run.parquet` | 全ステップの時系列データ | `supply_rate_applied`, `headroom`, `tau_vertical` |
| `summary.json` | 実行結果の集約 | `M_loss`, `supply_clip_time_fraction`, `case_status` |
| `run_config.json` | 実行時のパラメータ記録 | `physics_controls`, `supply` セクション |
| `checks/mass_budget.csv` | 質量収支検査ログ | `error_percent < 0.5%` |
| `checks/tau_supply_eval.json` | τ 安定性評価（`EVAL=1` 時） | 後述のパス/フェイル判定 |
| `plots/overview.png` | 質量損失と時間スケールの概観 | クリップ発生頻度 |
| `plots/supply_surface.png` | 供給率・表層密度・ヘッドルームの詳細 | `supply_clip_factor` が 1 未満の区間 |

### summary.json の主要キー

| キー | 意味 | 単位 |
|------|------|------|
| `M_loss` | 総質量損失（ブローアウト＋シンク） | M_Mars |
| `supply_clip_time_fraction` | 供給がクリップされた時間割合 | 無次元 |
| `tau_vertical` | 最終ステップの垂直光学深度 | 無次元 |
| `case_status` | 結果分類（`ok`, `blowout`, `no_blowout`） | 文字列 |
| `effective_prod_rate_kg_m2_s` | 実効供給率の平均 | kg m⁻² s⁻¹ |

詳細なカラム定義は [`analysis/AI_USAGE.md`](file:///Users/daichi/marsshearingsheet/analysis/AI_USAGE.md) の「出力ファイルの中身」を参照してください。

---

## 関連ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| [analysis/equations.md](file:///Users/daichi/marsshearingsheet/analysis/equations.md) | 全数式の定義（β, s_blow, 供給率, 遮蔽等） |
| [analysis/AI_USAGE.md](file:///Users/daichi/marsshearingsheet/analysis/AI_USAGE.md) | 実行手順と出力ファイルの解釈ガイド |
| [analysis/glossary.md](file:///Users/daichi/marsshearingsheet/analysis/glossary.md) | 用語集と変数命名規約 |
| [analysis/run-recipes.md](file:///Users/daichi/marsshearingsheet/analysis/run-recipes.md) | 標準的な実行レシピ集 |
| [AGENTS.md](file:///Users/daichi/marsshearingsheet/AGENTS.md) | プロジェクト全体の仕様と完成条件 |

---

## トラブルシューティング

| 症状 | 原因と対処 |
|------|------------|
| `supply_clip_factor` が常に 0 | ヘッドルームがゼロ。初期 Σ が Σ_τ=1 を超えている可能性。`INIT_SCALE_TO_TAU1=true` を確認 |
| `tau_vertical > 1` が継続 | 遮蔽テーブルパスが間違っている、または `shielding.mode` が正しくない |
| parquet 書き出し失敗 | `pyarrow` 未インストール。`pip install pyarrow` を実行 |
| プログレスバーが表示されない | TTY でない（リダイレクト先へ出力中）。`ENABLE_PROGRESS=1` でも無視される |
| 大量のディスク消費 | 高解像度スイープ。完了後に不要なケースを削除するか `OUT_ROOT` を外付けへ |
