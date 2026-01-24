## 付録 A. 再現実行と保存情報

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

本研究の再現性は，(i) 入力（設定ファイルとテーブル）を固定し，(ii) 実行時に採用された値と条件を保存し，(iii) 時系列・要約・検証ログを保存することで担保する．本付録では，論文として最低限必要な「保存すべき情報」をまとめる．

### A.1 固定する入力（再現の前提）

- **設定**: 物理スイッチ，初期条件，時間刻み，停止条件，感度掃引の対象パラメータ．
- **外部テーブル**: $\langle Q_{\rm pr}\rangle$ や遮蔽係数 $\Phi$ などの外部入力（付録 C）．
- **乱数シード**: 乱数を用いる過程がある場合はシードを固定する．

外部入力（テーブル）の役割と本文中での参照先を付録 C（表\ref{tab:app_external_inputs}）にまとめる．実行時に採用したテーブルの出典と適用範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする．

### A.2 保存する出力（再解析の最小セット）

本論文で示す結果は，以下の情報を保存して再解析できる形で管理した．

- **採用値の記録**: $\rho$，$\langle Q_{\rm pr}\rangle$，物理スイッチ，$s_{\rm blow}$ など，実行時に採用した値と出典を機械可読形式で保存する．
- **時系列**: 主要スカラー量（$\tau_{\rm los}$，$s_{\rm blow}$，$\Sigma_{\rm surf}$，$\dot{M}_{\rm out}$ など）の時系列．
- **PSD 履歴**: $N_k(t)$ と $\Sigma_{\rm surf}(t)$ の履歴．
- **要約**: $t_{\rm end}$ までの累積損失 $M_{\rm loss}$ などの集約．
- **検証ログ**: 式\ref{eq:mass_budget_definition} に基づく質量検査のログ．

実際の成果物は実行ディレクトリ（`OUTDIR/`）配下に保存し，後段の解析はこれらを入力として再構成する．最小セットは次の 5 点である．

- `OUTDIR/run_config.json`（JSON）: 展開後の設定と採用値，実行環境（`python`/`platform`/`argv`/`cwd`/`timestamp_utc`），依存パッケージの版，および外部ファイル（テーブル等）のパスとハッシュ（可能な範囲）．
- `OUTDIR/series/run.parquet`（Parquet）: 主要スカラー時系列（例: `time`, `dt`, `tau`, `a_blow`, `s_min`, `Sigma_surf`, `outflux_surface`, `prod_subblow_area_rate`, `M_out_dot`, `M_loss_cum`）．
- `OUTDIR/series/psd_hist.parquet`（Parquet）: PSD 履歴（例: `time`, `bin_index`, `s_bin_center`, `N_bin`, `Sigma_bin`, `f_mass`, `Sigma_surf`）．
- `OUTDIR/summary.json`（JSON）: 終端要約（例: `M_loss`, `mass_budget_max_error_percent`）．
- `OUTDIR/checks/mass_budget.csv`（CSV）: 質量検査ログ（例: `time`, `mass_initial`, `mass_remaining`, `mass_lost`, `error_percent`, `tolerance_percent`）．

補助的に，`OUTDIR/series/diagnostics.parquet`（遮蔽などの追加診断；存在する場合）や `OUTDIR/checks/mass_budget_cells.csv`（1D のセル別質量収支；設定により出力）を保存する．また，時間刻み・粒径ビンの収束比較の合否判定は `scripts/validate_run.py` により `OUTDIR/checks/validation.json` として出力し，表\ref{tab:validation_criteria}の確認に用いる．

保存時は質量流出率と累積損失を火星質量 $M_{\rm Mars}$ で規格化した単位で記録し，数値桁を揃える．定義は付録 E（記号表）を参照する．

### A.3 感度掃引で用いる代表パラメータ（例）

\begin{table}[t]
  \centering
  \caption{感度掃引で用いる代表パラメータ（例）}
  \label{tab:app_methods_sweep_defaults}
  \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
    \hline
    変数 & 代表値 & 意味 \\
    \hline
    $T_M$ & 4000, 3000 & 火星温度 [K] \\
    $\epsilon_{\rm mix}$ & 1.0, 0.5 & 混合係数（供給の有効度） \\
	    $\tau_0$ & 1.0, 0.5 & 初期視線方向光学的厚さ（$\tau_{\rm los}$ の規格化値） \\
    $i_0$ & 0.05, 0.10 & 初期傾斜角 \\
    $f_{Q^*}$ & 0.3, 1, 3（$\times$基準値） & $Q_D^*$ の係数スケール（proxy の不確かさの感度） \\
    \hline
  \end{tabular}
\end{table}

### A.4 検証結果の提示（代表ケース）

本論文では，表\ref{tab:validation_criteria}の合格基準に基づく検証を全ケースで実施し，合格した結果のみを採用する．代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列例を図\ref{fig:app_validation_mass_budget_example}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/thesis/validation_mass_budget_example.pdf}
  \caption{代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列（例）}
  \label{fig:app_validation_mass_budget_example}
