### 5.3 初期化・終了条件・チェックポイント

#### 5.3.1 初期 $\tau=1$ スケーリング

`init_tau1.scale_to_tau1=true` で，初期 PSD を $\tau=1$ になるようスケーリングする\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}．関連設定は表\ref{tab:init_tau1_settings}に示す．

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

- `optical_depth` が有効な場合は `tau0_target` から `Sigma_surf0` を定義し，`init_tau1.scale_to_tau1` とは併用できない（旧方式を使う場合は `optical_depth: null` を明示）．
- `scale_to_tau1=false` の場合は `initial.mass_total` がそのまま適用される．$\tau_{\rm stop}$ 超過で停止判定する．

初期 PSD は `initial.*` の設定と PSD グリッド定義に従って生成される．初期状態は `run_config.json` に記録され，再現実行時の参照点となる．

#### 5.3.2 温度停止 (Temperature Stop)

`numerics.t_end_until_temperature_K` を設定すると，火星表面温度が指定値以下になった時点でシミュレーションを終了する（温度ドライバが解決できる場合のみ有効）\citep{Hyodo2018_ApJ860_150}．

```yaml
numerics:
  t_end_years: null
  t_end_until_temperature_K: 2000
  t_end_temperature_margin_years: 0
  t_end_temperature_search_years: 10  # optional search cap
```

- **優先順位**: `t_end_until_temperature_K` → `t_end_orbits` → `t_end_years`．未指定の場合は `scope.analysis_years`（既定 2 年）にフォールバックする．
- `t_end_temperature_margin_years` で冷却達成後のマージン時間を追加可能．
- 運用スイープ（run_sweep.cmd）では `COOL_TO_K=1000` が既定のため，温度停止が実質デフォルトとなる点に注意する．

#### 5.3.3 チェックポイント (Segmented Run)

長時間実行をセグメント化し，中間状態を保存して再開可能にする．

```yaml
numerics:
  checkpoint:
    enabled: true
    interval_years: 0.083   # ~30 days
    keep_last_n: 3
    format: pickle          # pickle | hdf5
```

- クラッシュ時に最新チェックポイントから `--resume` で再開．
- `keep_last_n` でディスク使用量を制限．

---
