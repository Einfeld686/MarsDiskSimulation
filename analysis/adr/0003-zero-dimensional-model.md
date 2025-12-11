# ADR-0003: Zero-Dimensional Model Selection

## Status
Accepted

## Context
火星月形成円盤のシミュレーションでは、空間次元の選択が計算コストと物理的忠実度のトレードオフに直結する。

### 選択肢
1. **0D（one-zone）**: 代表半径での局所的な時間発展を追跡
2. **1D（radial）**: 半径方向の分布を解像
3. **2D/3D（full）**: 空間構造を完全に解像

### 0D を選択した理由
- [@Wyatt2008; @CridaCharnoz2012_Science338_1196] のレビューで、狭いリングを代表半径で扱う手法は確立されている
- 火星ロッシュ半径付近の内側リングは幅が限られており、0D 近似が妥当
- PSD 進化（Smoluchowski）と放射圧・衝突・昇華の相互作用を高時間分解能で追跡可能
- 1D/2D への拡張は設計上分離されており、0D コアを再利用可能

## Decision
**0D（one-zone）モデルを既定とする。**

具体的には:
1. `disk.geometry.r_in_RM` / `r_out_RM` で環状領域を指定
2. 内部的に代表半径 `r_m` を算出してケプラー諸量を評価
3. 空間積分は行わず、面密度の時間発展のみを追跡
4. レガシーの `geometry.r` / `runtime_orbital_radius_rm` は廃止

## Consequences
### Positive
- 計算コストが低く、パラメータ空間のスイープが容易
- PSD 進化の詳細な時間分解能を確保
- コードベースがシンプルで保守しやすい

### Negative
- 半径方向の質量輸送や勾配効果を捕捉できない
- 異なる半径ゾーン間の相互作用は無視される
- 1D 拡張時に 0D 前提の式にタグ付けが必要

### Neutral
- `scope.region` 設定で将来の 1D/multi-zone を想定した設計を維持

## References
- `analysis/assumption_trace.md#radius_fix_0d_scope_v1`
- `analysis/equations.md` の E.001, E.002 (0D 前提)
- `AGENTS.md` の完成条件（0D 時間発展が主要機能）
