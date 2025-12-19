#!/usr/bin/env python3
"""Run a Q_D* coefficient scale sweep and summarise outflux metrics."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _format_scale(scale: float) -> str:
    text = f"{scale:g}"
    return text.replace("-", "m").replace(".", "p")


def _run_case(cmd_base: List[str], outdir: Path, scale: float, extra_overrides: List[str], dry_run: bool) -> None:
    cmd = list(cmd_base)
    cmd.extend(["--override", "qstar.override_coeffs=true"])
    cmd.extend(["--override", f"qstar.coeff_scale={scale}"])
    cmd.extend(["--override", f"io.outdir={outdir}"])
    for override in extra_overrides:
        cmd.extend(["--override", override])
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.run(cmd, check=True)


def _summarise_run(outdir: Path) -> dict:
    summary = {"outdir": str(outdir)}
    summary_path = outdir / "summary.json"
    if summary_path.exists():
        with summary_path.open("r", encoding="utf-8") as fh:
            summary.update(json.load(fh))
    series_path = outdir / "series" / "run.parquet"
    if not series_path.exists():
        return summary
    try:
        df = pd.read_parquet(series_path)
    except Exception as exc:
        summary["series_read_error"] = str(exc)
        return summary

    def _pick_column(*candidates: str) -> str | None:
        for name in candidates:
            if name in df.columns:
                return name
        return None

    prod_col = _pick_column("prod_subblow_area_rate", "prod_subblow_area_rate_avg")
    out_col = _pick_column("M_out_dot", "M_out_dot_avg")
    if prod_col:
        summary.update(
            {
                "prod_subblow_area_rate_mean": float(df[prod_col].mean()),
                "prod_subblow_area_rate_median": float(df[prod_col].median()),
                "prod_subblow_area_rate_p90": float(df[prod_col].quantile(0.9)),
            }
        )
    if out_col:
        summary.update(
            {
                "M_out_dot_mean": float(df[out_col].mean()),
                "M_out_dot_max": float(df[out_col].max()),
            }
        )
    summary["n_steps"] = int(df.shape[0])
    return summary


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/base.yml"),
        help="Base YAML configuration for the sweep.",
    )
    parser.add_argument(
        "--scales",
        nargs="+",
        type=float,
        default=[1.0, 0.1, 0.01],
        help="Scale factors applied to Qs and B.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out/qstar_scale_sweep"),
        help="Root directory for sweep outputs.",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Additional overrides passed to marsdisk.run (repeatable).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running the simulation.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    cmd_base = [
        sys.executable,
        "-m",
        "marsdisk.run",
        "--config",
        str(args.config),
    ]
    results = []
    for scale in args.scales:
        case_dir = outdir / f"scale_{_format_scale(scale)}"
        _run_case(cmd_base, case_dir, scale, args.override, args.dry_run)
        if not args.dry_run:
            record = _summarise_run(case_dir)
            record["scale"] = float(scale)
            results.append(record)
    if results:
        df = pd.DataFrame(results)
        df.to_csv(outdir / "qstar_scale_summary.csv", index=False)
        print(df[["scale", "prod_subblow_area_rate_mean", "M_out_dot_mean"]])


if __name__ == "__main__":
    main()
