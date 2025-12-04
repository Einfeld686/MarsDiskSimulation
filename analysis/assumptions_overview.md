> **文書種別**: 解説（自動生成）
> AUTO-GENERATED: DO NOT EDIT BY HAND. Run `python -m analysis.tools.render_assumptions`.

## 0. この文書の目的
仮定トレースの機械可読データ（assumption_trace.*）から、タグ・設定・コードパスを人間が確認しやすい形でまとめる。
数式本文は `analysis/equations.md` が唯一のソースであり、本書では eq_id とラベルだけを参照する。UNKNOWN_REF_REQUESTS の slug は TODO(REF:slug) として維持する。

## 1. グローバルな仮定ラベル一覧
- 仮定トレースが未登録（0件）。

## 2. ブロック別の仮定メモ
### 2.1 ブローアウト関連（β, a_blow, t_blow=1/Ω）
- 概要: gas-poor 前提で Mars 放射圧のみを想定しているが、analysis でどの E.xxx を参照するか未整理。必要情報: 参照式ID、Q_pr テーブルの由来、`use_solar_rp` オフ時の扱い、`fast_blowout` 補正の条件。
- 関連するトレース: 未登録 (TODO/needs_ref)

### 2.2 遮蔽・ゲート（Φ(τ,ω0,g), τ=1 クリップ, gate_mode）
- 概要: 遮蔽係数とゲートの多段適用順が run.py 依存で、どの式を根拠にしているか不明瞭。必要情報: 適用順序の図、Φテーブルの出典、`tau_gate` や `freeze_sigma` の切替条件。
- 関連するトレース: 未登録 (TODO/needs_ref)

### 2.3 PSD と wavy 補正
- 概要: `wavy_strength` と最小粒径クリップ（`psd.floor.mode`, `s_min_effective`）がどの PSD 理論式（P1 など）に対応するか未ラベル。必要情報: 対応する E.xxx, blowout 即時消滅仮定の明文化、`apply_evolved_min_size` の効果。
- 関連するトレース: 未登録 (TODO/needs_ref)

### 2.4 衝突時間スケール（Wyatt / Ohtsuki 型）
- 概要: `surface.use_tcoll` と Smol カーネルが参照する t_coll の式が混在。必要情報: どの regime でどの式を使うかのガイド、`f_wake` や e/i ダンピングの仮定、Wyatt スケーリングの近似範囲。
- 関連するトレース: 未登録 (TODO/needs_ref)

### 2.5 昇華・ガス抗力
- 概要: `sinks.mode` や `rp_blowout.enable` がオプション化されているが、既定が gas-poor で TL2003 無効という前提が analysis に残っているか不明。必要情報: 昇華式の E.xxx 参照、`ALLOW_TL2003=false` の記述位置、gas-rich 感度試験時のトグル手順。
- 関連するトレース: 未登録 (TODO/needs_ref)

### 2.6 半径・幾何の固定
- 概要: 0D で r を固定している点、`disk.geometry` を無視するかどうかが run ごとに異なる。必要情報: 0D 固定を前提とする式の洗い出し、半径依存を後から1Dへ拡張する際の TODO(REF:slug) 登録箇所。
- 関連するトレース: 未登録 (TODO/needs_ref)

## 3. 今後埋めるべきギャップ
- 未解決のエントリはありません。
