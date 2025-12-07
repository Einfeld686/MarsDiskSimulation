# モデリング整合性ノート

## Canup & Salmon (2018) との整合性

- Fig.1 はハイブリッド計算の区分を示し、ロッシュ限界内を**連続円盤**として粘性拡散で扱い（質量記号 ``M_{\rm in}``）、外側は離散 N 体として扱う構成を明示している。Fig.4 でも同じ ``M_{\rm in}`` が粘性拡散しつつ外側スウォームへ質量を供給する流れ図となっており、本コードの「内側円盤質量スケール」をこの枠組みに一致させる。 
- Fig.2 の系列では、小衛星が生存するには初期ディスク総質量が **\(M_{\rm disk}\lesssim3\times10^{-5} M_M\)** である必要があることが示されている。テキストでも Roche 内側を連続円盤としてまとめ、同じ質量スケール ``M_{\rm in}`` を閾値として議論している。

## 3×10^-5\,M_M は「内側円盤スケール」

- 入力パラメータ `inner_disk_mass.M_in_ratio` は ``M_{\rm in} = 3\times10^{-5} M_M`` の校正値を既定とするが、**これは Roche 内側を含む初期ディスク全体の質量スケール**である。 
- 本モデルでは ``M_{\rm in}`` を `marsdisk/physics/initfields.sigma_from_Minner()` に渡して \(\Sigma(r)\) を決定し、表層は `surf_sigma_init()` で ``\tau\lesssim1`` にクリップする。したがって「初期表層総質量 = 3×10^-5\,M_M」ではなく、表層はそのうちの照射される薄層のみを受け持つ。

## ローカル表層への写像

1. `sigma_from_Minner()` が ``\int 2\pi r\,\Sigma(r)\,dr = M_{\rm in}`` を満たすように \(\Sigma(r)\) を規格化する。
2. `surf_sigma_init()` が有効不透明度 ``\kappa_{\rm eff}`` から ``\Sigma_{\tau=1}=1/\kappa_{\rm eff}`` を求め、`policy="clip_by_tau1"` で表層を ``\tau\lesssim1`` に制限する。
3. 時間発展では `marsdisk/physics/surface.step_surface_density_S1()` が ODE を解き、`prod_subblow_area_rate` として受け取る供給は `marsdisk/physics/supply.get_prod_area_rate()` が外部パラメータ化した関数を評価して与える。
4. 放射圧係数は `marsdisk/physics/radiation.beta()` が Mie テーブルから読み出す ``\langle Q_{\rm pr}\rangle`` を用いて計算し、ブローアウトサイズと表層フラックスを一貫して決定する。

この流れにより、Canup & Salmon (2018) の連続円盤 ``M_{\rm in}`` をローカル 0D/1D 表層モデルへ写像している。

## ガス抗力スイッチを OFF にする根拠

- Takeuchi & Lin (2003)[^TL03] はロッシュ近傍の薄い表層で外向きの照射駆動フローが卓越し得ることを示し、低ガス質量では放射と衝突が主要ドライバーになる。
- Strubbe & Chiang (2006)[^SC06] もデブリ円盤の希薄ガス条件では衝突・放射圧/CPR が支配的であると結論しており、本シナリオではガス抗力を一次項として扱わない設定が妥当である。

## 実装リファレンス

- 表層 ODE: `marsdisk/physics/surface.step_surface_density_S1()` および `compute_surface_outflux()`。
- 内部→表層供給: `marsdisk/physics/supply.get_prod_area_rate()` が `prod_subblow_area_rate` を生成し、`marsdisk/run.py` 内で `surface` モジュールへ渡している。
- 放射圧: `marsdisk/physics/radiation.beta()` と `load_qpr_table()` が Mie テーブルを参照し、テーブル未設定時はフォールバックの `_approx_qpr` を経由する。
- 初期化: `marsdisk/physics/initfields.surf_sigma_init()` が ``\Sigma_{\tau=1}`` クリップを適用する。詳細な検証手順は [docs/validation-notes.pdf](validation-notes.pdf) を参照。

## 補足

- シミュレーション出力の質量収支チェックや \(\dot M_{\rm out}(t)\) の検証例は `docs/validation.md` と上記 PDF で管理する。

### 温度選択とデバッグ

- 火星面温度は `radiation.TM_K` か温度ドライバ（`mars_temperature_driver.constant/table`）のいずれかを必須入力とし、採用経路は `summary.json` の `T_M_source`（文字列）と `T_M_used[K]` に記録される。旧 `temps.T_M` は廃止されたため、掃引時は `radiation.TM_K` またはドライバ設定を直接更新する。
- `io.debug_sinks: true` を設定すると昇華シンクおよびガス抗力の寄与を `out/<case>/debug/sinks_trace.jsonl` に JSON Lines 形式で書き出し、`dominant_sink`、`total_sink_dm_dt_kg_s`、`cum_sublimation_mass_kg` などを逐次追跡できる。大規模ジョブでファイルサイズが課題になる場合は既定の `false` へ戻す。
- 典型的な失敗例として、温度ドライバを有効にしたまま `TM_K` を残すと `M_loss` や `s_blow_m` が変化しない。テーブル駆動を使う際は `TM_K` をターゲット温度に合わせるか、`prefer_driver=true` を指定して `TM_K` を無視する。
[^TL03]: Takeuchi, T., & Lin, D. N. C. (2003). *ApJ*, 593, 524. 熱的に加熱された薄層の外向き表層流が低ガス密度で支配的になることを示す。
[^SC06]: Strubbe, L. E., & Chiang, E. I. (2006). *ApJ*, 648, 652. デブリ円盤において衝突と放射圧/CPR がガス抗力より優勢となる枠組みを提示。
