# marsshearingsheet – FY2025 MarsRing Simulation

REBOUND をベースに、火星周回デブリの断片化（fragmentation）をシミュレーションする C プロジェクト。

## ビルド方法（Ubuntu VM 想定）
```bash
sudo apt-get update && sudo apt-get install -y build-essential
make            # bin/problem が生成される
make test       # 単体テストを実行する
```

## ディレクトリ構成
```
rebound/   … REBOUND 本体 + 拡張コード
Makefile   … ビルド定義
Step1/     … Python 検証スクリプト
```
## Python CLI 実行例
```bash
python -m marsdisk.run --config configs/mars_0d_supply_sweep.yaml
```

## テーブル生成スクリプト実行例
```bash
python tools/make_qpr_table.py --s-min 1e-9 --s-max 1e-2 --Ns 60 --T 2000,2500,3000,3500,4000 --out data/qpr_planck.h5
```
