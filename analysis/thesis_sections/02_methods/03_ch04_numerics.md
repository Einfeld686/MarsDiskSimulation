## 4. 数値計算法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

本節では，粒径分布の離散化と時間積分法を示し，安定性（非負性）と質量保存を満たすための時間刻み制御と停止条件を定義する．

### 4.1 離散化

サイズ空間は対数等間隔のグリッドで離散化し，各ビン中心 $s_k$ に対応する $N_k$ を状態量として進める．注入・損失・再配分はビン上で行い，境界は $s_{\min,\rm eff}$ と $s_{\max}$ で定義する．半径方向は 1節で定義したセル分割に従う．

### 4.2 数値解法と停止条件

時間積分は IMEX-BDF(1) を用い，衝突ロス項のみ陰的，破片生成・供給・一次シンクは陽的に扱う\citep{Krivov2006_AA455_509,Birnstiel2011_AA525_A11}．更新式は式\ref{eq:imex_bdf1_update}で与え，内部ステップ幅 $dt_{\rm eff}$ は外側ステップ幅 $\Delta t$ 以下とする．$dt_{\rm eff}$ は $\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を初期値とし，必要に応じて縮小して非負性と質量保存（式\ref{eq:mass_budget_definition}）を確保する．

\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}

質量保存は式\ref{eq:mass_budget_definition}で定義し，各ステップで相対誤差 $\epsilon_{\rm mass}$ を評価する\citep{Krivov2006_AA455_509}．ここでは，Smol 更新で実際に用いた $dt_{\rm eff}$ に対して収支を評価する．$\Delta t$ は $t_{\rm blow}$ と $t_{{\rm coll},k}$ をともに解像するよう制約し，収束判定は 5節の基準に従う．

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + dt_{\rm eff}\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + dt_{\rm eff}\,\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

$\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}$ は衝突カーネルから評価したブローアウト未満粒子の生成率であり，質量検査にのみ用いる．$\dot{\Sigma}_{\rm extra}$ はブローアウト・昇華・追加シンクによる明示的な損失率の和である．

停止条件は，(i) 火星温度が所定の閾値 $T_M=T_{\rm end}$ に到達した時刻を積分終端 $t_{\rm end}$ とし（本論文では $T_{\rm end}=2000\,\mathrm{K}$），(ii) 各セルで $\tau_{\rm los}>\tau_{\rm stop}$ を検出した場合にそのセルを早期停止する．以上により，積分期間を物理的な高温期に合わせつつ，質量保存誤差が許容範囲に収まる設定でのみ結果を採用する．
