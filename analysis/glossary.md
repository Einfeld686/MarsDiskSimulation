このファイルはプロジェクト固有の用語と記法の単一グロッサリであり、LLM と自分自身の両方が同じ短い定義・参照先を使うためのもの。数式は `analysis/equations.md` を参照するだけで再掲しない。

許可される値:
- category: `physics-concept`, `numerical-parameter`, `code-object`
- audience: `me`, `expert-colleague`
- math_level: `no-equations`, `light-equations`, `full-derivation`
- status: `stable`, `draft`

| term | category | audience | math_level | origin | status | definition | anchors |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gas-poor disk | physics-concept | me | light-equations | REF_HYODO2017A | stable | 蒸気≲数% を前提にした薄いガス円盤シナリオ。 | E.013 |
| TL2003 torque | physics-concept | expert-colleague | light-equations | REF_TAKEUCHI2003 | draft | gas-rich 条件で表層流出を与えるトルク項。 | E.017 |
| Roche limit (Mars) | physics-concept | me | light-equations | REF_CANUP2018 | draft | 火星ロッシュ境界内での衛星形成が制限される距離。 | analysis/overview.md |
| blow-out time t_blow | numerical-parameter | me | full-derivation | analysis/equations.md | stable | β=0.5 粒子が飛び去るまでの代表時間尺度。 | E.014 |
| β (lightness parameter) | numerical-parameter | me | full-derivation | analysis/equations.md | stable | 放射圧と重力の比、0.5 で吹き飛び境界。 | E.013 |
| wavy_strength | numerical-parameter | expert-colleague | light-equations | RUN_WAVY_PSD_v01 | draft | PSD のジグザグ度合いを制御する無次元パラメータ。 | E.035 |
| IMEX-BDF(1) stepper | code-object | expert-colleague | full-derivation | marsdisk/physics/smol.py | draft | Smol 方程式で loss 陰・gain 陽の一次 BDF 更新を行う解法。 | E.010,E.011 |
