#!/usr/bin/env python3
"""Write sweep list combinations from environment variables."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _parse_list(raw: str) -> list[str]:
    if not raw:
        return []
    cleaned = raw
    for ch in [",", ";", "[", "]", "(", ")", "{", "}", ":"]:
        cleaned = cleaned.replace(ch, " ")
    tokens = []
    for token in cleaned.split():
        token = token.strip().strip('"').strip("'")
        if token:
            tokens.append(token)
    return tokens


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path, help="Output path for sweep list")
    ap.add_argument("--t-list", default=os.environ.get("T_LIST", ""), help="Temperature list")
    ap.add_argument("--eps-list", default=os.environ.get("EPS_LIST", ""), help="Epsilon list")
    ap.add_argument("--tau-list", default=os.environ.get("TAU_LIST", ""), help="Tau list")
    args = ap.parse_args()

    t_list = _parse_list(args.t_list)
    eps_list = _parse_list(args.eps_list)
    tau_list = _parse_list(args.tau_list)

    if not t_list:
        print("[error] T_LIST is empty", file=sys.stderr)
        return 2
    if not eps_list:
        print("[error] EPS_LIST is empty", file=sys.stderr)
        return 2
    if not tau_list:
        print("[error] TAU_LIST is empty", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with args.out.open("w", encoding="utf-8") as f:
        for t_val in t_list:
            for eps_val in eps_list:
                for tau_val in tau_list:
                    f.write(f"{t_val} {eps_val} {tau_val}\n")
                    rows += 1
    print(f"[info] sweep list rows={rows} out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
