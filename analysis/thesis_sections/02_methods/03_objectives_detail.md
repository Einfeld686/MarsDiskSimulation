## 研究目的（3点）と、それぞれが長期モデルへどう効くか

ここからが本研究の核です。研究目的は、次の三点として固定します。

### 目的1：\(\tau\) の定義を 3 次元幾何として扱い、表層での照射を許す

光がどれだけ遮られるかを表す無次元量があります。用語としては **光学的厚み（optical depth） \(\tau\)** です。以後は「遮られやすさ \(\tau\)」と書きます。

Hyodo et al. (2018) は、衝突直後計算の出力（20 hr と 33 hr のスナップショット）を 3 次元格子に落とし、火星表面から円盤粒子へ向かう視線に沿って**半径方向に積分した \(\tau\)** を計算しました。その際、質量を半径 1.5 m の粒子に換算して \(\tau\) を評価しています。

Hyodo et al. (2018) の計算手順を式\ref{eq:tau_cell_def}で書くと、まず各格子セルについて
\begin{equation}
\label{eq:tau_cell_def}
\tau_{\rm cell}=\frac{\sum_i \sigma_i}{S}
\end{equation}
ここで \(\tau_{\rm cell}\) はセルの光学的厚み、\(\sigma_i\) は粒子 \(i\) の幾何学断面積、\(S\) はセル断面積であり、各セルで断面積を足し合わせる仮定を置く。
そのうえで火星表面から粒子までの視線上にあるセルを足し上げ、半径方向に積分した \(\tau\) を式\ref{eq:tau_radial_sum}で評価します。
\begin{equation}
\label{eq:tau_radial_sum}
\tau=\sum \tau_{\rm cell}
\end{equation}
ここで \(\tau\) は火星から見た視線方向の積分光学厚であり、視線上のセルを合算する。
ここで \(\sigma_i=\pi r_p^2\) とし、すべての質量が \(r_p=1.5\,\rm m\) の粒子で表されると仮定します。Hyodo et al. (2017a) では、この粒径を用いた腕状構造の遮られやすさが \(\tau\sim10\) と評価されています（Sec. 3.4）。

Hyodo et al. (2018) の Fig. 5 では、密な tidal arm の中心部は \(\tau>1\) で放射圧の影響を受けにくい一方、arm の上側や外側（例：\(\gtrsim 15R_{\rm Mars}\)）は \(\tau<1\) となり放射圧を受ける、と整理されています。さらに \(\tau<1\) の粒子が全円盤質量の \(\sim20\%\)（20 hr）から \(\sim34\%\)（後半のスナップショット）を占め得る、と見積もられています。

一方で、この整理だけでは「厚い円盤なら安全」とは言い切れません。理由は単純で、\(\tau\) が視線方向の積分量であるため、円盤を鉛直に切ったときの**表層**の扱いが直接には入らないからです。

そこで本研究では、「光学的に厚い円盤でも、表層は照射され得る」という一般論を採用します。この考え方は、原始惑星系円盤で Takeuchi & Lin (2003) が導入した **表層と内部を分ける扱い**に対応します。火星デブリ円盤はガスが少ない可能性があるため、彼らの式をそのまま使うのではなく、**照射が表層に局在する**という幾何だけを取り込みます。

### 目的2：遷移期の \(\Delta M_{\rm in}\) を積算し、長期モデルの入力を更新する

Canup & Salmon (2018) の \(a_{\rm eq}\) への写像は、円軌道化・赤道化を「速い過程」として取り込むうえで有効です。しかしその一方で、遷移期に起こり得る不可逆損失が、長期モデルへ渡る前に明示的には積算されていません。

