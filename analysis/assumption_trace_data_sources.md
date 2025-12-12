# assumption_trace_data_sources（stub）

目的: 仮定スキャナが参照すべき入力ソースを一覧化する。詳細設計や探索キーワードは `out/plan/assumption_trace_data_sources.md` にある作業メモを参照し、本ファイルはリポジトリ内の正式な参照先を短くまとめる。

## 主な入力ソース
- 数式: `analysis/equations.md`（DocSync 済みの (E.xxx) 見出し）
- 出典カタログ: `analysis/references.registry.json`、`analysis/UNKNOWN_REF_REQUESTS.jsonl`
- コードインデックス: `analysis/source_map.json`、`analysis/inventory.json`
- 設定スキーマ: `marsdisk/schema.py`（Pydantic Config）、`marsdisk/config_utils.py`（label 付与）
- 設定例: `configs/` 配下の YAML（値・ブールトグル確認用）
- 既存 registry: `analysis/assumption_registry.jsonl`（正規化ターゲット）
- Φ/Q_pr テーブル: `tables/` 配下（two-stream/delta-Eddington など近似名を必ず記載）

補足: gap やデータソースの詳細メモは `out/plan/assumption_trace_gap_list.md` / `out/plan/assumption_trace_data_sources.md` を参照（手書きの作業ログ扱い）。

## 追加で固定すべきメタデータ
- Q_pr テーブル: 屈折率ソース（ファイル名・参照元）、粒子形状（球/混合）、ミー計算の実装（例: miepython バージョン）、波長グリッドと積分範囲、生成スクリプト（ops）を run_card/provenance に残す。
- Φ(τ,ω0,g) テーブル: two-stream / delta-Eddington などの近似名、`w0/g` のパラメタレンジ、LOS/鉛直どちらの τ を想定したかを明記する。
- 昇華・ガス抗力: 昇華 ds/dt の根拠（ヘルツ＝クヌーセン式、例: Markkanen 2020）、ガス抗力の根拠（Pollack–Burns–Tauber 1979 など）を区別し、TL2003 有効化条件が実装選択であることを記録する。

## プロビナンス標準との対応
assumption_id と provenance.type（literature / impl_choice / safety_cap / data_source）を分ける運用は、W3C PROV-DM（実体・活動・責任主体）、FAIR 原則（データ/アルゴリズムの再利用性）、研究ソフトウェアメタデータ（CodeMeta）、研究データ梱包（RO-Crate）の指針と整合する。現状は registry + run_card で代替し、将来的なメタデータ梱包を見据える。
