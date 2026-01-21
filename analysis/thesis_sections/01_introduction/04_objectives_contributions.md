## 4. 研究目的

長期進化計算では，SPH 出力で得られる円盤質量をそのまま初期条件として受け渡すことが多い．一方で遷移期には，内側円盤から惑星へ落下する成分や，表層から不可逆に失われる成分が生じ得る．これらを明示的に扱わない場合，長期モデルへ渡す内側円盤質量が過大評価され，衛星形成シナリオの比較に系統誤差が入り得る．
そこで本研究の目的は，遷移期の質量損失 $\Delta M_{\rm in}$ を導入して内側円盤初期条件を更新する枠組みを構築し，接続に伴う系統誤差を定量的に評価することである．具体的には，$\Delta M_{\rm in}$ を用いて長期モデルへ渡す内側円盤質量を式\ref{eq:min0_update}で更新し，更新の有無が長期進化・衛星形成結果に与える影響を調査する．

本研究の構成は以下の通りである．第1章では火星衛星形成の背景と先行研究を概観し，SPH 出力と長期進化モデルの接続における遷移期の位置づけを述べる．第2章ではモデルの全体像，支配方程式，ならびに $\Delta M_{\rm in}$ の評価と初期条件更新（式\ref{eq:min0_update}）の手順を提示する．第3章では代表ケースと感度解析の結果を示し，内側円盤質量の更新が長期進化・衛星形成に与える影響を比較する．第4章では結果の解釈，モデルの仮定と限界，今後の課題を議論し，第5章で結論をまとめる．

<!-- TEX_EXCLUDE_START -->
##### 先行研究リンク
- [Hyodo et al. (2017a)](../../paper/references/Hyodo2017a_ApJ845_125.pdf)
- [Hyodo et al. (2017b)](../../paper/references/Hyodo2017b_ApJ851_122.pdf)
- [Hyodo et al. (2018)](../../paper/references/Hyodo2018_ApJ860_150.pdf)
- [Canup & Salmon (2018)](../../paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf)
- [Salmon & Canup (2012)](../../paper/references/SalmonCanup2012_ApJ760_83.pdf)
- [Takeuchi & Lin (2003)](../../paper/references/TakeuchiLin2003_ApJ593_524.pdf)
<!-- TEX_EXCLUDE_END -->
