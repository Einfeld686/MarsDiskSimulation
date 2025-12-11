# ADR-0002: Gas-Poor Disk Assumption

## Status
Accepted

## Context
火星月形成シミュレーションでは、衝突起源円盤のガス/蒸気成分の扱いが物理モデルの選択に大きく影響する。

文献レビューの結果:
- [@Hyodo2017a_ApJ845_125; @Hyodo2018_ApJ860_150]: 巨大衝突後の円盤は溶融主体で蒸気は数%以下
- [@CanupSalmon2018_SciAdv4_eaar6887]: 小衛星を残すには低質量・低ガスの円盤条件が必要
- 初期周回で揮発成分は散逸しやすい

一方、[@TakeuchiLin2003_ApJ593_524] の表層ダストアウトフロー式は光学的に厚いガス円盤を前提としており、gas-poor 条件には適用外。

## Decision
**gas-poor（ガス希薄）を既定の前提とする。**

具体的には:
1. `radiation.ALLOW_TL2003 = false` を既定とし、TL2003 型表層アウトフローは無効化
2. `sinks.enable_gas_drag = false` としガス抗力を既定で無効化
3. gas-rich 感度試験を行う場合のみ明示的に有効化（`ALLOW_TL2003=true`）

## Consequences
### Positive
- 火星月形成の物理的条件により適合した既定設定
- 不要な計算パスを省略し、シミュレーション効率向上
- 結果の解釈が明確（ガス影響を含まない）

### Negative
- gas-rich 条件での比較研究には明示的な設定変更が必要
- TL2003 コードパスのテストカバレッジ維持が追加作業に

### Neutral
- 将来の 1D 拡張時にも同じ前提を維持するか再評価が必要

## References
- `analysis/equations.md` の冒頭注記
- `analysis/overview.md` の gas-poor 注記
- `analysis/assumption_trace.md#sublimation_gasdrag_scope_v1`
