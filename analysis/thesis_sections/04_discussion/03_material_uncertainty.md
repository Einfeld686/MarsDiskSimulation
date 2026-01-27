<!-- TEX_EXCLUDE_START -->
* 放射圧効率 $Q_{\rm pr}=Q_{\rm abs}+Q_{\rm sca}(1-g)$ の標準的定義は Burns et al. (1979) に明記されている．([Astrophysics Data System][1])
* フォルステライト蒸発における蒸発係数 $\alpha$ の例として，Nagahara--Ozawa (1996) で $\alpha\simeq0.06$〜$0.2$ が示されている（条件依存）．([科学ダイレクト][2])
* Tsuchiyama et al. (1998) では $\alpha=0.1$ を採用している旨が記載されている．
* Hyodo et al. (2017, ApJ 845, 125) の論文情報（DOI 等）は ADS で確認できる．
* Pignatale et al. (2018) は「ダストは金属鉄・硫化物・炭素に富み，ソリッドはケイ酸塩に富む」という要旨を明記している（本文冒頭の要約）．([スペースポール出版サーバー][3])

[1]: https://ui.adsabs.harvard.edu/abs/1979Icar...40....1B/abstract "https://ui.adsabs.harvard.edu/abs/1979Icar...40....1B/abstract"
[2]: https://www.sciencedirect.com/science/article/abs/pii/0016703796000142 "https://www.sciencedirect.com/science/article/abs/pii/0016703796000142"
[3]: https://publi2-as.oma.be/record/4196/files/pignatale2018.pdf "https://publi2-as.oma.be/record/4196/files/pignatale2018.pdf"
<!-- TEX_EXCLUDE_END -->

## 3. 物性値の不確かさが $M_{\rm loss}$ に与える影響

### 3.1 放射圧支配：$Q_{\rm pr}$ の定義

ここでは，放射圧パラメータ $\beta$，放射圧効率 $Q_{\rm pr}$，およびブローアウト臨界値 $\beta_{\rm crit}$ を整理する．
放射圧パラメータ $\beta(s)$ は，粒子半径 $s$ のダストに働く放射圧力 $F_{\rm rad}(s)$ と火星重力 $F_{\rm grav}(s)$ の比として式\ref{eq:beta_definition}で定義される．以下では，物性依存性がどの組に集約されるかを確認する．

距離 $r$ にある粒子が火星の熱放射（光度 $L$）を受けるとき，受け取るエネルギーフラックスは $L/(4\pi r^2)$ である．球形粒子の幾何学的断面積は $\pi s^2$ であり，光子の運動量フラックスは $1/c$ を介して放射圧に変換される．そこで，火星放射スペクトルで重み付けした Planck 平均 $\langle Q_{\rm pr}\rangle(s,T_M)$ を用いると，
\begin{align*}
F_{\rm rad}(s) &= \frac{L}{4\pi r^2}\,\frac{\pi s^2}{c}\,\langle Q_{\rm pr}\rangle(s,T_M) \\
F_{\rm grav}(s) &= \frac{G M_{\rm Mars} m}{r^2}
=\frac{G M_{\rm Mars}}{r^2}\left(\frac{4\pi}{3}\rho s^3\right)
\end{align*}
と書ける．ここで $c$ は光速，$G$ は重力定数，$M_{\rm Mars}$ は火星質量，$m=(4/3)\pi\rho s^3$ は粒子質量，$\rho$ は粒子のバルク密度である．したがって，両力が $r^{-2}$ で同じ距離依存性を持つ理想化のもとでは，
\begin{equation}
\beta(s)=\frac{3L}{16\pi c G M_{\rm Mars}}\,
\frac{\langle Q_{\rm pr}\rangle(s,T_M)}{\rho\,s}
\label{eq:beta_Q_over_rho}
\end{equation}
を得る．この式が示すとおり，$\beta$ が物性に依存する主要因は $\langle Q_{\rm pr}\rangle/\rho$（および粒径 $s$）に集約される．
放射圧効率 $Q_{\rm pr}(\lambda,s)$ は，波長 $\lambda$ ごとの吸収効率 $Q_{\rm abs}$，散乱効率 $Q_{\rm sca}$，および散乱の非等方性を表す非対称因子 $g\equiv\langle \cos\theta\rangle$ を用いて
\begin{equation}
Q_{\rm pr}(\lambda,s)=Q_{\rm abs}(\lambda,s)+Q_{\rm sca}(\lambda,s)\left(1-g(\lambda,s)\right)
\label{eq:Qpr_definition}
\end{equation}
と定義される \citep{Burns1979_Icarus40_1}．前方散乱が強いほど $g\to 1$ となり，散乱による運動量付与が減少して $Q_{\rm pr}$ が小さくなるため，$Q_{\rm pr}$ は吸収・散乱の強さだけでなく散乱位相関数（粒子形状・多孔質度）にも依存する．本研究では球形・コンパクト粒子を仮定し，複素屈折率から Mie 理論により $Q_{\rm abs}$ と $Q_{\rm sca}$ を評価する（\citealp{BohrenHuffman1983_Wiley}）．

