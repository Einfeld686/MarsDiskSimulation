# 目的
`marsdisk/physics/qstar.py` の Q_D* 係数テーブルを **1–7 km/s** まで拡張し、速度クランプ警告を実態に合わせる。文献根拠の明確化、テーブル形式、実装手順、テスト計画まで含めて整理する。

# 背景 / 現状整理
- 既定テーブルは `_DEFAULT_COEFFS={3.0, 5.0}` km/s の2点のみで、範囲外は端値クランプ＋警告（`marsdisk/physics/qstar.py`）。
- `qstar.v_ref_kms` は **`override_coeffs=true` か `coeff_table` 指定時のみ**テーブルに反映される。既定では無視される（`marsdisk/run_zero_d.py`）。
- 一部 config に 1.5–7.0 km/s が書かれているが、`override_coeffs` が無いため **実際には反映されていない**。
- Q_pr テーブル（`marsdisk/io/data/qpr_planck_*.csv`）と Q_D* テーブルは別物であり、混同しやすい。

# 目標 (Definition of Done)
1. **1–7 km/s をカバーする Q_D* 係数テーブル**が repo に存在し、出典を追跡できる。
2. `qstar` がそのテーブルを**標準で参照**し、`v<1` / `v>7` のみ警告・クランプになる。
3. `run_config.qstar` に採用テーブルの由来（source/path/coeff_units）が記録される。
4. 既存テスト＋必要な追加テストが通る。

# 調査・収集タスク
- **テーブル実在性の確認**: 外部アーカイブ内に 1–7 km/s の係数表があるなら、ファイル名と列定義を確定する。
- **文献根拠の整理**: Benz & Asphaug (1999), Leinhardt & Stewart (2012) に加え、1–2 km/s / 7 km/s の係数（または Q_D* 曲線）を示す文献を特定する。
- **材料差の扱い**: basalt 以外（ice/porous basalt）が必要なら別テーブルとして切り分ける。

# データ仕様 (案)
テーブルを CSV 化する場合の最小仕様:
- `v_ref_kms, Qs, a_s, B, b_g, coeff_units`
- 例: `1.0, 2.5e7, 0.38, 0.22, 1.36, ba99_cgs`
- 速度キーは km/s、係数は BA99 cgs または SI のいずれかで統一する。

YAML 直書きの場合（既存実装で対応可能）:
```yaml
qstar:
  override_coeffs: true
  coeff_units: ba99_cgs
  coeff_table:
    1.0: [Qs, a_s, B, b_g]
    2.0: [Qs, a_s, B, b_g]
    3.0: [Qs, a_s, B, b_g]
    5.0: [Qs, a_s, B, b_g]
    7.0: [Qs, a_s, B, b_g]
```

# 実装方針（選択肢）
1. **既定テーブル差し替え**: `qstar.py` の `_DEFAULT_COEFFS` を 1–7 km/s へ拡張（最も単純）。
2. **テーブル外部化**: `coeff_table_path` を追加し、CSV を読み込む（実装コストは増えるが運用しやすい）。
3. **config 注入のみ**: base.yml などで `override_coeffs=true` と `coeff_table` を明示（コード改変は最小）。

# 検証・テスト
- `tests/integration/test_qstar_units.py`: 速度クランプ件数と補間の単調性を確認。
- `tests/integration/test_qstar_fragments.py`: Q_D* の速度補間が破片モデルの境界条件を壊さないこと。
- 0D/1D の短時間ランで `run_config.qstar.velocity_clamp_counts` がゼロになることを確認。

# 依頼時の質問テンプレ（更新版）
1. 1–7 km/s の basalt 衝突で、`Q_D*` か (Qs, a_s, B, b_g) を直接示す表/図がある文献を教えてください（図番号と単位系も）。
2. 1–2 km/s および 7 km/s の係数を得る際、LS12 の補間で十分か、別の速度依存補正が必要かを示す文献はありますか。
3. 係数が直接得られない場合、Q_D* 曲線から (Qs, a_s, B, b_g) を復元する妥当な手順（フィット条件）を教えてください。
4. 1–7 km/s を既定レンジにした場合の注意点（クランプ運用、警告閾値、材料差の扱い）はありますか。

# 期待アウトプット
- 文献名 + 速度レンジ + 表/図番号 + 単位系
- 1,2,3,5,7 km/s の係数または Q_D* の数表（最低限 3,5 を含む）
- 採用テーブルの形式（YAML 直書き or CSV）と推奨実装パス
