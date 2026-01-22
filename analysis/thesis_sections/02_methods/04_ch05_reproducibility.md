## 5. 再現性（出力・検証）

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, marsdisk/io/checkpoint.py, marsdisk/io/archive.py, marsdisk/archive.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: 衝突カスケード検証と出力診断の基準
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: t_collスケール検証
- @ThebaultAugereau2007_AA472_169 -> paper/references/ThebaultAugereau2007_AA472_169.pdf | 用途: wavy PSD の検証（wavy有効時）
<!-- TEX_EXCLUDE_END -->

---
本章の目的は，計算結果を再解析・再現実行できるようにするため，保存すべき出力の階層（実行条件／時系列／PSD 状態／検証ログ）を定義し，併せて数値解の健全性を確認する検証基準と判定手順をまとめることである．ここでは，まず出力仕様（5.1.1）を定め，次に保存ログにもとづく検証（5.1.2）を述べる．

### 5.1 出力と検証

本節の目的は，出力仕様と検証基準を定義し，計算結果の再現性と採用可否の判断手順を明確化することである．ここでは，まず出力・I/O（5.1.1）を定め，次に検証手順（5.1.2）を述べる．

#### 5.1.1 出力・I/O・再現性

再解析と再現実行を可能にするため，1 回の実行ごとに，設定ファイル，外部テーブル，採用パラメータ，乱数シード，およびコードのバージョン情報を実行条件として保存する．これらは時不変の前提情報であり，時系列出力とは別に一度だけ記録する．

時間発展では，第4章で定義した外側の結合ステップを $t^n$（$t^{n+1}=t^n+\Delta t$）とし，Smoluchowski/表層 ODE の内部積分は $dt_{\rm eff}\le \Delta t$ の内部ステップに分割して行う（第4章）．本論文で解析に用いる時系列の基準は外側ステップ $t^n$ であり，主要診断量（例：$s_{\rm blow}(t)$，$\Sigma_{\rm surf}(t)$，$\dot{M}_{\rm out}(t)$，$M_{\rm loss}(t)$）と質量収支ログは各 $t^n$ ごとに保存する．PSD 履歴 $N_k(t^n)$ は外側ステップの一定の整数間隔で保存し（既定は毎ステップ），その保存間隔も実行条件として保存する．

再構成に必須な状態変数は，各粒径ビン（および 1D の場合は各半径セル）の数面密度 $N_k(t^n)$（あるいは $N_{i,k}(t^n)$）と，対応するサイズグリッド $s_k$ である（2.1.1節）．表層流出の面密度フラックス $\dot{\Sigma}_{\rm out}$ は式\ref{eq:surface_outflux}，円盤全体の質量流出率 $\dot{M}_{\rm out}$ は式\ref{eq:mdot_out_definition}で定義する（0D の面積近似は式\ref{eq:annulus_area_definition}）．また，各ステップで質量検査（式\ref{eq:mass_budget_definition}）を評価し，相対質量誤差 $\epsilon_{\rm mass}(t)$ を検証ログとして保存する．保存ファイルでは扱いやすさのため，質量と質量流出率を $M_{\rm Mars}$ で規格化した値も併記する（記号表：付録E）．出力形式・保存先・主要項目の一覧は付録Aにまとめる．

累積損失 $M_{\rm loss}$ は放射圧ブローアウトによる流出と追加シンクによる損失の和として定義し，外側の結合ステップ幅 $\Delta t$ ごとに逐次積算する．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

ここで $\dot{M}_{\rm sinks}$ は昇華など追加シンクによる質量損失率である．
式\ref{eq:mass_loss_update}では $\dot{M}^n$ を区間 $[t^n,t^{n+1}]$ における代表値として評価し，区分一定の近似で積算する．

大規模計算ではメモリ使用量を抑えるため，時系列および PSD 履歴を逐次書き出す．ただし逐次／一括のいずれの方式でも，保存する物理量の定義と検証ログ（質量収支など）が一致するよう，出力インタフェースを分離して実装する．