### 3.2 蒸発の不確かさ：$\alpha$ のレンジと $ds/dt$ 近似の成立条件

放射圧が支配的な条件でも，ブローアウト時間 $t_{\rm blow}$ と蒸発（昇華）時間 $t_{\rm sub}$ の大小関係が入れ替わる境界領域では，蒸発モデルの不確かさがどちらが先に起きるかを左右する．その境界を動かす主要因が，Hertz–Knudsen–Langmuir（HKL）型の正味蒸発フラックスに現れる蒸発係数 $\alpha$ である．
本研究では，粒子表面からの正味の質量フラックス $\dot m$（$\mathrm{kg\,m^{-2}\,s^{-1}}$）を，飽和蒸気圧と環境分圧の差で駆動される HKL 形式として

\begin{equation}
\dot m
= \alpha \left(P_{\rm sat}(T_p)-P_{\rm env}\right)
\sqrt{\frac{\mu}{2\pi R T_p}}
\label{eq:disc-hkl}
\end{equation}

と表す．ここで $P_{\rm sat}(T_p)$ は粒子温度 $T_p$ における飽和蒸気圧，$P_{\rm env}$ は周囲の同種蒸気の分圧，$\mu$ は（代表）モル質量，$R$ は気体定数である．$\alpha$ は $0<\alpha\le 1$ の無次元係数であり，理想的な運動論的上限（表面反応が律速しない極限）からどれだけ実効フラックスが抑制されるかをまとめて表す量と解釈できる．したがって $\alpha$ は材料定数というより，表面状態や実験条件の違いを吸収する速度論パラメータである．

$\alpha$ の取り得るレンジについては，フォルステライトに対する低圧蒸発実験が目安を与える．例えば Nagahara--Ozawa（1996）は Hertz--Knudsen 式に基づく係数（論文内では凝縮係数として議論）を評価し，真空条件で $\alpha\sim 0.06$，より高い全圧条件で $\alpha$ が $\sim 0.2$ 程度まで増加し得ることを示している \citep{NagaharaOzawa1996_GeCoA60_1445}．また Tsuchiyama ら（1998）は実験・既往研究を整理し，$\alpha$ が温度・$p(\mathrm{H_2})$ に依存して概ね $0.03$–$0.2$ 程度の幅をとることを報告している \citep{Tsuchiyama1998_MinerJ20_113}．このように値が条件依存である以上，$\alpha$ を単一値に固定するよりも，感度解析の軸として掃引するほうが妥当である．とくに $P_{\rm env}\ll P_{\rm sat}$ の極限では式\ref{eq:disc-hkl} より $\dot m\propto \alpha$ となるため，$t_{\rm sub}$ は第一近似として $t_{\rm sub}\propto 1/\alpha$ で伸縮し，$t_{\rm blow}\simeq t_{\rm sub}$ の境界位置が直接動く．

次に，粒子半径の時間変化を
\begin{equation}
\frac{ds}{dt}=-\frac{\dot m}{\rho}
\label{eq:disc-dsdt}
\end{equation}
で表す近似が暗に置いている前提を明文化する．これは，球形粒子の質量 $m=(4/3)\pi \rho s^3$ と表面からの質量損失 $dm/dt=-4\pi s^2\dot m$ を結び付けた結果であり，数学的には整合的である．一方で，この写像が物理的に意味を持つためには少なくとも三つの条件が必要となる．

第一に，粒子を単一温度 $T_p$ で代表できるだけの熱的準静性が必要である．粒子内部に大きな温度勾配が生じる，あるいは組成分離が進む場合には，蒸発は表面全体で一様に進むとは限らず，半径変化を単純な一様収縮として扱う近似から外れ得る．この点は「$ds/dt$ は幾何学的な代表半径の変化であり，微視的な局所蒸発の不均一性を平均化した量である」という限定として理解すべきである．

第二に，本研究では $\alpha$ を時間一定の係数として扱っている．実際には表面粗さの発達，融解・再凝縮に伴うテクスチャ変化，あるいは表面被膜の形成などにより，$\alpha$ は時間変化し得る．したがって定数 $\alpha$ モデルは，蒸発を過大評価する方向にも過小評価する方向にも偏り得る．ここでは単一の「もっともらしい値」を主張するのではなく，$\alpha$ を掃引して $t_{\rm sub}$ の変動幅として提示することが，結論の頑健性を担保するうえで有効である．

