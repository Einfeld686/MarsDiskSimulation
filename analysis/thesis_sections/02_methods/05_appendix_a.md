### 付録 A. 再現実行と保存情報

<!--
実装(.py): scripts/runsets/windows/preflight_checks.py, scripts/runsets/common/read_overrides_cmd.py, scripts/runsets/common/read_study_overrides.py, scripts/runsets/common/write_base_overrides.py, scripts/runsets/common/write_sweep_list.py, scripts/runsets/common/build_overrides.py, scripts/runsets/common/next_seed.py, scripts/runsets/common/calc_parallel_jobs.py, scripts/runsets/common/calc_cell_jobs.py, scripts/runsets/common/calc_cpu_target_jobs.py, scripts/runsets/common/calc_thread_limit.py, scripts/tests/measure_case_output_size.py, scripts/runsets/common/run_one.py, scripts/runsets/common/run_sweep_worker.py, scripts/runsets/common/hooks/plot_sweep_run.py, scripts/runsets/common/hooks/evaluate_tau_supply.py, scripts/runsets/common/hooks/archive_run.py, scripts/runsets/common/hooks/preflight_streaming.py, marsdisk/run.py
-->

本研究の再現性は，(i) 入力（設定ファイルとテーブル）を固定し，(ii) 実行時に採用された値と条件を保存し，(iii) 時系列・要約・検証ログを保存することで担保する．本付録では，論文として最低限必要な「保存すべき情報」をまとめる．

#### A.1 固定する入力（再現の前提）

- **設定（YAML）**: 物理スイッチ，初期条件，時間刻み，停止条件，感度掃引の対象パラメータ．
- **テーブル（CSV/NPZ）**: $\langle Q_{\rm pr}\rangle$ や遮蔽係数 $\Phi$ などの外部テーブル．
- **乱数シード**: 乱数を用いる過程がある場合はシードを固定する．

#### A.2 保存する出力（再解析の最小セット）

本論文で示す結果は，以下の情報を保存して再解析できる形で管理した．

- **実行条件の記録**: `run_card.md`（実行コマンド，環境，主要パラメータ，生成物ハッシュ）．
- **採用値の記録**: `run_config.json`（$\rho$，$\langle Q_{\rm pr}\rangle$ テーブル，物理トグル，$s_{\rm blow}$ など，実行時に採用した値と出典）．
- **時系列**: `series/run.parquet`（主要スカラー量の時系列）．
- **PSD 履歴**: `series/psd_hist.parquet`（$N_k(t)$ と $\Sigma_{\rm surf}(t)$ の履歴）．
- **要約**: `summary.json`（2 年累積量などの集約）．
- **検証ログ**: `checks/mass_budget.csv`（式\ref{eq:mass_budget_definition} に基づく質量検査）．

\begin{table}[t]
  \centering
  \caption{主要出力量と本文の参照先}
  \label{tab:appendix_outputs_map}
  \begin{tabular}{p{0.24\textwidth} p{0.36\textwidth} p{0.30\textwidth}}
    \hline
    量 & 本文での定義 & 保存先 \\
	    \hline
	    $s_{\rm blow}$ & 式\ref{eq:s_blow_definition} & \texttt{series/run.parquet} \\
	    $s_{\min,\mathrm{eff}}$ & 式\ref{eq:smin_eff_definition} & \texttt{series/run.parquet} \\
	    $\dot{\Sigma}_{\rm out}$ & 式\ref{eq:surface_outflux} & \texttt{series/run.parquet} \\
	    $\dot{M}_{\rm out}$ & 式\ref{eq:mdot_out_definition} & \texttt{series/run.parquet} \\
	    $M_{\rm loss}$ & 式\ref{eq:mass_loss_update} & \texttt{summary.json} \\
	    $\epsilon_{\rm mass}$ & 式\ref{eq:mass_budget_definition} & \texttt{checks/mass\_budget.csv} \\
	    $N_k(t)$ & 式\ref{eq:sigma_surf_definition} & \texttt{series/psd\_hist.parquet} \\
	    \hline
  \end{tabular}
\end{table}

#### A.3 感度掃引で用いる代表パラメータ（例）

