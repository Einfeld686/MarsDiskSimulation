<!--
document_type: reference
title: 記号一覧（遷移期・長期モデル接続：暫定）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

# 記号一覧（遷移期・長期モデル接続：暫定）

本ファイルは、現時点の導入（遷移期）文書に現れる記号を、TeX 化に先立って一時的に整理したものである。定義が先行研究依存で確定できない項目は文献確認中として残している。

\begin{table}[t]
  \centering
  \caption{記号一覧（遷移期・長期モデル接続：暫定）}
  \label{tab:symbols_transition}
  \begin{tabular}{p{0.17\linewidth}p{0.40\linewidth}p{0.09\linewidth}p{0.20\linewidth}}
    \hline
    記号 & 意味 & 単位 & 注記 \\
    \hline
    $M_{\rm in}$ &
    ロッシュ限界内側に存在する内側円盤の質量（長期モデルの主要入力） &
    $\mathrm{kg}$ &
    定義は文献確認中\newline \texttt{TODO(REF:}\newline \texttt{canup2018}\newline \texttt{\_min\_definition}\newline \texttt{\_v1)} \\
    $M_{\rm in}^{\rm SPH}$ &
    SPH 終端時刻におけるロッシュ限界内側の円盤質量（接続前の推定値） &
    $\mathrm{kg}$ &
    SPH 出力から集計（方法は文献確認中）\newline \texttt{TODO(REF:}\newline \texttt{sph}\newline \texttt{\_mass\_aggregation\_method}\newline \texttt{\_v1)} \\
    $\Delta M_{\rm in}$ &
    遷移期における内側円盤の不可逆損失（表層散逸・不可逆落下等の総和） &
    $\mathrm{kg}$ &
    本研究で評価対象。落下分の扱いは\newline \texttt{TODO(REF:}\newline \texttt{delta}\newline \texttt{\_min\_infall}\newline \texttt{\_policy\_v1)} \\
    $M_{\rm in,0}$ &
    長期モデル開始時刻 $t_0$ における内側円盤の有効質量（接続後の入力） &
    $\mathrm{kg}$ &
    $M_{\rm in,0}=M_{\rm in}^{\rm SPH}-\Delta M_{\rm in}$ \\
    $t_0$ &
    長期モデルの開始時刻（遷移期が終わったと見なす時刻） &
    $\mathrm{s}$ &
    定義は文献確認中（または $\mathrm{h}$）\newline \texttt{TODO(REF:}\newline \texttt{transition}\newline \texttt{\_start\_time\_definition}\newline \texttt{\_v1)} \\
    $r_d$ &
    内側円盤の外縁（半径） &
    $\mathrm{m}$ &
    定義は文献確認中（または $R_{\rm Mars}$）\newline \texttt{TODO(REF:}\newline \texttt{canup2018}\newline \texttt{\_rd\_definition}\newline \texttt{\_v1)} \\
    $a_{\rm eq,max}$ &
    円盤が赤道面へ緩和した後の「最大半長軸」等を表す候補記号 &
    未定 &
    定義関係は\newline \texttt{TODO(REF:}\newline \texttt{aeqmax}\newline \texttt{\_rd\_relation}\newline \texttt{\_v1)} \\
    $J_2$ &
    火星重力場の扁平項（第 2 帯状調和係数） &
    -- &
    遷移期の歳差運動・位相混合に関与 \\
    \hline
  \end{tabular}
\end{table}

## 補足：記号不整合（現状の把握）

- 「外縁」が $r_d$ と $a_{\rm eq,max}$ で混在している。現時点では、両者の定義関係が文書内で確定できないため、次の表では別項目として残している。  
- 先行研究（特に Canup & Salmon (2018)）の該当箇所を確認し、(i) 同一概念ならどちらかに統一する、(ii) 別概念なら本文で初出定義を与える、のいずれかを行う必要がある。\newline `TODO(REF:transition_symbols_pending_refs_v1)`

---
