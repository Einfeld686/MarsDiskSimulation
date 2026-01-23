## 4. 数値計算法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

### 4.1 離散化

**粒径空間の離散化**
サイズ空間は対数等間隔グリッドで離散化する．有効下限 $s_{\min,\mathrm{eff}}$ は，設定値 $s_{\min}$ と初期時刻のブローアウト粒径 $a_{\mathrm{blow}}(T_{\mathrm{init}})$ の大きい方として定める（実装では $s_{\min,\mathrm{eff}}=\max(s_{\min},a_{\mathrm{blow}})$ を採用する）．上限は $s_{\max}$ とし，$K$ 個のビン数 $K=n_{\mathrm{bins}}$ を与える．

ビン境界を $s_{k\pm1/2}$，代表サイズを $s_k=\sqrt{s_{k-1/2}s_{k+1/2}}$ とする．状態量 $N_k$ はビン $k$ に含まれる粒子の面数密度（$\mathrm{m^{-2}}$）であり，各ビンの代表質量を $m_k=\frac{4}{3}\pi\rho s_k^3$ とすると，表層面密度は $\Sigma=\sum_{k=1}^{K} m_k N_k$ で与えられる．以後，注入（供給）・損失（ブローアウト／昇華）・破片再配分はビン上で評価する．

**粒径範囲外の取り扱い**
$s<s_{\min,\mathrm{eff}}$ の成分は本研究の解像範囲外とし，放射圧による除去等で速やかに失われる成分として明示的な損失項に含める．また，$s>s_{\max}$ の大粒子は未解像成分として直接は追跡せず，必要に応じて「上限側への質量漏れ」を診断量として集計する（要確認：最終的に用いる診断量の定義）．

**半径方向の離散化**
半径方向は第1節で導入したセル分割に従い，各セル内では物理量を一様とみなす．粒径分布の更新はセルごとに行い，半径方向輸送（存在する場合）は別途のフラックス評価として組み込む（第2章で定義した輸送項に従う）．

### 4.2 数値解法と停止条件

**採用スキームの位置づけ**
既存研究では，collisional cascade の時間発展を一次の Euler 法と適応刻みで扱う例がある．一方で，Smoluchowski 型方程式の剛性に対しては陰的積分を用いることで大きな時間刻みを可能にすることが報告されている．本研究ではこれらを踏まえ，衝突ロス項を陰的に扱い，生成・供給・一次シンクを陽的に扱う一次 IMEX（IMEX-BDF(1)）を用いる．

**IMEX-BDF(1) 更新式**
外側ステップ幅を $\Delta t$ とし，Smoluchowski 更新に実際に用いる内部ステップ幅を $dt_{\mathrm{eff}}\le\Delta t$ とする．ビン $k$ の更新は
\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}
で与える．ここで $G_k$ は衝突破砕による生成項，$F_k$ は外部供給（注入）項，$S_k$ はブローアウト・昇華等の一次シンク（$\mathrm{s^{-1}}$）である．$t_{{\rm coll},k}$ は衝突カーネルから評価したビン $k$ の衝突時間スケールであり，カーネル行列 $C_{kj}$ と $N_k$ から「単位粒子あたりの衝突ロス率」を構成し，その逆数として定義する（対角成分の扱いはカーネル定義に従う）．本スキームはロス項に起因する剛性を緩和しつつ，計算コストを抑えるために一次の時間精度を選択したものである．

**時間刻み制御（非負性・質量保存）**
内部ステップ幅 $dt_{\rm eff}$ は，最小衝突時間に対する安全率で上限を設けて初期化し，非負性と質量収支に基づいて半減調整する（実装では $dt_{\max}=0.1\min_k t_{{\rm coll},k}$ を用いる）．手順は次の通りである．

1. $dt_{\rm eff}\leftarrow\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を設定する．
2. 式\ref{eq:imex_bdf1_update}で $N_k^{n+1}$ を計算する．
3. $N_k^{n+1}<0$ を含む場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
4. 式\ref{eq:mass_budget_definition}で相対誤差 $\epsilon_{\rm mass}$ を評価し，$\epsilon_{\rm mass}>\epsilon_{\rm tol}$ の場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
5. 条件 3–4 を満たした $dt_{\rm eff}$ を採用してステップを確定する．

ここで $\epsilon_{\rm tol}$ は質量保存誤差の許容値であり，本研究では $\epsilon_{\rm tol}=5\times10^{-3}$（0.5%）を用いる（要確認：本文・設定表との整合）．なお，質量収支の検査は「実際に採用された $dt_{\rm eff}$」に対して行う．

**質量収支の定義**
質量保存の検査は次式で定義する．
\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
\Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
\Delta\Sigma &= \Sigma^{n+1} + dt_{\rm eff}\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + dt_{\rm eff}\,\dot{\Sigma}_{\rm src}\right),\\
\epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}
$\dot{\Sigma}_{\rm src}$ は明示的な供給項 $F_k$ が与える質量注入率であり，$\dot{\Sigma}_{\rm src}=\sum_k m_k F_k$ として評価する．$\dot{\Sigma}_{\rm extra}$ は表層から系外へ失われる明示的な損失（ブローアウト・昇華など）を質量率として合算したものである．

#### 停止条件

**積分終端**
積分終端 $t_{\rm end}$ は解析対象期間として設定し，本研究では高温期の終端に対応する期間を採用する（例：火星温度モデル $T_{\rm Mars}(t)$ が所定値 $T_{\rm end}$ に到達する時刻を $t_{\rm end}$ とする，など；要確認）．

**光学的厚さに基づくセル停止**
各セルで線視方向光学的厚さ $\tau_{\rm los}$ が閾値 $\tau_{\rm stop}$ を超えた場合，当該セルの時間発展を早期停止する．実装では，$\tau_{\rm los}\propto \kappa,\Sigma_{\rm surf}$（幾何因子を含む）から評価した量が閾値を超えると停止する．$\tau_{\rm stop}=\ln 10$ は透過率 $\exp(-\tau_{\rm los})$ が $0.1$ 以下となる目安に対応し，この条件を満たすと「火星放射が表層へ到達する」という近似が破綻するため，以後の計算は本モデルの適用範囲外として扱う（停止は円盤の物理的停止を意味しない）．なお，光学的に厚い領域をクリップして擬似的に $\tau\lesssim1$ に保つのではなく，適用限界として停止する方針を採る．

**（任意）ブローアウト粒径が解像下限を下回る場合**
温度低下により $a_{\rm blow}$ が解像下限 $s_{\min}$ を下回る場合，放射圧除去が解像範囲より小さい粒径で起きるため，モデルの解像上の前提が変化する．実装には，この条件を満たしたときに計算を停止するオプションがあり，一定の最短積分期間を経た後に停止する．本論文では，この条件の採否と採用時の解釈を結果章で明示する（要確認）．

本節では，粒径分布の離散化，IMEX による時間積分，および非負性・質量収支に基づく刻み制御と停止条件を定義した．次節では，これらの設定の下で得られる進化計算の収束判定と結果の整理基準を述べる．
