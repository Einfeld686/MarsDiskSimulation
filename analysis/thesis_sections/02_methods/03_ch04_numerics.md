## 4. 離散化と時間積分法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

サイズ空間は対数等間隔のグリッドで離散化し，各ビン中心 $s_k$ に対応する $N_k$ を状態量として進める．注入・損失・再配分はビン上で行い，境界は $s_{\min,\rm eff}$ と $s_{\max}$ で定義する．

時間積分は IMEX-BDF(1) を用い，衝突ロス項のみ陰的，破片生成・供給・一次シンクは陽的に扱う．更新式は式\ref{eq:imex_bdf1_update}で与え，内部ステップ幅 $dt_{\rm eff}$ は外側ステップ幅 $\Delta t$ 以下とする．$dt_{\rm eff}$ は $\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を初期値とし，必要に応じて縮小して非負性と質量保存を確保する．

\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}

質量保存は式\ref{eq:mass_budget_definition}で定義し，各ステップで相対誤差 $\epsilon_{\rm mass}$ を評価する．$\Delta t$ は $t_{\rm blow}$ と $t_{{\rm coll},k}$ をともに解像するよう制約し，収束判定は検証節の基準に従う．

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + \Delta t\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

$\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}$ は衝突カーネルから評価したブローアウト未満粒子の生成率であり，質量検査にのみ用いる．$\dot{\Sigma}_{\rm extra}$ はブローアウト・昇華・追加シンクによる明示的な損失率の和である．
