# 粒子温度を用いた相判定の不足と対応案（run_temp_supply_sweep 系）

> 本メモは**粒子温度 $T_p$ と火星表面温度 $T_M$ の使い分け**が不十分なため、**相判定（液相/固相）にジッターが生じる**問題の原因と対策案を記録したものです。

---

## この文書で扱う物理

**火星月形成円盤**では、衝突直後の高温粒子が SiO₂ 液相から固相へ冷却する過程で、衝突カスケードや昇華の挙動が変化します。相判定の入力温度として粒子温度 $T_p$ ではなく火星表面温度 $T_M$ を使用すると、液相期間が過大評価され物理挙動が不正確になります。

### 関連する物理式
- **粒子温度スケール**: $T_p = T_M \times q_{\rm abs}^{0.25} \times \sqrt{R_M / (2r)}$（幾何学的距離と吸収効率による低温化）
- **放射圧効率**: $\langle Q_{\rm pr} \rangle$（式 [E.004](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E004)）
- **ブローアウト半径**: $s_{\rm blow}$（式 [E.014](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E014)）
- **昇華フラックス**: HKL 式（式 [E.018](file:///Users/daichi/marsshearingsheet/analysis/equations.md#E018)）

---

## 主要用語の定義

| 用語 | 記号 | 意味 | 参照 |
|------|------|------|------|
| **火星表面温度** | $T_M$ | 火星表面（熱源）の温度 [K] | E.013 |
| **粒子温度** | $T_p$ | ダスト粒子の平衡温度 [K]（$T_M$ より低い） | 本メモ |
| **吸収効率平均** | $q_{\rm abs,mean}$ | Planck 平均吸収効率（既定 0.4–1.0） | E.004 関連 |
| **相判定** | phase_state | 液相 / 固相 / 混合相の判定 | `phase.enabled` |
| **軌道半径** | $r$ | 粒子の公転半径 [m] または [R_M] | E.001, E.002 |
| **衝突カスケード** | — | 大粒子→小粒子の破砕連鎖（Smoluchowski） | E.010 |
| **昇華** | sublimation | 固相からの蒸発による質量損失 | E.018, E.019 |

---

## 関連コードとスキーマ

| モジュール | 役割 |
|------------|------|
| [siO2_disk_cooling/siO2_cooling_map.py](file:///Users/daichi/marsshearingsheet/siO2_disk_cooling/siO2_cooling_map.py) | `lookup_phase_state` 相判定関数 |
| [marsdisk/physics/tempdriver.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/tempdriver.py) | 温度ドライバ（$T_M$ テーブル／定数） |
| [marsdisk/physics/sublimation.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/sublimation.py) | 昇華フラックス（HKL 式） |
| [marsdisk/run.py](file:///Users/daichi/marsshearingsheet/marsdisk/run.py) | メインループ `run_zero_d`、相判定呼び出し |
| [marsdisk/schema.py](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py) | `Phase` 設定クラス |

---

## 背景
- `run_temp_supply_sweep.sh` は `phase.enabled=true` で実行し、`siO2_disk_cooling.siO2_cooling_map:lookup_phase_state` を相判定に用いる。
- 判定入力は「その場の温度」だが、現状は火星表面温度 `T_M(t)` をそのまま渡しており、粒子温度への幾何スケール `sqrt(R_M/(2r))` と吸収効率 `q_abs_mean^0.25` を掛けていない。
- `q_abs_mean` を 0.4 に引き下げたが、`T_M` テーブルと相判定は依然として `q_abs_mean` 非依存のまま。粒子温度 `T_p` の方が低い場合、液相継続を過大評価するリスクがある。

## 影響
- 相依存の挙動（例: 衝突カスケード/昇華の有効性）が `T_M` 基準で長めに液相判定される可能性。
- `T_p` を考慮するまでの間、液体期間が実際より長く記録される恐れがある。
- `siO2_disk_cooling` で生成済みの距離依存マップ／CSV（`siO2_cooling_map_T*.csv`）を phase 判定で参照しておらず、既存リソースを活用できていない。

## 対応オプション（要選択）
1. **簡易スケール適用**: `lookup_phase_state` を拡張し、`T_input = T_M × q_abs_mean^0.25 × sqrt(R_M/(2r))` に置換してから判定する。`r` と `q_abs_mean` を設定経由で渡せるようにする。
2. **テーブル駆動**: `siO2_disk_cooling` で `T_M → T_p(r)` のマップを生成し、相判定を粒子温度テーブル参照に切替。`q_abs_mean` 変更時はテーブル再生成。
3. **暫定停止**: 粒子温度対応が入るまで `phase.enabled` を false に戻し、液相/固相依存の分岐を無効化する。

## siO2_disk_cooling 再生成メモ（距離依存リソースを活用する場合）
- 粒子温度マップ（r 依存、q_abs_mean=0.4 反映）  
  - `python -m siO2_disk_cooling.siO2_cooling_map --T0 2000`  
  - `python -m siO2_disk_cooling.siO2_cooling_map --T0 4000`  
  - `python -m siO2_disk_cooling.siO2_cooling_map --T0 6000`  
  出力: `siO2_disk_cooling/outputs/siO2_cooling_map_T0*.csv` と `map_T0_*.png`（距離×時間の到達時刻・相マップ）。
- 火星表面温度テーブル（T_M のみ、r スケールなし）  
  - `marsdisk.physics.tempdriver.ensure_temperature_table` を使う。例:  
    ```python
    from pathlib import Path
    from marsdisk.schema import MarsTemperatureAutogen
    from marsdisk.physics.tempdriver import ensure_temperature_table
    autogen = MarsTemperatureAutogen(enabled=True, output_dir=Path("data"),
                                     dt_hours=1.0, min_years=2.0,
                                     time_margin_years=0.5, time_unit="day",
                                     column_time="time_day", column_temperature="T_K",
                                     model="slab")
    ensure_temperature_table(autogen, T0=4000.0, t_end_years=60.0, t_orb=1.0)
    ```
  - 出力: `data/mars_temperature_T4000p0K.csv` など（T_M 時系列）。
- オプション2を採用する場合、phase 判定で `siO2_cooling_map_T0*.csv` を読み、`q_abs_mean` 変更時に再生成するフローを `run_temp_supply_sweep.sh` 側で組み込む。オプション1/2を併用する場合は二重スケールを避ける。

## 推奨初手
- 影響を減らすため、オプション1で `r` を代表値（例: 1.7–2.4 R_M を設定／可変）としてスケール適用し、`q_abs_mean` を設定から注入できるようにする。並行してテーブル駆動（オプション2）の実装計画を詰める。

---

## 確認すべき出力項目

| ファイル | 確認項目 | 期待値 |
|----------|----------|--------|
| `summary.json` | `phase_state_final` | 液相/固相の妥当性 |
| `series/run.parquet` | `T_M_used`, `T_p_effective`（実装後） | $T_p < T_M$ |
| `run_config.json` | `phase.enabled`, `q_abs_mean` | 設定の再現性確認 |

---

## 関連ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| [analysis/equations.md](file:///Users/daichi/marsshearingsheet/analysis/equations.md) | Q_pr, β, 昇華 (E.004, E.013–E.019) の数式定義 |
| [analysis/AI_USAGE.md](file:///Users/daichi/marsshearingsheet/analysis/AI_USAGE.md) | 出力ファイルのカラム定義 |
| [analysis/glossary.md](file:///Users/daichi/marsshearingsheet/analysis/glossary.md) | 用語集と変数命名規約 |
| [AGENTS.md](file:///Users/daichi/marsshearingsheet/AGENTS.md) | SiO₂ Disk Cooling シミュレーションの記述 |
