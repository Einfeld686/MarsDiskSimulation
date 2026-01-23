<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

## 付録 E. 記号表

本論文で用いる記号と，その意味・単位をまとめる．本文中に示す式で用いる記号の定義も，本付録を正とする．主要記号は表\ref{tab:app_symbols_main}と表\ref{tab:app_symbols_main_cont}に示す．

### E.1 主要記号（本研究のダスト円盤モデル）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（本研究で用いる記号と単位）}
  \label{tab:app_symbols_main}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
	    $t$ & 時刻 & $\mathrm{s}$ & 解析では年へ換算して表示する場合がある \\
	    $r$ & 半径（代表半径） & $\mathrm{m}$ & 0D では代表値のみを用いる \\
	    $r_{\rm in},r_{\rm out}$ & 計算領域の内端・外端半径 & $\mathrm{m}$ & 環状領域 $[r_{\rm in},r_{\rm out}]$ \\
	    $A$ & 環状領域の面積 & $\mathrm{m^{2}}$ & 式\ref{eq:annulus_area_definition} \\
	    $A_\ell$ & セル $\ell$ の面積 & $\mathrm{m^{2}}$ & 1D の半径セル（リング）ごとの面積 \\
	    $M_{\rm in}$ & ロッシュ限界内側の内側円盤質量 & $\mathrm{kg}$ & 入力（3節） \\
		    $\Delta M_{\rm in}$ & 遷移期における不可逆損失（累積） & $\mathrm{kg}$ & 本論文では $M_{\rm loss}$ と同義 \\
		    $M_{\rm in}'$ & 更新後の内側円盤質量（長期モデルへ渡す量） & $\mathrm{kg}$ & $M_{\rm in}'=M_{\rm in}(t_0)-M_{\rm loss}(t_{\rm end})$ \\
	    $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
	    $T_{\rm orb}$ & 公転周期 & $\mathrm{s}$ & 式\ref{eq:torb_definition} \\
	    $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
    $s$ & 粒子半径 & $\mathrm{m}$ & PSD の独立変数 \\
	    $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
	    $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
    $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
    $Y_{kij}$ & 衝突 $(i,j)$ による破片生成の質量分率（ビン $k$ への配分） & -- & $\sum_k Y_{kij}=1$（式\ref{eq:fragment_yield_normalization}） \\
    $F_k$ & 供給ソース項（サイズビン $k$ への注入率） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:smoluchowski} \\
		    $S_k$ & 追加シンクの実効ロス率 & $\mathrm{s^{-1}}$ & 式\ref{eq:smoluchowski} \\
				    $\Sigma_{\rm surf}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
			    $\kappa_{\rm surf}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
			    $\tau_\perp$ & 鉛直方向の光学的厚さ（近似） & -- & $\tau_\perp=\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
		    $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ \\
	    $\kappa_{\rm eff}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
			    $f_{\rm los}$ & 鉛直光学的厚さ $\tau_\perp$ を $\tau_{\rm los}$ へ写像する幾何因子 & -- & $\tau_{\rm los}=f_{\rm los}\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
			    $\tau_{\rm los}$ & 火星視線方向光学的厚さ（近似） & -- & 式\ref{eq:tau_los_definition}; 遮蔽評価に用いる \\
			    $\tau_{\rm eff}$ & 火星方向の有効光学的厚さ & -- & 式\ref{eq:tau_eff_definition}; 初期規格化と停止判定に用いる \\
			    $\Sigma_{\tau_{\rm los}=1}$ & $\tau_{\rm los}=1$ に対応する参照面密度 & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau_los1_definition}（$\Sigma_{\tau_{\rm los}=1}=(f_{\rm los}\kappa_{\rm surf})^{-1}$） \\
		    $\Sigma_{\tau=1}$ & 光学的厚さ $\tau=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition} \\
		    \hline
	  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（続き）}
  \label{tab:app_symbols_main_cont}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
	    $T_M$ & 火星表面温度 & $\mathrm{K}$ & 放射・昇華の入力 \\
	    $\langle Q_{\rm abs}\rangle$ & 粒子温度評価に用いる有効吸収効率 & -- & 式\ref{eq:grain_temperature_definition} \\
	    $\langle Q_{\rm pr}\rangle$ & Planck 平均放射圧効率 & -- & テーブル入力 \\
		    $\beta$ & 軽さ指標（放射圧/重力） & -- & 式\ref{eq:beta_definition}; $\beta>0.5$ で非束縛 \\
		    $s_{\rm blow}$ & ブローアウト粒径 & $\mathrm{m}$ & 式\ref{eq:s_blow_definition} \\
		    $t_{\rm blow}$ & ブローアウト滞在時間 & $\mathrm{s}$ & 式\ref{eq:t_blow_definition} \\
		    $\chi_{\rm blow}$ & ブローアウト滞在時間係数 & -- & 式\ref{eq:t_blow_definition}; \texttt{auto} は式\ref{eq:chi_blow_auto_definition} \\
		    $\dot{\Sigma}_{\rm out}$ & 表層流出（面密度フラックス） & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:surface_outflux} \\
		    $\dot{M}_{\rm out}$ & 円盤全体の質量流出率 & $\mathrm{kg\,s^{-1}}$ & 式\ref{eq:mdot_out_definition}（出力は $\dot{M}_{\rm out}/M_{\rm Mars}$ を記録） \\
		    $M_{\rm loss}$ & 累積損失 & $\mathrm{kg}$ & $\dot{M}_{\rm out}$ 等を積分（出力は $M_{\rm loss}/M_{\rm Mars}$ を記録） \\
		    $R_{\rm base}$ & 供給の基底レート & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:R_base_definition} \\
		    $\mu_{\rm sup}$ & 供給スケール（無次元） & -- & 式\ref{eq:R_base_definition} \\
		    $f_{\rm orb}$ & $\mu_{\rm sup}=1$ のときの 1 軌道あたり供給比率 & -- & 式\ref{eq:R_base_definition} \\
		    $\tau_{\rm ref}$ & 供給スケール参照光学的厚さ & -- & 式\ref{eq:R_base_definition} \\
		    $C_{ij}$ & 衝突イベント率（単位面積あたり，$N_iN_j$ を含む） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:collision_kernel} \\
		    $v_{ij}$ & 相対速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vrel_pericenter_definition} \\
		    $e, i$ & 離心率・傾斜角（分散） & -- & 相対速度の評価に用いる \\
		    $Q_D^*$ & 破壊閾値（比エネルギー） & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:qdstar_definition} \\
		    $Q_R$ & reduced specific kinetic energy & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:q_r_definition} \\
		    $F_{LF}$ & 最大残存率（最大残存体質量/総質量） & -- & 式\ref{eq:F_LF_definition} \\
		    $\mu_{\rm LS}$ & 速度外挿に用いる指数 & -- & $v^{-3\mu_{\rm LS}+2}$（既定 0.45） \\
		    $\mu$ & 分子量（HKL） & $\mathrm{kg\,mol^{-1}}$ & 式\ref{eq:hkl_flux} \\
		    \hline
	  \end{tabular}
\end{table}
