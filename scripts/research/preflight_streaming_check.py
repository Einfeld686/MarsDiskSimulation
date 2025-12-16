#!/usr/bin/env python
"""Pre-flight check for streaming schema compatibility.

This script validates that the streaming merge will succeed for an existing
run directory by checking for schema consistency across chunk files.

Usage:
    python scripts/research/preflight_streaming_check.py /path/to/run_dir

Exit codes:
    0: All checks passed
    1: Schema issues detected (warnings only)
    2: Critical errors that would cause merge failure
"""
from pathlib import Path
import sys


def check_streaming_chunks(run_dir: Path) -> int:
    """Check Parquet chunk schemas for consistency."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("[ERROR] pyarrow not installed")
        return 2

    series_dir = run_dir / "series"
    if not series_dir.exists():
        print(f"[SKIP] No series directory found: {series_dir}")
        return 0

    exit_code = 0
    for pattern in ["run_chunk_*.parquet", "psd_hist_chunk_*.parquet", "diagnostics_chunk_*.parquet"]:
        chunks = sorted(series_dir.glob(pattern))
        if not chunks:
            continue

        print(f"\n[CHECK] {pattern}: {len(chunks)} chunks found")
        schemas = []
        for chunk in chunks:
            try:
                schema = pq.read_schema(chunk)
                schemas.append((chunk.name, schema))
            except Exception as e:
                print(f"  [ERROR] Failed to read {chunk.name}: {e}")
                exit_code = max(exit_code, 2)

        if len(schemas) < 2:
            print("  [OK] Single chunk or no valid schemas - no merge required")
            continue

        # Compare schemas
        base_name, base_schema = schemas[0]
        base_cols = set(base_schema.names)
        all_cols = set(base_cols)
        mismatches = []

        for name, schema in schemas[1:]:
            current_cols = set(schema.names)
            all_cols |= current_cols
            if current_cols != base_cols:
                added = current_cols - base_cols
                removed = base_cols - current_cols
                mismatches.append({
                    "chunk": name,
                    "added": added,
                    "removed": removed,
                })

        if mismatches:
            print(f"  [WARN] Schema differences detected across chunks:")
            for m in mismatches:
                if m["added"]:
                    print(f"    {m['chunk']}: +{m['added']}")
                if m["removed"]:
                    print(f"    {m['chunk']}: -{m['removed']}")
            print(f"  [INFO] Unified schema will have {len(all_cols)} columns (base had {len(base_cols)})")
            exit_code = max(exit_code, 1)

            # Test schema unification
            try:
                all_schemas = [s for _, s in schemas]
                unified = pa.unify_schemas(all_schemas, promote_options="permissive")
                print(f"  [OK] Schema unification succeeded: {len(unified)} fields")
            except pa.ArrowInvalid as e:
                print(f"  [ERROR] Schema unification failed: {e}")
                exit_code = max(exit_code, 2)
        else:
            print("  [OK] All chunk schemas are consistent")

    return exit_code


def check_required_columns(run_dir: Path) -> int:
    """Check that the merged parquet has required columns for plotting."""
    required_cols = [
        "time", "M_loss_cum", "M_sink_cum", "mass_lost_by_blowout",
        "Sigma_surf", "Sigma_tau1", "s_min", "a_blow",
    ]

    series_path = run_dir / "series" / "run.parquet"
    if not series_path.exists():
        # Check the last chunk instead
        chunks = sorted((run_dir / "series").glob("run_chunk_*.parquet"))
        if not chunks:
            print(f"[SKIP] No run.parquet or chunks found")
            return 0
        series_path = chunks[-1]
        print(f"[INFO] Using last chunk for column check: {series_path.name}")

    try:
        import pyarrow.parquet as pq
        schema = pq.read_schema(series_path)
        cols = set(schema.names)
        missing = [c for c in required_cols if c not in cols]
        if missing:
            print(f"[WARN] Missing columns for plotting: {missing}")
            print("       (These will be filled with null after schema fix)")
            return 1
        print(f"[OK] All required columns present in {series_path.name}")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to check columns: {e}")
        return 2


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"[ERROR] Run directory not found: {run_dir}")
        sys.exit(2)

    print(f"[INFO] Checking: {run_dir}")
    exit_code = 0
    exit_code = max(exit_code, check_streaming_chunks(run_dir))
    exit_code = max(exit_code, check_required_columns(run_dir))

    print(f"\n[RESULT] Exit code: {exit_code}")
    if exit_code == 0:
        print("         All checks passed!")
    elif exit_code == 1:
        print("         Warnings detected - merge should succeed with schema fix")
    else:
        print("         Critical errors - merge may fail")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