\end{figure}

### A.5 基準ケースで用いる物性値

本研究の基準ケースで採用する物性値（フォルステライト基準）を表\ref{tab:run_sweep_material_properties}にまとめる．密度・放射圧効率・昇華係数はフォルステライト値を採用し，$Q_D^*$ は peridot projectile 実験の $Q^*$ を参照して BA99 係数をスケーリングした proxy を用いる．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{基準ケースで用いる物性値（フォルステライト基準）}
  \label{tab:run_sweep_material_properties}
  \begin{tabular}{L{0.16\textwidth} L{0.34\textwidth} L{0.26\textwidth} L{0.16\textwidth}}
    \hline
    記号 & 意味 & 値 & 出典 \\
    \hline
	    $\rho$ &
	    粒子密度 [kg\,m$^{-3}$] &
	    3270 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $\langle Q_{\rm pr}\rangle$ &
    Planck 平均放射圧効率（テーブル） &
    フォルステライト（Mie テーブル） &
    \citep{BohrenHuffman1983_Wiley,Zeidler2015_ApJ798_125} \\
	    $\alpha$ &
	    HKL 蒸発係数 &
	    0.1 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $\mu$ &
	    分子量 [kg\,mol$^{-1}$] &
	    0.140694 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $A_{\rm solid}$ &
	    固相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm solid}-B_{\rm solid}/T$ &
	    13.809441833 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $B_{\rm solid}$ &
	    同上（$T$ は K） &
	    28362.904024 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $T_{\rm solid}^{\rm valid}$ &
	    固相フィットの適用温度範囲 [K] &
	    1673--2133 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
    $A_{\rm liq}$ &
    液相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm liq}-B_{\rm liq}/T$ &
    11.08 &
    \citep{FegleySchaefer2012_arXiv} \\
    $B_{\rm liq}$ &
    同上（$T$ は K） &
    22409.0 &
    \citep{FegleySchaefer2012_arXiv} \\
    $T_{\rm liq}^{\rm valid}$ &
    液相フィットの適用温度範囲 [K] &
    2163--3690 &
    \citep{FegleySchaefer2012_arXiv} \\
    $T_{\rm switch}$ &
    固相$\to$液相フィット切替温度 [K] &
    2163 &
    \citep{FegleySchaefer2012_arXiv} \\
	    $T_{\rm condense}$, $T_{\rm vaporize}$ &
	    相判定のヒステリシス閾値 [K]（相境界の切替幅） &
	    2162, 2163 &
	    本研究（スキーマ要件），基準: \citep{FegleySchaefer2012_arXiv} \\
    $f_{Q^*}$ &
    $Q_D^*$ 係数スケール（peridot proxy） &
    5.574 &
    \citep{Avdellidou2016_MNRAS464_734,BenzAsphaug1999_Icarus142_5} \\
    \hline
  \end{tabular}
\end{table}

<!-- TEX_EXCLUDE_START -->
### A.6 再現実行コマンド（Windows: run\_sweep.cmd）

Windows 環境での感度掃引の実行入口は `scripts/runsets/windows/run_sweep.cmd` とする．代表例として，設定ファイルと上書きファイルを明示した実行は次のとおりである．

\begin{verbatim}
scripts\runsets\windows\run_sweep.cmd ^
  --config scripts\runsets\common\base.yml ^
  --overrides scripts\runsets\windows\overrides.txt ^
  --out-root out
\end{verbatim}

同スクリプトの引数は次の Usage に従う（オプション名はスクリプト内の表示と一致）．

\begin{verbatim}
run_sweep.cmd [--study <path>] [--config <path>] [--overrides <path>]
            [--out-root <path>] [--dry-run] [--no-plot] [--no-eval]
            [--quiet] [--no-quiet] [--preflight-only] [--preflight-strict]
            [--debug]
\end{verbatim}

- `--study`: スイープ定義（YAML など）のパスを指定する．
- `--config`: ベース設定（YAML）のパスを指定する．
- `--overrides`: 上書き設定（テキスト）のパスを指定する．
- `--out-root`: 出力ルートを指定する．
- `--dry-run`: 実行計画の確認用に用いる．
- `--no-plot`: 実行後フックのうち可視化を抑制する．
- `--no-eval`: 実行後フックのうち評価を抑制する．
- `--quiet`/`--no-quiet`: ログ出力を切り替える．
- `--preflight-only`: 事前チェックのみ実行して終了する．
- `--preflight-strict`: 事前チェックを厳格モードで実行する．
- `--debug`: デバッグ出力を有効にする．

なお，スクリプトは既定で `requirements.txt` から依存関係を導入し，環境変数 `SKIP_PIP=1` により導入処理を省略できる（既に導入済みの場合は `REQUIREMENTS_INSTALLED=1`）．
<!-- TEX_EXCLUDE_END -->
