## Build Steps
1. `make` で `bin/problem` を生成（ただし.pyの場合は実行しなくても良い）
2. `make test` は現状ダミー。将来 `tests/` を追加予定

## Dependencies
- GCC, GNU Make
- math library (`-lm` は libc に同梱)
- 追加ライブラリなし（REBOUND ソースは `rebound/` に同梱）
- 出力は日本語で行うこと

## Coding Conventions
- C17 / `-Wall -Wextra -Werror`
- インデントは 4 スペース
