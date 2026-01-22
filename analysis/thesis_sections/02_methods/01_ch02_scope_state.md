<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/io/tables.py, marsdisk/physics/psd.py, marsdisk/physics/sizes.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/initfields.py
-->

## 2. 支配方程式と適用範囲

本モデルは gas-poor 条件の軸対称ダスト円盤を対象とし，放射圧と衝突カスケードを同一時間発展で結合する．$\tau_{\rm los}>\tau_{\rm stop}$ に達した場合は適用範囲外として計算を停止する．gas-rich 表層 ODE に基づく流出は扱わない．

軌道力学量は代表半径 $r$ で評価し，ケプラー速度 $v_K$ と角速度 $\Omega$ は式\ref{eq:vK_definition}–\ref{eq:omega_definition}で与える．0D では $r_{\rm in}$–$r_{\rm out}$ を平均化した代表半径を用いる．

\begin{equation}
\label{eq:vK_definition}
v_K(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r}}
\end{equation}

\begin{equation}
\label{eq:omega_definition}
\Omega(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r^{3}}}
\end{equation}

\begin{equation}
\label{eq:torb_definition}
T_{\rm orb}=\frac{2\pi}{\Omega}
\end{equation}

### 2.1 放射圧とブローアウト

放射圧と重力の比 $\beta(s)$ は式\ref{eq:beta_definition}で定義し，Planck 平均の $\langle Q_{\rm pr}\rangle$ は外部テーブルから補間する（付録C）．$\beta\ge0.5$ を非束縛条件とし，ブローアウト境界粒径 $s_{\rm blow}$ は式\ref{eq:s_blow_definition}で与える．ブローアウト滞在時間は式\ref{eq:t_blow_definition}とし，基準計算では $\chi_{\rm blow}$ を auto とする．auto は $\chi_{\beta}=1/\{1+0.5(\beta/0.5-1)\}$，$\chi_{Q}=\mathrm{clip}(Q_{\rm pr},0.5,1.5)$，$\chi_{\rm blow}=\mathrm{clip}(\chi_{\beta}\chi_{Q},0.5,2)$ で定義し，$\mathrm{clip}(x,a,b)=\min(\max(x,a),b)$ とする．

\begin{equation}
\label{eq:beta_definition}
\beta(s) = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}(s)\rangle}{4\,G\,M_{\rm Mars}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{2\,G\,M_{\rm Mars}\,c\,\rho}
\end{equation}

\begin{equation}
\label{eq:t_blow_definition}
t_{\rm blow}=\chi_{\rm blow}\Omega^{-1}
\end{equation}

表層流出は Smol 経路の一次シンクとして式\ref{eq:surface_outflux}で与え，ブローアウト対象ビンでは $S_{{\rm blow},k}=1/t_{\rm blow}$ とする．ブローアウト対象は $\beta\ge0.5$ に対応する $s_k\le s_{\rm blow}$ のビンとする．円盤全体の流出率は式\ref{eq:mdot_out_definition}で定義し，0Dでは領域面積 $A$ を用いて近似する．

\begin{equation}
\label{eq:surface_outflux}
\dot{\Sigma}_{\rm out} = \sum_k m_k S_{{\rm blow},k} N_k
\end{equation}

\begin{equation}
\label{eq:mdot_out_definition}
\dot{M}_{\rm out}(t)=\int_{r_{\rm in}}^{r_{\rm out}}2\pi r\,\dot{\Sigma}_{\rm out}(r,t)\,dr
\end{equation}

### 2.2 遮蔽

遮蔽係数 $\Phi$ は $\tau_{\rm los}$ の関数として与え，本研究では吸収減衰近似 $\Phi=\exp(-\tau_{\rm los})$ を用いる．基準計算では遮蔽を無効化し，$\Phi=1$ として扱う．$\Phi$ から有効不透明度 $\kappa_{\rm eff}$ を定義し，診断量 $\Sigma_{\tau_{\rm eff}=1}$ を式\ref{eq:sigma_tau1_definition}で評価する．

\begin{equation}
\label{eq:phi_definition}
\Phi=\exp(-\tau_{\rm los})
\end{equation}

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\rm eff} = \Phi\,\kappa_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau_{\rm eff}=1} =
\begin{cases}
 \kappa_{\rm eff}^{-1}, & \kappa_{\rm eff} > 0,\\
 \infty, & \kappa_{\rm eff} \le 0
\end{cases}
\end{equation}

### 2.3 表層への質量供給