以上により，任意の時刻における PSD と主要診断量を後段解析で再構成できる．次節では，保存した検証ログに基づき，計算結果の採用可否を判定する検証手順を示す．

<!-- TEX_EXCLUDE_START -->
実装では I/O ストリーミングを既定で ON とし（`memory_limit_gb=10`, `step_flush_interval=10000`, `merge_at_end=true`），大規模スイープで逐次フラッシュによりメモリを抑える．運用の既定スイープでは，各実行を `BATCH_ROOT`（`OUT_ROOT` があればそれを使用）配下の `SWEEP_TAG/<RUN_TS>__<GIT_SHA>__seed<BATCH_SEED>/<case_title>/` に保存する．
<!-- TEX_EXCLUDE_END -->

---
#### 5.1.2 検証手順

##### 5.1.2.1 検証項目・合格基準・結果

本研究では，保存則（質量保存），スケール検証（衝突寿命），既知現象の定性的再現（wavy PSD），数値解法の安定性と収束（IMEX）の4観点から，表\ref{tab:validation_criteria}の基準で検証した．本論文で提示する結果は，これらの基準を満たすことを確認した計算に限定する．

衝突寿命スケーリングの比較に用いる代表衝突時間 $t_{\rm coll}$ は，Smol 経路では $t_{\rm coll}\equiv\min_k t_{\rm coll,k}$（式\ref{eq:t_coll_definition}）と定める．表層 ODE 経路では $t_{\rm coll}\equiv t_{\rm coll}^{\rm est}$ とする．

\begin{table}[t]
  \centering
  \caption{検証項目と合格基準}
  \label{tab:validation_criteria}
  \begin{tabular}{p{0.27\textwidth} p{0.69\textwidth}}
    \hline
    検証項目 & 合格基準（許容誤差） \\
    \hline
    質量保存 &
	    相対質量誤差 $|\epsilon_{\rm mass}(t)|$（式\ref{eq:mass_budget_definition}）の最大値が $0.5\%$ 以下 \\
    衝突寿命スケーリング &
    推定衝突時間 $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\perp})$ に対し，モデル内の代表衝突時間 $t_{\rm coll}$ の比が $0.1$–$10$ の範囲に入る（\cite{StrubbeChiang2006_ApJ648_652}） \\
    “wavy” PSD &
    ブローアウト即時除去を含めた場合に，$s_{\rm blow}$ 近傍で $x_k\equiv\log N_k$ の二階差分 $\Delta^2 x_k=x_{k+1}-2x_k+x_{k-1}$ の符号が交互に反転する（隣接ビン比のジグザグ）ことを確認する（実装健全性の定性チェック；\cite{ThebaultAugereau2007_AA472_169}） \\
    IMEX の安定性と収束 &
    IMEX-BDF(1)（衝突ロス陰・破片生成と供給注入および一次シンク陽）が数面密度 $N_k$ の非負性を保ち，$\Delta t\le0.1\min_k t_{\rm coll,k}$ の条件で主要診断量（$\Sigma_{\rm surf}(t)$，$\dot{M}_{\rm out}(t)$，$M_{\rm loss}(t)$）が $1\%$ 以内で収束する（\cite{Krivov2006_AA455_509}） \\
    \hline
\end{tabular}
\end{table}

IMEX の収束判定では，同一条件で外側ステップ幅を $\Delta t$ と $\Delta t/2$ にした2つの計算を行う．粗い刻みの時刻列 $\{t^n\}$ に対し，細かい刻みの結果を線形補間して $\tilde{q}^{(\Delta t/2)}(t^n)$ とし，主要時系列 $q\in\{\Sigma_{\rm surf},\dot{M}_{\rm out}\}$ について最大相対差
\[
\delta_q\equiv\frac{\max_n\left|q^{(\Delta t)}(t^n)-\tilde{q}^{(\Delta t/2)}(t^n)\right|}{\max_n \tilde{q}^{(\Delta t/2)}(t^n)}
\]
を定義する．さらに終端累積損失について
\[
\delta_{M}\equiv\frac{\left|M_{\rm loss}^{(\Delta t)}(t_{\rm end})-M_{\rm loss}^{(\Delta t/2)}(t_{\rm end})\right|}{M_{\rm loss}^{(\Delta t/2)}(t_{\rm end})}
\]
を定義する．ただし分母が0の場合は分子が0であることを要求する．本研究では，$\delta_q<0.01$ かつ $\delta_{M}<0.01$ を満たすとき「収束」と判定する．

