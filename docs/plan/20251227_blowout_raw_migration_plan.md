# ブローアウト半径の移行型Bプラン（raw/effective 分離）

## 目的
- 物理的なブローアウト半径（raw）と、床クリップ後の有効値（effective）を明確に分離し、診断や解析での混同を防ぐ。

## 方針（移行型B）
- `s_blow_m` を **物理値（raw）** に変更する。
- 旧挙動（床クリップ後の値）は `s_blow_m_effective` として新規に保存する。
- `s_min_components` には `blowout_raw` と `blowout_effective` を追加する。
- 既存の依存箇所は順次 `s_blow_m_effective` を参照するように更新する。

## 実装手順（チェックリスト）
- [x] 影響箇所を洗い出す（`rg "s_blow_m" marsdisk scripts tests analysis`）
- [x] 出力キーの命名を確定する（`s_blow_m`, `s_blow_m_effective`, `s_min_components["blowout_raw"]`, `s_min_components["blowout_effective"]`）
- [x] `_resolve_blowout` を raw/effective の両方を返す形に変更する
- [x] `run_zero_d` の変数命名を整理し、床・PSD には effective を使用する
- [x] 出力へ raw/effective の両方を保存する
  - [x] 時系列 `out/<run_id>/series/run.parquet`
  - [x] 集計 `out/<run_id>/summary.json`
  - [x] `out/<run_id>/run_config.json` の provenance 追加（必要なら）
- [x] 旧モデル互換値の利用時は非推奨警告をデフォルトで出す（サイレント化手段を定義）
- [x] `s_min_components` へ raw/effective を追加し、旧 `blowout` の意味を明示する
- [x] テスト更新
  - [x] `tests/unit/test_high_priority_math_risks.py` の blowout テストを raw 前提に更新
  - [x] raw と effective の関係を確認する追加テストを作成
- [x] 解析・スクリプトの参照更新
  - [x] `scripts/` や `analysis/` の `s_blow_m` 依存箇所を `s_blow_m_effective` へ移行
  - [x] `scripts/` の参照更新（必須）
- [x] 仕様文書の更新
  - [x] `analysis/equations.md` の記録列説明を raw/effective に合わせる
  - [x] 必要に応じて `analysis/overview.md` へ補足
- [x] DocSyncAgent と doc テスト、evaluation を順に実行（分析文書を変更した場合）

## 受け入れ基準
- [x] `s_blow_m` が物理式の raw に一致し、`s_blow_m_effective` が床クリップ後の値になる
- [x] `s_min_components` に raw/effective が出力され、意味が明確に区別できる
- [x] 既存の集計や図が、必要に応じて effective 側へ切り替わっている
- [x] 既存テストに加え、raw/effective の両方を検証するテストが通る

## 注意点
- 旧 `s_blow_m` の意味が変わるため、下流の解析や図の参照更新が必須。
- 互換性のため、`s_blow_m_effective` を新設して移行期間を確保する。過渡期は両方を保持する。
- 旧モデル互換値の利用は警告で通知し、必要に応じて抑制手段を用意する。
