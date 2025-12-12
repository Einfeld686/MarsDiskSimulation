# temp_supply_sweep.sh の状況整理と方針案

> **作成日**: 2025-12-13  
> **ステータス**: 草案（現状整理＋修正提案）

---

## 現状（スクリプト実装）
- `scripts/research/run_temp_supply_sweep.sh` は temp_supply スイープを回すバッチスクリプト。  
  - 供給: `supply.mode=const` を前提に `supply.enabled=true`, `supply.const.prod_area_rate_kg_m2_s=${SUPPLY_RATE}`, `supply.mixing.epsilon_mix=${MU}` を override。  
  - 遮蔽: `shielding.mode=${SHIELDING_MODE}`、固定 Στ=1 は `SHIELDING_SIGMA`（デフォルト 1e-2）で指定。  
  - 出力: 外付け SSD (`/Volumes/KIOXIA/marsdisk_out`) を優先、plots は overview/supply_surface を生成。  
  - 乱数: `BATCH_SEED` と各ケースの `dynamics.rng_seed` を分離。  
  - Streaming: オプションで `io.streaming.*` override をサポート。
- 近期の変更点: `supply.mixing.mu` から `supply.mixing.epsilon_mix` 明示に変更済み。供給パスは有効化され、const×epsilon_mix が run_config に記録される。

## 問題点（観測）
- **Sigma_tau1 が小さすぎると供給が headroom=0 で全カット**  
  デフォルト `SHIELDING_SIGMA=1e-2` では κ_eff~1e-3 に対し τ≈1 に到達せず、`prod_subblow_area_rate=0` になるケースが多数発生。auto/auto_max を使わない限り、意図した τ≈1 にならない。
- **初期 Σ が Στ=1 を超えていて即クリップ**  
  auto でも初期 Σ_surf が上限より大きいと headroom=0 で供給が止まる。`init_tau1.scale_to_tau1` を明示しない限り初期整合が取れない。
- **成功判定が手動依存**  
  τ≈1 と供給維持の基準がスクリプトに埋まっておらず、run 後の判定が人手依存になっている。

## 新しい方針案
- **遮蔽のデフォルトを auto に**  
  `SHIELDING_SIGMA` デフォルトを `auto` にし、必要時のみ `auto_max`（デバッグ用）や固定値を指定する。  
  本番は `fixed_tau1_sigma=auto` を基本とし、`init_tau1.scale_to_tau1=true` で初期 Σ を Στ=1 以下にクランプする。
- **初期整合を明示**  
  全ケースに `--override "init_tau1.scale_to_tau1=true"` を追加し、初期 headroom=0 を回避。  
  auto_max を使う場合は「デバッグ専用」のコメントを入れ、本番結果から除外する。
- **成功判定のフック**  
  オプションフラグ（例: `EVAL=1`）で各 run 後に `scripts/research/evaluate_tau_supply.py` を呼び、  
  `--window-fraction 0.5 --min-duration-days 0.1 --threshold-factor 0.9` で JSON を保存（`plots/` か `checks/`）。  
  成否と tau_median/longest_supply_duration をログにまとめ、成功ケースを機械的に抽出できるようにする。
- **ログ/コメントの整備**  
  スクリプト冒頭に「本番: auto+scale_to_tau1、auto_max はデバッグ専用」と明記。  
  実効供給（const×epsilon_mix）を echo する一行を入れ、run_config の `effective_prod_rate_kg_m2_s` と整合を確認しやすくする。

## TODO（実装タスク候補）
- [ ] SHIELDING_SIGMA のデフォルトを `auto` に変更し、auto_max 用の分岐コメントを追加。
- [ ] 追加 override に `init_tau1.scale_to_tau1=true` を組み込む。
- [ ] EVAL フラグと `evaluate_tau_supply.py` 呼び出しのオプションを追加し、結果 JSON を格納するパスを決める。
- [ ] ログ整備（実効供給、遮蔽モード、Sigma_tau1 モードの出力）。
- [ ] （任意）warmup 立ち上げモードを入れる場合は環境変数で切り替え、評価区間を warmup 後にシフトする。

---

## 関連ドキュメント

