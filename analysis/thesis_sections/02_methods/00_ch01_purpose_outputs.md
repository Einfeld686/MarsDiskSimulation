文書種別: リファレンス（Diátaxis: Reference）

<!--
NOTE: このファイルは analysis/thesis_sections/02_methods/*.md の結合で生成する。
編集は分割ファイル側で行い、統合は `python -m analysis.tools.merge_methods_sections --write` を使う。
-->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @CanupSalmon2018_SciAdv4_eaar6887 -> paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf | 用途: 火星円盤の物理的前提（低質量円盤の文脈）
- @Hyodo2017a_ApJ845_125 -> paper/references/Hyodo2017a_ApJ845_125.pdf | 用途: 衝突起源円盤の前提条件と対象設定
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: Smoluchowski衝突カスケードの枠組み
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: 表層ブローアウトと衝突寿命の整理
<!-- TEX_EXCLUDE_END -->

# シミュレーション手法

## 1. 目的・出力・問いとの対応

本節では、火星のロッシュ限界内に形成される高温ダスト円盤を対象として、本研究で用いる数値シミュレーション手法の目的と出力を定義する。序論で掲げた研究課題に対し、本手法が直接算出する物理量と出力ファイルの対応を明確にする。

本手法はガスが希薄な条件（gas-poor）を仮定する（[@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887]）。粒径分布（particle size distribution; PSD）の時間発展と、表層の放射圧起因アウトフロー（outflux）を、同一のタイムループで結合して計算する。これにより、2 年スケールでの質量流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}$ を評価する。放射圧に起因する粒子運動と粒径分布進化は、既存の枠組みに従う（[@Krivov2006_AA455_509; @StrubbeChiang2006_ApJ648_652]）。

数式と記号の定義は付録にまとめた式番号 (E.###) を正とする。本文では、計算手順と出力仕様の理解に必要な範囲で、主要式のみを再掲する。以降では、離散化、数値解法、運用フロー、ならびに検証条件を、物理過程の因果関係が追える順序で記述する。

序論で提示した 3 つの問いと、本手法が直接生成する量・出力の対応を次の表に示す。

\begin{table}[t]
  \centering
  \caption{序論の問いと手法で直接生成する量の対応}
  \label{tab:methods_questions_outputs}
  \begin{tabular}{p{0.20\textwidth} p{0.32\textwidth} p{0.38\textwidth}}
    \hline
    序論の問い & 手法で直接生成する量 & 対応する出力 \\
    \hline
    問1: 高温期（1000 K まで／固定地平 2 年）の総損失量 &
    時間依存の流出率と累積損失 &
    \texttt{series/run.parquet} の\newline
    \texttt{M\_out\_dot}\newline
    \texttt{mass\_lost\_by\_blowout}\newline
    \texttt{mass\_lost\_by\_sinks}\newline
    \texttt{summary.json} の \texttt{M\_loss} \\
    問2: 粒径分布の時間変化と吹き飛びやすい粒径帯 &
    粒径ビンごとの数密度履歴と下限粒径 &
    \texttt{series/psd\_hist.parquet} の\newline
    \texttt{bin\_index}\newline
    \texttt{s\_bin\_center}\newline
    \texttt{N\_bin}\newline
    \texttt{Sigma\_surf}\newline
    \texttt{series/run.parquet} の \texttt{s\_min} \\
    問3: 短期損失を踏まえた残存質量の評価 &
    累積損失と質量収支の時系列 &
    \texttt{summary.json} の \texttt{M\_loss}\newline
    （初期条件との差分で残存量を評価）\newline
    \texttt{series/run.parquet} の\newline
    \texttt{mass\_lost\_by\_blowout}\newline
    \texttt{mass\_lost\_by\_sinks} \\
    \hline
  \end{tabular}
\end{table}

手法の記述は、まず入力パラメータと出力（時系列・要約量）を明確にする。次に 1 ステップの処理順序を示す。続いて、放射圧、物質供給、衝突、昇華、遮蔽を順に定式化する。最後に、一括実行（`run_sweep`）と再現性確保のための出力・検証手続きを述べる。

設定キーや実装パスのような実装依存の情報は付録に整理し、本文では物理モデルと時間発展の説明を優先する。本文で頻出する略語は次の表にまとめる。

\begin{table}[t]
  \centering
  \caption{本文で用いる主要略語}
  \label{tab:methods_abbrev}
  \begin{tabular}{p{0.18\textwidth} p{0.76\textwidth}}
    \hline
    略語・記号 & 意味 \\
    \hline
    $\tau$ & 光学的厚さ（optical depth） \\
    LOS & 視線方向（line of sight） \\
    ODE & 常微分方程式（ordinary differential equation） \\
    IMEX & implicit--explicit 法 \\
    BDF & backward differentiation formula \\
    $Q_{\rm pr}$ & 放射圧効率（radiation pressure efficiency） \\
    $Q_D^*$ & 破壊閾値（critical specific energy） \\
    HKL & Hertz--Knudsen--Langmuir フラックス \\
    1D & one-dimensional \\
    \hline
  \end{tabular}
\end{table}

以上により、本節では研究課題と出力の対応を定義した。次節以降では、これらの出力を規定する物理過程と数値解法を順に述べる。
