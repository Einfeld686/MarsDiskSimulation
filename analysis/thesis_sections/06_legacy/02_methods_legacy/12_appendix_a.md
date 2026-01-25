## 付録 A. 運用実行（run_sweep.cmd を正とする）

代表的な実行コマンドとシナリオは analysis/run-recipes.md に集約する．運用スイープは `scripts/runsets/windows/run_sweep.cmd` を正とし，既定の `CONFIG_PATH`/`OVERRIDES_PATH` と引数の扱いは同スクリプトに従う．  
> **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEFAULT_PATHS` / `::REF:CLI_ARGS`

```cmd
rem Windows: sweep
scripts\runsets\windows\run_sweep.cmd --config scripts\runsets\common\base.yml --overrides scripts\runsets\windows\overrides.txt --out-root out
```

- `--no-preflight` は拒否される．既定では `SKIP_PREFLIGHT=1` でスキップされるため，事前チェックを走らせる場合は `SKIP_PREFLIGHT=0` を指定する．`--preflight-only` で事前チェックのみ実行．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PREFLIGHT_ARGS` / `::REF:PREFLIGHT`
- `--no-plot` / `--no-eval` は hook を抑制し，`HOOKS_ENABLE` のフィルタに反映される．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CLI_ARGS` / `::REF:HOOKS`
- 依存関係は `requirements.txt` から自動導入され，`SKIP_PIP=1` または `REQUIREMENTS_INSTALLED=1` で無効化できる．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEPENDENCIES`
- `OUT_ROOT` は内部/外部の自動選択が働き，`io.archive.dir` が未設定/無効なら `OUT_ROOT\\archive` を付加した overrides を生成する．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:OUT_ROOT` / `::REF:ARCHIVE_CHECKS`
- `io.archive.*` の要件を満たさない場合は実行中断．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:ARCHIVE_CHECKS`
- 実行本体は `run_temp_supply_sweep.cmd` を子として起動する．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CHILD_RUN`
- スイープ並列は既定で有効 (`SWEEP_PARALLEL=1`) で，ネスト回避のため `MARSDISK_CELL_PARALLEL=0` によりセル並列は無効化される．サイズプローブで `PARALLEL_JOBS` が調整される場合がある．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PARALLEL`

### run_sweep.cmd の主要環境変数

既定値は `run_sweep.cmd` のデフォルト設定に従う．主要環境変数は表\ref{tab:run_sweep_env}に示す．  
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

- 固定地平で動かす場合は `COOL_TO_K=none` と `T_END_YEARS` を指定する．  
  > **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:TEMPERATURE_STOP`

---
