## 5. 出力と検証

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

本節では，計算結果を再解析可能な形で保存するための出力仕様と，本文で採用する計算の合格基準（検証）をまとめる．

### 5.1 出力と検証

本研究では，再解析可能性を担保するため，(i) 入力条件（設定・外部テーブル参照）と由来情報，(ii) 主要診断量の時系列，(iii) PSD 履歴，(iv) 終端集計，(v) 検証ログを，実行ごとに保存する（付録 A）．これらが揃えば，後段の図表生成は保存された出力を入力として再構成できる．

保存形式は JSON/Parquet/CSV であり，入力と採用値の記録（`run_config.json`），主要スカラー時系列（`series/run.parquet`），PSD 履歴（`series/psd_hist.parquet`），終端要約（`summary.json`），質量検査ログ（`checks/mass_budget.csv`）を最小セットとして保持する．補助的に，`series/diagnostics.parquet`（遮蔽などの追加診断；存在する場合）や `checks/mass_budget_cells.csv`（1D のセル別質量収支；設定により出力）を保存する．また，収束比較（時間刻み・粒径ビン）の判定結果は，別実行の比較から `checks/validation.json` として出力し，本文の合否判定に用いる．1D 計算では半径セルごとの時系列を保存するため，任意時刻の円盤全体量は半径積分（離散和）により再構成できる．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する\citep{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示し，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様の規格化量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

検証は，質量保存，時間刻み収束，および粒径ビン収束（PSD ビン数）の 3 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．質量保存は式\ref{eq:mass_budget_definition}で定義する相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下であることを要求する．時間刻み収束と粒径ビン収束（PSD ビン数）に用いる相対差は $|X({\rm coarse})-X({\rm ref})|/|X({\rm ref})|$ と定義する．ref はより細かい離散化（時間刻みなら $\Delta t/2$，粒径ビンならビン数 2 倍）とする．

時間刻み収束は，$\Delta t$（coarse）と $\Delta t/2$（ref）の計算で，累積損失 $M_{\rm loss}$ の相対差が $1\%$ 以下となることにより確認する．$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で更新される累積量であり，離散化誤差が時間積分を通じて蓄積した影響を直接反映するため，収束判定の代表指標として採用する．

粒径ビン収束（PSD ビン数）は，基準の粒径ビン設定（coarse）と，粒径ビン幅を 1/2 とした設定（ref；ビン数を 2 倍にした PSD）の計算結果を比較し，時間刻み収束と同一の指標（$M_{\rm loss}$ の相対差）で $1\%$ 以下となることにより確認する．この比較により，粒径離散化に起因する系統誤差が本論文の結論に影響しない範囲であることを担保する．

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
    粒径ビン収束（PSD ビン数） & 基準ビンとビン数を 2 倍にした計算の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
    \hline
\end{tabular}
\end{table}

以上の出力仕様と検証基準により，結果の再現性（入力→出力の対応）と数値的健全性（質量保存と収束性：時間刻み・粒径ビン）を担保したうえで，本論文の結果・議論を構成する．
