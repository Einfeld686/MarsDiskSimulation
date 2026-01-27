## 1. 放射圧ブローアウトによる質量損失

### 1.1 Canup--Salmon (2018) の衝突直後の火星表面温度の見積もり

\citet{CanupSalmon2018_SciAdv4_eaar6887} は，巨大衝突により形成されたデブリ円盤からフォボス・ダイモスが形成され得ることを示し，その円盤が Vesta-to-Ceres-sized 規模の衝突体で生成され得ると結論づけている．
SPH シミュレーション結果は，$M_{\rm imp}=0.5\times10^{-3}M_{\rm Mars}$，$v_{\rm imp}=1.5v_{\rm esc}$（$7\,\mathrm{km\,s^{-1}}$），衝突角 $45^\circ$ の条件である．この計算では，衝突後約 $10\,\mathrm{h}$ の時点で円盤質量が $8.5\times10^{-6}M_{\rm Mars}$ 程度となり，円盤外縁はフォボス・ダイモスの形成領域（$5$–$7R_{\rm Mars}$）と整合するスケールに達している．さらに，ロッシュ限界外側を周回する円盤物質は火星起源が優勢（質量比で約 $85\%$）であり，蒸気分率は質量で約 $12\%$，温度は $1800$–$2000\,\mathrm{K}$ と報告されている．また，成功例は衝突角 $30^\circ$–$60^\circ$，衝突速度 $5$–$15\,\mathrm{km\,s^{-1}}$ の範囲に広がることも示されている．ここでの $1800$–$2000\,\mathrm{K}$ は，円盤物質（とくに外側円盤）の温度である．
円盤表層微粒子が火星から受ける放射場を $T_{M,0}$ で表現するには，衝突点近傍で加熱された火星表面がどの程度の温度に達し，その高温域がどの程度の面積で放射を担うのかを切り分けて見積もる必要がある．そのため，本研究では，\citet{Hyodo2018_ApJ860_150} による衝突直後火星の表面温度分布と，それをオーダー評価する近似式を用いて火星表面温度を見積もる．

\citet{Hyodo2018_ApJ860_150} は，巨大衝突直後の火星表面が衝突点近傍で顕著に加熱され，表面温度 $T_{\rm pla}$ が $5000$–$6000\,\mathrm{K}$ に達する高温域を含むことを示している．他にも $3000$–$4000\,\mathrm{K}$，$\sim1000\,\mathrm{K}$ の領域が共存する．この温度上昇を簡便に見積もるため，衝突点近傍の温度上昇 $\Delta T$ を

\begin{equation}
\Delta T \simeq \frac{E_{\rm heat}}{C_p M_{\rm heat}}
\label{eq:disc-dT_hyodo}
\end{equation}

で近似している．ここで $E_{\rm heat}$ は加熱に寄与するエネルギー，$M_{\rm heat}$ は加熱される物質量，$C_p$ は比熱である．\citet{Hyodo2018_ApJ860_150} は，等圧コアの体積が衝突体と同程度であるとして $M_{\rm heat}\sim M_{\rm imp}$ を仮定し，さらに衝突エネルギー $E_{\rm imp}$ が火星と衝突体へ概ね等分配され，そのうち内部エネルギー増分に回る割合も考慮して $E_{\rm heat}\sim0.25E_{\rm imp}$ としている．比熱として $C_p=1000\,\mathrm{J\,kg^{-1}\,K^{-1}}$ を置くと，$\Delta T\sim4000\,\mathrm{K}$ が得られ，数値結果と整合する．
このスケーリングを，\citet{CanupSalmon2018_SciAdv4_eaar6887} の例（$v_{\rm imp}=1.5v_{\rm esc}$）においても用いることにする．衝突体の運動エネルギーを $E_{\rm imp}\simeq \tfrac{1}{2}M_{\rm imp}v_{\rm imp}^2$ と置き，\citet{Hyodo2018_ApJ860_150} と同様に $E_{\rm heat}\sim0.25E_{\rm imp}$，$M_{\rm heat}\sim M_{\rm imp}$ を仮定すると，

