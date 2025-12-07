# SiO₂ Disk Cooling シミュレーション

このフォルダでは、火星表面が黒体放射で冷却すると仮定した場合の SiO₂ 粒子の距離×時間マップを生成します。放射冷却は Hyodo et al. (2018) のスラブ解 (E.042)、粒子温度は同論文の灰色体平衡 (E.043) に基づきます。[@Hyodo2018_ApJ860_150]

## 物理モデル
- 冷却方程式: $\frac{dT}{dt}=-(\sigma/(D\rho c_p))T^4$（Hyodo18 式(2)–(4)）
- 解析解: $T_{\mathrm{Mars}}(t)=(T_0^{-3}+3\sigma t/(D\rho c_p))^{-1/3}$（(E.042)）
- 粒子温度: $T_p(r,t)=T_{\mathrm{Mars}}(t)\,\bar{Q}_{\mathrm{abs}}^{1/4}\sqrt{R_{\mathrm{Mars}}/(2r)}$（(E.043)）
- $⟨Q_{\mathrm{abs}}⟩$: 既定は上限近似として $q_{\mathrm{abs,mean}}=1.0$ を置き、将来は Bohren & Huffman の Mie 理論と Blanco/Draine/Hocuk のプランク平均表へ差し替える。[@BohrenHuffman1983_Wiley; @Blanco1976_ApSS41_447; @Draine2003_SaasFee32; @Hocuk2017_AA604_A58]
- 閾値: $T_{\mathrm{glass}}=1475~\mathrm{K}$, $T_{\mathrm{liquidus}}=1986~\mathrm{K}$（Bruning の DTA 測定と Ojovan/Melosh の低圧 SiO₂ 相図に基づく）[@Bruning2003_JNCS330_13; @Ojovan2021_Materials14_5354; @Melosh2007_MPS42_2079]

## パラメータ
| 記号 | 値 | 単位 |
| --- | --- | --- |
| $R_{\mathrm{Mars}}$ | $3.3895\times10^6$ | m |
| $\sigma$ | $5.670374419\times10^{-8}$ | W m$^{-2}$ K$^{-4}$ |
| $\rho$ | 3000 | kg m$^{-3}$ |
| $c_p$ | 1000 | J kg$^{-1}$ K$^{-1}$ |
| $D$ | $1.0\times10^5$ | m |
| 時間グリッド | 0–2 年 (6 時間刻み) | - |
| 距離グリッド | $r/R_{\mathrm{Mars}}=1.0–2.4$ (300 分割) | - |
> Hyodo17/18 の衝突後温度場を前提に、溶融シリケイトの代表値（$\rho\sim2.6–3.3\times10^3$ kg m$^{-3}$, $c_p\sim0.7–1.5\times10^3$ J kg$^{-1}$ K$^{-1}$, $k\sim0.6$ W m$^{-1}$ K$^{-1}$）を Lesher & Spera / Robertson から採用して $D=10^5$ m を設定しています。[@Hyodo2018_ApJ860_150; @Hyodo2017a_ApJ845_125; @LesherSpera2015_EncyclopediaVolcanoes; @Robertson1988_USGS_OFR88_441]

## 実行方法
基本
```
python -m siO2_disk_cooling.siO2_cooling_map
```
- `--plot-mode {arrival,phase}`: 既定は到達時間マップ、`phase` で固体分率マップ（青=固体優勢、赤=蒸気優勢）。
- `--cell-width-Rmars <Δr/R_Mars>`: marsdisk のセル幅に揃える場合に指定。未指定なら `--marsdisk-config` (既定 `configs/base.yml` が存在すればそれ) から `disk.geometry.r_in_RM`/`r_out_RM`/`n_cells` を読み取り自動推定する。
- `--marsdisk-config <path>`: 上記のセル幅自動推定に使う marsdisk 設定パス。指定しない場合は隣接リポジトリの `configs/base.yml` を試し、見つからなければ均等分割（`--n_r`）にフォールバック。

## 出力物
- PNG: 各初期温度ごとの到達時刻マップ (glass/liquidus) または固体分率マップ
- CSV: `r_over_Rmars`, `t_to_Tglass_yr`, `t_to_Tliquidus_yr`

## 注意事項
- 光学的に薄い円盤を仮定し、太陽や粒子間の相互放射は無視しています。
- 粒子半径は固定で熱容量の効果を無視し、準静的平衡温度を用いています。
- 閾値は純粋な SiO₂ に対する代表値であり、混合物や圧力依存性は考慮していません。
