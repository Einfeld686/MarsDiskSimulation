## 5. 出力と検証

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

### 5.1 出力と検証

直接追跡する状態量は，各粒径ビン $k$ に離散化した粒子数面密度 $N_k(t)$ と，表層面密度 $\Sigma_{\rm surf}(t)$ である．したがって，再解析のために必要な情報は，(a) これらの時間発展を決める入力条件（初期条件・物理パラメータ・外部テーブルの参照情報を含む）と，(b) 主要診断量の時系列，(c) PSD（粒径分布）の履歴，(d) 計算終了時点の集計，および (e) 数値的健全性を確認する検証ログである．これらを実行ごとに保存しておけば，本文の図表は保存された出力のみを入力として再構成できる（保存情報の要点は付録 Aにまとめる）．

保存する診断量の中心は，各ステップの時刻 $t$ と時間刻み $\Delta t$ に加え，放射圧流出を特徴づける $\tau_{\rm los},\,s_{\rm blow},\,s_{\min}$，および表層の状態を表す $\Sigma_{\rm surf},\,\dot{M}_{\rm out}$ などである．PSD は $N_k(t)$ を独立に記録し，任意時刻の分布形状とその変化を追跡できるようにする．1D 計算では半径セルごとに同様の時系列を保存するため，円盤全体の量は半径積分（離散和）として再構成できる．出力は JSON/Parquet/CSV で保存し，入力条件の記録，主要スカラー時系列，PSD 履歴，終端要約，質量検査ログが最小セットとして残るよう構成している．

円盤からの累積損失 $M_{\rm loss}$ は，表層流出率 $\dot{M}_{\rm out}$ と追加シンク（昇華など）による損失率 $\dot{M}_{\rm sinks}$ を区分一定近似で積算し，式\ref{eq:mass_loss_update}で更新する\citep{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示すため，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様に規格化した量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

ここで $\Delta t$ は外側ステップ幅であり，$\dot{M}_{\rm out}^{n}$ と $\dot{M}_{\rm sinks}^{n}$ は区間 $[t^n,t^{n+1})$ に対するステップ平均量として扱う．粒径分布の更新で $dt_{\rm eff}<\Delta t$ が採用された場合でも，この平均量で損失を積算することで $M_{\rm loss}$ を更新する．

計算の検証は，質量保存，時間刻み収束，および粒径ビン収束（PSD 解像度）の 3 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．質量保存は，式\ref{eq:mass_budget_definition}で定義する相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下であることを要求する．

一方，数値離散化に起因する系統誤差は，より細かい離散化に対する相対差で評価する．ここでは任意の指標 $X$ について相対差を

\begin{equation}
\label{eq:relative_difference_definition}
\Delta_{\rm rel}(X)\equiv \frac{|X({\rm coarse})-X({\rm ref})|}{|X({\rm ref})|}
\end{equation}

と定義する．時間刻み収束では ${\rm ref}$ を $\Delta t/2$ とした計算とし，$\Delta_{\rm rel}(M_{\rm loss})\le 1\%$ を合格条件とする．$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で時間積分される累積量であるため，離散化誤差が蓄積して現れやすく，収束判定の代表指標として適している．

粒径ビン収束では，${\rm ref}$ を粒径ビン幅を 1/2 にしてビン数を 2 倍とした PSD の計算とし，時間刻み収束と同じく $\Delta_{\rm rel}(M_{\rm loss})\le 1\%$ を要求する．この比較により，粒径離散化の取り方が，結論に影響し得る大きさの系統誤差を導入していないことを確認する．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{3pt}
\caption{検証項目と合格基準}
\label{tab:validation_criteria}
\begin{tabular}{p{0.27\textwidth} p{0.69\textwidth}}
\hline
検証項目 & 合格基準（許容誤差） \\
\hline
質量保存 & 相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下 \\
時間刻み収束 & $\Delta t$ と $\Delta t/2$ の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
粒径ビン収束（PSD 解像度） & 基準ビンとビン数を 2 倍にした計算の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
\hline
\end{tabular}
\end{table}

### 5.2 仮定と限界

本手法は，いくつかの近似を導入している．
まず，半径方向の輸送過程（粘性拡散や PR ドラッグなど）は支配方程式としては解かず，各半径セルにおける局所進化を独立に評価する．
次に，衝突速度の評価では，相対速度を与える離心率 $e$ と傾斜角 $i$ を代表値として固定し，低離心率・低傾斜の近似式を速度スケールとして用いる．この近似は，厳密な励起・散乱過程を扱わない代わりに，衝突頻度と破壊効率の主要な依存性を一つのスケールに押し込み，衝突カスケードの時間発展を記述可能にするものである．
また，自己遮蔽は遮蔽係数 $\Phi$ を有効不透明度 $\kappa_{\rm eff}$ に反映させ，照射・表層アウトフローの評価に用いる．一方，適用範囲判定（早期停止）は視線方向光学的厚さ $\tau_{\rm los}>\tau_{\rm stop}$ により行う．しかし，遮蔽によって放射圧パラメータ $\beta$ 自体が連続的に減衰するような詳細な放射輸送は扱わない．したがって本手法は，遮蔽が強くなり過ぎ，表層という概念が曖昧になる領域では，そもそも適用対象外として計算を停止する設計になっている．
さらに，昇華は粒径縮小 $ds/dt$ を一次シンクへ写像し，粒径空間の移流としては追跡しない．この近似は，昇華が分布形状を滑らかに輸送する効果よりも，その粒径帯の粒子が消失する効果を優先して取り込むものである．
