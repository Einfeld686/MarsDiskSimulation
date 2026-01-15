> **文書種別**: リファレンス（Diátaxis: Reference）

<!--
NOTE: このファイルは analysis/thesis_sections/02_methods/*.md の結合で生成する。
編集は分割ファイル側で行い、統合は `python -m analysis.tools.merge_methods_sections --write` を使う。
-->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# シミュレーション手法

## 1. 目的・出力・問いとの対応

本資料は火星ロッシュ限界内の高温ダスト円盤を対象とする数値手法を、論文の Methods 相当の水準で記述する（[@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887]）。gas-poor 条件下での粒径分布（particle size distribution; PSD）進化と、表層（surface layer）の放射圧起因アウトフロー（outflux）を**同一タイムループで結合**し、2 年スケールの $\dot{M}_{\rm out}(t)$ と $M_{\rm loss}$ を評価する（[@Krivov2006_AA455_509; @StrubbeChiang2006_ApJ648_652; @Wyatt2008]）。数式の定義は analysis/equations.md の (E.###) を正とし、本書では主要式を必要最小限に再掲したうえで、離散化・数値解法・運用フロー・検証条件を整理する。

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
- 次に 1 ステップの処理順序（図 3.1–3.2）を把握する。
- その後、放射圧・供給・衝突・昇華・遮蔽の各過程を個別に読む。
- 最後に運用（run_sweep）と再現性（出力・検証）を確認する。

本文では物理的な因果と時間発展の説明を優先し、設定キーや実装パスは付録に整理する。式は必要最小限に再掲し、詳細な定義と記号表は analysis/equations.md を正とする。

本書で用いる略語は以下に統一する。光学的厚さ（optical depth; $\tau$）、視線方向（line of sight; LOS）、常微分方程式（ordinary differential equation; ODE）、implicit-explicit（IMEX）、backward differentiation formula（BDF）、放射圧効率（radiation pressure efficiency; $Q_{\rm pr}$）、破壊閾値（critical specific energy; $Q_D^*$）、Hertz–Knudsen–Langmuir（HKL）フラックス、1D（one-dimensional）。
