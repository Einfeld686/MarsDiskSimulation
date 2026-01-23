## 4. 数値計算法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

本節では，粒径分布の離散化と時間積分法を示し，安定性（非負性）と質量保存を満たすための時間刻み制御と停止条件を定義する．

### 4.1 離散化

サイズ空間は対数等間隔のグリッドで離散化し，各ビン中心 $s_k$ に対応する $N_k$ を状態量として進める．注入・損失・再配分はビン上で行い，境界は $s_{\min,\rm eff}$ と $s_{\max}$ で定義する．この粒径範囲の外側は本研究の解像範囲外として扱い，下限側はブローアウト等により速やかに失われる成分，上限側は未解像の大粒子成分として代表化するという近似の下で，質量収支が閉じるように扱う．半径方向は 1節で定義したセル分割に従う．

### 4.2 数値解法と停止条件

時間積分は IMEX-BDF(1) を用い，衝突ロス項のみ陰的，破片生成・供給・一次シンクは陽的に扱う\citep{Krivov2006_AA455_509,Birnstiel2011_AA525_A11}．更新式は式\ref{eq:imex_bdf1_update}で与え，内部ステップ幅 $dt_{\rm eff}$ は外側ステップ幅 $\Delta t$ 以下とする．$dt_{\rm eff}$ は $\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を初期値とし，必要に応じて縮小して非負性と質量保存（式\ref{eq:mass_budget_definition}）を確保する．具体的な時間刻み制御は次の手順で行う．

1. $dt_{\rm eff}\leftarrow\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を設定する．
2. 式\ref{eq:imex_bdf1_update}で $N_k^{n+1}$ を計算する．
3. $N_k^{n+1}<0$ を含む場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
4. 式\ref{eq:mass_budget_definition}で $\epsilon_{\rm mass}$ を評価し，$\epsilon_{\rm mass}>0.5\%$ の場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
5. 3–4 を満たした $dt_{\rm eff}$ を採用してステップを確定する．

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

停止条件は，(i) 火星温度が所定の閾値 $T_M=T_{\rm end}$ に到達した時刻を積分終端 $t_{\rm end}$ とし（本論文では $T_{\rm end}=2000\,\mathrm{K}$），(ii) 各セルで有効光学的厚さ $\tau_{\rm eff}>\tau_{\rm stop}$ を満たした場合にそのセルを早期停止する．$\tau_{\rm stop}=\ln 10$ は透過率 $\exp(-\tau_{\rm eff})$ が $0.1$ 以下となる目安に対応し，到達したセルでは火星放射が表層へ到達するという近似が破綻するため，以後の時間発展は本モデルの適用範囲外として追跡しない（停止は円盤の物理的停止を意味しない）．以上により，積分期間を物理的な高温期に合わせつつ，質量保存誤差が許容範囲に収まる設定でのみ結果を採用する．
