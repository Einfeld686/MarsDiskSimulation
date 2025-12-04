# glossary (A-priority terms only)

本ファイルは、火星起源ダスト円盤モデルのうち「最重要（A優先）」な用語だけをまとめた AI・開発者向け用語集です。数式や導出は `analysis/equations.md` を唯一の参照源とし、ここでは意味づけと参照リンクのみを保持します。

| term_id | label | audience | math_level | origin | status | priority | definition_ja | eq_refs | lit_refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G.A01 | Mars moon-forming disk | both | light | papers+code | draft | A | 巨大衝突後に火星のまわりへ残るダスト主体の円盤。「火星月形成円盤」として Phobos/Deimos の材料供給源になり、本リポジトリの時間発展モデルが追跡する対象。 |  | Hyodo2017a,Hyodo2017b,Hyodo2018,Ronnet2016,Pignatale2018,Kuramoto2024,CanupSalmon2018 |
| G.A02 | gas-poor disk | both | light | papers+code | draft | A | 蒸気や背景ガスの質量が固体よりずっと小さい状態の月形成円盤。ガス抗力や TL2003 型表層アウトフローを無視できる前提として採用される「ガス希薄ディスク」。 |  | Hyodo2017a,Hyodo2018,CanupSalmon2018,Kuramoto2024 |
| G.A03 | TL2003 gas-rich surface outflow | me | full | paper:TakeuchiLin2003 | draft | A | 光学的に厚いガス層が支配する表層ダストの外向き流出モデルである「TL2003 表層アウトフロー」。本プロジェクトでは gas-rich 感度試験でのみ `ALLOW_TL2003=true` とし、標準では無効化する。 | E.007 | TakeuchiLin2003,StrubbeChiang2006 |
| G.A04 | radiation-pressure ratio β | both | full | code:radiation.py | draft | A | 放射圧と重力の比を表す無次元量である β。0.5 を超えると粒子軌道が束縛を外れ、吹き飛びサイズより小さい粒子が系外へ逃げる。 | E.013 | Hyodo2018,Ronnet2016,StrubbeChiang2006 |
| G.A05 | blow-out size s_blow | both | light | code:radiation.py | draft | A | β≃0.5 となる粒径で「吹き飛びサイズ」s_blow。これより小さいダストは放射圧で短時間に失われ、PSD の実効的最小サイズとして扱う。 | E.014 | Hyodo2018,StrubbeChiang2006 |
| G.A06 | Planck-mean Q_pr | both | full | code:radiation.py | draft | A | 火星表面温度でプランク平均した放射圧効率 ⟨Q_pr⟩。放射圧パラメータ β や吹き飛びサイズ s_blow など放射依存の量は、このプランク平均 Q_pr を通じて評価する。 | E.004 | Hyodo2018,Ronnet2016 |
| G.A07 | sub-blow-out particles | both | light | code+papers | draft | A | 吹き飛びサイズ s_blow より小さく、β が大きいため 1 公転以内に系外へ放出される小粒子群。内部破砕カスケードで供給され、円盤質量損失の主担い手となる「sub-blow-out 粒子」。 | E.035 | Hyodo2018,StrubbeChiang2006 |
