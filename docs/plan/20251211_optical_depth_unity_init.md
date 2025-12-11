# 表面初期τ≈1 に合わせるための調整メモ

## 背景・目的
- temp_supply スイープは初期質量 1e-5 M_Mars を均一配置しており、初期光学的厚さ τ は数十以上になる。遮蔽クリップで Σ_τ=1=1e-2 kg/m² に落としているが、初期状態から τ≈1 としたい要望が出たため、調整方針を整理する。
- 詳細な式・面積換算は analysis/ に集約し、ここでは段取りのみ記す。

## 目標
- 0D 初期条件で Σ_surf を「τ≈1 となる値」（Σ_τ=1=1/κ_surf 基準）に近づける。
- temp_supply_* 全YAMLや base.yml に適用し、run_temp_supply_sweep.sh が即座に反映できる形を想定。

## 調整案（主ルートと補助）
- 主ルート: `surface.sigma_surf_init_override` を Σ_τ=1 に合わせて設定し、それに整合する `initial.mass_total` を面積から逆算して後付けする（0Dでは Σ_surf を基準に据える）。計算式・換算は analysis/ 側に置く。
- 補助案: 旧 mass_total を優先しつつ Σ_surf をクリップ値に合わせたい場合、`initial.mass_total` をスケールダウンする形で τ≈1 に寄せる。
- 遮蔽クリップの整合: `fixed_tau1_sigma` は現状 1e-2 に固定。初期 Σ_surf を同値に揃えると初手での大幅削減を回避できる。
- 後方互換スイッチ: デフォルトは旧挙動を維持し、新モードは明示トグル（例: `init_tau1.enabled: false` を既定）でオンにする。破壊的変更を避けるため、旧設定をそのまま選べる形を必ず残す。

## 簡易チェックリスト
- [ ] κ_surf（現PSD, s_min=1e-7〜3 m, n_bins=40）の初期値を取得し、Σ_τ=1=1/κ_surf を算出。
- [ ] その Σ_τ=1 を `surface.sigma_surf_init_override` に設定し、`initial.mass_total` も同値に合わせたときの τ を確認。
- [ ] temp_supply_* YAML と base.yml に値を反映し、試験実行で初期ステップ τ≈1 を確認。
- [ ] DocSyncAgent／analysis-doc-tests／evaluation_system を必要に応じて実行（config変更のみならスキップ可とする）。

## リスク・注意
- Σ_τ=1 が極端に小さい場合、初期質量が減りすぎて出力スケールが変わるため、スイープ結果の比較軸が変わる点に注意。旧 `initial.mass_total` はログに残す、出力IDに「tau1init」等のフラグを付けて区別するなどの運用を検討。
- κ_surf は材料や PSD α に依存するため、変更が入った場合は Σ_τ=1 再計算が必要（再計算トリガー: PSD α 変更、材料プロパティ変更〔ρ, Q_pr テーブル等〕）。

## 次のアクション（提案）
- κ_surf 初期値をコード計算で取得する簡易スクリプトを用意し、Σ_τ=1 をログに出す。
- temp_supply_* と base.yml へ `sigma_surf_init_override` の反映／mass_total スケールダウンを段階的に実施する（主ルートを優先）。
- 後方互換スイッチを設計: `init_tau1.enabled`（既定 false）を追加し、オンにしたときだけ Σ_τ=1 初期化を実行する。
- 再計算トリガーを明示: PSD α の変更、材料プロパティ（ρ, Q_pr テーブル等）変更時は必ず Σ_τ=1 を再評価する。
