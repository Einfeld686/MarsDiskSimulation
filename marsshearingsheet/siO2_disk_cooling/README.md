# SiO₂ Disk Cooling シミュレーション

このフォルダでは、火星表面が黒体放射で冷却すると仮定した場合の SiO₂ 粒子の距離×時間マップを生成します。

## 物理モデル
- 冷却方程式: $\frac{dT}{dt}=-(\sigma/(D\rho c_p))T^4$
- 解析解: $T_{\mathrm{Mars}}(t)=(T_0^{-3}+3\sigma t/(D\rho c_p))^{-1/3}$
- 粒子温度: $T_p(r,t)=T_{\mathrm{Mars}}(t)\sqrt{R_{\mathrm{Mars}}/(2r)}$
- 閾値: $T_{\mathrm{glass}}=1475~\mathrm{K}$, $T_{\mathrm{liquidus}}=1986~\mathrm{K}$

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

## 実行方法
```
python siO2_disk_cooling/siO2_cooling_map.py
```

## 出力物
- PNG: 各初期温度ごとの到達時刻マップ (glass/liquidus)
- CSV: `r_over_Rmars`, `t_to_Tglass_yr`, `t_to_Tliquidus_yr`

## 注意事項
- 光学的に薄い円盤を仮定し、太陽や粒子間の相互放射は無視しています。
- 粒子半径は固定で熱容量の効果を無視し、準静的平衡温度を用いています。
- 閾値は純粋な SiO₂ に対する代表値であり、混合物や圧力依存性は考慮していません。