\begin{table}[t]
  \centering
  \caption{感度掃引で用いる代表パラメータ（例）}
  \label{tab:methods_sweep_defaults}
  \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
    \hline
    変数 & 代表値 & 意味 \\
    \hline
    $T_M$ & 4000, 3000 & 火星温度 [K] \\
    $\epsilon_{\rm mix}$ & 1.0, 0.5 & 混合係数（供給の有効度） \\
    $\tau_0$ & 1.0, 0.5 & 初期光学的厚さ \\
    $i_0$ & 0.05, 0.10 & 初期傾斜角 \\
    \hline
  \end{tabular}
\end{table}

#### A.4 検証結果の提示（代表ケース）

本論文では，表\ref{tab:validation_criteria}の合格基準に基づく検証を全ケースで実施し，合格した結果のみを採用する．代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列例を図\ref{fig:validation_mass_budget_example}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder_validation_mass_budget.pdf}
  \caption{代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列（例）}
  \label{fig:validation_mass_budget_example}
\end{figure}

<!-- TEX_EXCLUDE_START -->
以下は運用スクリプトや OS 依存の実行方法，リポジトリ内部の詳細（環境変数・hook・ファイル一覧）であり，論文PDFでは除外する．

代表的な実行コマンドとシナリオは analysis/run-recipes.md に集約する．運用スイープは `scripts/runsets/windows/run_sweep.cmd` を正とし，既定の `CONFIG_PATH`/`OVERRIDES_PATH` と引数の扱いは同スクリプトに従う．  
- **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEFAULT_PATHS`\newline `::REF:CLI_ARGS`

```cmd
rem Windows: sweep
scripts\runsets\windows\run_sweep.cmd ^
  --config scripts\runsets\common\base.yml ^
  --overrides scripts\runsets\windows\overrides.txt ^
  --out-root out
```

- `--no-preflight` は拒否される．既定では `SKIP_PREFLIGHT=1` でスキップされるため，事前チェックを走らせる場合は `SKIP_PREFLIGHT=0` を指定する．\newline `--preflight-only` で事前チェックのみ実行．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PREFLIGHT_ARGS`\newline `::REF:PREFLIGHT`
- `--no-plot` と `--no-eval` は hook を抑制し，`HOOKS_ENABLE` のフィルタに反映される．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CLI_ARGS` / `::REF:HOOKS`
- 依存関係は `requirements.txt` から自動導入され，\newline `SKIP_PIP=1` または `REQUIREMENTS_INSTALLED=1` で無効化できる．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEPENDENCIES`
- `OUT_ROOT` は内部/外部の自動選択が働き，\newline `io.archive.dir` が未設定/無効なら `OUT_ROOT\\archive` を付加した overrides を生成する．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:OUT_ROOT`\newline `::REF:ARCHIVE_CHECKS`
- `io.archive.*` の要件を満たさない場合は実行中断．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:ARCHIVE_CHECKS`
- 実行本体は `run_temp_supply_sweep.cmd` を子として起動する．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CHILD_RUN`
- スイープ並列は既定で有効 (`SWEEP_PARALLEL=1`) で，\newline ネスト回避のため `MARSDISK_CELL_PARALLEL=0` によりセル並列は無効化される．\newline サイズプローブで `PARALLEL_JOBS` が調整される場合がある．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PARALLEL`

#### run_sweep の物性値（既定）

`run_sweep.cmd` の既定設定（`scripts/runsets/common/base.yml` と `scripts/runsets/windows/overrides.txt` のマージ）で採用する物性値を表\ref{tab:run_sweep_material_properties}にまとめる．密度・放射圧効率・昇華係数はフォルステライト値を採用し，$Q_D^*$ は peridot projectile 実験の $Q^*$ を参照して BA99 係数をスケーリングした proxy を用いる（1.1節参照）．\newline
なお，`qstar.coeff_table` が与えられている場合，実行時には `qstar.coeff_scale` を追加で乗算せず，表の値をそのまま用いる（`coeff_scale` は table 生成時に用いた倍率として保存する）．

