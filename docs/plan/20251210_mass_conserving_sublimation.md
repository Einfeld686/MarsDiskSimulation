# 昇華を「粒径のみ更新・質量は blowout 時のみ損失」とする実装プラン

> **ステータス**: 実装完了（2026-01-01更新）

## 実装完了状況

以下の機能が実装済み：

- ✅ `marsdisk/schema.py`: `sinks.sub_params.mass_conserving` フラグ追加
- ✅ `marsdisk/physics/sinks.py`: 昇華フラックス→質量源項の分岐（振替なし/あり）
- ✅ `marsdisk/run_zero_d.py`: `mass_conserving=true` 時の分岐ロジック実装
- ✅ 出力集計（`M_sink_dot`/`M_out_dot`）の振替ロジック実装
- ✅ 複数の設定ファイルで `mass_conserving: true` を使用（temp_supply シナリオ等）

---

目的と背景
----------
- 昇華が粒径を縮めるだけで質量を減らさないモードを追加し、s が blowout 境界未満になった分だけをブローアウト損失として計上する挙動を導入する。
- 現行は `sinks.mode: sublimation` / `enable_sublimation: true` で ds/dt<0 が質量損失に積算されるため、「昇華は微細化のみ、損失はブローアウトのみ」という理想と異なる。

対象外
------
- phase モデルや TL2003/gas-rich シナリオの変更は扱わない。
- 表層 ODE の再設計は行わず、Smol 側 ds/dt に限定した挙動を追加する。

実装方針
--------
1. スキーマ
   - `sinks.sub_params.mass_conserving: bool`（デフォルト false）。true で「質量は維持し、blowout 閾値を下回ったときだけ損失に振替える」モードにする。
2. 昇華計算（Smol側）
   - ds/dt で粒径 s を更新。更新後 s_new<a_blow なら、その粒子質量をブローアウト損失に計上し、粒子を削除。s_new>=a_blow なら質量維持のまま s を縮小。
   - mass_conserving=false のときは従来どおり ds/dt を質量損失に反映。
3. 出力・診断
   - mass_conserving=true 時は `M_sink_dot`/`M_sink_cum` を 0 に保ち、振替分は `M_out_dot` に反映。必要なら「昇華由来 blowout フラックス」の補助列を追加。
4. 後方互換
   - フラグ未指定（false）は従来挙動。既存テストに影響しないよう分岐で守る。

受入条件
--------
- `mass_budget_max_error_percent` が従来と同等（0.5% 以内）を維持。
- mass_conserving=true のとき `M_sink_cum=0` を確認し、振替分が `M_out_cum` に積算されていること。
- 振替した質量（昇華で s_new<a_blow になった分）が質量差分と一致すること。

デフォルト方針（段階導入）
------------------------
- 目標の既定挙動: ds/dt で s が a_blow 未満になった分だけ即ブローアウト損失とし、それ以外は粒径だけ縮める（質量は維持）。
- 移行段階: まず `mass_conserving` フラグを追加し、初期はデフォルト false（後方互換を確保）。十分な検証後、デフォルト true への切替を検討する。
- 一時的には temp_supply など限定シナリオで true を明示し、挙動を確認したうえで全体デフォルト化を判断する。

実装スコープ（コード箇所）
---------------------------
- `marsdisk/schema.py`: `sinks.sub_params.mass_conserving` 追加。
- `marsdisk/physics/sinks.py`: 昇華フラックス→質量源項の分岐（振替なし/あり）。
- Smol 側昇華適用部（ds/dt 更新箇所）: s_new<a_blow でブローアウト振替、s_new>=a_blow は質量維持でサイズのみ更新。
- 出力集計（`M_sink_dot`/`M_out_dot`）：振替ロジックに合わせて0または加算。

ログ/診断
---------
- mass_conserving=true のとき、振替が発火したステップ数と総振替質量をログする（補助列や summary フィールドで記録）。
- 必要に応じて「昇華由来 blowout フラックス」補助列を追加し、診断に使う。

ヒステリシス/フロア
--------------------
- s_new≈a_blow 付近の切替で跳ねを避けるため、ヒステリシス幅（例: a_blow×(1±1e-3)）または最小質量フロアを検討。

テスト計画（具体）
------------------
- mass_conserving=true ケース: 小さなテスト設定で ds/dt<0 を与え、`M_sink_cum=0` かつ振替分が `M_out_cum` に等しいことを確認。
- mass_conserving=false ケース: 従来の `M_sink_cum` と一致することを回帰テスト。
- 境界: s_new が a_blow 付近をまたぐケースで不連続が出ないか確認。

影響範囲と反映
--------------
- デフォルト false なので既存シナリオは挙動不変。temp_supply 等で true をセットする場合のみ変化。
- 採用時は関係する config（シナリオ）に `mass_conserving: true` を明示し、run_card へ記録。

ドキュメント更新
----------------
- `analysis/config_guide.md` にフラグ説明を追記。
- DocSync/coverage 系コマンド（`make analysis-sync` 等）はコード変更後に実行。
- 必要なら analysis 側の挙動説明（昇華→ブローアウト振替）を短く追記。
テスト計画
----------
- unit: mass_conserving=true で ds/dt<0 でも `M_sink_cum=0` かつ blowout に質量が移ることを確認。
- regression: mass_conserving=false で従来の `M_sink_cum` を再現。
- 境界: s_new≈a_blow でのヒステリシスまたは小フロアを確認し、不連続がないか見る。

作業手順
--------
1. `marsdisk/schema.py` にフラグ追加。
2. `marsdisk/physics/sinks.py`（昇華→質量源項）と Smol 側の適用部を分岐実装。
3. 出力ロジック（`M_sink_dot`/`M_out_dot`）の振替を実装。
4. テスト追加（回帰 + mass_conserving モード）。
5. ドキュメント最小追記（config_guide などにフラグ説明）。

リスクと緩和
------------
- 質量保存ズレ: 振替実装にバグがあると C4 が崩れるため、テストで `mass_budget` を確認。
- 不連続: s_new≈a_blow でのスイッチングによる跳ねはヒステリシス/フロアで抑制を検討。
- 既存ランへの影響: デフォルト false で回避。フラグを明示したケースのみ挙動変更。
