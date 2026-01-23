<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

## 4. 数値計算法

### 4.1 離散化

粒径空間 $s\in[s_{\min},\,s_{\max}]$ を対数等間隔のビンに離散化し，ビン $k$ に含まれる粒子の面数密度
\[
N_k(t)=\int_{s_{k-1/2}}^{s_{k+1/2}} n(s,t)\,ds
\]
を状態量として時間発展させる．対数ビンによる粒径分布の表現は，衝突破砕カスケードの数値計算で広く用いられる\citep{Krivov2006_AA455_509,Thebault2003_AA408_775}．

各ビン中心を $s_k$，粒子質量を $m_k$ とし（球形粒子を仮定して $m_k=(4\pi/3)\rho s_k^3$），セル内の表面密度は
\[
\Sigma(t)=\sum_k m_k N_k(t)
\]
で評価する．衝突による再配分（破片生成）はビン上で行い，破片配分は各衝突における質量保存を満たすように構成する（例：$\sum_k m_k Y_{kij}=m_i+m_j$）．

下限側ではブローアウト半径の時間変化を考慮し，有効下限 $s_{\min,\mathrm{eff}}$ を用いる．具体的には，供給の注入下限やブローアウト判定に
\[
s_{\min,\mathrm{eff}}=\max\!\left(s_{\min},\,a_{\mathrm{blow,eff}}\right)
\]
を用いる（サイズ格子自体は $[s_{\min},s_{\max}]$ に固定し，物理過程の適用下限のみを $s_{\min,\mathrm{eff}}$ で切り替える）．上限 $s_{\max}$ は本研究で追跡する最大粒径であり，供給・初期条件はこの範囲に射影する．半径方向は 1節で定義したセル分割に従う．

### 4.2 数値解法と停止条件

時間積分は，衝突ロス項の剛性に対処するためロス項のみを陰的に扱い，破片生成・外部供給・一次シンクを陽的に扱う一次精度の IMEX 更新（IMEX-BDF(1)，すなわちロス項に対する陰的 Euler）を用いる．粒径分布の時間発展計算において暗黙（または半暗黙）積分が用いられることは先行研究でも一般的である\citep{Birnstiel2011_AA525_A11}．更新式は
\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}
で与える．ここで $G_k$ は衝突に伴う破片生成（ゲイン），$t_{{\rm coll},k}$ は衝突ロス時定数，$F_k$ は外部供給に対応する明示的ソース，$S_k$ はブローアウト・昇華・追加シンク等の一次シンク係数である．内部ステップ幅 $dt_{\rm eff}$ は外側ステップ幅 $\Delta t$ 以下とし，数値安定性のため
\[
dt_{\rm eff}\leftarrow\min\!\left(\Delta t,\,0.1\min_k t_{{\rm coll},k}\right)
\]
を初期値として用いる．その後，非負性と質量収支の検査に基づき必要に応じて $dt_{\rm eff}$ を縮小する．具体的には次の手順で時間刻み制御を行う．

1. $dt_{\rm eff}\leftarrow\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を設定する．
2. 式\ref{eq:imex_bdf1_update}で $N_k^{n+1}$ を計算する．
3. $N_k^{n+1}<0$ を含む場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
4. 式\ref{eq:mass_budget_definition}で $\epsilon_{\rm mass}$ を評価し，$\epsilon_{\rm mass}>0.5\%$ の場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
5. 3–4 を満たした $dt_{\rm eff}$ を採用してステップを確定する．

質量収支は各ステップで相対誤差 $\epsilon_{\rm mass}$ を評価する．ここでは Smol 更新で実際に用いた $dt_{\rm eff}$ に対して収支を検査する：
\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + dt_{\rm eff}\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + dt_{\rm eff}\,\dot{\Sigma}_{\rm prod}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}
ここで，$\dot{\Sigma}_{\rm prod}$ は外部供給により格子へ注入された質量供給率（$F_k$ に対応する全ビンの注入量の和）であり，$\dot{\Sigma}_{\rm extra}$ はブローアウト・昇華・追加シンク等，系外への明示的損失率の和である．本検査は数値誤差の診断として用い，許容範囲に収まる設定でのみ結果を採用する．

停止条件は，(i) 火星温度が所定の閾値 $T_M=T_{\rm end}$ に到達した時刻を積分終端 $t_{\rm end}$ とし（本論文では $T_{\rm end}=2000\,\mathrm{K}$），(ii) 各セルで視線方向の光学的厚さがしきい値 $\tau_{\rm stop}$ を超えた場合にそのセルを早期停止する．判定には，遮蔽が有効で $\kappa_{\rm eff}$ が有限な場合は $\tau_{\rm eff}$，それ以外は $\tau_{\rm los}$ を用いる（2.2節；遮蔽 OFF では $\Phi=1$ となり $\tau_{\rm eff}=\tau_{\rm los}$ に退化する）．$\tau_{\rm stop}=\ln 10$ は入射束の減衰が 1 桁程度となる目安として設定し，到達したセルでは表層へ到達する放射場の近似が破綻するため，以後の時間発展は本モデルの適用範囲外として追跡しない．
