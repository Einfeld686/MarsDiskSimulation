## 5. 出力と検証

本節では，計算結果を再解析可能な形で保存するための出力仕様と，本文で採用する計算の合格基準（検証）をまとめる．

### 5.1 出力と検証

本研究では，再解析可能性を担保するため，(i) 入力条件（設定・外部テーブル参照）と由来情報，(ii) 主要診断量の時系列，(iii) PSD 履歴，(iv) 終端集計，(v) 検証ログを，実行ごとに保存する（付録 A）．これらが揃えば，後段の図表生成は保存された出力を入力として再構成できる．

保存形式は JSON/Parquet/CSV であり，入力と採用値の記録（`run_config.json`），主要スカラー時系列（`series/run.parquet`），PSD 履歴（`series/psd_hist.parquet`），終端要約（`summary.json`），質量検査ログ（`checks/mass_budget.csv`）を最小セットとして保持する．補助的に，遮蔽や供給クリップなどの追加診断時系列を保存し，実行環境・実行コマンドも併せて記録する．1D 計算では半径セルごとの時系列を保存するため，任意時刻の円盤全体量は半径積分（離散和）により再構成できる．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する\citep{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示し，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様の規格化量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

検証は質量保存，時間刻み収束，および粒径ビン収束（PSD 解像度）の 3 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．

質量保存は式\ref{eq:mass_budget_definition}で定義する相対質量誤差 $\epsilon_{\rm mass}$ の最大値が $0.5\%$ 以下であることを要求する．

時間刻み収束は，$\Delta t$ と $\Delta t/2$ の 2 計算を比較し，代表量として累積損失 $M_{\rm loss}$ の相対差が $1\%$ 以下となることにより確認する．

粒径ビン収束（PSD 解像度）は，基準の粒径ビン数とその 2 倍の粒径ビン数で計算した結果を比較し，同じ基準で $M_{\rm loss}$ の相対差が $1\%$ 以下となることを要求する．

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
    粒径ビン収束（PSD 解像度） & 基準の粒径ビン数とその 2 倍の粒径ビン数の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
    \hline
\end{tabular}
\end{table}

以上の出力仕様と検証基準により，結果の再現性（入力→出力の対応）と数値的健全性（質量保存・時間刻み・粒径ビン（PSD 解像度））を担保したうえで，本論文の結果・議論を構成する．
