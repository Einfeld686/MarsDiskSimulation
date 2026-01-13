# 修士論文スタイルガイド

## 適用範囲
- 対象: `analysis/thesis/` と `analysis/thesis_sections/`。
- 目的: `paper/out/` に出力する修士論文の体裁を統一する。
- 未解決参照は AI_USAGE の方式に従い、本文には `TODO(REF:slug)` を付し、`analysis/UNKNOWN_REF_REQUESTS.jsonl` に登録する。

## 原稿の正/生成
- セクション素材は `analysis/thesis_sections/` を正とする。
- `analysis/thesis/` は結合結果のため、編集は原則 `analysis/thesis_sections/` 側で行う。

## 図（figure）
- 図を入れる箇所は `figure` 環境で出力する。
- `\includegraphics` はコメントアウトし、差し替え可能なプレースホルダとする。
- `\caption` と `\label` は必須。本文は必ず `図\ref{fig:...}` で参照する。
- 「上図」「次図」など相対参照は使わない。

```tex
\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{...}
  \label{fig:...}
\end{figure}
```

## 表（table）
- Markdown 表ではなく `table` + `tabular` を使う。
- `\caption` と `\label` は必須。本文は `表\ref{tab:...}` で参照する。
- 「上表」「次表」など相対参照は使わない。

```tex
\begin{table}[t]
  \centering
  \caption{...}
  \label{tab:...}
  \begin{tabular}{lcc}
    ...
  \end{tabular}
\end{table}
```

## 数式（equation）
- 重要な式は `equation` 環境で番号付けし、必ず `\label` を付ける。
- 本文では `式\ref{eq:...}` で参照する。
- 式の直後に、記号の意味と適用範囲（仮定）を文章で説明する。

```tex
\begin{equation}
  \label{eq:...}
  ...
\end{equation}
```

## 参照の原則
- 図・表・式は `図\ref` / `表\ref` / `式\ref` に統一する。
- 相対参照（上図/下表/次式など）は使わない。
