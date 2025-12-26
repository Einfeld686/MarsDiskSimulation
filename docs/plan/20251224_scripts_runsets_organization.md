# scripts 整理計画: runsets 方式

**作成日**: 2025-12-24  
**ステータス**: 提案  
**対象**: `scripts/` 配下の実行ラッパ整理（1D が主、0D は検証用）

---

## 目的

- 実行ラッパを OS/用途で整理し、再現性と運用性を上げる。
- **1D を標準運用**とし、**0D は検証用（短時間チェック/CI）**に限定する。
- 物理設定の単一ソースは `configs/` に残し、`scripts/` は実行条件を担う。

---

## 参照スクリプト（現行）

- `scripts/research/run_temp_supply_sweep.sh`: 環境変数 + `--override` を使ったスイープ実行。
- `scripts/research/run_temp_supply_sweep_1d.sh`: 1D の既定値を付与する薄いラッパー。

上記の「**共通ランナー + 1D ラッパー**」構成を踏襲する。

---

## 方針

1. `scripts/` 直下は増やさず、`runsets/` に実行入口を集約する。
2. 1D は `run_1d_*` を基準にし、0D は `run_0d_verify*` に限定する。
3. OS 依存（.sh/.cmd、環境変数、ストレージ選択）は `runsets/<os>/` に閉じる。
4. `configs/` に物理パラメータを固定し、`runsets` は **実行条件のみ**を上書きする。

---

## 提案ディレクトリ構成

```
scripts/
  runsets/
    common/
      README.md                 # runsets の方針と共通変数一覧
      sweep_env.txt             # --override で使う共通スイッチ例（任意）
    mac/
      run_1d_sweep.sh           # 1D sweep 本命
      run_1d_single.sh          # 1D 単発
      run_0d_verify.sh          # 0D 検証用
    windows/
      run_1d_sweep.cmd
      run_1d_single.cmd
      run_0d_verify.cmd
```

> 既存の `scripts/research/run_temp_supply_sweep*.{sh,cmd}` は「共通ランナー」として残し、
> `runsets/*` から呼び出す形を基本とする。

---

## 実行フロー（想定）

1. `runsets/<os>/run_1d_sweep.*` が **1D 既定値**を設定  
   - `GEOMETRY_MODE=1D`, `GEOMETRY_NR=...`, `SWEEP_TAG=...` など
2. `runsets/<os>/run_1d_sweep.*` が `scripts/research/run_temp_supply_sweep.*` を呼ぶ  
   - `BASE_CONFIG` は `configs/` 側の 1D 基準 YAML を参照
3. `runsets/<os>/run_0d_verify.*` は 0D 検証用の最小条件のみを上書き  
   - 1D を壊さないため、0D 実行は明示的に分離

---

## 具体的な役割分担（例）

- **共通ランナー**: `scripts/research/run_temp_supply_sweep.sh`
  - sweep ループ、環境変数解釈、出力ディレクトリ規約
- **1D ラッパー**: `scripts/runsets/mac/run_1d_sweep.sh`
  - 1D 既定値、OS 依存の I/O 設定（外部 SSD、streaming）
- **0D 検証**: `scripts/runsets/mac/run_0d_verify.sh`
  - `GEOMETRY_MODE=0D` + 短時間 `T_END_SHORT_YEARS` など最小限

---

## 移行ステップ（案）

1. `scripts/runsets/` を新設し、OS 別の薄いラッパーを追加
2. 1D 既定値は `run_temp_supply_sweep_1d.sh` の内容を移植
3. 0D は **検証専用スクリプト**として明示分離
4. `scripts/README.md` に runsets の導線のみ追記（本体は変更しない）

---

## 非スコープ

- 物理モデル・式の変更
- `configs/` の大規模再配置
- `analysis/` の更新

---

## 完了条件

- 1D 実行は `scripts/runsets/<os>/run_1d_*` から完走できる
- 0D は `run_0d_verify*` のみで実行され、運用上の誤使用が減る
- 既存の `run_temp_supply_sweep*` は「共通ランナー」として機能し続ける