本研究では、遷移期を \([t_{\rm SPH}, t_{\rm ss}]\) として定義し、この区間の損失を時間積分します。\(t_{\rm ss}\) は「準定常な円盤として状態量を定義できるようになった時刻」であり、少なくとも式\ref{eq:tss_max_obj}のように、円軌道化の時間 \(t_{\rm circ}\) と歳差混合の時間 \(t_{\rm prec}\) の大きい方で見積もります。
\begin{equation}
\label{eq:tss_max_obj}
t_{\rm ss}\;\approx\;\max(t_{\rm circ},\,t_{\rm prec})
\end{equation}
ここで \(t_{\rm circ}\) は円軌道化の時間、\(t_{\rm prec}\) は歳差混合の時間であり、遷移期はより遅い過程で決まると仮定する。Hyodo et al. (2017b) の見積もりでは、\(t_{\rm circ}\) は数十日、\(t_{\rm prec}\) は 1–100 年になり得る。したがって損失の積算区間は、日〜年スケールまで広がり得るため、損失量は式\ref{eq:delta_min_obj}で評価する。
\begin{equation}
\label{eq:delta_min_obj}
\Delta M_{\rm in} = \int_{t_{\rm SPH}}^{t_{\rm ss}} \dot M_{\rm loss}(t)\,dt
\end{equation}
ここで \(\dot M_{\rm loss}(t)\) は表層での不可逆損失率であり、\(t_{\rm SPH}\) を衝突直後計算の終端時刻として積分する。
\begin{equation}
\label{eq:min_input_update_obj}
M_{\rm in}^{\rm (input)} = M_{\rm in}^{\rm (SPH)} - \Delta M_{\rm in}
\end{equation}
式\ref{eq:min_input_update_obj}では、\(M_{\rm in}^{\rm (SPH)}\) を衝突直後計算が与える内側円盤質量、\(M_{\rm in}^{\rm (input)}\) を長期モデルへ渡す入力として定義する。損失は \(\tau<1\) の表層や高 \(a_{\rm eq}\) の外縁側に偏る可能性があるため、一様減少として扱わないことが重要です。

この「入力更新」は、長期モデル（Salmon & Canup 2012 型の連続円盤進化）を置き換えるものではありません。長期モデルが前提とする「準定常な円盤が定義できる時刻」へ到達するまでの間に、**入力側で失われた分を補正してから渡す**ための接続部です。

### 目的3：火星表面冷却の一次近似を、同じ仮定のまま積分形へ直して有効期間を見積もる

Hyodo et al. (2018) は、火星表面温度の冷却時間を、放射損失率と熱容量の比で見積もり、深さ \(D=100\) km の加熱層について代表値として約 717 日を示しています。これは、分母側の \(T^4\) を代表温度で固定する「割り算型」の評価です。

同じ仮定（熱容量一定、黒体放射、冷却層の厚さ一定）を保ったまま、温度が下がると放射が弱まる効果を入れるには、温度の微分方程式として書き直して積分します。面積あたりの熱収支を式\ref{eq:cooling_ode_obj}で表すと、
\begin{equation}
\label{eq:cooling_ode_obj}
\rho C_p D \frac{dT}{dt} = -\sigma_{\rm SB} T^4
\end{equation}
ここで \(\rho\) は密度、\(C_p\) は比熱、\(D\) は加熱層厚さであり、黒体放射と一定物性を仮定する。
これを \(T_0\to T_1\) で積分すると式\ref{eq:cooling_integral_obj}となります。
\begin{equation}
\label{eq:cooling_integral_obj}
t(T_0\to T_1)=\frac{\rho C_p D}{3\sigma_{\rm SB}}\left(\frac{1}{T_1^3}-\frac{1}{T_0^3}\right)
\end{equation}
式\ref{eq:cooling_integral_obj}は、温度低下による放射損失の減衰を含めた冷却時間を与える。

Hyodo et al. (2018) と同じ代表値（\(\rho=3000\,{\rm kg\,m^{-3}}\)、\(C_p=1000\,{\rm J\,kg^{-1}\,K^{-1}}\)、\(D=100\,{\rm km}\)）を用いると、4000 K → 1000 K は **約 55 年**になります。

この差は、「どれくらいの期間、火星起源の強い放射が円盤表層へ作用し得るか」という入力を変えます。そこで本研究では、火星表面温度 \(T_{\rm Mars}(t)\) の扱いを感度要因として明示し、短い年スケール（割り算型）と長い数十年スケール（積分型）の両方で \(\Delta M_{\rm in}\) を評価します。

<!-- TEX_EXCLUDE_START -->
### 先行研究リンク
- [Hyodo et al. (2017a)](../../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)
- [Hyodo et al. (2017b)](../../paper/pdf_extractor/outputs/Hyodo2017b_ApJ851_122/result.md)
- [Hyodo et al. (2018)](../../paper/pdf_extractor/outputs/Hyodo2018_ApJ860_150/result.md)
- [Canup & Salmon (2018)](../../paper/pdf_extractor/outputs/CanupSalmon2018_SciAdv4_eaar6887/result.md)
- [Salmon & Canup (2012)](../../paper/pdf_extractor/outputs/SalmonCanup2012_ApJ760_83/result.md)
- [Takeuchi & Lin (2003)](../../paper/pdf_extractor/outputs/TakeuchiLin2003_ApJ593_524/result.md)

<!-- TEX_EXCLUDE_END -->

---
