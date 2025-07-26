# ======== Makefile ========

CC      := gcc
MODE    ?= A
CFLAGS  := -std=c17 -Irebound -Isrc -Wall -Wextra -Werror

SRC     := $(wildcard rebound/src/*.c)
SRC     += src/smoluchowski.c
ifeq ($(MODE),C)
SRC     += src/hybrid.c
endif

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
