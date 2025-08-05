# Step1 Python 検証スクリプト

火星周辺の微粒子ディスクに対し、放射圧ブローアウト質量分率
\(F_{\rm blow}\)、放射圧による質量除去比 \(\eta_{\rm loss}\)、
有効光学厚さ低下率 \(R_{\tau}\) の 2 次元マップを生成する
`extended_static_map.py` を提供します。

## 理論式

* Dohnanyi (1969): サイズ分布 \(n(a) \propto a^{-q}\)
* Burns et al. (1979): 放射圧係数 β と P–R ドラッグ
* Wyatt (2005): 衝突時スケール \(t_{\rm col} \simeq (\Omega \tau)^{-1}\)
* Strubbe & Chiang (2006): \(\tau_{\rm eff}/\tau_0\)

## 実行例

```bash
# デフォルト設定でバッチ処理
python extended_static_map.py

# 解像度を落としたテストモード
python extended_static_map.py --n_s 40 --n_sigma 40 --r_max 2.6

# 生成物
ls output/
#=> extended_maps_r2.6R.png  extended_disk_map_r2.6R.csv  master_summary.csv
```

## Σ プロファイル

- `--profile_mode` で Σ プロファイルの形を選択できる。
- `profile_mode="piecewise"` のとき `--gamma`, `--Sigma0_in` は無視される。
- `profile_mode="gamma"` のとき新オプション（`--r_transition` など）は無視される。

### 使い方サンプル

```bash
# 内側 5e3 kg/m²，外側総質量 1e-8 M_M，p=5 の例
python extended_static_map.py --profile_mode piecewise \
  --Sigma_inner 5e3 --M_outer 1e-8 --p_outer 5

# 旧来の gamma プロファイルを再現したい場合
python extended_static_map.py --profile_mode gamma \
  --Sigma0_in 1e4 --gamma 3
```

