# ======== Makefile ========

CC      := gcc
CFLAGS  := -std=c17 -Irebound -Wall -Wextra -Werror
SRC     := $(wildcard rebound/src/*.c)          # REBOUND 本体
# 必要に応じて自分の追加ソースを列挙
# SRC    += rebound/MarsRing/problem.c

TARGET  := bin/problem              # 出力バイナリ

all: $(TARGET)

$(TARGET): $(SRC)
	@mkdir -p bin
	$(CC) $(CFLAGS) $^ -o $@ -lm

test:
	@echo "テスト未実装"

clean:
	rm -rf bin
# ==========================
