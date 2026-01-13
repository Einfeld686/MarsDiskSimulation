> **文書種別**: リファレンス（Diátaxis: Reference）

<!--
NOTE: このファイルは analysis/thesis_sections/02_methods/*.md の結合で生成する。
編集は分割ファイル側で行い、統合は `python -m analysis.tools.merge_methods_sections --write` を使う。
-->


# シミュレーション手法

本資料は火星ロッシュ限界内の高温ダスト円盤を対象とする数値手法を、論文の Methods 相当の水準で記述する。gas-poor 条件下での粒径分布（particle size distribution; PSD）進化と、表層（surface layer）の放射圧起因アウトフロー（outflux）を**同一タイムループで結合**し、2 年スケールの $\dot{M}_{\rm out}(t)$ と $M_{\rm loss}$ を評価する。数式の定義は analysis/equations.md の (E.###) を正とし、本書では主要式を必要最小限に再掲したうえで、離散化・数値解法・運用フロー・検証条件を整理する。

序論（analysis/thesis/introduction.md）で提示した 3 つの問いと、本手法が直接生成する量・出力の対応を表\ref{tab:methods_questions_outputs}に示す。

\begin{table}[t]
  \centering
  \caption{序論の問いと手法で直接生成する量の対応}
  \label{tab:methods_questions_outputs}
  \begin{tabular}{p{0.22\textwidth} p{0.36\textwidth} p{0.38\textwidth}}
    \hline
    序論の問い & 手法で直接生成する量 & 対応する出力 \\
    \hline
    問1: 高温期（1000 K まで／固定地平 2 年）の総損失量 &
    時間依存の流出率と累積損失 &
    \texttt{series/run.parquet} の \texttt{M\_out\_dot}, \texttt{mass\_lost\_by\_blowout}, \texttt{mass\_lost\_by\_sinks}／\texttt{summary.json} の \texttt{M\_loss} \\
    問2: 粒径分布の時間変化と吹き飛びやすい粒径帯 &
    粒径ビンごとの数密度履歴と下限粒径 &
    \texttt{series/psd\_hist.parquet} の \texttt{bin\_index}, \texttt{s\_bin\_center}, \texttt{N\_bin}, \texttt{Sigma\_surf}／\texttt{series/run.parquet} の \texttt{s\_min} \\
    問3: 短期損失を踏まえた残存質量の評価 &
    累積損失と質量収支の時系列 &
    \texttt{summary.json} の \texttt{M\_loss}（初期条件との差分で残存量を評価）／\texttt{series/run.parquet} の \texttt{mass\_lost\_by\_blowout}, \texttt{mass\_lost\_by\_sinks} \\
    \hline
  \end{tabular}
\end{table}

読み進め方は次の順序を推奨する。

- まず入力と出力（何を与え、何が返るか）を確認する。
- 次に 1 ステップの処理順序（図 2.1–2.2）を把握する。
- その後、放射圧・供給・衝突・昇華・遮蔽の各過程を個別に読む。
- 最後に運用（run_sweep）と再現性（出力・検証）を確認する。

本文では物理的な因果と時間発展の説明を優先し、設定キーや実装パスは付録に整理する。式は必要最小限に再掲し、詳細な定義と記号表は analysis/equations.md を正とする。

本書で用いる略語は以下に統一する。光学的厚さ（optical depth; $\tau$）、視線方向（line of sight; LOS）、常微分方程式（ordinary differential equation; ODE）、implicit-explicit（IMEX）、backward differentiation formula（BDF）、放射圧効率（radiation pressure efficiency; $Q_{\rm pr}$）、破壊閾値（critical specific energy; $Q_D^*$）、Hertz–Knudsen–Langmuir（HKL）フラックス、1D（one-dimensional）。

---
## 1. 研究対象と基本仮定

本モデルは gas-poor 条件下の**軸対称・鉛直積分**ディスクを対象とし、半径方向に分割した 1D 計算を基準とする。粒径分布 $n(s)$ をサイズビンで離散化し、Smoluchowski 衝突カスケード（collisional cascade）と表層の放射圧・昇華による流出を同一ループで結合する。

- 標準の物理経路は Smoluchowski 経路（C3/C4）を各半径セルで解く 1D 手法で、実装の計算順序は図 2.2 に従う。放射圧〜流出の依存関係のみを抜粋すると ⟨$Q_{\rm pr}$⟩→β→$s_{\rm blow}$→遮蔽Φ→Smol IMEX→外向流束となる。半径方向の粘性拡散（radial viscous diffusion; C5）は演算子分割で追加可能とする。  
  > **参照**: analysis/overview.md §1, analysis/physics_flow.md §2「各タイムステップの物理計算順序」
- 運用スイープの既定は 1D とし、C5 は必要時のみ有効化する。具体的な run_sweep 手順と環境変数は付録 A、設定→物理対応は付録 B を参照する。
- [@TakeuchiLin2003_ApJ593_524] に基づく gas-rich 表層 ODE は `ALLOW_TL2003=false` が既定で無効。gas-rich 感度試験では環境変数を `true` にして `surface.collision_solver=surface_ode`（例: `configs/scenarios/gas_rich.yml`）を選ぶ。  
  > **参照**: analysis/equations.md（冒頭注記）, analysis/overview.md §1「gas-poor 既定」

1D は $r_{\rm in}$–$r_{\rm out}$ を $N_r$ セルに分割し、各セルの代表半径 $r_i$ で局所量を評価する。角速度 $\Omega(r_i)$ とケプラー速度 $v_K(r_i)$ は (E.001)–(E.002) に従い、$t_{\rm blow}$ や $t_{\rm coll}$ の基準時間に用いる。C5 を無効化した場合はセル間結合を行わず、半径方向の流束を解かない局所進化として扱う。

### 1.1 物性モデル (Hybrid Basalt/SiO₂)

物性は **Hybrid Basalt/SiO₂** を採用する。力学パラメータ（密度・$Q_D^*$）は玄武岩、放射圧効率 $\langle Q_{\rm pr}\rangle$ は SiO₂ テーブル、昇華は SiO 蒸気圧を用いる。混合物近似であるため、$\rho$ と $\langle Q_{\rm pr}\rangle$ の感度掃引を想定し、実行時の採用値は `run_config.json` に保存する。

$\langle Q_{\rm pr}\rangle$ はテーブル入力（CSV/NPZ）を標準とし、Planck 平均の評価に用いる。遮蔽係数 $\Phi(\tau,\omega_0,g)$ もテーブル入力を基本とし、双線形補間で適用する。これらのテーブルは `run_config.json` にパスが保存され、再現実行時の参照点となる。

> **参照**: analysis/equations.md（Hybrid Basalt/SiO₂ の前提）

---
## 遷移期の定義と基本仮定

本研究が扱うのは、巨大衝突で形成された火星周回デブリ円盤が、衝突直後の非軸対称・高離心・高傾斜な状態から、長期の衛星形成モデルが仮定する「ほぼ軸対称で円軌道に近い円盤」へ移るまでの**遷移期**である。衝突直後の円盤量は数値流体計算（例：Citron et al., 2015; Hyodo et al., 2017a）が与えるが、長期モデルへ渡すためには、円盤を軸対称な状態量へまとめ直す必要がある（Hyodo et al., 2017b; Canup & Salmon, 2018）。

長期モデルでは、ロッシュ限界内側の円盤を連続体として表し、内側円盤質量 \(M_{\rm in}\) と外縁 \(r_d\) の時間変化を、粘性拡散と外側天体との重力相互作用（共鳴トルクなど）で更新する（Salmon & Canup, 2012; Canup & Salmon, 2018）。この枠組みでは、内側円盤質量の主な減少項は「惑星への落下」と「ロッシュ限界外への拡散」である（Salmon & Canup, 2012; Canup & Salmon, 2018）。

一方で、遷移期には、照射を受ける表層に微粒子が存在し得るため、放射圧で除去され得る（Hyodo et al., 2018）。光学的に厚い円盤でも、直接照射されるのは表層の薄い領域であり、内部が厚いことだけから「放射圧が効かない」とは言い切れない（Takeuchi & Lin, 2003）。この種の不可逆損失が遷移期に生じるなら、長期モデルへ渡す直前に \(M_{\rm in}\) を更新する必要があるが、その積算手順は先行研究では明示されていない（Canup & Salmon, 2018）。

そこで本研究では、遷移期に生じ得る内側円盤の追加損失 \(\Delta M_{\rm in}\) を見積もり、長期モデルへ渡す入力を
\(M_{\rm in}\rightarrow M_{\rm in}'\) として更新する枠組みを定義する。以下では、文献を併記した記述は先行研究の結果または前提を要約したものであり、文献のない記述は本研究で置く定義または仮定である。

この章では、次章で文献の仮定を比較するために、(i) 遷移期の時間範囲、(ii) 内側円盤の空間領域、(iii) 表層／深部の簡約、(iv) 扱う物理過程と入出力、を先に固定する。

### 遷移期の始点 \(t_0\) と終点 \(t_{\rm end}\)

本研究は、数値流体計算が出力する「衝突後数十時間」の円盤を初期条件として固定し、その時刻を \(t=t_0\) とする（Citron et al., 2015; Hyodo et al., 2017a）。そして、\(t_{\rm end}\) までに起きる内側円盤の不可逆損失を時間積分して \(\Delta M_{\rm in}\) を得る。更新後の内側質量は、損失積分を式\ref{eq:delta_min_integral}で定義し、式\ref{eq:min_prime_update}で更新する。
\begin{equation}
\label{eq:delta_min_integral}
\Delta M_{\rm in} = \int_{t_0}^{t_{\rm end}} \dot{M}_{\rm loss}(t)\,dt
\end{equation}
ここで \(\dot{M}_{\rm loss}(t)\) は遷移期の不可逆損失率であり、評価区間は \(t_0\) から \(t_{\rm end}\) とする。
\begin{equation}
\label{eq:min_prime_update}
M_{\rm in}' = M_{\rm in}(t_0) - \Delta M_{\rm in}
\end{equation}
ここで \(M_{\rm in}(t_0)\) は SPH 終端時刻における内側円盤質量であり、\(M_{\rm in}'\) を長期モデル入力として用いる。

ここで \(t_{\rm end}\) は「長期モデルが仮定する準定常な円盤に近づき、状態量 \(M_{\rm in}\)・\(r_d\) で表せるようになった時刻」である（Salmon & Canup, 2012; Canup & Salmon, 2018）。ただし、円軌道化・赤道化がどれだけ速いかは円盤の密度や衝突頻度に依存し、遷移期の長さは一意に決まらない（Hyodo et al., 2017b）。本研究ではこの不確実さを隠さず、\(t_{\rm end}\) を入力として明示し、\(\Delta M_{\rm in}\) が \(t_{\rm end}\) にどの程度依存するかを感度として評価する。

### 対象領域：ロッシュ限界内側の円盤（半径一次元）

計算対象はロッシュ限界内側の円盤に限定する。岩石質物質のロッシュ限界は火星半径の数倍（例：\(a_R\approx 2.7R_{\rm Mars}\)）に位置するとされ、長期モデルでもこの内側領域を連続円盤として扱う（Canup & Salmon, 2018）。本研究でも、円盤を半径方向のリングに分割して追跡する。言葉としては「半径一次元モデル」である。以後は「一次元モデル」と呼ぶ。

この一次元モデルで直接追うのは、遷移期に内側円盤から失われる固体成分の量である。外側円盤での集積や、その後の衛星軌道進化は本研究では直接扱わず、更新後の \(M_{\rm in}'\) を長期モデルへ渡すための入力として出力する（Salmon & Canup, 2012; Canup & Salmon, 2018）。

半径方向の粘性拡散（リング間の物質移動）は、遷移期が短い場合には主効果でない可能性がある。そのため標準では入れず、必要な場合にだけ感度として追加する方針にする。どの項を「遷移期の更新」に含め、どの項を「長期モデル」に任せるかは、次章で先行研究の分担（写像の置き方）として整理する。

### 鉛直方向の簡約：深部と表層

放射圧や強い照射は、円盤全体に一様に効くわけではない。光が届くのは表面付近であり、遮蔽された内部では同じ効き方にならない。光学的に厚い円盤でも、表面の薄い層は直接照射され、その層の粒子運動が放射圧の影響を受け得る（Takeuchi & Lin, 2003）。一方、火星デブリ円盤を扱う研究では、視線方向に積分した光学的厚み \(\tau\) に基づき遮蔽を議論している（Hyodo et al., 2018）。本研究は、これらを矛盾なく扱うために、鉛直方向の「表層」と「深部」を分けて定義する。

そこで本研究では、各半径リングを次の 2 領域に分ける。

- 深部（貯蔵庫）：照射が届きにくい領域
- 表層（照射される層）：照射の影響を受ける領域（目安として鉛直方向の光学的厚みが \(\tau\sim1\) となる近傍）

本研究でいう「表層の厚み」は文献で一意に定義されていないため、**衝突カーネルで用いる幾何学的スケールハイト \(H\simeq i\,a\)** を厚みの代理指標として扱う。ここで \(i\) は代表的な軌道傾斜角であり、表層再供給や衝突頻度の見積もりに影響する。基準値として \(i_0=0.05\,\rm rad\) を置くが、根拠は未確定のため感度パラメータとして明示し、時間制約の下で **2 パターン（\(i_0=0.05\) と \(0.10\,\rm rad\)）** に限定して比較する。（要確認：\(i_0=0.05\,\rm rad\) の根拠）

重要なのは、損失量が「表層に存在する物質量」と「深部から表層へ供給される速さ」に強く依存することを、この二層化で明示できる点である。表層質量の見積もりと、\(\tau\) の定義の違いが何を意味するかは、次章で文献に沿って数式として整理する。

### 表層で結合して扱う過程：破砕・昇華・放射圧

遷移期に内側円盤から不可逆に失われる固体成分は、少なくとも次の連鎖で生じ得る。

(1) 衝突による破砕で、粒径分布が小粒側へ伸びる。  
(2) 小粒は放射圧を受けやすく、円盤から除去される（Hyodo et al., 2018）。  
(3) 高温では昇華で粒径が縮み、放射圧除去が進みやすくなる。  

本研究では、粒子数がサイズごとにどう増減するかを、衝突の結果として書いた式を用いる。衝突方程式（Smoluchowski equation）である。以後は「衝突方程式」と呼ぶ。衝突方程式をサイズビンで離散化し、昇華によるサイズ変化と、放射圧による除去（ブローアウト）判定を結合して、表層からの損失率 \(\dot{M}_{\rm loss}(t)\) を計算する。

このように結合して扱う狙いは、衝突で供給された微粒子が、昇華でさらに小さくなり、放射圧で除去される、という過程を途中で切らずに評価することにある。

### 表層への供給（深部→表層）のパラメータ化

表層での損失量は、深部がどの程度の速さで表層を補給できるかで大きく変わる。原始惑星系円盤では、乱流拡散が深部から表層への供給を担い得ることが議論されている（Takeuchi & Lin, 2003）。一方、火星デブリ円盤ではガス量が不確かであり、ガスの鉛直拡散を既定に置くのは難しい。そこで本研究では、深部から表層への供給を、円盤の厚み（軌道傾斜角のばらつき）や衝突による鉛直混合をまとめた効果として、**「表層再供給」**としてパラメータ化する。

具体的には、深部と表層の間の質量交換を表す時間スケール \(t_{\rm mix}\)（または効率 \(\epsilon_{\rm mix}\)）を導入し、これを \(t_{\rm end}\) と並ぶ主要な入力として扱う。こうすることで、「表層がすぐ枯渇する場合」と「深部が表層を継続的に補給する場合」の両方を同じ枠組みで比較できる。

### 入力・出力と、次章への接続

本研究の入力は、数値流体計算が与える初期条件と、長期モデルへ接続するために必要な系のパラメータから構成する（Citron et al., 2015; Hyodo et al., 2017a; Salmon & Canup, 2012; Canup & Salmon, 2018）。少なくとも次を含める。

- 初期内側質量 \(M_{\rm in}(t_0)\) と、半径方向の質量分布
- 初期粒径分布（表層・深部の配分を含む）
- 火星からの照射条件（火星表面温度履歴 \(T_{\rm Mars}(t)\) など）
- 表層再供給パラメータ（\(t_{\rm mix}\) または \(\epsilon_{\rm mix}\)）と、遷移期の終端 \(t_{\rm end}\)

出力は、遷移期の不可逆損失 \(\Delta M_{\rm in}\) と、更新後の内側質量 \(M_{\rm in}'\) である。これを長期形成モデルへ渡すことで、従来の「惑星への落下＋粘性拡散」に閉じた質量収支（Salmon & Canup, 2012; Canup & Salmon, 2018）に対し、遷移期の追加シンクを手続きとして接続できる。

次章では、衝突直後計算の出力を長期モデルの入力へ写像する既存の方法と、その写像が曖昧になりやすい遷移期の扱いを、文献に沿って整理する。
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
## 温度と相の不確かさ：2000 K 固定の枠組みと「固体が残る」枠組みをどう同居させるか

内側円盤で固体（微粒子）がどのくらい存在できるかは、表層での損失（放射圧・昇華・蒸気散逸）が起こるかどうかを左右します。
ここは先行研究でも一意には決まりません。理由は、内側円盤が「高温の蒸気を保ったまま粘性で広がる」場合と、「溶融滴がすぐに冷えて固体が混ざる」場合の両方が、同じ巨大衝突の文脈から出てくるからです。

Salmon & Canup (2012) は、ロッシュ限界内側の円盤が短時間で広がるとき、放射で冷える時間がそれより長いため、粘性散逸で得た熱を保ちやすい、と議論します。その結果、散逸率が放射で逃がせる上限で決まり、光球温度 \(\sim2000\,\rm K\) を仮定した粘性と広がり時間（数十年規模）を導きます。

一方で Hyodo et al. (2017a) は、衝突直後にできたメートル級の溶融滴が、放射で \(\sim11\) 分程度で固化温度まで冷え得ると見積もっています。さらに衝突カスケードが進むと、メートル級から \(\mu\rm m\) 級まで幅広い粒径が混ざり得ることを述べています。Hyodo et al. (2018) が放射圧の影響を議論していることも踏まえると、少なくとも一部の領域・一部の時間帯では「固体（微粒子）が存在する」と見なすのが自然です。

そこで本研究では、相（蒸気・固体）を一つに決め打ちしません。代わりに、固体が表層に存在し得る時間幅を不確かさとして持ち込み、その幅が \(\Delta M_{\rm in}\) にどう効くかを評価します。

- 表層に固体（微粒子）が存在し得る時間幅を \([t_{\rm SPH}, t_{\rm ss}]\) として明示し、その区間での損失を積算する  
- 「熱で決まる粘性が強く働く」場合はこの時間幅が短くなり、損失は小さくなる  
- 「低質量で急冷しやすい」場合はこの時間幅が長くなり、損失は大きくなる  

Salmon & Canup (2012) の放射で制限される粘性は内側円盤の拡散時間を数十年と見積もり、遷移期（数十日〜1–100 年）や表面冷却の時間幅と重なり得ます。この重なりが、相・温度の不確かさを長期モデル入力の更新に直結させます。

つまり本研究は、固体の存在を前提にするのではなく、**固体が存在できる窓の幅を不確かさとして持ち込み、その不確かさが \(\Delta M_{\rm in}\) にどう効くか**を評価します。

<!-- TEX_EXCLUDE_START -->
### 先行研究リンク
- [Salmon & Canup (2012)](../../paper/pdf_extractor/outputs/SalmonCanup2012_ApJ760_83/result.md)
- [Hyodo et al. (2017a)](../../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)
- [Hyodo et al. (2018)](../../paper/pdf_extractor/outputs/Hyodo2018_ApJ860_150/result.md)

<!-- TEX_EXCLUDE_END -->
---
## 手法の骨格：表層と内部に分け、再供給で損失を決める

本研究のモデル化方針は次のとおりです。

- 円盤を「照射される表層」と「遮蔽される内部」に分ける。
- 表層からは放射圧・昇華などによる損失が起こり得る一方、表層は内部からの混合・衝突で再供給される。
- 再供給の時間尺度は軌道傾斜角のばらつき（鉛直厚み）の減衰で変化する。

ここで「初期光学的厚さ」（`optical_depth.tau0_target`）は、初期の表層密度 \(\Sigma_{\rm surf0}\) を決めるためのノブです。衝突直後計算から \(\Sigma_{\rm surf0}\) を一意に定められないため、\(\tau_0\) を 0.5 と 1.0 に限定した感度として扱い、初期表層質量の不確かさを代表させます。供給スケールは `mu_reference_tau` を基準に定義されるため、\(\tau_0\) の掃引は「供給量の掃引」ではありません。評価は \(\tau\approx1\) を中心に置くため、\(\tau_0=0.1\) のような低光学厚は主解析から外します。

損失は表層で起きますが、総損失は表層の在庫だけでは決まりません。**内部から表層へどれだけ供給されるか**で、損失は増えたり止まったりします。

モデルとしては、表層にある質量を \(M_{\rm surf}\)、内部にある質量を \(M_{\rm int}\) と分け、
表層での損失を \(\dot M_{\rm loss}\)、内部→表層の再供給の時間を \(t_{\rm supply}\) と置きます。
すると最も単純には式\ref{eq:surf_mass_balance}で表せます。
\begin{equation}
\label{eq:surf_mass_balance}
\frac{dM_{\rm surf}}{dt}=\frac{M_{\rm int}}{t_{\rm supply}}-\dot M_{\rm loss}(M_{\rm surf},\,t)
\end{equation}
ここで \(M_{\rm surf}\) は表層質量、\(M_{\rm int}\) は内部質量、\(t_{\rm supply}\) は内部から表層への再供給時間であり、表層損失は \(\dot M_{\rm loss}\) で与える。\(t_{\rm supply}\) を軌道傾斜角のばらつき（鉛直厚み）が減衰すると長くなる量として扱うことで、
「最初は供給があり損失が続くが、薄い赤道円盤へ収束すると供給が止まり損失も弱まる」という振る舞いを表現します。

Takeuchi & Lin (2003) の原始惑星系円盤では、ガスの鉛直構造や乱流が供給に効きます。しかし火星デブリ円盤はガスが少ない可能性があるため、同じ供給経路は前提にせず、**表層供給を傾斜角分布の減衰で表現**します。

<!-- TEX_EXCLUDE_START -->
### 先行研究リンク
- [Takeuchi & Lin (2003)](../../paper/pdf_extractor/outputs/TakeuchiLin2003_ApJ593_524/result.md)

<!-- TEX_EXCLUDE_END -->
---
## 2. モデル構成と結合フロー

この節ではフロー図に先立ち、$\tau$ と最小粒径の定義を先に固定する（詳細は §3.1–3.2）。  

- **$\tau_{\perp}$**: 表層 ODE の $t_{\rm coll}=1/(\Omega\tau_{\perp})$ に用いる。
- **$\tau_{\rm los}$**: 遮蔽・相判定・$\tau_{\rm stop}$ 判定の入力に用いる。
- **$\tau_{\rm gate}$**: ブローアウトのみをゲートする（供給は phase により有効化され、$\tau_{\rm gate}$ は供給を止めない）。
- **$\tau_{\rm stop}$**: 停止閾値であり、$\tau=1$ と同義ではない（停止判定専用）。
- **$\Sigma_{\tau=1}$**: 診断用の面密度で、標準では $\Sigma_{\rm surf}$ を直接クリップしない。
- **$\tau_0=1$**: 初期化スケーリングの目標で、`init_tau1.scale_to_tau1=true` のときに用いる。
- **$s_{\min,\mathrm{eff}}$**: PSD グリッドの下限に反映する有効最小粒径。既定は $s_{\min,\mathrm{eff}}=\max(s_{\min,\mathrm{cfg}}, s_{\mathrm{blow,eff}})$ だが、`psd.floor.mode="none"` では $s_{\min,\mathrm{eff}}=s_{\min,\mathrm{cfg}}$ を維持する。$s_{\rm sub}$ は ds/dt としてのみ扱う（床を動かすのは `psd.floor.mode` を明示した場合のみ）。

### 2.0 支配方程式の位置づけ

本書では主要式を抜粋して再掲し、式番号・記号定義は analysis/equations.md を正とする。

- **軌道力学と時間尺度**: (E.001)–(E.002) で $\Omega$, $v_K$ を定義し、$t_{\rm blow}$ の基準は (E.007) に従う。放射圧の整理は [@Burns1979_Icarus40_1] を採用する。
- **衝突カスケード**: PSD の時間発展は Smoluchowski 方程式 (E.010) を用い、質量収支は (E.011) で検査する。枠組みは [@Krivov2006_AA455_509; @Dohnanyi1969_JGR74_2531] に基づく。
- **破砕強度と破片生成**: 破壊閾値 $Q_D^*$ の補間 (E.026) は [@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79] を参照する。
- **放射圧ブローアウト**: β と $s_{\rm blow}$ の定義は (E.013)–(E.014)、表層流出は (E.009) に依拠する。
- **昇華と追加シンク**: HKL フラックス (E.018) と飽和蒸気圧 (E.036) に基づき、昇華モデルの位置づけは [@Markkanen2020_AA643_A16] を参照する。
- **遮蔽と表層**: 自遮蔽係数 $\Phi$ は (E.015)–(E.017) により表層に適用し、gas-rich 条件の参照枠は [@TakeuchiLin2003_ApJ593_524] で位置づける。

以下の図は、入力（YAML/テーブル）から初期化・時間発展・診断出力に至る主経路を示す。**実装順序は analysis/physics_flow.md を正**とし、ここでは概念的な依存関係の整理として示す。

### 2.1 シミュレーション全体像

```mermaid
flowchart TB
    subgraph INPUT["入力"]
        CONFIG["YAML 設定ファイル"]
        TABLES["テーブルデータ<br/>Qpr, Φ, 温度"]
    end

    subgraph INIT["初期化"]
        PSD0["初期 PSD 生成"]
        TEMP0["火星温度 T_M"]
        TAU1["τ0=1 表層定義"]
    end

    subgraph LOOP["時間発展ループ"]
        direction TB
        DRIVER["温度ドライバ更新"]
        RAD["放射圧評価<br/>β, s_blow"]
        SUBL["昇華/下限更新<br/>ds/dt, s_min"]
        PSDSTEP["PSD/κ 評価"]
        SHIELD["光学深度・遮蔽 Φ"]
        PHASE["相判定/τゲート"]
        SUPPLY["表層再供給/輸送"]
        SINKTIME["シンク時間 t_sink"]
        EVOLVE["表層/Smol 更新<br/>IMEX-BDF(1)"]
        CHECK["質量収支・停止判定"]
    end

    subgraph OUTPUT["出力"]
        SERIES["series/run.parquet"]
        PSDHIST["series/psd_hist.parquet"]
        SUMMARY["summary.json"]
        BUDGET["checks/mass_budget.csv"]
        CKPT["checkpoint/"]
    end

    CONFIG --> INIT
    TABLES --> INIT
    INIT --> LOOP
    DRIVER --> RAD --> SUBL --> PSDSTEP --> SHIELD --> PHASE --> SUPPLY --> SINKTIME --> EVOLVE --> CHECK
    CHECK -->|"t < t_end"| DRIVER
    CHECK -->|"t ≥ t_end or T_M ≤ T_stop"| OUTPUT
```

### 2.2 メインループ詳細

```mermaid
flowchart LR
    subgraph STEP["1ステップの処理"]
        direction TB
        
        S1["1. 温度ドライバ更新<br/>T_M(t) → 冷却モデル"]
        S2["2. 放射圧計算<br/>⟨Q_pr⟩ → β → s_blow"]
        S3["3. 昇華/下限更新<br/>ds/dt, s_min"]
        S4["4. PSD/κ 評価<br/>τ 計算"]
        S5["5. 遮蔽 Φ 適用<br/>κ_eff, Σ_tau1"]
        S6["6. 相判定/τゲート<br/>sink 選択"]
        S7["7. 表層再供給/輸送<br/>deep mixing"]
        S8["8. シンク時間<br/>t_sink 評価"]
        S9["9. Smol/Surface 積分<br/>衝突 + 供給 + 損失"]
        S10["10. 診断・停止判定・出力"]
        
        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10
    end
```

補足: 損失項（ブローアウト・追加シンク）は S9 の IMEX 更新に含まれ、S6 は相判定とゲート選択、S8 は $t_{\rm sink}$ の評価、S10 は診断集計と出力を担当する。

各ステップでは温度ドライバの出力から $T_M$ を更新し、放射圧関連量（$\langle Q_{\rm pr}\rangle$, β, $s_{\rm blow}$）と遮蔽量（$\Phi$, $\kappa_{\rm eff}$, $\tau_{\rm los}$）を再評価する。供給はフィードバックや温度スケールを通して表層に注入され、必要に応じて深層リザーバを経由する。表層 ODE または Smoluchowski 更新の後に、ブローアウトと追加シンクによる損失を加味し、質量収支と停止条件を評価する。

図 2.2 の手順と実装の対応は次の通りである。S1 は温度ドライバの評価と $T_M$ の更新、S2 は $Q_{\rm pr}$ テーブルから β と $s_{\rm blow}$ を評価する。S3 は昇華 ds/dt と $s_{\\rm min}$ を評価し、S4 で PSD と $\\kappa$ を更新して $\\tau$ を計算する。S5 は $\\Phi$ を適用して $\\kappa_{\\rm eff}$ と $\\Sigma_{\\tau=1}$ を評価し、S6 で相判定と $\\tau$ ゲートにより有効な損失経路を選択する。S7 は供給率の名目値を計算し、フィードバック・温度スケール・深層輸送を適用する。S8 はシンク時間 $t_{\\rm sink}$ を評価し、S9 で衝突カーネルに基づく gain/loss と供給・シンクを含めた IMEX 更新を行う。S10 は $\\dot{M}_{\\rm out}$ などの診断集計、$\\tau_{\\rm stop}$ 超過の停止判定、C4 質量収支検査、および出力書き込みに対応する。

### 2.3 物理過程の相互作用

```mermaid
graph LR
    subgraph SURFACE["表層 (Surface)"]
        PSD["粒径分布 n(s)"]
        SIGMA["面密度 Σ_surf"]
    end
    
    subgraph RADIATION["放射"]
        TM["火星温度 T_M"]
        BETA["軽さ指標 β"]
        BLOW["ブローアウト s_blow"]
    end
    
    subgraph COLLISIONS["衝突"]
        KERNEL["衝突カーネル C_ij"]
        QSTAR["破壊閾値 Q_D*"]
        FRAG["破片分布"]
    end
    
    subgraph SINKS["損失"]
        BLOWOUT["ブローアウト流出"]
        SUBL["昇華 ds/dt"]
    end
    
    subgraph SUPPLY_BOX["供給"]
        EXT["表層再供給率"]
        DEEP["深層リザーバ"]
        FB["τフィードバック"]
    end
    
    TM --> BETA --> BLOW
    BLOW --> PSD
    PSD --> KERNEL --> FRAG --> PSD
    PSD --> SIGMA
    SIGMA -->|"τ"| FB --> EXT --> DEEP --> SIGMA
    PSD --> BLOWOUT
    TM --> SUBL --> PSD
    QSTAR --> KERNEL
```

主要状態変数は PSD 形状 $n_k$（`psd_state.number`）、表層面密度 $\Sigma_{\rm surf}$、深層リザーバ面密度 $\Sigma_{\rm deep}$、累積損失量 $M_{\rm out}$/$M_{\rm sink}$ であり、時間発展ごとに同時更新される。Smol 更新では $N_k$ を一時的に構成して積分し、更新後に $n_k$ へ写像して `psd_state` に戻す。計算順序と依存関係は analysis/physics_flow.md の結合順序図に従う。

### 2.4 供給・衝突・昇華の時系列因果

供給（supply）・衝突（collision）・昇華（sublimation）は同一ステップ内で相互依存するため、因果順序を以下の通り固定する。図 2.2 の S3（昇華）、S6（相判定/ゲート）、S7（供給）、S8（シンク時間）、S9（衝突/IMEX 更新）に対応する内部順序を明示し、診断列と対応させる。

```mermaid
flowchart TB
    A[S3: ds/dt evaluation] --> B[S6: phase / tau gate]
    B --> C[S7: supply scaling & transport]
    C --> D[S8: sink timescale]
    D --> E[S9: collision kernel + IMEX update]
    E --> F[S10: diagnostics & mass budget]
```

S3 では昇華 ds/dt を評価し、S6 で相判定と $\\tau$ ゲートにより有効な損失経路を選択する。S7 で名目供給 `supply_rate_nominal` にフィードバックと温度補正を適用して `supply_rate_scaled` を得た後、深層輸送を含めた表層注入量を決定する。S8 でシンク時間 $t_{\\rm sink}$ を評価し、S9 で衝突カーネルから loss/gain を構成して IMEX 更新を実施する。S10 で `smol_gain_mass_rate` / `smol_loss_mass_rate` / `ds_dt_sublimation` / `M_out_dot` を含む診断と質量収支を保存する。

#### 2.4.1 供給フロー（Supply）

```mermaid
flowchart TB
    A["nominal supply"] --> B["feedback scale"]
    B --> C["temperature scale"]
    C --> D["tau gate / phase gate"]
    D --> E["split: surface vs deep"]
    E --> F["surface injection"]
    E --> G["deep reservoir"]
    G --> H["deep-to-surface flux"]
    H --> F
```

- 対応する診断列は `supply_rate_nominal` → `supply_rate_scaled` → `supply_rate_applied`、深層経路は `prod_rate_diverted_to_deep` / `deep_to_surf_flux` / `prod_rate_applied_to_surf` に記録される。
- 供給の有効化は phase（solid）と液相ブロックで決まり、$\\tau_{\\rm gate}$ はブローアウトのみをゲートする。停止判定（$\\tau_{\\rm stop}$）とは区別して扱う。

#### 2.4.2 衝突フロー（Collision）

```mermaid
flowchart TB
    A["compute v_rel"] --> B["kernel C_ij"]
    B --> C["loss term"]
    B --> D["fragment yield Y"]
    D --> E["gain term"]
    C & E --> F["assemble Smol RHS"]
    F --> G["IMEX update"]
```

- 相対速度は $e,i$ と $c_{\\rm eq}$ から評価し、カーネル $C_{ij}$ を構成する。
- loss/gain は `smol_loss_mass_rate` / `smol_gain_mass_rate` として診断され、最小衝突時間 $t_{\\rm coll,\\,min}$ が $\\Delta t$ の上限に用いられる。
- 破片分布 $Y$ は PSD グリッド上で再配分され、質量保存は C4 により検査される。

#### 2.4.3 昇華フロー（Sublimation）

```mermaid
flowchart TB
    A["evaluate HKL flux"] --> B["compute ds/dt"]
    B --> C["size drift / rebin"]
    B --> D["sink timescale"]
    C & D --> E["merge into loss term"]
    E --> F["IMEX update"]
```

- HKL フラックスから ds/dt を評価し、必要に応じて再ビニングで PSD を更新する。
- `sub_params.mass_conserving=true` の場合は $s<s_{\\rm blow}$ を跨いだ質量をブローアウトへ振り替える。
- 昇華由来の損失は `ds_dt_sublimation` / `mass_lost_sublimation_step` として出力される。

---
## 3. 状態変数と離散化

### 3.1 粒径分布 (PSD) グリッド

PSD は衝突カスケードの統計的記述に基づき、自己相似分布の枠組み [@Dohnanyi1969_JGR74_2531] と離散化の実装例 [@Krivov2006_AA455_509] を踏まえて対数ビンで表す。ブローアウト近傍の波状構造（wavy）はビン幅に敏感であるため、格子幅の指針 [@Birnstiel2011_AA525_A11] を参照して分解能を選ぶ。
初期 PSD の既定は、衝突直後の溶融滴優勢と微粒子尾を持つ分布 [@Hyodo2017a_ApJ845_125] を反映し、溶融滴由来のべき分布は衝突起源の傾きを [@Jutzi2010_Icarus207_54] に合わせて設定する。

PSD は $n(s)$ を対数等間隔のサイズビンで離散化し、面密度・光学的厚さ・衝突率の評価を一貫したグリッド上で行う。隣接比 $s_{i+1}/s_i \lesssim 1.2$ を推奨し、供給注入と破片分布の双方がビン分解能に依存しないように設計する。PSD グリッドの既定値は表\ref{tab:psd_grid_defaults}に示す。

\begin{table}[t]
  \centering
  \caption{PSD グリッドの既定値}
  \label{tab:psd_grid_defaults}
  \begin{tabular}{p{0.36\textwidth} p{0.2\textwidth} p{0.32\textwidth}}
    \hline
    設定キー & 既定値 & glossary 参照 \\
    \hline
    \texttt{sizes.s\_min} & 1e-6 m & G.A05 (blow-out size) \\
    \texttt{sizes.s\_max} & 3.0 m & — \\
    \texttt{sizes.n\_bins} & 40 & — \\
    \hline
  \end{tabular}
\end{table}

- PSD は正規化分布 $n_k$ を保持し、表層面密度 $\Sigma_{\rm surf}$ を用いて実数の数密度 $N_k$（#/m$^2$）へスケールする。スケーリングは $\sum_k m_k N_k = \Sigma_{\rm surf}$ を満たすように行う。
- Smol 経路の時間積分は $N_k$ を主状態として実行し、`psd_state_to_number_density` → IMEX 更新 → `number_density_to_psd_state` の順に $n_k$ へ戻す。したがって、$n_k$ は形状情報として保持され、時間積分そのものは $N_k$ に対して行われる。
- **有効最小粒径**は (E.008) の $s_{\min,\mathrm{eff}}=\max(s_{\min,\mathrm{cfg}}, s_{\mathrm{blow,eff}})$ を標準とする。昇華境界 $s_{\rm sub}$ は ds/dt のみで扱い、PSD 床はデフォルトでは上げない（動的床を明示的に有効化した場合のみ適用）。
- `psd.floor.mode` は (E.008) の $s_{\min,\mathrm{eff}}$ を固定/動的に切り替える。`sizes.evolve_min_size` は昇華 ds/dt などに基づく **診断用** の $s_{\min}$ を追跡し、既定では PSD 床を上書きしない。
- 供給注入は PSD 下限（$s_{\min}$）より大きい最小ビンに集約し、質量保存と面積率の一貫性を保つ。
- `wavy_strength>0` で blow-out 近傍の波状（wavy）構造を付加し、`tests/integration/test_surface_outflux_wavy.py::test_blowout_driven_wavy_pattern_emerges` で定性的再現を確認する（[@ThebaultAugereau2007_AA472_169]）。
- 既定の 40 ビンでは隣接比が約 1.45 となるため、高解像（$\lesssim 1.2$）が必要な場合は `sizes.n_bins` を増やす。

PSD は形状（$n_k$）と規格化（$\Sigma_{\rm surf}$）を分離して扱うため、衝突解法と供給注入は同一のビン定義を共有しつつ、面密度の時間発展は独立に制御できる。これにより、供給・昇華・ブローアウトによる総質量変化と、衝突による分布形状の再配分を明示的に分離する。

> **詳細**: analysis/config_guide.md §3.3 "Sizes"  
> **用語**: analysis/glossary.md "s", "PSD"

### 3.2 光学的厚さ $\tau$ の定義

光学的厚さは用途ごとに以下を使い分ける。

- **垂直方向**: $\tau_{\perp}$ は表層 ODE の $t_{\rm coll}=1/(\Omega\tau_{\perp})$ に用いる。実装では $\tau_{\rm los}$ から $\tau_{\perp}=\tau_{\rm los}/\mathrm{los\_factor}$ を逆算して適用する。
- **火星視線方向**: $\tau_{\rm los}=\tau_{\perp}\times\mathrm{los\_factor}$ を遮蔽・温度停止・供給フィードバックに用いる。
- Smol 経路では $t_{\rm coll}$ をカーネル側で評価し、$\tau_{\rm los}$ は遮蔽とゲート判定の診断量として扱う。

$\tau$ に関するゲート・停止・診断量は次のように区別する。

- **$\tau_{\rm gate}$**: ブローアウト有効化のゲート。$\tau_{\rm los}\ge\tau_{\rm gate}$ の場合は放射圧アウトフローを抑制する（停止しない）。
- **$\tau_{\rm stop}$**: 計算停止の閾値。$\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する。
- **$\Sigma_{\tau=1}$**: $\kappa_{\rm eff}$ から導出する診断量。初期化や診断の参照に使うが、標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない。
- **$\tau_0=1$**: 初期化のスケーリング目標で、`init_tau1.scale_to_tau1=true` のときに $\tau_{\rm los}$ または $\tau_{\perp}$ を指定して用いる。

$\tau_{\rm los}$ は遮蔽（$\Phi$）の入力として使われるほか、放射圧ゲート（$\tau_{\rm gate}$）や停止条件（$\tau_{\rm stop}$）の判定に用いる。$\Sigma_{\tau=1}$ は診断量として保存し、初期化や診断に参照するが、標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない。

> **参照**: analysis/equations.md（$\tau_{\perp}$ と $\tau_{\rm los}$ の定義）, analysis/physics_flow.md §6

---
## 4. 衝突カスケードと破片生成

衝突カスケードは小粒子供給の主因であり、PSD の形状と供給率を同時に決める。統計的な衝突解法は Smoluchowski 方程式の枠組み [@Krivov2006_AA455_509] を基礎に置き、破砕強度は玄武岩モデル [@BenzAsphaug1999_Icarus142_5] と LS12 補間 [@LeinhardtStewart2012_ApJ745_79] に従って定義する。

主要な PSD の時間発展は式\ref{eq:psd_smol}で与える（再掲: E.010）。

\begin{equation}
\label{eq:psd_smol}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

右辺第1項が破片生成、第2項が衝突ロス、$F_k$ が供給ソース、$S_k$ が追加シンク（昇華・ガス抗力など）を表す。

### 4.1 衝突カーネル

nσv 型カーネル (E.024) を用い、相対速度は Rayleigh 分布 (E.020) から導出する（[@LissauerStewart1993_PP3; @WetherillStewart1993_Icarus106_190; @Ohtsuki2002_Icarus155_436; @ImazBlanco2023_MNRAS522_6150; @IdaMakino1992_Icarus96_107]）。カーネルの定義は式\ref{eq:collision_kernel}に示す。

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

- 破壊閾値 $Q_D^*$: [@LeinhardtStewart2012_ApJ745_79] 補間 (E.026)
- 速度分散: せん断加熱と減衰の釣り合いから $c_{\rm eq}$ を固定点反復で求め、相対速度に反映する (E.021; [@Ohtsuki2002_Icarus155_436])
- 速度外挿: 重力項のみ LS09 型 $v^{-3\mu+2}$ で拡張（[@StewartLeinhardt2009_ApJ691_L133; @Jutzi2010_Icarus207_54]）
- ここでの $\mu$ は衝突速度外挿（LS09）の係数であり、供給式で使う $\mu$（`mu_reference_tau` 由来）とは別物として扱う。

衝突カーネルはサイズビン対ごとに衝突率 $C_{ij}$ を評価し、衝突ロス項と破片生成項を形成する。動力学パラメータ（$e, i$）は表層状態と供給の速度条件を反映して更新され、$C_{ij}$ の評価に反映される。

S9 の衝突更新では、$C_{ij}$ から各ビンの衝突寿命 $t_{\rm coll}$ と loss/gain を算定し、破片分布テンソル $Y$ に基づいて生成項を配分する。$t_{\rm coll}$ の最小値は $\Delta t$ の上限制御に用いられ、ビンごとの質量収支が C4 検査で追跡される。破片生成は PSD 下限のビン境界条件と整合させ、供給注入と同一のビン系で質量保存を保証する。

> **詳細**: analysis/equations.md (E.020)–(E.021), (E.024), (E.026)  
> **設定**: analysis/config_guide.md §3.5 "QStar"

### 4.2 衝突レジーム分類

衝突は **最大残存率 $F_{LF}$** に基づいて2つのレジームに分類する。レジームの条件と処理は表\ref{tab:collision_regimes}にまとめる。

\begin{table}[t]
  \centering
  \caption{衝突レジームの分類と処理}
  \label{tab:collision_regimes}
  \begin{tabular}{p{0.28\textwidth} p{0.2\textwidth} p{0.42\textwidth}}
    \hline
    レジーム & 条件 & 処理 \\
    \hline
    侵食（cratering） & $F_{LF} > 0.5$ & ターゲット残存、クレーター破片生成 \\
    壊滅的破砕（fragmentation） & $F_{LF} \le 0.5$ & 完全破壊、破片分布 $g(m) \propto m^{-\eta}$ \\
    \hline
  \end{tabular}
\end{table}

- Thébault et al. (2003) に基づく侵食モデル（[@Thebault2003_AA408_775]）
- [@Krivov2006_AA455_509] に基づく壊滅的破砕モデル
- 破砕境界と最大残存率の分岐式は [@StewartLeinhardt2009_ApJ691_L133; @LeinhardtStewart2012_ApJ745_79] に従う
- 破片分布はビン内積分で質量保存を満たすように正規化し、供給・破砕由来の面密度が一貫するように設計する。

破砕生成物はフラグメント分布テンソル $Y$ を通じて各ビンに再配分され、Smoluchowski 解法の gain 項として更新される。侵食レジームでは質量が大粒径側に残存し、小粒径への供給は限定的となる。

### 4.3 エネルギー簿記

`diagnostics.energy_bookkeeping.enabled=true` で簿記モードを有効化し、`diagnostics.energy_bookkeeping.stream` が true かつ `FORCE_STREAMING_OFF` が未設定なら `series/energy.parquet`・`checks/energy_budget.csv` をストリーミングで書き出す（オフ時は最後にまとめて保存）。サマリには `energy_bookkeeping.{E_rel_total,E_dissipated_total,E_retained_total,f_ke_mean_last,f_ke_energy_last,frac_*_last}` が追加され、同じ統計を run_card に残す。出力カラムの一覧は表\ref{tab:energy_columns}に示す。

\begin{table}[t]
  \centering
  \caption{エネルギー簿記の出力カラム}
  \label{tab:energy_columns}
  \begin{tabular}{p{0.32\textwidth} p{0.42\textwidth} p{0.12\textwidth}}
    \hline
    出力カラム & 意味 & 単位 \\
    \hline
    \texttt{E\_rel\_step} & 衝突の総相対運動エネルギー & J \\
    \texttt{E\_dissipated\_step} & 散逸エネルギー（熱化） & J \\
    \texttt{E\_retained\_step} & 残留運動エネルギー & J \\
    \texttt{n\_cratering} & 侵食衝突の頻度 & — \\
    \texttt{n\_fragmentation} & 破砕衝突の頻度 & — \\
    \texttt{frac\_cratering} & 侵食衝突の割合 & — \\
    \texttt{frac\_fragmentation} & 破砕衝突の割合 & — \\
    \hline
  \end{tabular}
\end{table}

エネルギー散逸率は式\ref{eq:energy_dissipation}で定義する。

\begin{equation}
\label{eq:energy_dissipation}
E_{diss} = (1 - f_{ke})\,E_{rel}
\end{equation}

関連する設定キーは表\ref{tab:energy_settings}にまとめる。

\begin{table}[t]
  \centering
  \caption{エネルギー簿記に関連する設定キー}
  \label{tab:energy_settings}
  \begin{tabular}{p{0.38\textwidth} p{0.38\textwidth} p{0.14\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{dynamics.eps\_restitution} & 反発係数（$f_{ke,\mathrm{frag}}$ のデフォルトに使用） & 0.5 \\
    \texttt{dynamics.f\_ke\_cratering} & 侵食時の非散逸率 & 0.1 \\
    \texttt{dynamics.f\_ke\_fragmentation} & 破砕時の非散逸率 & None（$\varepsilon^2$ 使用） \\
    \texttt{diagnostics.energy\_bookkeeping.stream} & energy 系列/簿記をストリーム出力 & true（\texttt{FORCE\_STREAMING\_OFF} で無効化） \\
    \hline
  \end{tabular}
\end{table}

エネルギー簿記は数値安定性と物理整合性の診断を目的とし、時間発展のフィードバックには用いない。記録された散逸・残存エネルギーは衝突速度場の妥当性評価に用いる。

> **詳細**: analysis/equations.md (E.045a), (E.051), (E.052)

---
## 5. 熱・放射・表層損失

放射圧と昇華は粒子の軽さ指標 β と表層質量の時間変化を通じて短期損失を支配する。放射圧の整理は古典的な定式化 [@Burns1979_Icarus40_1] に基づき、光学特性は Mie 理論の整理 [@BohrenHuffman1983_Wiley] を踏まえて $\langle Q_{\rm pr}\rangle$ テーブルを用いる。遮蔽の参照枠は gas-rich 表層流出の議論 [@TakeuchiLin2003_ApJ593_524] に置きつつ、gas-poor 条件を既定とする。

### 5.1 温度ドライバ

火星表面温度の時間変化を `constant` / `table` / `autogen` で選択する。各モードの概要は表\ref{tab:temp_driver_modes}に示す。

- `autogen` は解析的冷却（slab）や Hyodo 型などの内蔵ドライバを選択し、温度停止条件と連動する（[@Hyodo2018_ApJ860_150]）。

\begin{table}[t]
  \centering
  \caption{温度ドライバのモード}
  \label{tab:temp_driver_modes}
  \begin{tabular}{p{0.2\textwidth} p{0.4\textwidth} p{0.32\textwidth}}
    \hline
    モード & 内容 & 設定参照 \\
    \hline
    \texttt{table} & 外部 CSV テーブル補間 & \texttt{radiation.mars\_temperature\_driver.table.*} \\
    \texttt{slab} & 解析的 $T^{-3}$ 冷却 (Stefan--Boltzmann) & 内蔵式 \\
    \texttt{hyodo} & 線形熱流束に基づく冷却 & \texttt{radiation.mars\_temperature\_driver.hyodo.*} \\
    \hline
  \end{tabular}
\end{table}

温度は放射圧効率 $\langle Q_{\rm pr}\rangle$、昇華フラックス、相判定に同時に入力され、`T_M_used` と `T_M_source` が診断に記録される。遮蔽係数 $\Phi$ は温度ドライバにはフィードバックせず、放射圧評価・相判定（粒子平衡温度の推定）でのみ用いる。

> **詳細**: analysis/equations.md (E.042)–(E.043)  
> **フロー図**: analysis/physics_flow.md §3 "温度ドライバ解決フロー"  
> **設定**: analysis/config_guide.md §3.2 "mars_temperature_driver"

### 5.2 放射圧・ブローアウト

軽さ指標 β (E.013) とブローアウト粒径 $s_{\rm blow}$ (E.014) を $\langle Q_{\rm pr}\rangle$ テーブルから評価する。本書では粒径を $s_{\rm blow}$ と表記し、コードや出力列では `a_blow` が同義の名称として残る。

- $\langle Q_{\rm pr}\rangle$ はテーブル入力（CSV/NPZ）を既定とし、Planck 平均から β と $s_{\rm blow}$ を導出する。
- ブローアウト（blow-out）損失は **phase=solid かつ $\tau$ ゲートが開放**（$\tau_{\rm los}<\tau_{\rm gate}$）のときのみ有効化し、それ以外は outflux=0 とする。
- 外向流束は $t_{\rm blow}=1/\Omega$（E.007）を基準とし、実装では `chi_blow_eff` を掛けた $t_{\rm blow}=\chi_{\rm blow}/\Omega$ を用いる。補正状況は `dt_over_t_blow`・`fast_blowout_flag_gt3/gt10` とともに診断列へ出力する。
- β の閾値判定により `case_status` を分類し、ブローアウト境界と PSD 床の関係を `s_min_components` に記録する。
- 表層流出率 $\dot{M}_{\rm out}$ の定義は (E.009) を参照し、表層 ODE を使う場合は $t_{\rm blow}$ を (E.007) の形で評価する。

放射圧の軽さ指標とブローアウト粒径は式\ref{eq:beta_definition}と式\ref{eq:s_blow_definition}で定義する（再掲: E.013, E.014）。

\begin{equation}
\label{eq:beta_definition}
\beta = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{4\,G\,M_{\mathrm{M}}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\mathrm{blow}} = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{2\,G\,M_{\mathrm{M}}\,c\,\rho}
\end{equation}

表層の外向流束は式\ref{eq:surface_outflux}で評価する（再掲: E.009）。

\begin{equation}
\label{eq:surface_outflux}
\dot{M}_{\mathrm{out}} = \Sigma_{\mathrm{surf}}\,\Omega
\end{equation}

ブローアウト境界は β=0.5 を閾値とする非束縛条件に対応し、$s_{\rm blow}$ と $s_{\min,\mathrm{eff}}$ の関係が PSD 形状と流出率を支配する。ゲート有効時は $\tau$ によって outflux が抑制される。

> **詳細**: analysis/equations.md (E.009), (E.012)–(E.014), (E.039)  
> **用語**: analysis/glossary.md G.A04 (β), G.A05 (s_blow)  
> **設定**: analysis/config_guide.md §3.2 "Radiation"

### 5.3 遮蔽 (Shielding)

$\Phi(\tau,\omega_0,g)$ テーブル補間で有効不透明度を評価し、$\Sigma_{\tau=1}=1/\kappa_{\rm eff}$ を診断として記録する。表層が光学的に厚くなり $\tau_{\rm los}>\tau_{\rm stop}$ となった場合は停止し、クリップは行わない。Φ テーブルの基礎近似は二流・δ-Eddington 系の解析解に基づく（[@Joseph1976_JAS33_2452; @HansenTravis1974_SSR16_527; @CogleyBergstrom1979_JQSRT21_265]）。

遮蔽による有効不透明度と光学的厚さ 1 の表層面密度は式\ref{eq:kappa_eff_definition}と式\ref{eq:sigma_tau1_definition}で与える（再掲: E.015, E.016）。

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\mathrm{eff}} = \Phi(\tau)\,\kappa_{\mathrm{surf}}
\end{equation}

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau=1} =
\begin{cases}
 \kappa_{\mathrm{eff}}^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0.
\end{cases}
\end{equation}

- Φテーブルは既定で外部入力とし、双線形補間で $\Phi$ を評価する。
- `shielding.mode` により `psitau` / `fixed_tau1` / `off` を切り替える。
- **停止条件**: $\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する（停止とクリップは別物として扱う）。
- **$\Sigma_{\tau=1}$ の扱い**: $\Sigma_{\tau=1}$ は診断量であり、初期化ポリシーに用いるが、標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない。

遮蔽係数は放射圧評価と供給フィードバックに入るため、$\tau_{\rm los}$ の定義とゲート順序は実装上の重要な仕様となる。$\tau_{\rm stop}$ は停止判定のみを担い、供給抑制や状態量クリップとは区別する。

> **詳細**: analysis/equations.md (E.015)–(E.017)  
> **設定**: analysis/config_guide.md §3.4 "Shielding"

### 5.4 相判定 (Phase)

SiO₂ 冷却マップまたは閾値から相（phase）を `solid`/`vapor` に分類し、シンク経路を自動選択する。

- 判定には火星温度と遮蔽後の光学的厚さを用い、`phase_state` と `sink_selected` を診断に記録する。

固体相では放射圧ブローアウトが主要な損失経路となり、蒸気相では水素流体逃亡（hydrodynamic escape）スケーリングを用いた損失に切り替わる。蒸気相では `hydro_escape_timescale` から $t_{\rm sink}$ を評価し、`sink_selected="hydro_escape"` として記録する。相判定は表層 ODE とシンク選択のゲートとして機能し、同一ステップ内でブローアウトと流体力学的損失が併用されることはない。

> **フロー図**: analysis/physics_flow.md §4 "相判定フロー"  
> **設定**: analysis/config_guide.md §3.8 "Phase"

### 5.5 昇華 (Sublimation) と追加シンク

HKL（Hertz–Knudsen–Langmuir）フラックス (E.018) と飽和蒸気圧 (E.036) で質量損失を評価する（[@Markkanen2020_AA643_A16]）。Clausius 係数は [@Kubaschewski1974_Book] を基準とし、液相枝は [@FegleySchaefer2012_arXiv; @VisscherFegley2013_ApJL767_L12] を採用する。SiO 既定パラメータと支配的蒸気種の整理は [@Melosh2007_MPS42_2079] を参照し、$P_{\mathrm{gas}}$ の扱いは [@Ronnet2016_ApJ828_109] と同様に自由パラメータとして扱う。昇華フラックスの適用範囲は [@Pignatale2018_ApJ853_118] を参照する。

HKL フラックスは式\ref{eq:hkl_flux}で与える（再掲: E.018）。飽和蒸気圧は式\ref{eq:psat_definition}で定義する（再掲: E.036）。

\begin{equation}
\label{eq:hkl_flux}
J(T) =
\begin{cases}
 \alpha_{\mathrm{evap}}\max\!\bigl(P_{\mathrm{sat}}(T) - P_{\mathrm{gas}},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}, &
 \text{if mode}\in\{\text{``hkl'', ``hkl\_timescale''}\} \text{ and HKL activated},\\[10pt]
 \exp\!\left(\dfrac{T - T_{\mathrm{sub}}}{\max(dT, 1)}\right), & \text{otherwise.}
\end{cases}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\mathrm{sat}}(T) =
\begin{cases}
 10^{A - B/T}, & \text{if }\texttt{psat\_model} = \text{``clausius''},\\[6pt]
 10^{\mathrm{PCHIP}_{\log_{10}P}(T)}, & \text{if }\texttt{psat\_model} = \text{``tabulated''}.
\end{cases}
\end{equation}

- `sub_params.mass_conserving=true` の場合は ds/dt だけを適用し、$s<s_{\rm blow}$ を跨いだ分をブローアウト損失へ振り替えてシンク質量を維持する。
- `sinks.mode` を `none` にすると追加シンクを無効化し、表層 ODE/Smol へのロス項を停止する。
- ガス抗力は `sinks.mode` のオプションとして扱い、gas-poor 既定では無効。
- 昇華境界 $s_{\rm sub}$ は PSD 床を直接変更せず、粒径収縮（ds/dt）と診断量として扱う。

昇華は PSD をサイズ方向にドリフトさせる過程として実装し、必要に応じて再ビニング（rebinning）を行う。損失項は IMEX の陰的ロスに含め、衝突ロスと同様に時間積分の安定性を確保する。

> **詳細**: analysis/equations.md (E.018)–(E.019), (E.036)–(E.038)  
> **設定**: analysis/config_guide.md §3.6 "Sinks"

---
## 6. 表層再供給と輸送

表層再供給（supply）は表層への面密度生成率として与え、サイズ分布と深層輸送を通じて PSD に注入する。ここでの表層再供給は外側からの流入を精密に表すものではなく、深部↔表層の入れ替わりを粗く表現するためのパラメータ化である。定常値・べき乗・テーブル・区分定義の各モードを用意し、温度・$\tau$ フィードバック・有限リザーバを組み合わせて非定常性を表現する。

供給の基礎率は式\ref{eq:prod_rate_definition}で定義する（再掲: E.027）。

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\mathrm{prod}}(t,r) = \max\!\left(\epsilon_{\mathrm{mix}}\;R_{\mathrm{base}}(t,r),\,0\right)
\end{equation}

`const` / `powerlaw` / `table` / `piecewise` モードで表層への供給率を指定する。`const` は `mu_orbit10pct` を基準に、参照光学的厚さ (`mu_reference_tau`) に対応する表層密度の `orbit_fraction_at_mu1` を 1 公転で供給する定義に統一する。旧 μ (E.027a) は診断・ツール用の導出値としてのみ扱う。ここでの μ（供給式の指標）は衝突速度外挿の μ と別であり、混同しないよう区別して扱う。

供給は「名目供給→フィードバック補正→温度スケール→ゲート判定→深層/表層への配分」の順に評価される。供給が深層へ迂回した場合でも、表層面密度と PSD の更新は同一タイムステップ内で整合的に行われる。

S7 に対応する供給処理では、`supply_rate_nominal` を基準に `supply_rate_scaled`（フィードバック・温度補正後）を評価し、ゲート判定後の `supply_rate_applied` を表層へ注入する。deep mixing が有効な場合は `prod_rate_diverted_to_deep` と `deep_to_surf_flux` により深層からの再注入を記録し、表層面密度への寄与は `prod_rate_applied_to_surf` として診断される。これらの列は supply の順序が図 2.2 と一致していることの検算に用いる。

> **詳細**: analysis/equations.md (E.027), (E.027a)  
> **用語**: analysis/glossary.md G.A11 (epsilon_mix)  
> **設定**: analysis/config_guide.md §3.7 "Supply"

### 6.1 フィードバック制御 (Supply Feedback)

`supply.feedback.enabled=true` で $\tau$ 目標に追従する比例制御を有効化する。設定項目は表\ref{tab:supply_feedback_settings}に示す。

\begin{table}[t]
  \centering
  \caption{供給フィードバックの設定}
  \label{tab:supply_feedback_settings}
  \begin{tabular}{p{0.4\textwidth} p{0.36\textwidth} p{0.14\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.feedback.target\_tau} & 目標光学的厚さ & 0.9 \\
    \texttt{supply.feedback.gain} & 比例ゲイン & 1.2 \\
    \texttt{supply.feedback.response\_time\_years} & 応答時定数 [yr] & 0.4 \\
    \texttt{supply.feedback.tau\_field} & $\tau$ 評価フィールド (\texttt{tau\_los}) & \texttt{tau\_los} \\
    \texttt{supply.feedback.min\_scale} / \texttt{max\_scale} & スケール係数の上下限 & 1e-6 / 10.0 \\
    \hline
  \end{tabular}
\end{table}

- `supply_feedback_scale` 列にステップごとのスケール係数を出力する。
- フィードバックは供給ゲートの**上流**で適用され、$\tau_{\rm stop}$ 超過時は停止判定が優先される。

### 6.2 温度カップリング (Supply Temperature)

`supply.temperature.enabled=true` で火星温度に連動した供給スケーリングを有効化する。温度カップリングの設定項目は表\ref{tab:supply_temperature_settings}にまとめる。

- `mode=scale`: べき乗スケーリング $(T/T_{\rm ref})^{\alpha}$
- `mode=table`: 外部 CSV テーブルから補間

\begin{table}[t]
  \centering
  \caption{温度カップリングの設定}
  \label{tab:supply_temperature_settings}
  \begin{tabular}{p{0.46\textwidth} p{0.44\textwidth}}
    \hline
    設定キー & 意味 \\
    \hline
    \texttt{supply.temperature.reference\_K} & 基準温度 [K] \\
    \texttt{supply.temperature.exponent} & べき指数 $\alpha$ \\
    \texttt{supply.temperature.floor} / \texttt{cap} & スケール係数の下限・上限 \\
    \hline
  \end{tabular}
\end{table}

### 6.3 リザーバと深層ミキシング

`supply.reservoir.enabled=true` で有限質量リザーバを追跡し、`supply.transport.mode=deep_mixing` を選択すると、供給は深層リザーバに蓄積された後、ミキシング時間 `t_mix_orbits` 公転で表層へ放出される。$\tau=1$ 超過は停止判定で扱う。

- `depletion_mode=hard_stop`: リザーバ枯渇で供給ゼロ
- `depletion_mode=taper`: 残量に応じて漸減（`taper_fraction` で制御）

### 6.4 注入パラメータ

注入パラメータは表\ref{tab:supply_injection_settings}に示す。

\begin{table}[t]
  \centering
  \caption{注入パラメータの設定}
  \label{tab:supply_injection_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.34\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.injection.mode} & \texttt{min\_bin} / \texttt{powerlaw\_bins} & \texttt{powerlaw\_bins} \\
    \texttt{supply.injection.q} & べき指数（衝突カスケード断片） & 3.5 \\
    \texttt{supply.injection.s\_inj\_min} / \texttt{s\_inj\_max} & 注入サイズ範囲 [m] & 自動 \\
    \texttt{supply.injection.velocity.mode} & \texttt{inherit} / \texttt{fixed\_ei} / \texttt{factor} & \texttt{inherit} \\
    \hline
  \end{tabular}
\end{table}

注入モードは PSD 形状の境界条件として働くため、供給率とビン解像度の整合が重要である。感度試験では注入指数 $q$ と最小注入サイズを変化させ、ブローアウト近傍の wavy 構造や質量収支への影響を評価する。

---
## 7. 数値時間積分と半径方向結合

### 7.1 IMEX-BDF(1)

Smoluchowski 衝突カスケードの時間積分には IMEX（implicit-explicit）と BDF(1)（backward differentiation formula）の一次組合せを採用する。状態ベクトルはサイズビン $k$ ごとの数密度（または面密度）で表現し、衝突ゲイン・ロスと表層再供給・シンクを同時に組み込む。剛性の強いロス項を陰的に扱うことで安定性を確保し、生成・供給・表層流出は陽的に更新する。

- **剛性項（損失）**: 陰的処理
- **非剛性項（生成・供給）**: 陽的処理
- **ロス項の構成**: 衝突ロスに加え、ブローアウト（$s \le s_{\rm blow}$）と追加シンク（$t_{\rm sink}$）を損失項として組み込む。表層 ODE では $t_{\rm coll}$ と $t_{\rm sink}$ を同一の陰的更新式にまとめる。
- **時間刻み（外側）**: `numerics.dt_init` が外側の結合ステップ $dt$ を与え、温度・遮蔽・供給・相判定・出力などの更新はこの $dt$ で進む。1D では `numerics.dt_min_tcoll_ratio` により $dt \ge \mathrm{ratio}\cdot\min t_{\rm coll}$ の下限を課し、0D ではこの制約を使わない。
- **内部ステップ（Smol）**: IMEX ソルバ内部では $dt_{\rm eff}=\min(dt,\,\mathrm{safety}\cdot\min t_{\rm coll})$ を初期値とし、$N_k<0$ となる場合や質量誤差が許容値を超える場合は $dt_{\rm eff}$ を 1/2 に縮めて再評価する。`smol_dt_eff` として記録され、外側の時間は $dt$ だけ進む。非有限の質量誤差が出た場合は例外として扱う。
- **参考値**: `out/temp_supply_sweep_1d/20260105-180522__2499a82da__seed111066691/T3000_eps0p5_tau0p5`（$\tau\approx0.5$）では `numerics.dt_init=20 s` に対し、初期ステップの $t_{\rm coll,\,min}\approx7.37\times10^{-7}\,\mathrm{s}$、`smol_dt_eff\approx7.37\times10^{-8}\,\mathrm{s}`、`dt_over_t_blow_median\approx7.75\times10^{-3}` を記録した。
- **$t_{\rm coll}$ の扱い**: Smol 経路ではカーネル由来の最短衝突時間（$t_{\rm coll,\,min}$）を $\Delta t$ 制御に用い、表層 ODE 経路では $\tau_{\perp}$ から $t_{\rm coll}$ を評価する。
- **質量検査**: (E.011) を毎ステップ評価し、|error| ≤ 0.5% を `out/checks/mass_budget.csv` に記録する。`safety` に応じて $\Delta t$ は $0.1\min t_{\rm coll}$ に自動クリップされる。
- **高速ブローアウト**: $\Delta t/t_{\rm blow}$ が 3 を超えると `fast_blowout_flag_gt3`、10 を超えると `fast_blowout_flag_gt10` を立てる。`io.correct_fast_blowout=true` の場合は `fast_blowout_factor` を outflux に乗じ、`io.substep_fast_blowout=true` かつ $\Delta t/t_{\rm blow}>\mathrm{substep\_max\_ratio}$（既定 1.0）の場合は $n_{\rm substeps}=\lceil \Delta t/(\mathrm{substep\_max\_ratio}\,t_{\rm blow})\rceil$ に分割して IMEX 更新を行う。診断列は `dt_over_t_blow`/`fast_blowout_factor`/`fast_blowout_corrected`/`n_substeps` を参照する。
- **精度と安定性**: 一次精度（IMEX Euler）で剛性ロス項の安定性を優先し、$\Delta t$ 制御で収束性を担保する。

IMEX-BDF(1) は剛性ロス項で負の数密度が生じるのを防ぐため、ロス項を陰的に扱う設計とする。$N_k<0$ が検出された場合は $dt_{\rm eff}$ を半減して再評価し、許容誤差内の質量検査（C4）を満たした $dt_{\rm eff}$ が採用される。陽的に扱う生成項は衝突の破片生成と供給注入に限定し、質量保存は C4 の検査で逐次確認する。

S9 の数値更新では、衝突ロス・ブローアウト・追加シンクを陰的側に集約し、衝突生成・供給注入を陽的に与える。$\Delta t$ は $t_{\rm coll}$ と $t_{\rm blow}$ の双方を解像するよう制約され、`dt_over_t_blow` と `smol_dt_eff` が診断列として保存される。$dt_{\rm eff}$ が $dt$ より小さい場合でも外側の時間は $dt$ だけ進むため、質量検査は `smol_dt_eff` を使って評価する。

> **詳細**: analysis/equations.md (E.010)–(E.011)  
> **フロー図**: analysis/physics_flow.md §7 "Smoluchowski 衝突積分"

### 7.2 1D（C5）挿入位置・境界条件・$\Delta t$ 制約

run_sweep 既定では `geometry.mode=1D`（`Nr=32`）で半径方向セルを持つが、`numerics.enable_viscosity` は未指定のため C5 は無効で、セル間の結合は行わない。C5 を有効化する場合は、各ステップの局所更新後に半径方向の粘性拡散 `step_viscous_diffusion_C5` を**演算子分割で挿入**する設計とする。

- **境界条件**: 内外端ともにゼロフラックス（Neumann）境界を採用する。
- **$\Delta t$ 制約**: 粘性拡散は $\theta$ 法（既定 $\theta=0.5$ の Crank–Nicolson）で半陰的に解くため、追加の安定制約は課さず、各セルの $t_{\rm coll}$ および `dt_over_t_blow` 制御に従う（run_sweep 既定と同じ）。
- **適用スイッチ**: `numerics.enable_viscosity=true` で C5 を有効化し、未設定時は無効。

C5 は半径方向の面密度拡散を解くため、1D 実行のセル間結合を担当する。数値的には三重対角系の解として実装され、境界条件により質量フラックスの流出入を抑制する。

---
## 8. 初期化・終了条件・チェックポイント

### 8.1 初期 $\tau=1$ スケーリング

`init_tau1.scale_to_tau1=true` で、初期 PSD を $\tau=1$ になるようスケーリングする。関連設定は表\ref{tab:init_tau1_settings}に示す。

\begin{table}[t]
  \centering
  \caption{初期 $\tau=1$ スケーリングの設定}
  \label{tab:init_tau1_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.3\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{init\_tau1.scale\_to\_tau1} & 有効化フラグ & \texttt{false} \\
    \texttt{init\_tau1.tau\_field} & \texttt{vertical} / \texttt{los} & \texttt{los} \\
    \texttt{init\_tau1.target\_tau} & 目標光学的厚さ & 1.0 \\
    \hline
  \end{tabular}
\end{table}

- `optical_depth` が有効な場合は `tau0_target` から `Sigma_surf0` を定義し、`init_tau1.scale_to_tau1` とは併用できない（旧方式を使う場合は `optical_depth: null` を明示）。
- `scale_to_tau1=false` の場合は `initial.mass_total` がそのまま適用される。$\tau_{\rm stop}$ 超過で停止判定する。

初期 PSD は `initial.*` の設定と PSD グリッド定義に従って生成される。初期状態は `run_config.json` に記録され、再現実行時の参照点となる。

### 8.2 温度停止 (Temperature Stop)

`numerics.t_end_until_temperature_K` を設定すると、火星表面温度が指定値以下になった時点でシミュレーションを終了する（温度ドライバが解決できる場合のみ有効）。

```yaml
numerics:
  t_end_years: null
  t_end_until_temperature_K: 2000
  t_end_temperature_margin_years: 0
  t_end_temperature_search_years: 10  # optional search cap
```

- **優先順位**: `t_end_until_temperature_K` → `t_end_orbits` → `t_end_years`。未指定の場合は `scope.analysis_years`（既定 2 年）にフォールバックする。
- `t_end_temperature_margin_years` で冷却達成後のマージン時間を追加可能。
- 運用スイープ（run_sweep.cmd）では `COOL_TO_K=1000` が既定のため、温度停止が実質デフォルトとなる点に注意する。

### 8.3 チェックポイント (Segmented Run)

長時間実行をセグメント化し、中間状態を保存して再開可能にする。

```yaml
numerics:
  checkpoint:
    enabled: true
    interval_years: 0.083   # ~30 days
    keep_last_n: 3
    format: pickle          # pickle | hdf5
```

- クラッシュ時に最新チェックポイントから `--resume` で再開。
- `keep_last_n` でディスク使用量を制限。

---
## 9. 出力・I/O・再現性

時間発展の各ステップは Parquet/JSON/CSV へ記録し、後段の解析・可視化で再構成可能な形で保存する。必須の出力は `series/run.parquet`、`series/psd_hist.parquet`、`summary.json`、`checks/mass_budget.csv` で、追加診断は設定に応じて `diagnostics.parquet` や `energy.parquet` を生成する。

**必須出力**
- `series/run.parquet` は時系列の `time`, `dt`, `tau`, `a_blow`（コード上の名称、物理量は $s_{\rm blow}$）, `s_min`, `prod_subblow_area_rate`, `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks` などを保持する。衝突・時間刻みの診断は `smol_dt_eff`, `t_coll_kernel_min`, `dt_over_t_blow` を参照する。
- `series/psd_hist.parquet` は `time`×`bin_index` の縦持ちテーブルで、`s_bin_center`, `N_bin`, `Sigma_surf` を保持する。
- `summary.json` は $M_{\rm loss}$、case status、質量保存の最大誤差などを集約する。
- `checks/mass_budget.csv` は C4 質量検査を逐次追記し、ストリーミング有無に関わらず必ず生成する。

**追加診断（任意）**
- `series/diagnostics.parquet` は `t_sink_*`, `kappa_eff`, `tau_eff`, `phi_effective`, `ds_dt_sublimation` などの補助診断を保持する。
- `series/energy.parquet` は衝突エネルギーの内訳を記録する（energy bookkeeping を有効化した場合のみ）。

I/O は `io.streaming` を既定で ON とし（`memory_limit_gb=10`, `step_flush_interval=10000`, `merge_at_end=true`）、大規模スイープでは逐次フラッシュでメモリを抑える。CI/pytest など軽量ケースでは `FORCE_STREAMING_OFF=1` または `IO_STREAMING=off` を明示してストリーミングを無効化する。`checks/mass_budget.csv` はストリーミング設定に関わらず生成する。

- 実行結果は `out/<YYYYMMDD-HHMM>_<short-title>__<shortsha>__seed<n>/` に格納し、`run_card.md` へコマンド・環境・主要パラメータ・生成物ハッシュを記録して再現性を担保する。
- `run_config.json` には採用した $\rho$, $Q_{\rm pr}$, $s_{\rm blow}$, 物理トグル、温度ドライバの出典が保存され、再解析時の基準となる。

> **参照**: analysis/run-recipes.md §出力, analysis/AI_USAGE.md (I/O 規約)

---
## 長期モデルへ渡せる出力（5点）

最後に、出力を長期モデルへ接続できる形で 5 点にまとめます。

1. 遷移期の累積損失 \(\Delta M_{\rm in}\) と、遷移期後の実効 \(M_{\rm in}(t_{\rm ss})\)  
2. ロッシュ限界外側の初期条件：\(M_{\rm out}\)、\(dM/da_{\rm eq}\)、\(a_{\rm eq,max}\)  
3. 角運動量指標（\(L_d\)、\(L_d^\*\)、\(L_d/M_d\) など）  
4. 表層（\(\tau<1\)）質量と再供給時間 \(t_{\rm supply}\) の履歴  
5. 相（蒸気割合）・粒径分布・損失内訳（放射圧／昇華／蒸気散逸）  


この 5 点がそろうと、Salmon & Canup (2012) 型の「内側円盤＝連続体」進化や、Canup & Salmon (2018) の火星版長期形成モデルに対して、入力 \(M_{\rm in}\) と外側円盤初期条件を更新したときに結果がどれほど変わるかを、再現性のある形で議論できます。

<!-- TEX_EXCLUDE_START -->
### 先行研究リンク
- [Salmon & Canup (2012)](../../paper/pdf_extractor/outputs/SalmonCanup2012_ApJ760_83/result.md)
- [Canup & Salmon (2018)](../../paper/pdf_extractor/outputs/CanupSalmon2018_SciAdv4_eaar6887/result.md)

<!-- TEX_EXCLUDE_END -->
---
## 10. 検証手順

### ユニットテスト

```bash
pytest tests/ -q
```

主要テストは analysis/run-recipes.md §検証チェックリスト を参照。特に以下でスケールと安定性を確認する。

- Wyatt/Strubbe–Chiang 衝突寿命スケール: `pytest tests/integration/test_scalings.py::test_strubbe_chiang_collisional_timescale_matches_orbit_scaling`
- Blow-out 起因 “wavy” PSD の再現: `pytest tests/integration/test_surface_outflux_wavy.py::test_blowout_driven_wavy_pattern_emerges`
- IMEX-BDF(1) の $\Delta t$ 制限と質量保存: `pytest tests/integration/test_mass_conservation.py::test_imex_bdf1_limits_timestep_and_preserves_mass`
- 1D セル並列の on/off 一致確認（Windowsのみ）: `pytest tests/integration/test_numerical_anomaly_watchlist.py::test_cell_parallel_on_off_consistency`
- 質量収支ログ: `out/checks/mass_budget.csv` で |error| ≤ 0.5% を確認（C4）

検証では、$t_{\rm coll}$ スケールが理論式のオーダーと一致すること、$\Delta t$ の制約が安定性を満たすこと、ブローアウト近傍で wavy 構造が再現されることを確認する。これらの基準は設定変更後の回帰検証にも適用する。

### 実行後の数値チェック（推奨）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内であること。
- `series/run.parquet` の `dt_over_t_blow` が 1 未満に収まっているかを確認し、超過時は `fast_blowout_flag_*` と併せて評価する。
- 衝突が有効なケースでは `smol_dt_eff < dt` が成立し、`t_coll_kernel_min` と一貫しているかを確認する。

### ドキュメント整合性

```bash
make analysis-sync      # DocSync
make analysis-doc-tests # アンカー健全性・参照率検査
python -m tools.evaluation_system --outdir <run_dir>  # Doc 更新後に直近の out/* を指定
```

> **詳細**: analysis/overview.md §16 "DocSync/検証フローの固定"

---
## 11. 先行研究リンク

- 温度ドライバ: [Hyodo et al. (2018)](../paper/pdf_extractor/outputs/Hyodo2018_ApJ860_150/result.md)
- 放射圧・ブローアウト: [Burns et al. (1979)](../paper/pdf_extractor/outputs/Burns1979_Icarus40_1/result.md), [Strubbe & Chiang (2006)](../paper/pdf_extractor/outputs/StrubbeChiang2006_ApJ648_652/result.md), [Wyatt (2008)](../paper/pdf_extractor/outputs/Wyatt2008/result.md), [Takeuchi & Lin (2002)](../paper/pdf_extractor/outputs/TakeuchiLin2002_ApJ581_1344/result.md), [Takeuchi & Lin (2003)](../paper/pdf_extractor/outputs/TakeuchiLin2003_ApJ593_524/result.md), [Shadmehri (2008)](../paper/pdf_extractor/outputs/Shadmehri2008_ApSS314_217/result.md)
- PSD/衝突カスケード: [Dohnanyi (1969)](../paper/pdf_extractor/outputs/Dohnanyi1969_JGR74_2531/result.md), [Krivov et al. (2006)](../paper/pdf_extractor/outputs/Krivov2006_AA455_509/result.md), [Birnstiel et al. (2011)](../paper/pdf_extractor/outputs/Birnstiel2011_AA525_A11/result.md), [Thébault & Augereau (2007)](../paper/pdf_extractor/outputs/ThebaultAugereau2007_AA472_169/result.md)
- 初期 PSD: [Hyodo et al. (2017a)](../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md), [Jutzi et al. (2010)](../paper/pdf_extractor/outputs/Jutzi2010_Icarus207_54/result.md)
- 速度分散: [Ohtsuki et al. (2002)](../paper/pdf_extractor/outputs/Ohtsuki2002_Icarus155_436/result.md), [Lissauer & Stewart (1993)](../paper/pdf_extractor/outputs/LissauerStewart1993_PP3/result.md), [Wetherill & Stewart (1993)](../paper/pdf_extractor/outputs/WetherillStewart1993_Icarus106_190/result.md), [Ida & Makino (1992)](../paper/pdf_extractor/outputs/IdaMakino1992_Icarus96_107/result.md), [Imaz Blanco et al. (2023)](../paper/pdf_extractor/outputs/ImazBlanco2023_MNRAS522_6150/result.md)
- 破砕強度・最大残存率: [Benz & Asphaug (1999)](../paper/pdf_extractor/outputs/BenzAsphaug1999_Icarus142_5/result.md), [Leinhardt & Stewart (2012)](../paper/pdf_extractor/outputs/LeinhardtStewart2012_ApJ745_79/result.md), [Stewart & Leinhardt (2009)](../paper/pdf_extractor/outputs/StewartLeinhardt2009_ApJ691_L133/result.md)
- 遮蔽 (Φ): [Joseph et al. (1976)](../paper/pdf_extractor/outputs/Joseph1976_JAS33_2452/result.md), [Hansen & Travis (1974)](../paper/pdf_extractor/outputs/HansenTravis1974_SSR16_527/result.md), [Cogley & Bergstrom (1979)](../paper/pdf_extractor/outputs/CogleyBergstrom1979_JQSRT21_265/result.md)
- 光学特性: [Bohren & Huffman (1983)](../paper/pdf_extractor/outputs/BohrenHuffman1983_Wiley/result.md)
- 昇華: [Markkanen & Agarwal (2020)](../paper/pdf_extractor/outputs/Markkanen2020_AA643_A16/result.md), [Kubaschewski (1974)](../paper/pdf_extractor/outputs/Kubaschewski1974_Book/result.md), [Fegley & Schaefer (2012)](../paper/pdf_extractor/outputs/FegleySchaefer2012_arXiv/result.md), [Visscher & Fegley (2013)](../paper/pdf_extractor/outputs/VisscherFegley2013_ApJL767_L12/result.md), [Pignatale et al. (2018)](../paper/pdf_extractor/outputs/Pignatale2018_ApJ853_118/result.md), [Ronnet et al. (2016)](../paper/pdf_extractor/outputs/Ronnet2016_ApJ828_109/result.md), [Melosh (2007)](../paper/pdf_extractor/outputs/Melosh2007_MPS42_2079/result.md)

参照インデックス: [paper/abstracts/index.md](../paper/abstracts/index.md) / [analysis/references.registry.json](../analysis/references.registry.json)

---
## 付録 A. 運用実行（run_sweep.cmd を正とする）

代表的な実行コマンドとシナリオは analysis/run-recipes.md に集約する。運用スイープは `scripts/runsets/windows/run_sweep.cmd` を正とし、既定の `CONFIG_PATH`/`OVERRIDES_PATH` と引数の扱いは同スクリプトに従う。  
> **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEFAULT_PATHS` / `::REF:CLI_ARGS`

```cmd
rem Windows: sweep
scripts\runsets\windows\run_sweep.cmd --config scripts\runsets\common\base.yml --overrides scripts\runsets\windows\overrides.txt --out-root out
```

- `--no-preflight` は拒否される。既定では `SKIP_PREFLIGHT=1` でスキップされるため、事前チェックを走らせる場合は `SKIP_PREFLIGHT=0` を指定する。`--preflight-only` で事前チェックのみ実行。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PREFLIGHT_ARGS` / `::REF:PREFLIGHT`
- `--no-plot` / `--no-eval` は hook を抑制し、`HOOKS_ENABLE` のフィルタに反映される。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CLI_ARGS` / `::REF:HOOKS`
- 依存関係は `requirements.txt` から自動導入され、`SKIP_PIP=1` または `REQUIREMENTS_INSTALLED=1` で無効化できる。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEPENDENCIES`
- `OUT_ROOT` は内部/外部の自動選択が働き、`io.archive.dir` が未設定/無効なら `OUT_ROOT\\archive` を付加した overrides を生成する。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:OUT_ROOT` / `::REF:ARCHIVE_CHECKS`
- `io.archive.*` の要件を満たさない場合は実行中断。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:ARCHIVE_CHECKS`
- 実行本体は `run_temp_supply_sweep.cmd` を子として起動する。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CHILD_RUN`
- スイープ並列は既定で有効 (`SWEEP_PARALLEL=1`) で、ネスト回避のため `MARSDISK_CELL_PARALLEL=0` によりセル並列は無効化される。サイズプローブで `PARALLEL_JOBS` が調整される場合がある。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PARALLEL`

### run_sweep.cmd の主要環境変数

既定値は `run_sweep.cmd` のデフォルト設定に従う。主要環境変数は表\ref{tab:run_sweep_env}に示す。  
> **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:SWEEP_DEFAULTS`

\begin{table}[t]
  \centering
  \caption{run\_sweep.cmd の主要環境変数}
  \label{tab:run_sweep_env}
  \begin{tabular}{p{0.28\textwidth} p{0.42\textwidth} p{0.18\textwidth}}
    \hline
    変数 & 意味 & 既定値 \\
    \hline
    \texttt{SWEEP\_TAG} & 出力タグ & \texttt{temp\_supply\_sweep\_1d} \\
    \texttt{GEOMETRY\_MODE} & 形状モード & \texttt{1D} \\
    \texttt{GEOMETRY\_NR} & 半径セル数 & 32 \\
    \texttt{SHIELDING\_MODE} & 遮蔽モード & \texttt{off} \\
    \texttt{SUPPLY\_MU\_REFERENCE\_TAU} & 供給基準$\tau$ & 1.0 \\
    \texttt{SUPPLY\_FEEDBACK\_ENABLED} & $\tau$フィードバック & 0 \\
    \texttt{SUPPLY\_TRANSPORT\_MODE} & 供給トランスポート & \texttt{direct} \\
    \texttt{SUPPLY\_TRANSPORT\_TMIX\_ORBITS} & ミキシング時間 [orbits] & \texttt{off} \\
    \texttt{COOL\_TO\_K} & 温度停止閾値 [K] & 1000 \\
    \texttt{PARALLEL\_MODE} & 並列モード（\texttt{SWEEP\_PARALLEL=1} ではセル並列は無効化） & \texttt{cell} \\
    \texttt{SWEEP\_PARALLEL} & スイープ並列 & 1 \\
    \texttt{PARALLEL\_JOBS} & sweep job 数 & 6 \\
    \hline
  \end{tabular}
\end{table}

- 固定地平で動かす場合は `COOL_TO_K=none` と `T_END_YEARS` を指定する。  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:TEMPERATURE_STOP`

---
## 付録 B. 設定→物理対応クイックリファレンス

設定と物理の対応を表\ref{tab:config_physics_map}にまとめる。

\begin{table}[t]
  \centering
  \caption{設定キーと物理の対応}
  \label{tab:config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 詳細参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & config\_guide §3.2 \\
    \texttt{radiation.mars\_temperature\_driver.*} & 冷却ドライバ & config\_guide §3.2 \\
    \texttt{shielding.mode} & 遮蔽 $\Phi$ & config\_guide §3.4 \\
    \texttt{sinks.mode} & 昇華/ガス抗力 & config\_guide §3.6 \\
    \texttt{blowout.enabled} & ブローアウト損失 & config\_guide §3.9 \\
    \texttt{supply.mode} & 表層再供給 & config\_guide §3.7 \\
    \texttt{supply.feedback.*} & $\tau$フィードバック制御 & config\_guide §3.7 \\
    \texttt{supply.temperature.*} & 温度カップリング & config\_guide §3.7 \\
    \texttt{supply.reservoir.*} & 有限質量リザーバ & config\_guide §3.7 \\
    \texttt{supply.transport.*} & 深層ミキシング & config\_guide §3.7 \\
    \texttt{init\_tau1.*} & 初期$\tau=1$スケーリング & config\_guide §3.3 \\
    \texttt{phase.*} & 相判定 & config\_guide §3.8 \\
    \texttt{numerics.checkpoint.*} & チェックポイント & config\_guide §3.1 \\
    \texttt{numerics.t\_end\_until\_temperature\_K} & 温度停止条件 & config\_guide §3.1 \\
    \texttt{ALLOW\_TL2003} & gas-rich 表層 ODE トグル & config\_guide §3.6, §3.9 \\
    \texttt{psd.wavy\_strength} & "wavy" 強度（0 で無効） & config\_guide §3.3 \\
    \hline
  \end{tabular}
\end{table}

完全な設定キー一覧は analysis/config_guide.md を参照。

---
## 付録 C. 関連ドキュメント

関連ドキュメントの役割を表\ref{tab:related_docs}に整理する。

\begin{table}[t]
  \centering
  \caption{関連ドキュメントと参照用途}
  \label{tab:related_docs}
  \begin{tabular}{p{0.3\textwidth} p{0.28\textwidth} p{0.36\textwidth}}
    \hline
    ドキュメント & 役割 & 参照時のユースケース \\
    \hline
    \texttt{analysis/equations.md} & 物理式の定義（E.xxx） & 式の導出・記号・単位の確認 \\
    \texttt{analysis/physics\_flow.md} & 計算フロー Mermaid 図 & モジュール間依存と実行順序の把握 \\
    \texttt{analysis/config\_guide.md} & 設定キー詳細 & YAML パラメータの意味と許容範囲 \\
    \texttt{analysis/glossary.md} & 用語・略語・単位規約 & 変数命名と単位接尾辞の確認 \\
    \texttt{analysis/overview.md} & アーキテクチャ・データフロー & モジュール責務と 3 層分離の理解 \\
    \texttt{analysis/run-recipes.md} & 実行レシピ・感度掃引 & シナリオ別の実行手順と検証方法 \\
    \hline
  \end{tabular}
\end{table}

---
## 付録 D. 略語索引

略語は表\ref{tab:abbreviations}にまとめる。

\begin{table}[t]
  \centering
  \caption{略語索引}
  \label{tab:abbreviations}
  \begin{tabular}{p{0.18\textwidth} p{0.44\textwidth} p{0.28\textwidth}}
    \hline
    略語 & 日本語 / 英語 & 備考 \\
    \hline
    PSD & 粒径分布 / particle size distribution & サイズビン分布 $n(s)$ \\
    LOS & 視線方向 / line of sight & $\tau_{\rm los}$ に対応 \\
    ODE & 常微分方程式 / ordinary differential equation & 表層 ODE \\
    IMEX & implicit-explicit & IMEX-BDF(1) に使用 \\
    BDF & backward differentiation formula & 一次 BDF \\
    $Q_{\rm pr}$ & 放射圧効率 / radiation pressure efficiency & テーブル入力 \\
    $Q_D^*$ & 破壊閾値 / critical specific energy & 破壊強度 \\
    HKL & Hertz--Knudsen--Langmuir & 昇華フラックス \\
    C5 & 半径方向拡散 / radial viscous diffusion & 1D 拡張 \\
    1D & one-dimensional & 幾何モード \\
    \hline
  \end{tabular}
\end{table}
---
document_type: reference
title: 記号一覧（遷移期・長期モデル接続：暫定）
---

# 記号一覧（遷移期・長期モデル接続：暫定）

本ファイルは、現時点の導入（遷移期）文書に現れる記号を、TeX 化に先立って一時的に整理したものである。定義が先行研究依存で確定できない項目は文献確認中として残している。

\begin{table}[t]
  \centering
  \caption{記号一覧（遷移期・長期モデル接続：暫定）}
  \label{tab:symbols_transition}
  \begin{tabular}{p{0.20\linewidth}p{0.46\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
    \hline
    記号 & 意味 & 単位 & 注記 \\
    \hline
    $M_{\rm in}$ &
    ロッシュ限界内側に存在する内側円盤の質量（長期モデルの主要入力） &
    $\mathrm{kg}$ &
    文献確認中 \\
    $M_{\rm in}^{\rm SPH}$ &
    SPH 終端時刻におけるロッシュ限界内側の円盤質量（接続前の推定値） &
    $\mathrm{kg}$ &
    SPH 出力から集計（方法は文献確認中） \\
    $\Delta M_{\rm in}$ &
    遷移期における内側円盤の不可逆損失（表層散逸・不可逆落下等の総和） &
    $\mathrm{kg}$ &
    本研究で評価対象（落下分の扱いは要確認） \\
    $M_{\rm in,0}$ &
    長期モデル開始時刻 $t_0$ における内側円盤の有効質量（接続後の入力） &
    $\mathrm{kg}$ &
    $M_{\rm in,0}=M_{\rm in}^{\rm SPH}-\Delta M_{\rm in}$ \\
    $t_0$ &
    長期モデルの開始時刻（遷移期が終わったと見なす時刻） &
    $\mathrm{s}$（または $\mathrm{h}$） &
    定義は文献確認中 \\
    $r_d$ &
    内側円盤の外縁（半径） &
    $\mathrm{m}$（または $R_{\rm Mars}$） &
    定義は文献確認中 \\
    $a_{\rm eq,max}$ &
    円盤が赤道面へ緩和した後の「最大半長軸」等を表す候補記号 &
    未定 &
    定義関係は要確認 \\
    $J_2$ &
    火星重力場の扁平項（第 2 帯状調和係数） &
    -- &
    遷移期の歳差運動・位相混合に関与 \\
    \hline
  \end{tabular}
\end{table}

## 補足：記号不整合（現状の把握）

- 「外縁」が $r_d$ と $a_{\rm eq,max}$ で混在している。現時点では、両者の定義関係が文書内で確定できないため、表\ref{tab:symbols_transition} では別項目として残している。  
- 先行研究（特に Canup \& Salmon (2018)）の該当箇所を確認し、(i) 同一概念ならどちらかに統一する、(ii) 別概念なら本文で初出定義を与える、のいずれかを行う必要がある。（要確認）

---