\begin{equation}
\Delta T \simeq \frac{0.25\times \tfrac{1}{2}M_{\rm imp}v_{\rm imp}^2}{C_p M_{\rm imp}}
= \frac{1}{8}\frac{v_{\rm imp}^2}{C_p}
\label{eq:disc-dT_canup}
\end{equation}

となる．ここで $\Delta T$ は $M_{\rm imp}$ に依存せず，$v_{\rm imp}$ と $C_p$ により決まる（$M_{\rm heat}\sim M_{\rm imp}$）．ここに，$v_{\rm imp}=7\,\mathrm{km\,s^{-1}}$（$=7\times10^3\,\mathrm{m\,s^{-1}}$）と $C_p=1000\,\mathrm{J\,kg^{-1}\,K^{-1}}$ を代入すると，

\[
\Delta T \approx 6.1\times10^3\,\mathrm{K}
\]

が得られる．これは，\citet{Hyodo2018_ApJ860_150} が示した数千 K 級の局所高温域が，Canup & Salmon 型の衝突速度条件でも原理的に生じ得ることを示す．

次に，本研究で用いる $T_{M,0}$ を，この局所高温を踏まえて定義し直す．$T_{M,0}$ は，円盤表層微粒子が受ける火星放射場を黒体の有効温度で代表するパラメータである．衝突直後の火星表面温度は一様ではないため，放射場を等価な一様黒体に置き換えるには，高温域が担う面積分率によって決まる．そこで，衝突点近傍の高温域（温度 $T_{\rm hot}$，面積 $S_{\rm hot}$）と，それ以外の背景領域（温度 $T_{\rm bg}$）からなる二温度モデルを考え，有効温度 $T_{M,0}$ を

\begin{equation}
4\pi R_{\rm Mars}^2 \sigma_{\rm SB} T_{M,0}^4
\simeq \sigma_{\rm SB}\left(S_{\rm hot}T_{\rm hot}^4 + (4\pi R_{\rm Mars}^2-S_{\rm hot})T_{\rm bg}^4\right)
\label{eq:disc-Teff}
\end{equation}

で定義する．$T_{\rm bg}\ll T_{\rm hot}$ とみなせる場合には，

\[
T_{M,0}\simeq T_{\rm hot}\left(\frac{S_{\rm hot}}{4\pi R_{\rm Mars}^2}\right)^{1/4}
\]

となり，$T_{M,0}$ は高温域の面積分率の $1/4$ 乗となる．
$S_{\rm hot}$ は本来 SPH シミュレーション結果に依存するが，最も強く加熱される領域の代表スケールは衝突体サイズと同程度という仮定を置いて計算する．これは\citet{Hyodo2018_ApJ860_150} において $M_{\rm heat}\sim M_{\rm imp}$ を仮定し，その根拠として等圧コアの体積が衝突体と同程度であるとした仮定を用いている．これによると，高温域は衝突体半径 $R_{\rm imp}$ 程度の領域に主として局在し，$S_{\rm hot}\sim\pi R_{\rm imp}^2$ と置くことができる．その場合，$T_{\rm hot}\sim6000\,\mathrm{K}$ を仮定しても $T_{M,0}$ は $\sim10^3\,\mathrm{K}$ 級に落ち，$T_{M,0}\sim(1$–$2)\times10^3\,\mathrm{K}$ が目安となる．
一方で，衝突点近傍の溶融・蒸気プルームがより広域を覆い，高温域が衝突体サイズの数倍へ拡大するなら $S_{\rm hot}$ が増加し，$T_{M,0}$ は非線形に上昇する．高温域半径が $R_{\rm hot}\sim(3$–$7)R_{\rm imp}$ まで広がると，式\ref{eq:disc-Teff} が与える $T_{M,0}$ は $\sim(2$–$3)\times10^3\,\mathrm{K}$ に達し得る．

