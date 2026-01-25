## 付録 C. 関連ドキュメント

関連ドキュメントの役割を表\ref{tab:related_docs}に整理する．

\begin{table}[t]
  \centering
  \caption{関連ドキュメントと参照用途}
  \label{tab:related_docs}
  \begin{tabular}{p{0.3\textwidth} p{0.28\textwidth} p{0.36\textwidth}}
    \hline
    ドキュメント & 役割 & 参照時のユースケース \\
    \hline
    \texttt{analysis/equations.md} & 物理式の定義（E.xxx） & 式の導出・記号・単位の確認 \\
    \texttt{analysis/physics\_flow.md} & 計算フロー Mermaid 図 & モジュール間依存と実行順序の把握 \\
    \texttt{analysis/config\_guide.md} & 設定キー詳細 & YAML パラメータの意味と許容範囲 \\
    \texttt{analysis/glossary.md} & 用語・略語・単位規約 & 変数命名と単位接尾辞の確認 \\
    \texttt{analysis/overview.md} & アーキテクチャ・データフロー & モジュール責務と 3 層分離の理解 \\
    \texttt{analysis/run-recipes.md} & 実行レシピ・感度掃引 & シナリオ別の実行手順と検証方法 \\
    \hline
  \end{tabular}
\end{table}

---
