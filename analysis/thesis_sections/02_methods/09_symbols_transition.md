<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

### 付録 E. 記号表

本論文で用いる記号と、その意味・単位をまとめる。本文中に示す式で用いる記号の定義も、本付録を正とする。

#### E.1 主要記号（本研究のダスト円盤モデル）

\begin{table}[t]
  \centering
  \caption{主要記号表（本研究で用いる記号と単位）}
  \label{tab:symbols_main}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
    \hline
    記号 & 意味 & 単位 & 備考 \\
    \hline
    $t$ & 時刻 & $\mathrm{s}$ & 解析では年へ換算して表示する場合がある \\
    $r$ & 半径（代表半径） & $\mathrm{m}$ & 0D では代表値のみを用いる \\
    $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
    $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
    $s$ & 粒径 & $\mathrm{m}$ & PSD の独立変数 \\
    $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
    $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
    $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
    $\Sigma_{\mathrm{surf}}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
    $\Sigma_{\mathrm{deep}}$ & 深層リザーバ面密度 & $\mathrm{kg\,m^{-2}}$ & 深層ミキシング有効時に追跡 \\
    $\kappa_{\mathrm{surf}}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
    $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\mathrm{eff}}=\Phi\kappa_{\mathrm{surf}}$ \\
    $\kappa_{\mathrm{eff}}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
    $\tau_{\perp}$ & 垂直方向光学的厚さ & -- & 表層衝突寿命の評価に用いる \\
    $\tau_{\mathrm{los}}$ & 火星視線方向光学的厚さ & -- & 遮蔽・停止判定に用いる \\
    $\Sigma_{\tau=1}$ & $\tau=1$ に対応する表層面密度 & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition}; 診断量 \\
    $T_M$ & 火星表面温度 & $\mathrm{K}$ & 放射・昇華・相判定の入力 \\
    $\langle Q_{\mathrm{pr}}\rangle$ & Planck 平均放射圧効率 & -- & テーブル入力 \\
    $\beta$ & 軽さ指標（放射圧/重力） & -- & 式\ref{eq:beta_definition}; $\beta>0.5$ で非束縛 \\
    $s_{\mathrm{blow}}$ & ブローアウト粒径 & $\mathrm{m}$ & 式\ref{eq:s_blow_definition} \\
    $t_{\mathrm{blow}}$ & ブローアウト滞在時間 & $\mathrm{s}$ & 式\ref{eq:t_blow_definition} \\
    $\dot{M}_{\mathrm{out}}$ & 表層流出率 & $\mathrm{kg\,s^{-1}}$ & 式\ref{eq:surface_outflux} \\
    $M_{\mathrm{loss}}$ & 累積損失 & $\mathrm{kg}$ & $\dot{M}_{\mathrm{out}}$ 等を積分 \\
    $C_{ij}$ & 衝突カーネル（衝突率） & $\mathrm{s^{-1}}$ & 式\ref{eq:collision_kernel} \\
    $v_{ij}$ & 相対速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vij_definition} \\
    $e, i$ & 離心率・傾斜角（分散） & -- & 相対速度の評価に用いる \\
    $c_{\mathrm{eq}}$ & 速度分散（平衡値） & $\mathrm{m\,s^{-1}}$ & 固定点反復で評価（本文4.1.1） \\
    $Q_D^*$ & 破壊閾値（比エネルギー） & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:qdstar_definition} \\
    \hline
  \end{tabular}
\end{table}

#### E.2 遷移期・長期モデル接続で用いる記号（暫定）

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

#### E.1 補足：記号不整合（現状の把握）

- 「外縁」が $r_d$ と $a_{\rm eq,max}$ で混在している。現時点では、両者の定義関係が文書内で確定できないため、次の表では別項目として残している。  
- 先行研究（特に Canup & Salmon (2018)）の該当箇所を確認し、(i) 同一概念ならどちらかに統一する、(ii) 別概念なら本文で初出定義を与える、のいずれかを行う必要がある。\newline `TODO(REF:transition_symbols_pending_refs_v1)`

---
