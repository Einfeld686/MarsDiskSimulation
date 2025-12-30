# 列指向バッファ化 実装プラン

> **作成日**: 2025-12-30  
> **ステータス**: 提案中  
> **対象**: `marsdisk/run_one_d.py`, `marsdisk/run_zero_d.py`, `marsdisk/runtime/history.py`, `marsdisk/io/streaming.py`, `marsdisk/io/writer.py`, `marsdisk/output_schema.py`

---

## 目的

- 1D/0D の `list[dict]` 生成と `_ensure_keys` 呼び出しを削減し、I/O 系の Python オーバーヘッドを下げる
- `t_coll_kernel_min` など **ステップ定数列の一括付与**を可能にする
- Streaming ON/OFF の双方で **出力スキーマ互換**を維持する

---

## 背景

- `run_one_d` はセルごとに巨大な `record` 辞書を生成し、最後に `t_coll_kernel_min` を **Python ループで後付け**している。
- Parquet 書き出し時に `list[dict] -> DataFrame -> pyarrow` の変換が発生し、I/O の支配度が高いケースで顕著に遅い。
- 既存の最適化（cache/Numba 等）は計算コストには効くが、**記録生成/変換のコストは残っている**。

---

## 非スコープ

- 物理モデル変更・新式導入
- 出力列の互換性破壊（列名・単位の変更）
- `psd_hist` / `mass_budget_cells` の全面的な列指向化（フェーズ後半で検討）

---

## 方針（設計概要）

1) **ColumnarBuffer を追加**し、行指向（list[dict]）と列指向を切替可能にする  
2) `writer` に **列指向入力**を受け付ける API を追加し、`pyarrow.Table` 直書きを許可  
3) `run_one_d` / `run_zero_d` の記録生成を **列指向に置換**し、定数列は一括で付与  
4) **安全なフォールバック**（row モード）を残し、段階導入する

---

## 実装フェーズ

### フェーズA: ColumnarBuffer と writer の土台

- `marsdisk/runtime/history.py` に ColumnarBuffer を追加（records/diagnostics 用）
- `marsdisk/io/writer.py` に以下の新規 API を追加
  - `write_parquet_columns(columns: Mapping[str, Sequence], ...)`
  - `write_parquet_table(table: pa.Table, ...)`
- `marsdisk/io/streaming.py` が ColumnarBuffer を認識し、**行/列どちらでも flush**できるようにする
- **出力列の欠落は flush 直前に補完**（`ensure_columns` を ColumnarBuffer 側で実施）

### フェーズB: run_one_d を列指向に置換

- `records` 生成を **列配列への append** に置換
- `t_coll_kernel_min` は **ステップ末に一括埋め**（`np.full(n, value)` 相当）
- `output_schema` のキーリストを列順の基準として使用し、動的列は最小限にする
- 既存の `psd_hist_records` / `mass_budget_cells` は当面 list[dict] を維持

### フェーズC: run_zero_d への展開（任意）

- 0D の `records/diagnostics` にも ColumnarBuffer を適用
- Streaming ON/OFF と `summary.json` の互換性確認

### フェーズD: 拡張（任意）

- `psd_hist` / `mass_budget_cells` の列指向化
- 1D の `diagnostics` も列指向化

---

## 設定・トグル案

`io` に以下のいずれかを追加（互換優先）:

- `io.record_storage_mode: "row" | "columnar"`（既定 `"row"`）
- または `io.columnar_records: bool`（既定 `false`）

**安全弁**:
- `MARSDISK_DISABLE_COLUMNAR=1` で強制 row に戻す

---

## 変更予定の主なファイル

| ファイル | 変更内容 |
|---------|----------|
| `marsdisk/runtime/history.py` | ColumnarBuffer 定義・History への組込み |
| `marsdisk/io/writer.py` | Columnar 入力対応の追加 API |
| `marsdisk/io/streaming.py` | Columnar flush 対応 |
| `marsdisk/run_one_d.py` | record 生成を列指向化、定数列の一括付与 |
| `marsdisk/run_zero_d.py` | 任意で列指向化 |
| `marsdisk/output_schema.py` | 列順・必須列の整理（破壊的変更なし） |
| `marsdisk/schema.py` | 新トグルの追加 |

---

## テスト計画

- `tests/integration/test_run_one_d_output_parity.py`
- `tests/integration/test_run_one_d_streaming_schema.py`
- `tests/integration/test_mass_budget_cells.py`
- `tests/integration/test_run_zero_d_output_parity.py`（0D拡張時）
- 新規: `tests/integration/test_columnar_records.py`  
  - row/columnar で列集合と主要値が一致すること  
  - `t_coll_kernel_min` の一括付与が正しいこと

---

## 性能検証

- 既存の短縮ケースで **I/O ON/OFF** の A/B を実施
- `cProfile` / `pstats` で `_ensure_keys`, `writer.write_parquet` の比率を比較
- `scripts/tests/measure_case_output_size.py` で出力サイズ差を記録

