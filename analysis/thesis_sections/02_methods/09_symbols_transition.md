<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

### 付録 E. 記号表

本論文で用いる記号と，その意味・単位をまとめる．本文中に示す式で用いる記号の定義も，本付録を正とする．

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
	    $r_{\rm in},r_{\rm out}$ & 計算領域の内端・外端半径 & $\mathrm{m}$ & 環状領域 $[r_{\rm in},r_{\rm out}]$ \\
	    $A$ & 環状領域の面積 & $\mathrm{m^{2}}$ & 式\ref{eq:annulus_area_definition} \\
	    $M_{\rm in}$ & ロッシュ限界内側の内側円盤質量 & $\mathrm{kg}$ & 入力（§1.1） \\
	    $\Delta M_{\rm in}$ & 遷移期における放射圧起因の不可逆損失（累積） & $\mathrm{kg}$ & $\Delta M_{\rm in}=\int \dot{M}_{\rm out}(t)\,dt$ \\
	    $M_{\rm in}'$ & 更新後の内側円盤質量（長期モデルへ渡す量） & $\mathrm{kg}$ & $M_{\rm in}'=M_{\rm in}(t_0)-\Delta M_{\rm in}$ \\
	    $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
	    $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
    $s$ & 粒子半径 & $\mathrm{m}$ & PSD の独立変数 \\
	    $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
	    $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
    $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
    $Y_{kij}$ & 衝突 $(i,j)$ による破片生成の質量分率（ビン $k$ への配分） & -- & $\sum_k Y_{kij}=1$（式\ref{eq:fragment_yield_normalization}） \\
    $F_k$ & 供給ソース項（サイズビン $k$ への注入率） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:smoluchowski} \\
    $S_k$ & 追加シンクの実効ロス率 & $\mathrm{s^{-1}}$ & 式\ref{eq:smoluchowski} \\
    $\Sigma_{\mathrm{surf}}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
    $\Sigma_{\mathrm{deep}}$ & 深層リザーバ面密度 & $\mathrm{kg\,m^{-2}}$ & 深層ミキシング有効時に追跡 \\
    $\kappa_{\mathrm{surf}}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
    $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\mathrm{eff}}=\Phi\kappa_{\mathrm{surf}}$ \\
    $\kappa_{\mathrm{eff}}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
		    $\tau_{\perp}$ & 垂直方向光学的厚さ & -- & 表層衝突寿命の評価に用いる \\
		    $\tau_{\mathrm{los}}$ & 火星視線方向光学的厚さ & -- & 遮蔽・停止判定に用いる \\
		    $f_{\rm los}$ & 視線補正係数（$\tau_{\rm los}=f_{\rm los}\tau_{\perp}$） & -- & §2.1.2 \\
		    $\Sigma_{\tau_{\mathrm{los}}=1}$ & $\tau_{\mathrm{los}}=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition} \\
		    $\Sigma_{\tau_{\perp}=1}$ & $\tau_{\perp}=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & $\Sigma_{\tau_{\perp}=1}=f_{\rm los}\Sigma_{\tau_{\mathrm{los}}=1}$ \\
		    $T_M$ & 火星表面温度 & $\mathrm{K}$ & 放射・昇華・相判定の入力 \\
	    $\langle Q_{\mathrm{pr}}\rangle$ & Planck 平均放射圧効率 & -- & テーブル入力 \\
	    $\beta$ & 軽さ指標（放射圧/重力） & -- & 式\ref{eq:beta_definition}; $\beta>0.5$ で非束縛 \\
		    $s_{\mathrm{blow}}$ & ブローアウト粒径 & $\mathrm{m}$ & 式\ref{eq:s_blow_definition} \\
		    $t_{\mathrm{blow}}$ & ブローアウト滞在時間 & $\mathrm{s}$ & 式\ref{eq:t_blow_definition} \\
		    $\dot{\Sigma}_{\mathrm{out}}$ & 表層流出（面密度フラックス） & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:surface_outflux} \\
		    $\dot{M}_{\mathrm{out}}$ & 円盤全体の質量流出率 & $\mathrm{kg\,s^{-1}}$ & 式\ref{eq:mdot_out_definition}（出力は $\dot{M}_{\rm out}/M_{\rm Mars}$ を記録） \\
		    $M_{\mathrm{loss}}$ & 累積損失 & $\mathrm{kg}$ & $\dot{M}_{\mathrm{out}}$ 等を積分（出力は $M_{\rm loss}/M_{\rm Mars}$ を記録） \\
		    $C_{ij}$ & 衝突イベント率（単位面積あたり，$N_iN_j$ を含む） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:collision_kernel} \\
	    $v_{ij}$ & 相対速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vrel_pericenter_definition} \\
    $e, i$ & 離心率・傾斜角（分散） & -- & 相対速度の評価に用いる \\
    $c_{\mathrm{eq}}$ & 速度分散（平衡値） & $\mathrm{m\,s^{-1}}$ & 固定点反復で評価（本文4.1.1） \\
    $Q_D^*$ & 破壊閾値（比エネルギー） & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:qdstar_definition} \\
    \hline
  \end{tabular}
\end{table}
