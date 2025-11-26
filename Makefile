# ======== Makefile ========

CC      := gcc
MODE    ?= A
CFLAGS  := -std=c17 -Irebound -Isrc -Wall -Wextra -Werror
OUTDIR  ?= out

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

test: bin/test_smol
	bin/test_smol

bin/test_smol: tests/test_smol.c src/smoluchowski.c
	@mkdir -p bin
	$(CC) $(CFLAGS) $^ -o $@ -lm

clean:
	rm -rf bin

analysis-sync:
	python -m tools.doc_sync_agent --all --write

analysis-sync-commit:
	python -m tools.doc_sync_agent --all --write --commit

analysis-coverage-guard:
	python -m tools.coverage_guard --fail-under 0.75

analysis-doc-tests:
	python tools/run_analysis_doc_tests.py

analysis-pipeline:
	python tools/run_analysis_pipeline.py --outdir $(OUTDIR)

analysis-update: analysis-pipeline
# ==========================