PSD グリッド解像度についても同様に，$n_{\rm bins}$ を変更した2つの計算（例：$n_{\rm bins}$ と $2n_{\rm bins}$）を行い，同じ判定規則（$\delta_q$ と $\delta_M$）で主要診断量の収束を確認する．

“wavy” PSD の確認は，保存した $N_k(t^n)$ から $s_{\rm blow}$ 近傍のビン（例：$s_{\rm blow}\le s_k\le 30\,s_{\rm blow}$）を取り，$x_k\equiv\log N_k$ の二階差分 $\Delta^2 x_k=x_{k+1}-2x_k+x_{k-1}$ が符号反転を繰り返すことを指標として行う（$N_k\le0$ のビンは除外する）．

これらの基準は，設定変更後の回帰検証にも用いる．検証結果の提示形式として，代表計算における質量検査 $\epsilon_{\rm mass}(t)$ の時系列を付録Aの図\ref{fig:validation_mass_budget_example}に示す．

<!-- TEX_EXCLUDE_START -->
##### 5.1.2.1a リポジトリ運用（自動テスト）

```bash
pytest tests/ -q
```
<!-- TEX_EXCLUDE_END -->

<!-- TEX_EXCLUDE_START -->
##### 5.1.2.2 実行後の数値チェック（推奨）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内であること．
- `series/run.parquet` の `dt_over_t_blow` が 1 未満に収まっているかを確認する．\newline 超過時は `fast_blowout_flag_*` と併せて評価する．
- 衝突が有効な実行では `smol_dt_eff < dt` が成立し，`t_coll_kernel_min` と一貫しているかを確認する．
<!-- TEX_EXCLUDE_END -->

<!-- TEX_EXCLUDE_START -->
##### 5.1.2.3 ドキュメント整合性

```bash
make analysis-sync      # DocSync
make analysis-doc-tests # アンカー健全性・参照率検査
python -m tools.evaluation_system --outdir <run_dir>  # Doc 更新後に直近の out/* を指定
```

- **詳細**: analysis/overview.md §16 "DocSync/検証フローの固定"
<!-- TEX_EXCLUDE_END -->

以上により，本章では再現実行に必要な保存情報と，質量保存・スケール検証等の合格基準を整理した．次の結果章では，これらの基準を満たす計算結果のみを提示する．


---
<!-- TEX_EXCLUDE_START -->
### 5.2 先行研究リンク

- 温度ドライバ: [Hyodo et al. (2018)](../paper/pdf_extractor/outputs/Hyodo2018_ApJ860_150/result.md)
- gas-poor/衝突起源円盤の文脈:\newline
  [Hyodo et al. (2017a)](../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)\newline
  [Canup & Salmon (2018)](../paper/pdf_extractor/outputs/CanupSalmon2018_SciAdv4_eaar6887/result.md)\newline
  [Olofsson et al. (2022)](../paper/pdf_extractor/outputs/Olofsson2022_MNRAS513_713/result.md)
- 放射圧・ブローアウト:\newline
  [Burns et al. (1979)](../paper/pdf_extractor/outputs/Burns1979_Icarus40_1/result.md), [Strubbe & Chiang (2006)](../paper/pdf_extractor/outputs/StrubbeChiang2006_ApJ648_652/result.md)\newline
  [Takeuchi & Lin (2002)](../paper/pdf_extractor/outputs/TakeuchiLin2002_ApJ581_1344/result.md), [Takeuchi & Lin (2003)](../paper/pdf_extractor/outputs/TakeuchiLin2003_ApJ593_524/result.md)\newline
  [Shadmehri (2008)](../paper/pdf_extractor/outputs/Shadmehri2008_ApSS314_217/result.md)