第三に，式\ref{eq:disc-hkl} に含まれる $P_{\rm env}$ の扱いは本質的に「周囲がどれほど希薄か」に依存する．本研究では $P_{\rm env}\simeq 0$（蒸気が速やかに逃げる）という自由蒸発の極限を採用しており，これは蒸発を強めに見積もる方向に働く．実際の巨大衝突後円盤は多相（液体・固体・蒸気）が共存し得るため，状況によっては $P_{\rm env}$ を無視できず，正味フラックス $\dot m$ が抑制され得る．例えば \citet{Hyodo2017a_ApJ845_125} は，火星周回円盤は主として液相でありつつ，蒸気相も質量比で $<5\,\mathrm{wt}\%$ 程度存在し得ることを示している．蒸気が存在する以上，$P_{\rm env}$ の増加は $t_{\rm sub}$ を長くしやすく，その意味で本研究の蒸発評価は「蒸発を起こしやすい側に倒した」上限評価として位置づけられる．

最後に，蒸発が粒子の構造・力学を通じて放射圧応答（$\beta$）や衝突・破砕過程に跳ね返る効果は，式\ref{eq:disc-dsdt} の枠外にある．蒸発に伴う割れや多孔化が進めば有効密度の低下を通じて $\beta$ が増加し，ブローアウトが促進され得る．一方で被膜形成が支配的なら $\alpha$ が低下し，蒸発は抑制され得る．したがって現段階では，蒸発を「放射圧とは独立な半径収縮」として切り出し，まず $t_{\rm blow}$ と $t_{\rm sub}$ の大小関係で支配過程を分類する整理が現実的である．

以上を踏まえると，本研究の主要結論である「$M_{\rm loss}$ が放射圧支配で決まる」という状況では，物性不確かさは二段階で効く．第一段階として $\langle Q_{\rm pr}\rangle/\rho$ が $s_{\rm blow}$ と $t_{\rm blow}$ を動かし，第二段階として $\alpha$ と $P_{\rm env}$ の仮定が $t_{\rm sub}$ を動かす．したがって改良の優先順位としては，$\langle Q_{\rm pr}\rangle/\rho$ と $\alpha$ を独立パラメータとして掃引し，$t_{\rm blow}=t_{\rm sub}$ の境界がどの範囲で移動し得るかを系統的に示すことが最も実務的である．これにより，$\alpha$ の設定や真空近似の妥当性が問われた場合でも，境界の変動幅として定量的に応答できる．

### 3.3 フォルステライト仮定の妥当性と，代替物質が主流になり得る条件

本研究では，基準物性としてフォルステライト（Mg$_2$SiO$_4$）を仮定し，光学定数から Mie 理論で $\langle Q_{\rm pr}\rangle$ を評価する（\citealp{BohrenHuffman1983_Wiley}）とともに，昇華についてはフォルステライトの実験・コンパイル値を参考に $\alpha$ を設定した（\citealp{Tsuchiyama1998_MinerJ20_113,NagaharaOzawa1996_GeCoA60_1445}）．この仮定は，ケイ酸塩を主成分とする凝縮固体を代表させる最小モデルとして位置づけられる．

一方で，巨大衝突起源円盤の微粒子が単一鉱物に限定される保証はない．衝突・凝縮過程では，微粒子（dust）と比較的大きな固体（solid）で化学的・物理的性質が分化し得ることが示されており \citep{Pignatale2018_ApJ853_118}，微粒子の主成分がフォルステライトから系統的にずれる可能性は残る．

放射圧支配の枠組みでは，この違いは第一近似として式\ref{eq:beta_Q_over_rho}の $\langle Q_{\rm pr}\rangle/\rho$ に集約される．したがって代替物質が主流になる条件は，（i）有効密度（多孔化を含む）が大きく変化する場合，または（ii）赤外域での吸収・散乱特性の違いにより $\langle Q_{\rm pr}\rangle$ が系統的に変化する場合である．$\langle Q_{\rm pr}\rangle/\rho$ が増加すれば $s_{\rm blow}$ は大きくなり，放射圧除去は起こりやすくなる一方，減少すればブローアウトは抑制される．

蒸発についても，揮発性の高い成分が卓越すれば $t_{\rm sub}$ が短くなって蒸発優勢の領域が広がり得る．本研究では $\alpha$ を感度軸として扱ったため，この不確かさは「$t_{\rm blow}=t_{\rm sub}$ 境界の移動」として同じ枠組みで整理できる．したがって今後は，光学定数テーブルと昇華パラメータを材料ごとに差し替える感度解析により，フォルステライト仮定の外側にある系統誤差を定量化することが課題となる．
