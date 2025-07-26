# marsshearingsheet – FY2025 MarsRing Simulation

REBOUND をベースに、火星周回デブリの断片化（fragmentation）をシミュレーションする C プロジェクト。

## ビルド方法（Ubuntu VM 想定）
```bash
sudo apt-get update && sudo apt-get install -y build-essential
make            # bin/problem が生成される
make test       # 単体テスト（未実装ならスキップされます）
```

## ディレクトリ構成
```
rebound/   … REBOUND 本体 + 拡張コード
Makefile   … ビルド定義
Step1/     … Python 検証スクリプト
```