- PSD/衝突カスケード:\newline
  [Dohnanyi (1969)](../paper/pdf_extractor/outputs/Dohnanyi1969_JGR74_2531/result.md)\newline
  [Krivov et al. (2006)](../paper/pdf_extractor/outputs/Krivov2006_AA455_509/result.md)\newline
  [Thébault & Augereau (2007)](../paper/pdf_extractor/outputs/ThebaultAugereau2007_AA472_169/result.md)
- 供給・ソース/損失バランス: [Wyatt, Clarke & Booth (2011)](../paper/pdf_extractor/outputs/WyattClarkeBooth2011_CeMDA111_1/result.md)
- 初期 PSD:\newline
  [Hyodo et al. (2017a)](../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)\newline
  [Jutzi et al. (2010)](../paper/pdf_extractor/outputs/Jutzi2010_Icarus207_54/result.md)
- 速度分散:\newline
  [Ohtsuki et al. (2002)](../paper/pdf_extractor/outputs/Ohtsuki2002_Icarus155_436/result.md)\newline
  [Lissauer & Stewart (1993)](../paper/pdf_extractor/outputs/LissauerStewart1993_PP3/result.md)\newline
  [Wetherill & Stewart (1993)](../paper/pdf_extractor/outputs/WetherillStewart1993_Icarus106_190/result.md)\newline
  [Ida & Makino (1992)](../paper/pdf_extractor/outputs/IdaMakino1992_Icarus96_107/result.md)\newline
  [Imaz Blanco et al. (2023)](../paper/pdf_extractor/outputs/ImazBlanco2023_MNRAS522_6150/result.md)
- 破砕強度・最大残存率:\newline
  [Benz & Asphaug (1999)](../paper/pdf_extractor/outputs/BenzAsphaug1999_Icarus142_5/result.md)\newline
  [Leinhardt & Stewart (2012)](../paper/pdf_extractor/outputs/LeinhardtStewart2012_ApJ745_79/result.md)\newline
  [Stewart & Leinhardt (2009)](../paper/pdf_extractor/outputs/StewartLeinhardt2009_ApJ691_L133/result.md)
- 遮蔽 (Φ):\newline
  [Joseph et al. (1976)](../paper/pdf_extractor/outputs/Joseph1976_JAS33_2452/result.md)\newline
  [Hansen & Travis (1974)](../paper/pdf_extractor/outputs/HansenTravis1974_SSR16_527/result.md)\newline
  [Cogley & Bergstrom (1979)](../paper/pdf_extractor/outputs/CogleyBergstrom1979_JQSRT21_265/result.md)
- 光学特性: [Bohren & Huffman (1983)](../paper/pdf_extractor/outputs/BohrenHuffman1983_Wiley/result.md)
- 昇華:\newline
  [Markkanen & Agarwal (2020)](../paper/pdf_extractor/outputs/Markkanen2020_AA643_A16/result.md)\newline
  [Kubaschewski (1974)](../paper/pdf_extractor/outputs/Kubaschewski1974_Book/result.md)\newline
  [Fegley & Schaefer (2012)](../paper/pdf_extractor/outputs/FegleySchaefer2012_arXiv/result.md)\newline
  [Visscher & Fegley (2013)](../paper/pdf_extractor/outputs/VisscherFegley2013_ApJL767_L12/result.md)\newline
  [Pignatale et al. (2018)](../paper/pdf_extractor/outputs/Pignatale2018_ApJ853_118/result.md)\newline
  [Ronnet et al. (2016)](../paper/pdf_extractor/outputs/Ronnet2016_ApJ828_109/result.md)\newline
  [Melosh (2007)](../paper/pdf_extractor/outputs/Melosh2007_MPS42_2079/result.md)

- 参照インデックス: [paper/abstracts/index.md](../paper/abstracts/index.md)\newline
  [analysis/references.registry.json](../analysis/references.registry.json)
<!-- TEX_EXCLUDE_END -->


---
