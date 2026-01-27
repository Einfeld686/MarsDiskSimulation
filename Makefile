# ======== Makefile ========

CC      := gcc
MODE    ?= A
CFLAGS  := -std=c17 -Irebound -Isrc -Wall -Wextra -Werror
OUTDIR  ?= out
EVAL_OUTDIR ?= out/analysis_eval_run

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
	python tools/make_physics_flow.py --write
	python -m tools.doc_sync_agent --all --write
	python tools/readme_sync.py --write

analysis-abstract-sync:
	python -m analysis.tools.merge_abstract_sections --write

analysis-abstract-update: analysis-abstract-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)

analysis-intro-sync:
	python -m analysis.tools.merge_introduction_sections --write

analysis-intro-update: analysis-intro-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)

analysis-related-work-sync:
	python -m analysis.tools.merge_related_work_sections --write

analysis-related-work-update: analysis-related-work-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)

analysis-methods-sync:
	python -m analysis.tools.merge_methods_sections --write

analysis-methods-update: analysis-methods-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)

analysis-results-sync:
	python -m analysis.tools.merge_results_sections --write

analysis-results-update: analysis-results-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)

analysis-discussion-sync:
	python -m analysis.tools.merge_discussion_sections --write

analysis-conclusion-sync:
	python -m analysis.tools.merge_conclusion_sections --write

analysis-discussion-update: analysis-discussion-sync
	$(MAKE) analysis-update
	python -m tools.evaluation_system --outdir $(EVAL_OUTDIR)


analysis-sync-commit:
	python -m analysis.tools.render_assumptions
	python tools/make_physics_flow.py --write
	python -m tools.doc_sync_agent --all --write --commit

analysis-coverage-guard:
	python -m tools.coverage_guard --fail-under 0.75

analysis-doc-tests:
	python tools/run_analysis_doc_tests.py

readme-sync:
	python tools/readme_sync.py --write

readme-sync-check:
	python tools/readme_sync.py --check

analysis-assumptions:
	python -m analysis.tools.render_assumptions
	python -m tools.doc_sync_agent --all --write

assumptions-autogen-check:
	python -m tools.doc_sync_agent --all --write
	python -m analysis.tools.scan_assumptions
	python -m analysis.tools.render_assumptions
	python tools/run_analysis_doc_tests.py
	python -m tools.evaluation_system --outdir $(OUTDIR)

# Remove temporary debug artifacts while preserving archived backups
clean-tmp:
	@echo "Removing temporary debug directories (preserving backup tarball and inventory)..."
	rm -rf tmp_debug_mass_budget tmp_debug_mass_budget2
	rm -rf tmp_debug_sampling
	rm -rf tmp_debug_test_gate tmp_debug_test_gate2 tmp_debug_test_gate3
	rm -rf tmp_debug_test_psat
	rm -rf tmp_eval_fixture
	@echo "Preserved: tmp_debug_backup_*.tar.gz, tmp_debug_inventory.txt"

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

# OCR output migration and eq placeholder checks
ocr-update:
	python -m tools.ocr_output_migration
	pytest -q tests/integration/test_eqn_placeholder_guard.py
	pytest -q tests/integration/test_eqn_external_audit_guard.py
	pytest -q tests/integration/test_eqn_placeholder_reconciliation_guard.py

# 任意: 参照レジストリとの差分検出（標準フローには含まない）
analysis-refs:
	python tools/reference_tracker.py validate

# 任意: 未解決参照リクエストの確認（warn-only, 標準フロー外）
analysis-unknown-refs:
	python tools/check_unknown_refs.py

# --strict で CI fail-fast にする場合
analysis-unknown-refs-strict:
	python tools/check_unknown_refs.py --strict

plan-lint:
	python tools/plan_lint.py

# Thesis build (TeX → PDF). Deliverables: paper/out/*.pdf, intermediates: paper/out/build/
thesis-sync: analysis-abstract-sync analysis-intro-sync analysis-related-work-sync analysis-methods-sync analysis-results-sync analysis-discussion-sync analysis-conclusion-sync

thesis-pdf: thesis-sync
	python tools/build_thesis_draft.py --pdf --outdir paper/out/build --sync-sections off

# Build from existing analysis/thesis/*.md without syncing thesis_sections (useful for local manual edits / quick TeX iteration).
thesis-pdf-nosync:
	python tools/build_thesis_draft.py --pdf --outdir paper/out/build --sync-sections off

thesis: thesis-pdf

thesis-nosync: thesis-pdf-nosync