表層への供給は面密度生成率として与え，混合係数 $\epsilon_{\rm mix}$ と入力関数 $R_{\rm base}$ から式\ref{eq:prod_rate_definition}で定義する．供給率は PSD のソース項 $F_k$ として式\ref{eq:supply_injection_definition}で注入し，質量保存条件 $\sum_k m_k F_k=\dot{\Sigma}_{\rm in}$ を満たすよう重み $w_k$ を正規化する．基準計算では注入重みを初期 PSD の質量分率に比例させる．べき乗注入を用いる場合は $s_{\rm floor}=\max(s_{\min,\rm eff},s_{\rm inj,min})$，$s_{\rm ceil}=s_{\rm inj,max}$ として式\ref{eq:supply_injection_powerlaw_bins}で $w_k$ を定め，$s_{\rm inj,min},s_{\rm inj,max}$ を注入サイズ範囲の下限・上限とする．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\rm prod}(t,r) = \max\!\left(\epsilon_{\rm mix}\;R_{\rm base}(t,r),\,0\right)
\end{equation}

\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},\qquad \sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}

\begin{equation}
\label{eq:supply_injection_powerlaw_bins}
\tilde{w}_k=\int_{\max(s_{k-},s_{\rm floor})}^{\min(s_{k+},s_{\rm ceil})} s^{-q}\,ds,\qquad
F_k=\frac{\dot{\Sigma}_{\rm in}\,\tilde{w}_k}{\sum_j m_j\tilde{w}_j}
\end{equation}

### 2.4 衝突カスケード

PSD の時間発展は Smoluchowski 方程式（式\ref{eq:smoluchowski}）で与え，注入 $F_k$ と一次シンク $S_k$（ブローアウト・昇華）を含める．破片生成テンソル $Y_{kij}$ は質量保存条件 $\sum_k Y_{kij}=1$ を満たすよう定義する．

\begin{equation}
\label{eq:smoluchowski}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

\begin{equation}
\label{eq:fragment_yield_normalization}
\sum_k Y_{kij}=1
\end{equation}

衝突イベント率 $C_{ij}$ は式\ref{eq:collision_kernel}で与え，相対速度 $v_{ij}$ は入力の $e,i$ と $v_K$ から式\ref{eq:vrel_pericenter_definition}で評価する．スケールハイトは $H_k=H_{\rm factor}\,i\,r$ とし，基準計算では $H_{\rm factor}=1$ を採用する．ビンの衝突寿命は式\ref{eq:t_coll_definition}とし，時間刻みの上限に用いる．破壊閾値 $Q_D^*$ は式\ref{eq:qdstar_definition}の速度補間を用い，最大残存率 $F_{LF}$ と破片分布 $w^{\rm frag}_k$ を通じて式\ref{eq:fragment_tensor_definition}で $Y_{kij}$ を構成する．

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

\begin{equation}
\label{eq:vrel_pericenter_definition}
v_{ij}=v_K\,\sqrt{\frac{1+e}{1-e}}
\end{equation}

\begin{equation}
\label{eq:t_coll_definition}
t_{{\rm coll},k}=\left(\frac{\sum_j C_{kj}+C_{kk}}{N_k}\right)^{-1}
\end{equation}

\begin{equation}
\label{eq:qdstar_definition}
Q_{D}^{*}(s,\rho,v)=Q_s(v)\,s^{-a_s(v)}+B(v)\,\rho\,s^{b_g(v)}
\end{equation}

\begin{equation}
\label{eq:fragment_weights}
w^{\rm frag}_k(k_{\rm LR})=\frac{\int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\rm frag}}\,ds}{\sum_{\ell\le k_{\rm LR}}\int_{s_{\ell-}}^{s_{\ell+}} s^{-\alpha_{\rm frag}}\,ds}
\end{equation}

\begin{equation}
\label{eq:fragment_tensor_definition}
Y_{kij}=F_{LF}\delta_{k k_{\rm LR}}+(1-F_{LF})\,w^{\rm frag}_k(k_{\rm LR})
\end{equation}

### 2.5 昇華と追加シンク

昇華は HKL フラックス $J(T)$ を用い，粒径縮小を式\ref{eq:dsdt_definition}で与える．昇華で用いる粒子温度は灰色体近似で式\ref{eq:grain_temperature_definition}とする．飽和蒸気圧は Clausius 形またはテーブル補間を用い（式\ref{eq:psat_definition}），基準ケースの係数は付録Aに示す．

\begin{equation}
\label{eq:grain_temperature_definition}
T_p = T_M\,\langle Q_{\rm abs}\rangle^{1/4}\sqrt{\frac{R_{\rm Mars}}{2r}}
\end{equation}

\begin{equation}
\label{eq:hkl_flux}
J(T) =
 \alpha_{\rm evap}\max\!\bigl(P_{\rm sat}(T) - P_{\rm gas},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\rm sat}(T) =
\begin{cases}
 10^{A - B/T}, & \text{Clausius 型},\\
  10^{{\rm PCHIP}_{\log_{10}P}(T)}, & \text{テーブル補間}.
\end{cases}
\end{equation}

\begin{equation}
\label{eq:dsdt_definition}
\frac{ds}{dt}=-\frac{J(T)}{\rho}
\end{equation}
