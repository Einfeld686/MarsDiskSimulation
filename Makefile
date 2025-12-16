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
	python -m analysis.tools.render_assumptions
	python -m analysis.tools.make_run_sections --write
	python -m tools.doc_sync_agent --all --write


analysis-sync-commit:
	python -m analysis.tools.render_assumptions
	python -m tools.doc_sync_agent --all --write --commit

analysis-coverage-guard:
	python -m tools.coverage_guard --fail-under 0.75

analysis-doc-tests:
	python tools/run_analysis_doc_tests.py

analysis-assumptions:
	python -m analysis.tools.render_assumptions
	python -m tools.doc_sync_agent --all --write

assumptions-autogen-check:
	python -m tools.doc_sync_agent --all --write
	python -m analysis.tools.scan_assumptions
	python -m analysis.tools.render_assumptions
	python tools/run_analysis_doc_tests.py
	python -m tools.evaluation_system --outdir $(OUTDIR)

analysis-pipeline:
	python tools/run_analysis_pipeline.py --outdir $(OUTDIR)

# AGENTS.md: DocSync → doc-tests → evaluation_system
analysis-update: analysis-sync
	python -m tools.doc_sync_agent equations --equations analysis/equations.md --inventory analysis/inventory.json --write analysis/equation_code_map.json
	python analysis/tools/make_coverage.py
	python -m tools.coverage_guard
	python tools/run_analysis_doc_tests.py
	@echo "[analysis-update] evaluation_system requires --outdir; run manually:"
	@echo "  python -m tools.evaluation_system --outdir <run_dir>"

# 任意: 参照レジストリとの差分検出（標準フローには含まない）
analysis-refs:
	python tools/reference_tracker.py validate

# 任意: 未解決参照リクエストの確認（warn-only, 標準フロー外）
analysis-unknown-refs:
	python tools/check_unknown_refs.py

# --strict で CI fail-fast にする場合
analysis-unknown-refs-strict:
	python tools/check_unknown_refs.py --strict
# ==========================