| ドキュメント | 役割 |
|-------------|------|
| [20251212_temp_supply_tau_unity_fix.md](file:///Users/daichi/marsshearingsheet/docs/plan/20251212_temp_supply_tau_unity_fix.md) | 本方針案の前提となる原因調査・実装済み機構の詳細 |
| [20251211_temp_supply_runflow.md](file:///Users/daichi/marsshearingsheet/docs/plan/20251211_temp_supply_runflow.md) | temp_supply 実行フロー整理 |
| [run_temp_supply_sweep.sh](file:///Users/daichi/marsshearingsheet/scripts/research/run_temp_supply_sweep.sh) | スイープ実行スクリプト |
| [evaluate_tau_supply.py](file:///Users/daichi/marsshearingsheet/scripts/research/evaluate_tau_supply.py) | 成功判定スクリプト |

---

## 実装済みの機構（参照）

以下は `20251212_temp_supply_tau_unity_fix.md` で整備済み。本スクリプト修正時に活用すること。

| 機能 | 設定パス | 説明 |
|------|----------|------|
| **供給有効化** | `supply.enabled` | 既定 `true`。sweep では明示的に `true` を指定済み |
| **epsilon_mix 明示** | `supply.mixing.epsilon_mix` | mu エイリアス依存を排除し直接指定に変更済み |
| **Στ=1 自動設定** | `shielding.fixed_tau1_sigma=auto` | 1/κ_eff(t0) を固定値として採用 |
| **Στ=1 デバッグ用** | `shielding.fixed_tau1_sigma=auto_max` | max(1/κ_eff, Σ_init)×1.05 で headroom 確保（本番禁止） |
| **初期Σスケール** | `init_tau1.scale_to_tau1=true` | 初期 Σ_surf を Στ=1 以下にクランプ |

---

## 成功判定の基準

[evaluate_tau_supply.py](file:///Users/daichi/marsshearingsheet/scripts/research/evaluate_tau_supply.py) で定義されている判定基準：

| 条件 | デフォルト値 | 説明 |
|------|-------------|------|
| **評価区間** | 後半 50%（`--window-fraction 0.5`） | ウォームアップ・初期過渡を除外 |
| **τ 条件** | 中央値 0.5–2.0 | `tau_vertical` の中央値がこの範囲内 |
| **供給維持** | ≥90%（`--threshold-factor 0.9`） | 設定供給（`const×epsilon_mix`）の 90%以上 |
| **連続期間** | 0.1 日以上（`--min-duration-days 0.1`） | 上記2条件を同時に満たす連続区間 |

**使用例**:
```bash
python scripts/research/evaluate_tau_supply.py \
  --run-dir "${RUN_DIR}" \
  --window-fraction 0.5 \
  --min-duration-days 0.1 \
  --threshold-factor 0.9
```

---

## auto / auto_max の使い分けガイド

| モード | 用途 | Στ=1 の決め方 | 本番利用 |
|--------|------|---------------|----------|
| `auto` | 本番・キャリブレーション | 1/κ_eff(t0) 固定 | ✅ 推奨 |
| `auto_max` | デバッグ・供給経路確認 | max(1/κ_eff, Σ_init)×1.05 | ❌ 禁止 |
| 固定値 | 特定条件の再現 | 指定値をそのまま使用 | ⚠️ 要検討 |

> [!WARNING]
> `auto_max` を使った run は本番の図表・結論に使用しないこと。供給経路が動くかの診断目的に限定する。

---

## 完了条件（チェックリスト）

### スクリプト修正
- [ ] `SHIELDING_SIGMA` のデフォルトを `auto` に変更
- [ ] `--override \"init_tau1.scale_to_tau1=true\"` を全ケースに追加
- [ ] `EVAL=1` フラグで `evaluate_tau_supply.py` を呼び出すオプションを追加
- [ ] 結果 JSON を `plots/` または `checks/` に格納
- [ ] ログに実効供給・遮蔽モード・Στ=1 採用値を出力

### 検証
- [ ] auto + scale_to_tau1 で headroom>0 となることを確認（prod_subblow>0）
- [ ] 成功判定（τ中央値 0.5–2、供給維持≥90%）を満たすケースが存在
- [ ] auto_max 使用時は「デバッグ専用」の警告ログが出力される

### ドキュメント
- [ ] 本ドキュメントの TODO 消化後、`analysis/run-recipes.md` に成功判定基準を追記
- [ ] 成功ケースの run_id を `analysis/run_catalog.md` に登録（RUN.* 形式）
