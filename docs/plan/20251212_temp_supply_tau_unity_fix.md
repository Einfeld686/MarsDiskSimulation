# temp_supply τ≈1 失敗の整理と復旧プラン

> **作成日**: 2025-12-12  
> **ステータス**: たたき台（原因切り分けと復旧手順の草案）

---

## 現状の問題（観測値）

> [!CAUTION]
> 以下の観測は、供給が実質的に機能していない可能性を示唆しています。

### 1. 実行結果の異常

**対象**: `/Volumes/KIOXIA/marsdisk_out/temp_supply_sweep/20251212-105035__58574b78a__seed396228398/T6000_mu1p0_phi20/series/run.parquet`

| カラム名 | 観測値 | 期待値（正常時） |
|----------|--------|------------------|
| `prod_subblow_area_rate` | 全区間 **0** | `1e-10 × mu = 1e-10 kg m⁻² s⁻¹` |
| `Sigma_surf` | `Sigma_tau1_active = 1.0e-2` に張り付き（ヒット率 100%） | τ=1 到達後にクリップされる |
| `tau_los_mars` | 中央値 **~9.6e-7** | ≈1.0 を目標としていたはず |
| `t_coll` | 初期 0.46 日 → **~1.7×10⁷ 年** に伸長 | 衝突が継続するなら ~年オーダー |

**問題点**: 衝突寄与が実質消滅しており、供給も記録されていないため円盤が枯渇状態。

### 2. run_config.json の欠落

