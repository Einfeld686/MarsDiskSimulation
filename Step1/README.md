# Step1 Python 検証スクリプト

`test.py` は火星周辺の静的な光学的厚さ・放射圧・時スケールマップを生成するスクリプトです。

## 実行例

```bash
# デフォルト
python test.py
# 高温火星 / 密集グリッド
python test.py --T_mars 4000 --r_disk 4.5e6 --n_s 600 --n_sigma 600
# 生成物
ls output/
#=> map_tau_beta.png  disk_map.csv
```