以上より，Canup & Salmon 型衝突は外側円盤温度として $1800$–$2000\,\mathrm{K}$ を与える一方で，\citet{Hyodo2018_ApJ860_150} の近似式に沿えば衝突点近傍の火星表面は $6000\,\mathrm{K}$ 程度まで上昇し得る．その局所高温がどの程度の面積を担うかが，有効放射温度 $T_{M,0}$ を決める支配因子となる．全体的には $T_{M,0}\sim10^3$–数$\times10^3\,\mathrm{K}$ を採用し，局所的に $T_{M,0}\sim3000$–$5000\,\mathrm{K}$ 相当の表面温度も考えることができる．

### 1.2 質量損失が衛星形成に与える影響

本研究の短時間シミュレーションが与える放射圧ブローアウトの累積損失 $M_{\rm loss}(t_{\rm end})$ を，長期の衛星形成計算へ接続する際における放射圧による早期損失が，\citet{CanupSalmon2018_SciAdv4_eaar6887} 型の成功条件に与える影響を議論する．
内側円盤からの放射圧ブローアウトは，パラメータによって $M_{\rm loss}(t_{\rm end})\sim 2\times10^{-8}$ から $1.1\times10^{-4}\,M_{\rm Mars}$ まで広い範囲を取り得る．また，累積損失が $99\%$ に達する時刻 $t_{99}$ は $0.19$–$0.84\,\mathrm{yr}$ であり，質量流出率も $t\simeq0.05$–$1.3\,\mathrm{yr}$ で十分小さくなる（図\ref{fig:results_cumloss_grid}，図\ref{fig:results_moutdot_grid}）．これは，放射圧ブローアウトがごく初期の短時間でほぼ終わるイベント的損失として現れることを意味する．
一方で，Canup & Salmon の長期集積モデルでは，ロッシュ限界外側の円盤が $10^4$–$10^5$ 年で衛星へ集積し，内側で成長した比較的大きい衛星が潮汐により $10^5$–$10^6$ 年で内側へ落下するという時間発展が明示されている．したがって，本研究が捉える $t\lesssim1\,\mathrm{yr}$ の損失過程は，長期計算を開始する以前に，初期円盤がすでに削られているとすることができる．

ここで，短時間で内側円盤から失われる質量を
\[
\Delta M \equiv M_{\rm loss}(t_{\rm end})
\]
と置き，これを長期集積計算に入る前の補正項とみなす．本研究の短時間計算が与えるのは内側円盤からの損失であるため，長期計算へ渡す円盤質量の第一近似として，

\begin{equation}
M_{\rm disk,eff} \equiv M_{\rm disk,0}-\Delta M
\label{eq:disc-mdisk-eff}
\end{equation}

と定義する．ここで $M_{\rm disk,0}$ は衝突直後に形成された円盤（内側＋外側を含む）の総質量，$M_{\rm disk,eff}$ は長期集積計算の開始時点で有効に残っている総質量である．
フォボス・ダイモス級の小衛星を同期軌道近傍に生存させるには，初期円盤質量が $M_{\rm disk}\le 3\times10^{-5}M_{\rm Mars}$ であり，かつ潮汐パラメータが $(Q/k_2)<80$ 程度であることが必要である．この質量上限条件を式\ref{eq:disc-mdisk-eff}で書き換えると，
\begin{equation}
M_{\rm disk,0} \le 3\times10^{-5}M_{\rm Mars} + \Delta M
\label{eq:disc-mdisk-upper-shift}
\end{equation}
となり，$\Delta M$ だけ衝突直後円盤質量の上限が平行移動する．
$\Delta M\simeq10^{-5}M_{\rm Mars}$ 程度の早期損失が生じるなら，式\ref{eq:disc-mdisk-upper-shift}は $M_{\rm disk,0}\lesssim 4\times10^{-5}M_{\rm Mars}$ となる．これは Canup & Salmon の集積計算に入れる円盤は $3\times10^{-5}$ 以下とした条件を，衝突直後の円盤に対しては約 $33\%$ 緩めることに相当する．
また，初期円盤質量が同期軌道外側に残る質量へどの程度変換されるかを変換効率