- `run_config.json` に **`supply` ブロックが存在しない**。
- `process_overview` にも supply/production を示すフィールドがない。
- 実行スクリプト（[run_temp_supply_sweep.sh](file:///Users/daichi/marsshearingsheet/scripts/research/run_temp_supply_sweep.sh)）では以下を渡している:
  ```bash
  --override "supply.mode=${SUPPLY_MODE}"           # default: const
  --override "supply.const.prod_area_rate_kg_m2_s=${SUPPLY_RATE}"  # default: 1.0e-10
  --override "supply.mixing.mu=${MU}"               # 0.1, 0.5, 1.0
  ```

### 3. τ クリップの矛盾

- 設定: `shielding.mode=fixed_tau1`, `Sigma_tau1=1.0e-2 kg m⁻²`
- 実効 κ: `1.9e-5 ~ 1.2e-3 m² kg⁻¹`（`run.parquet` の `kappa_eff` カラム）
- **τ=1 に必要な Σ**: `Σ_τ=1 = 1/κ ≈ 5×10² ~ 5×10⁴ kg m⁻²`
- **現状の上限**: `Sigma_tau1 = 1.0e-2` では `τ = κ × Σ = 1.9e-7 ~ 1.2e-5` 程度にしかならず、τ≈1 には到達不可能。

---

## 原因仮説

### 仮説1: 供給経路の消失（主疑い）

`physics_mode=default` で supply ブロックのロード/シリアライズが抜け落ち、`supply_spec` が `None`（または `mode=const, prod_area_rate=0`）として `get_prod_area_rate` に渡されている可能性。**亜種として、enabled/epsilon_mix が 0 固定のままになるケースも濃厚**。

**根拠**:
- `run_config.json` に supply ブロックが記録されていない
- `prod_subblow_area_rate` が全ステップで 0
- supply.enabled は sweep で明示しておらず、YAML 側が false なら 0 固定になり得る（推測A）
- `SupplyMixing._alias_mu` は「epsilon_mix が無ければ mu を入れる」実装のため、YAML に epsilon_mix=0 があると mu の override が効かず raw×0=0 になる（推測B）

**コード調査ポイント**:
1. [`marsdisk/run.py:1525`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L1525): `supply_spec = cfg.supply` の取得
2. [`marsdisk/run.py:2037`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L2037): `supply.get_prod_area_rate(time_sub, r, supply_spec)` の呼び出し
3. [`marsdisk/run.py:2991-3007`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L2991-L3007): `process_overview` の構築（supply 有効/無効が含まれていない）
4. [`marsdisk/run.py:3281-3415`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L3281-L3415): `run_config` の構築（supply 情報が記録されていない可能性）

### 仮説2: τ 上限の設定ミス

`shielding.fixed_tau1_sigma=1e-2` が τ≈1 目標と矛盾。供給が復活しても上限クリップで τ が 1 に近づかない。

**計算式**（参考）:
```
τ_los = κ_eff × Σ_surf × los_factor
Σ_τ=1 = 1 / κ_eff
```

現状の `κ_eff ≈ 1e-3` であれば、`Σ_τ=1 ≈ 1000 kg m⁻²` が必要。

---

## 解決案（アクション案）

### アクション1: 供給パスの復旧

**目的**: 供給が正しく `run.py` 内で処理され、`run_config.json` に記録されることを確認・修正する。

1. **Config ロードの確認**
   - [`marsdisk/schema.py:155-198`](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py#L155-L198) の `Supply` クラス定義を確認
    - CLI オーバーライド（`--override supply.mode=const` 等）が正しくパースされているか `_apply_overrides_dict`（[run.py:241-276](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L241-L276)）を確認
   - YAML 側に `supply.enabled: false` や `supply.mixing.epsilon_mix: 0` が残っていないか確認し、override では `epsilon_mix` を直接指定する

2. **`process_overview` への追加**
    - [`run.py:2991-3007`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L2991-L3007) に supply 有効/無効を明示するフィールド（`supply_enabled`, `supply_mode` など）を追加

3. **`run_config` への記録**
    - [`run.py:3281`](file:///Users/daichi/marsshearingsheet/marsdisk/run_zero_d.py#L3281) 以降の `run_config` 構築に supply 設定を追加

4. **警告ログの追加**
   - `supply_spec` が None または const で rate=0 の場合に warning を出す
   - `prod_subblow_area_rate` が初期数ステップで 0 なら warning を投げるチェックを追加

5. **Regression テストの追加**
   - 小さな const 供給（`const=1e-10`, `epsilon_mix=1.0`）で 1 ステップ目の `prod_subblow_area_rate ≈ 1e-10` になる簡易テスト（pytest）を追加

### アクション2: τ クリップの再設定

**目的**: 目標 τ≈1 に対して適切な `Sigma_tau1` を使用する。

1. **κ の取得と計算**
   - 初期 κ（`kappa_eff` カラム）を `run.parquet` から取得
   - `Sigma_tau1 ≈ 1/κ` を計算し、適切な値を設定

2. **設定の見直し**
   ```yaml
   shielding:
     mode: fixed_tau1
     fixed_tau1_sigma: 1000.0  # 例: κ=1e-3 なら 1/κ=1000
   ```

3. **代替案の検討**
   - τ 固定ではなく Φ テーブルで τ をスケールさせる選択肢も検討（`phi_const_0p20`→`0p37`/`0p60` の影響を評価）

### アクション3: 再現性チェック

1. **1ケース再実行**
   ```bash
   cd /Users/daichi/marsshearingsheet
   source .venv/bin/activate
    python -m marsdisk.run \
      --config configs/sweep_temp_supply/temp_supply_T4000_eps1.yml \
      --override "radiation.TM_K=6000" \
     --override "supply.enabled=true" \
      --override "supply.mode=const" \
       --override "supply.const.prod_area_rate_kg_m2_s=1.0e-10" \
     --override "supply.mixing.epsilon_mix=1.0" \
      --override "io.outdir=out/debug_supply_test"
    ```

2. **検証ポイント**
   - `prod_subblow_area_rate > 0` が記録されるか
   - `tau_los_mars` がクリップ上限に達するまで増えるか
   - `run_config.json` に supply ブロックが出力されるか

3. **summary.json への記録追加**（なければ実装）
   - supply 有効フラグ
   - `Sigma_tau1` 採用値

---

## チェックリスト（完了条件）

- [x] supply ブロックが `run_config.json` に出力され、`process_overview` で有効/無効が確認できる
- [x] const 供給ケースで `prod_subblow_area_rate > 0` が記録され、初期ステップで期待値（`prod_area_rate_kg_m2_s × epsilon_mix`）に近い
- [ ] τ クリップを見直した設定で `tau_los_mars ≈ 1` に到達するサンプル run を取得
- [x] Regression テスト（小型ケース）が追加され、pytest でカバーされる
- [ ] 影響するドキュメント（`analysis/` に式・設定を追記、必要なら `run-recipes.md` へのメモ）を更新する段取りを決める

---

## 実装済みと現状確認

### 実装済み
- Supply に `enabled` を追加しデフォルト true（`schema.py`）。`supply.enabled=false` なら供給を 0 にする。
- `physics/supply.get_prod_area_rate` で enabled をチェック。
- `run.py` で supply 有効/モード/epsilon_mix/const rate を取得し、`process_overview` と `run_config.json` に記録。
- `collisions_smol` で Στ=1 headroom=0 の場合にデバッグログを出すよう追加（クリップ原因の特定用）。
- `scripts/research/run_temp_supply_sweep.sh` を `supply.enabled=true` と `supply.mixing.epsilon_mix=${MU}` 明示に変更（mu エイリアス依存を排除）。
- `shielding.fixed_tau1_sigma`: `"auto"`（1/κ_eff(t0)固定）に加え、デバッグ用途の `"auto_max"` を追加（max(1/κ_eff, Σ_init)×(1+5%)）。モードと採用 Στ=1 を run_config に記録。
- `init_tau1.scale_to_tau1`: 初期 Σ を Στ=1 以下にクランプするオプションを追加し、初期クリップ発生と適用値を run_config に記録。

### 短時間テスト結果
- τ上限を緩めた 1e-6 年 run（`shielding.fixed_tau1_sigma=1000`）では `prod_subblow_area_rate=1e-10` が全ステップで正に立つことを確認（出力 `/tmp/codex_supply_check/series/run.parquet`）。
- デフォルトの `Sigma_tau1=1e-2` では headroom=0 となり供給が 0 にクリップされることを確認。τ≈1 を狙うには上限を κ に合わせて桁上げする必要がある。
- `fixed_tau1_sigma=auto` では κ_eff(t0)≈2.16e-3 → Στ=1≈462 が自動設定されるが、初期 Σ_surf（外部初期条件）がそれを上回る場合、即時クリップされ `prod_subblow_area_rate` は 0 のままになる（auto でも初期質量の調整が必要）。
- 回帰テスト `tests/test_supply_positive.py` を追加し、十分大きな Στ=1（1000）環境で供給>0 を保証することを確認済み。

### なお残る課題
- 回帰テストは最小の供給>0 ケースのみ追加済み（tests/test_supply_positive.py）。auto/auto_max や初期クリップ警告まで含む拡張テストは未実装。
- 適正な `Sigma_tau1`（例: κ_eff~1e-3 なら ≳1e3 kg/m²）をどう選ぶか要決定。固定値か κ から 1/κ を毎回計算するモードかを検討する。
- run_config への供給記録は入ったが、解析側での確認手順（analysis/run-recipes 等）への追記は未実施。

### 論点と方針（追記）
- **Sigma_tau1 の決め方**: まずは「run 開始時に κ_eff(t0) を測り、`Sigma_tau1=1/κ_eff(t0)` を固定値として使う」案を優先。後段で必要なら κ を平滑化しつつ追従するモードを検討する（τ≈1 を維持する目的と数値安定性のバランス）。
- **回帰テスト方針**: τクリップの影響を避けるため、`fixed_tau1_sigma` を十分大きくした短時間 run で `prod_subblow_area_rate>0` を確認する最小ケースを pytest に追加する。
- **τ≈1 成功判定の指標**: 代表半径 r=cfg.disk.geometry 中央での `tau_los_mars` の時間中央値が 0.5–2 の範囲に収まる、など統計量と閾値を一文で定義しておく。
- **外部供給の位置づけ**: 現段階の供給は「未解像の輸送を置き換える仮定」であり、パラメータ依存（供給を弱める/ゼロにする）の感度確認をセットで示す。
- **外部供給の流れ（実装側の確定事項）**: supply.enabled（既定 true）→ mode で const/powerlaw/table/piecewise を選択 → `_rate_basic` で raw 供給を計算 → `epsilon_mix` を乗算し 0 未満をクリップ → `prod_subblow_area_rate` として run.parquet に記録。supply 有効/モード/epsilon_mix/const rate は run_config/process_overview に残す。

## 追加施策プラン（本事象対策）
- **初期ΣとΣτ=1の整合**  
  - init_tau1 / surface.sigma_surf_init_override を `Sigma_tau1` 以下に収まるようスケールダウンするモードを追加（例: `init_tau1.scale_to_tau1=true`）。  
  - 実装: run_zero_d の初期化で `sigma_override_applied = min(sigma_override_applied, Sigma_tau1_auto_or_fixed)` を適用する分岐を追加。  
  - 完了条件: 初期ステップで headroom>0 となり、`prod_subblow_area_rate` がクリップされない。

- **Στ=1 上限の設定オプション拡充（デバッグ用途を明示）**  
  - auto は基本モード（1/κ_eff(t0) 固定）。auto_max（例: `fixed_tau1_sigma=auto_max`）はデバッグ目的で「max(1/κ_eff(t0), Sigma_surf_init)×(1+δ)`（δ>0 で headroom 確保）に設定し、初期過大クリップを避けて供給・衝突パスが動くか確認する。  
  - κ の平滑化（初期数ステップ平均）に基づく auto 派生値のオプションを検討。  
  - 完了条件: auto/auto_max で headroom>0 を作り、短時間テストで供給が正になることを確認。

- **初期質量の段階投入（テストモード）**  
  - 初期質量を 0 に設定し、外部供給で徐々に立ち上げるテスト用モードを用意（例: `initial.mass_total=0`, `supply.warmup_steps` を導入）。  
  - 目的: Στ=1 を超えずに供給挙動を観測する。

- **警告と可視化の強化**  
  - 初期 `Sigma_surf > Sigma_tau1` で警告ログを出す。  
  - summary/run_config に「初期クリップ発生」フラグと使用した Στ=1 を記録。

### 注意書き（auto_max の扱い）
- `fixed_tau1_sigma=auto_max` は初期クリップ回避の**デバッグ用**。物理的に τ≈1 を目指す場合は、`init_tau1.scale_to_tau1=true` で初期 Σ を Στ=1 以下にスケールするか、適切な Στ=1 を固定/auto で与える方針を優先すること。本番の結果・図表・結論への使用は避け、供給経路が動くかの診断にとどめる。
- もし auto_max を本番レベルで使いたい場合は、名称と定義を「τ=1 の不確かさを許す上限」（例: `tau_cap_factor/κ_eff(t0)`）に再設計し、run-recipes と成果物で τ>1 を許容することを明示する。

### 考えておきたいこと
- auto_max をあくまでデバッグ用途にとどめるか、物理解釈を持たせるかの線引き。後者の場合は τ≈1 を外れても良い“緩和モード”として再定義する必要がある。
- 成功判定（τ≈1, prod_subblow>90%）をどの時間・半径で測るかを run-recipes に具体化する（解析の自動化を視野に）。 

## 本番運用の方針（提案）
- 本番では `fixed_tau1_sigma=auto` と `init_tau1.scale_to_tau1=true` を基準とし、供給は open-loop（事前に決めた関数）で制御を最小化する。
- ベースライン: supply.enabled=false（供給なし）で blowout 支配を確認。
- キャリブレーション: auto + 初期整合の下で供給率・epsilon_mix をスイープし、成功判定を満たす最小供給を選ぶ。
- 本番: キャリブレーションで決めた供給を固定し、複数 seed で長時間走らせる。temp 供給を入れる場合は供給オン区間と評価区間を明示する。
- 避けるべき条件: auto_max を本番に混在させる、τ≈1 達成を目視のみで判断する、auto なのに初期 Σ が上限超過のまま放置する。

## run-recipes で具体化すべき成功判定（提案）
- 評価区間: ウォームアップ・初期過渡を除外し、例として後半 50% を評価対象にする（warmup_steps を使うならその区間も除外）。
- τ条件: 評価区間での `tau_los_mars` の中央値が 0.5–2。
- 供給維持条件: 評価区間で `prod_subblow_area_rate` が設定供給（`prod_area_rate_kg_m2_s × epsilon_mix`）の 90%以上。
- 連続期間: 上記2条件を同時に満たす連続区間が存在すること（run.parquet の出力間隔に合わせて「連続 N 点」または物理時間で「連続 Δt」を定義）。

- **成功判定の定義とドキュメント反映**  
  - 成功基準: 代表半径での `tau_los_mars` 時間中央値が 0.5–2、かつ `prod_subblow_area_rate` が設定値に対して >90% を維持する期間が連続して存在。  
  - analysis/run-recipes へ上記基準を追記し、チェック手順を明文化。

- **回帰テストの追加**  
  - `tests/test_supply_positive.py` を拡張し、(i) auto_max で供給>0、(ii) 初期クリップ警告が立たない、を検査するケースを追加。  
  - 併せて `shielding.fixed_tau1_sigma=auto` で初期 Σ_surf に対して headroom>0 となることを確認するフィクスチャを導入。

## 実装手順サマリ（優先順）
1. 初期Σを Στ=1 以下に収める機構（init_tau1 スケール、初期クリップ警告、run_config/summary フラグ）を導入し、auto で headroom>0 を確保。  
2. τ≈1 成功判定の指標を analysis/run-recipes に追記し、確認手順を固定。  
3. auto_max（デバッグ目的）と warmup モードを追加し、必要時のみ利用できるようスクリプト切替を用意。  
4. テスト: test_supply_positive を拡張し、auto_max と初期警告なし条件を検証するケースを追加。  
5. スイープスクリプト: auto/auto_max 切替と初期質量スケールのオプションを追加。  
6. 短時間 run で再確認し、prod_subblow>0 と tau_los_mars 指標が基準内に入ることを確認。

---

## 参照

### コードファイル
- [`marsdisk/schema.py`](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py): Supply クラス定義（L155-198）
- [`marsdisk/run.py`](file:///Users/daichi/marsshearingsheet/marsdisk/run.py): オーケストレータ（supply_spec L1525, process_overview L2991-3007）
- [`marsdisk/physics/supply.py`](file:///Users/daichi/marsshearingsheet/marsdisk/physics/supply.py): `get_prod_area_rate` 関数（L93-98）
- [`scripts/research/run_temp_supply_sweep.sh`](file:///Users/daichi/marsshearingsheet/scripts/research/run_temp_supply_sweep.sh): パラメータスイープ実行スクリプト

### 関連ドキュメント
- [`docs/plan/20251211_optical_depth_unity_init.md`](file:///Users/daichi/marsshearingsheet/docs/plan/20251211_optical_depth_unity_init.md): 既存の τ≈1 初期化メモ
- [`docs/plan/20251211_temp_supply_runflow.md`](file:///Users/daichi/marsshearingsheet/docs/plan/20251211_temp_supply_runflow.md): 直近の temp_supply 実行フロー整理
 - コメント反映の補足: supply.enabled/epsilon_mix の明示と Στ=1 の桁合わせを優先すること

### Supply スキーマ構造（参考）

```python
# marsdisk/schema.py より抜粋

class SupplyConst(BaseModel):
    prod_area_rate_kg_m2_s: float = 0.0

class SupplyMixing(BaseModel):
    epsilon_mix: float = 0.05
    mu: Optional[float] = None  # alias for epsilon_mix

class Supply(BaseModel):
    # μ は epsilon_mix の別名で、epsilon_mix が未設定のときのみ上書きされる点に注意
    enabled: bool = True
    mode: Literal["const", "powerlaw", "table", "piecewise"] = "const"
    const: SupplyConst = SupplyConst()
    powerlaw: SupplyPowerLaw = SupplyPowerLaw()
    table: SupplyTable = SupplyTable()
    mixing: SupplyMixing = SupplyMixing()
    piecewise: list[SupplyPiece] = []
```

### get_prod_area_rate 関数（参考）

```python
# marsdisk/physics/supply.py:93-98
def get_prod_area_rate(t: float, r: float, spec: Supply) -> float:
    """Return the mixed surface production rate in kg m⁻² s⁻¹."""
    raw = _rate_basic(t, r, spec)
    rate = raw * spec.mixing.epsilon_mix
    return max(rate, 0.0)
```

実効レート = `prod_area_rate_kg_m2_s × epsilon_mix（または mu）`

---

## 補足: 期待される動作フロー

1. `run_temp_supply_sweep.sh` が CLI オーバーライドで supply パラメータを渡す
2. `marsdisk/run.py` が `cfg.supply` から `Supply` オブジェクトを取得
3. 各タイムステップで `supply.get_prod_area_rate(t, r, supply_spec)` が呼ばれ、`prod_rate` が計算される
4. `prod_rate` が `prod_subblow_area_rate` として診断出力（`run.parquet`）に記録される
5. `run_config.json` に supply 設定が書き出される（現状これが欠落している疑い）
