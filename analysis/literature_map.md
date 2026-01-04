# literature_map (A-priority only)

本ファイルは、火星月形成円盤モデルに直接関わる「最重要（A優先）」文献だけをまとめた対応表です。どの論文をどの目的で参照するかを固定し、スライド自動生成や AI ガイダンスの土台とします。数式は `analysis/equations.md` を参照してください。

| lit_id | citation_short | year | category | status | priority | audience | math_level | origin | role_ja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hyodo2017a | Hyodo et al. 2017, ApJ 845, 125 | 2017 | impact-disk:SPH-ICs | reference-only | A | me+ai | full | Impact origin I | 巨大衝突 SPH から円盤質量・角運動量・温度など初期条件を与える基礎論文。gas-poor 前提や初期質量スケールの根拠として採用する。 |
| Hyodo2017b | Hyodo et al. 2017, ApJ 851, 122 | 2017 | impact-disk:evolution | reference-only | A | me+ai | full | Impact origin II | 衝突後の円盤進化と衛星成長を追うモデル。0D 近似の適用範囲や拡散時間との比較に使う背景シナリオ。 |
| Pignatale2018 | Pignatale et al. 2018, ApJ 853, 118 | 2018 | impact-disk:composition | reference-only | A | me+ai | full | Impact origin III | 衝突円盤内での蒸気・溶融物からの凝縮組成を計算する論文。粒子密度や揮発性元素の扱いを決める際の組成モデルとして参照する。 |
| Ronnet2016 | Ronnet et al. 2016, ApJ 828, 109 | 2016 | impact-disk:condensation | reference-only | A | me+ai | light | extended gaseous disk | 外縁に広がるガス円盤での凝縮が衛星性質を再現しうることを示す。ガス圧・温度構造と粒径スケールの整合性チェックに用いる。 |
| Hyodo2018 | Hyodo et al. 2018, ApJ 860, 150 | 2018 | impact-disk:volatile-loss | reference-only | A | me+ai | full | Impact origin IV | 高温円盤での揮発性蒸気や微小ダストの脱出・放射圧損失を評価する。β や gas-poor 前提の妥当性を検討する土台とする。 |
| Kuramoto2024 | Kuramoto 2024, review | 2024 | review:origin-scenarios | reference-only | A | me | light | Mars moons origin review | 火星衛星の起源シナリオを総覧し、gas-poor と gas-rich の位置付けを整理する総説。標準前提の説明や感度試験の枠組みに使う。 |
| CanupSalmon2018 | Canup & Salmon 2018, SciAdv 4, eaar6887 | 2018 | impact-disk:mass-gas-constraints | reference-only | A | me+ai | light | low-mass gas-poor disk | Phobos/Deimos を残すには低質量・低ガス円盤が必要と示す。gas-poor を標準とする根拠と初期質量上限の制約に用いる。 |
| TakeuchiLin2003 | Takeuchi & Lin 2003, ApJ 593, 524 | 2003 | gas-disk:surface-outflow | partial | A | me+ai | full | TL2003 surface outflow | 光学的に厚いガス円盤の表層ダスト外流を与える TL2003 方程式の出典。gas-rich 感度試験でのみ有効化するオプションモードの根拠として使う。 |
| StrubbeChiang2006 | Strubbe & Chiang 2006, ApJ 648, 652 | 2006 | debris-disk:collisional-outflow | implemented | A | me+ai | full | collisional cascade + outflow | PR drag と blow-out 時間尺度、Smol カーネルの e,i スケーリング整合確認に使う。Wyatt 型 t_coll とも突き合わせる。 |
| Wyatt2008 | Wyatt 2008, ARA&A 46, 339 | 2008 | debris-disk:collisional-timescale | reference-only | A | me+ai | light | collisional lifetime scaling | Wyatt型 $t_{\rm coll}=1/(\Omega\tau)$ 近似の出典。Smol カーネル時の比較・表層 ODE (S1) の参照に利用。 |
| IdaMakino1992 | Ida & Makino 1992, Icarus 96, 107 | 1992 | planetesimal-dynamics:velocity-dispersion | reference-only | A | me+ai | light | e–i relation in low-e regime | 低離心率の $\langle e^{2}\rangle=2\langle i^{2}\rangle$ 関係を与える一次文献。相対速度近似の前提整理に用いる。 |