\begin{equation}
\eta \equiv \frac{M(>a_{\rm sync})}{M_{\rm disk}}
\label{eq:disc-eta}
\end{equation}

で定義する．ここで $M(>a_{\rm sync})$ は最終的に同期軌道 $a_{\rm sync}$ の外側に残った衛星の総質量である．
\citet{CanupSalmon2018_SciAdv4_eaar6887}では，$M_{\rm disk}=10^{-5}M_{\rm Mars}$ の Run 1 では $M(>a_{\rm sync})=2.71\times10^{-8}M_{\rm Mars}$，$M_{\rm disk}=2\times10^{-5}M_{\rm Mars}$ の Run 16 では $1.83\times10^{-8}M_{\rm Mars}$，$M_{\rm disk}=3\times10^{-5}M_{\rm Mars}$ の Run 59 では $4.25\times10^{-8}M_{\rm Mars}$ が得られている．したがって，$\eta$ は概ね $\eta\sim(0.9$–$2.7)\times10^{-3}$（0.1–0.3\%）程度と見積もられる．
フォボス＋ダイモスの総質量 $M_{\rm PD}$ を同期軌道外側に残すには，少なくとも
\[
M_{\rm disk,eff} \gtrsim \frac{M_{\rm PD}}{\eta}
\]
が必要である．上の $\eta$ 範囲を用いると，$M_{\rm disk,eff}$ は概ね $(0.74$–$2.19)\times10^{-5}M_{\rm Mars}$ 程度以上であることが要請される．これを式\ref{eq:disc-mdisk-eff}で衝突直後質量へ戻すと，
\begin{equation}
M_{\rm disk,0} \gtrsim \frac{M_{\rm PD}}{\eta} + \Delta M
\label{eq:disc-mdisk-lower-shift}
\end{equation}
となり，$\Delta M$ は上限だけでなく下限も同じだけ押し上げる．
$\Delta M=10^{-5}M_{\rm Mars}$ を仮定すると，下限は $M_{\rm disk,0}\gtrsim (1.74$–$3.19)\times10^{-5}M_{\rm Mars}$ へ移動し，上限は先の式\ref{eq:disc-mdisk-upper-shift}より $M_{\rm disk,0}\lesssim 4\times10^{-5}M_{\rm Mars}$ となる．結果として，衝突直後円盤質量に対して
\[
M_{\rm disk,0}\sim (1.7\text{–}4.0)\times10^{-5}M_{\rm Mars}
\]
程度の許容域を与えることができる．
早期損失がこれほど影響する理由として，$\sigma$ をほぼ比例的に下げる作用を持つため，式\ref{eq:disc-timescale-scaling}において $(Q/k_2)$ でも潮汐が相対的に効きやすい方向になるからであると考えることができる．\citet{CanupSalmon2018_SciAdv4_eaar6887} の $M_{\rm disk}=3\times10^{-5}M_{\rm Mars}$ のケースにおいて，ロッシュ限界外側の初期質量は $M_{\rm disk}(>a_R)=1.5\times10^{-6}M_{\rm Mars}$ であり，ロッシュ限界内側の元手は $2.85\times10^{-5}M_{\rm Mars}$ 程度である．この内側成分から $\Delta M=10^{-5}M_{\rm Mars}$ が失われると，内側の質量は約 $35\%$ 減少する．一次近似として $\sigma$ が同率で下がるとみなすなら，式\ref{eq:disc-timescale-scaling}の支配パラメータ $(Q/k_2)\sigma$ も $35\%$ 減り，Canup & Salmon が境界として示した $(Q/k_2)\simeq80$ は，$\sigma$ が軽くなった円盤に対して $(Q/k_2)\simeq 50$ 程度に相当する方向へ動く．