\begin{table}[t]
  \centering
  \caption{run\_sweep 既定で用いる物性値（フォルステライト基準）}
  \label{tab:run_sweep_material_properties}
  \begin{tabular}{p{0.18\textwidth} p{0.38\textwidth} p{0.22\textwidth} p{0.16\textwidth}}
    \hline
    記号 & 意味 & 値 & 出典 \\
    \hline
    $\rho$ &
    粒子密度 [kg\,m$^{-3}$] &
    3270 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $\langle Q_{\rm pr}\rangle$ &
    Planck平均放射圧効率（テーブル） &
    \texttt{data/qpr\_planck\_forsterite\_mie.csv} &
    \cite{BohrenHuffman1983_Wiley,Zeidler2015_ApJ798_125} \\
    $\alpha$ &
    HKL 蒸発係数 &
    0.1 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $\mu$ &
    分子量 [kg\,mol$^{-1}$] &
    0.140694 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $A_{\rm solid}$ &
    固相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm solid}-B_{\rm solid}/T$ &
    13.809441833 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $B_{\rm solid}$ &
    同上（$T$ は K） &
    28362.904024 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $T_{\rm solid}^{\rm valid}$ &
    固相フィットの適用温度範囲 [K] &
    1673--2133 &
    TODO(REF:van\_lieshout\_2014\_forsterite\_material\_params\_v1) \\
    $A_{\rm liq}$ &
    液相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm liq}-B_{\rm liq}/T$ &
    11.08 &
    \cite{FegleySchaefer2012_arXiv} \\
    $B_{\rm liq}$ &
    同上（$T$ は K） &
    22409.0 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm liq}^{\rm valid}$ &
    液相フィットの適用温度範囲 [K] &
    2163--3690 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm switch}$ &
    固相$\to$液相フィット切替温度 [K] &
    2163 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm condense}$, $T_{\rm vaporize}$ &
    相判定のヒステリシス閾値 [K]（運用値） &
    2162, 2163 &
    本研究（スキーマ要件）, 基準: \cite{FegleySchaefer2012_arXiv} \\
    $f_{Q^*}$ &
    $Q_D^*$ 係数スケール（peridot proxy） &
    5.574 &
    \cite{Avdellidou2016_MNRAS464_734,BenzAsphaug1999_Icarus142_5} \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \caption{run\_sweep 既定の $Q_D^*$ 係数テーブル（\texttt{qstar.coeff\_table}）}
  \label{tab:run_sweep_qdstar_coeff_table}
  \begin{tabular}{p{0.14\textwidth} p{0.20\textwidth} p{0.14\textwidth} p{0.20\textwidth} p{0.14\textwidth}}
    \hline
    $v_{\rm ref}$ [km/s] & $Q_s$ & $a_s$ & $B$ & $b_g$ \\
    \hline
    1 & 1.9509e8 & 0.38 & 0.8187652527440811 & 1.36 \\
    2 & 1.9509e8 & 0.38 & 1.28478039442684 & 1.36 \\
    3 & 1.9509e8 & 0.38 & 1.6722 & 1.36 \\
    4 & 2.92635e8 & 0.38 & 2.2296 & 1.36 \\
    5 & 3.9018e8 & 0.38 & 2.787 & 1.36 \\
    6 & 3.9018e8 & 0.38 & 3.137652034251613 & 1.36 \\
    7 & 3.9018e8 & 0.38 & 3.4683282387928047 & 1.36 \\
    \hline
  \end{tabular}
\end{table}

表\ref{tab:run_sweep_qdstar_coeff_table} の係数は BA99 の基準テーブル [@BenzAsphaug1999_Icarus142_5] を基準に，$f_{Q^*}=5.574$（表\ref{tab:run_sweep_material_properties}）で $Q_s,B$ のみをスケーリングして作成している（peridot proxy: [@Avdellidou2016_MNRAS464_734]）．

#### run_sweep.cmd の主要環境変数

