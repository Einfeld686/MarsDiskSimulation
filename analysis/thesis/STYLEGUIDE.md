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

## Methods 章の構成ゲート（受入条件）
修正後の Methods 章が「構成として直った」と判定する条件を、次に固定する（判定対象は論文PDFに出力される本文。`TEX_EXCLUDE` で除外される情報は判定対象外）。

- **本文完結性**: 本文だけで、モデル仮定・支配方程式・数値解法・初期条件・停止条件・出力定義・検証基準が追える（内部ドキュメント参照が不要）。
- **参照の閉包**: 本文中の参照は、図・表・式・付録のいずれかに閉じる（`analysis/*.md` など内部文書への参照が無い）。
- **運用情報の排除**: 本文に OS 依存の運用情報が存在しない（例：`run_sweep.cmd`、環境変数、DocSync/CI の実行手順、pytest 名・ログパス）。
- **付録の最小化**: 付録は「参照価値が高い一覧」に限り、本文の読み筋を阻害しない（付録B/Cは、設定→物理のクイック参照／外部入力テーブルの一覧として位置づける）。

確認（開発用）
- `python -m analysis.tools.merge_methods_sections --write`
- `python analysis/tools/check_methods_gate.py`