既定値は `run_sweep.cmd` のデフォルト設定に従う．主要環境変数は次の表に示す．  
- **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:SWEEP_DEFAULTS`

\begin{table}[t]
  \centering
  \caption{run\_sweep.cmd の主要環境変数}
  \label{tab:run_sweep_env}
  \begin{tabular}{p{0.28\textwidth} p{0.42\textwidth} p{0.18\textwidth}}
    \hline
    変数 & 意味 & 既定値 \\
    \hline
    \texttt{SWEEP\_TAG} & 出力タグ & \texttt{temp\_supply}\newline \texttt{\_sweep}\newline \texttt{\_1d} \\
    \texttt{GEOMETRY\_MODE} & 形状モード & \texttt{1D} \\
    \texttt{GEOMETRY\_NR} & 半径セル数 & 32 \\
    \texttt{SHIELDING\_MODE} & 遮蔽モード & \texttt{off} \\
    \texttt{SUPPLY\_MU}\newline \texttt{\_REFERENCE\_TAU} & 供給基準$\tau$ & 1.0 \\
    \texttt{SUPPLY\_FEEDBACK\_ENABLED} & $\tau$フィードバック & 0 \\
    \texttt{SUPPLY\_TRANSPORT\_MODE} & 供給トランスポート & \texttt{direct} \\
    \texttt{SUPPLY\_TRANSPORT}\newline \texttt{\_TMIX\_ORBITS} & ミキシング時間 [orbits] & \texttt{off} \\
    \texttt{COOL\_TO\_K} & 温度停止閾値 [K] & 1000 \\
    \texttt{PARALLEL\_MODE} & 並列モード\newline （\texttt{SWEEP\_PARALLEL=1} ではセル並列は無効化） & \texttt{cell} \\
    \texttt{SWEEP\_PARALLEL} & スイープ並列 & 1 \\
    \texttt{PARALLEL\_JOBS} & sweep job 数 & 6 \\
    \hline
  \end{tabular}
\end{table}

- 固定地平で動かす場合は `COOL_TO_K=none` と `T_END_YEARS` を指定する．\newline
  **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:TEMPERATURE_STOP`

#### run_sweep のスイープ定義（run_temp_supply_sweep.cmd 経由）

`run_sweep.cmd` は `run_temp_supply_sweep.cmd` を呼び出し，**ベース設定 + 追加 overrides + ケース overrides** の 3 層をマージして各ケースを実行する．優先順位は「base defaults < overrides file < per-case overrides」で，各ケースの設定は一時ファイルに出力して `marsdisk.run` に渡される．

- **ベース設定**: `scripts/runsets/common/base.yml` を基準とし，\newline Windows 既定の `scripts/runsets/windows/overrides.txt` を追加する．
- **ケース生成**: `T_LIST`, `EPS_LIST`, `TAU_LIST`, `I0_LIST` の直積でスイープを作る．\newline `--study` を指定した場合は，`read_study_overrides.py` でリストや環境変数を上書きできる．
- **既定のスイープ値**（run_sweep 既定値）:

  \begin{table}[t]
    \centering
    \caption{run\_sweep 既定のスイープパラメータ}
    \label{tab:run_sweep_defaults}
    \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
      \hline
      変数 & 既定値 & 意味 \\
      \hline
      \texttt{T\_LIST} & 4000, 3000 & 火星温度 $T_M$ [K] \\
      \texttt{EPS\_LIST} & 1.0, 0.5 & 混合係数 $\epsilon_{\rm mix}$ \\
      \texttt{TAU\_LIST} & 1.0, 0.5 & 初期光学的厚さ $\tau_0$ \\
      \texttt{I0\_LIST} & 0.05, 0.10 & 初期傾斜角 $i_0$ \\
      \hline
    \end{tabular}
  \end{table}

- **ケースごとの overrides**:
  - `io.outdir`: 出力先（後述のケースディレクトリ）
  - `dynamics.rng_seed`: 乱数シード
  - `radiation.TM_K`: 火星温度（`T_LIST`）
  - `supply.mixing.epsilon_mix`: 混合係数（`EPS_LIST`）
  - `optical_depth.tau0_target`: 初期光学的厚さ（`TAU_LIST`）
  - `dynamics.i0`: 初期傾斜角（`I0_LIST`）
  - `radiation.mars_temperature_driver.table`\newline `.path`: `COOL_MODE!=hyodo` のとき `data/mars_temperature_T{T}p0K.csv` を使用
  - `numerics.t_end_*` と `scope.analysis_years`:\newline `END_MODE` に応じて温度停止または固定年数に切り替え

- **出力ディレクトリ構造**（run_sweep 既定）:\newline
  `out/<SWEEP_TAG>/<RUN_TS>__<GIT_SHA>__seed<BATCH_SEED>/<TITLE>/`\newline
  ここで `TITLE` は `T{T}_eps{EPS}_tau{TAU}_i0{I0}` の形式（小数点は `p` 置換）．


---
<!-- TEX_EXCLUDE_END -->
