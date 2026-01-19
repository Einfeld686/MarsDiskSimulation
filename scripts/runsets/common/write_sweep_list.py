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


def _parse_extra_cases(raw: str, *, expected_columns: int) -> list[tuple[str, ...]]:
    if not raw:
        return []
    cleaned = raw.strip()
    if not cleaned:
        return []
    if cleaned.lower() in {"none", "off", "false", "0"}:
        return []
    tokens = _parse_list(cleaned)
    if not tokens:
        return []
    if expected_columns == 5:
        stride = 5
        if len(tokens) % 5 == 0:
            stride = 5
        elif len(tokens) % 4 == 0:
            stride = 4
            print(
                "[warn] EXTRA_CASES expects quintuples when MU_LIST is set; "
                "treating entries as quadruples.",
                file=sys.stderr,
            )
        else:
            print(
                f"[warn] EXTRA_CASES expects quintuples; got tokens={len(tokens)}",
                file=sys.stderr,
            )
            stride = 5
    else:
        stride = 4
        if len(tokens) % 4 != 0:
            print(
                f"[warn] EXTRA_CASES expects quadruples; got tokens={len(tokens)}",
                file=sys.stderr,
            )
    cases: list[tuple[str, ...]] = []
    for idx in range(0, len(tokens) - (stride - 1), stride):
        cases.append(tuple(tokens[idx : idx + stride]))
    return cases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path, help="Output path for sweep list")
    ap.add_argument("--t-list", default=os.environ.get("T_LIST", ""), help="Temperature list")
    ap.add_argument("--eps-list", default=os.environ.get("EPS_LIST", ""), help="Epsilon list")
    ap.add_argument("--tau-list", default=os.environ.get("TAU_LIST", ""), help="Tau list")
    ap.add_argument("--i0-list", default=os.environ.get("I0_LIST", ""), help="Inclination list")
    ap.add_argument("--mu-list", default=os.environ.get("MU_LIST", ""), help="Mu list")
    ap.add_argument(
        "--extra-cases",
        default=os.environ.get("EXTRA_CASES", ""),
        help="Additional sweep cases (quadruples)",
    )
    args = ap.parse_args()

    t_list = _parse_list(args.t_list)
    eps_list = _parse_list(args.eps_list)
    tau_list = _parse_list(args.tau_list)
    i0_list = _parse_list(args.i0_list)
    mu_list = _parse_list(args.mu_list)
    if len(mu_list) == 1 and mu_list[0].lower() in {"off", "none", "false"}:
        mu_list = []

    if not t_list:
        print("[error] T_LIST is empty", file=sys.stderr)
        return 2
    if not eps_list:
        print("[error] EPS_LIST is empty", file=sys.stderr)
        return 2
    if not tau_list:
        print("[error] TAU_LIST is empty", file=sys.stderr)
        return 2
    if not i0_list:
        print("[error] I0_LIST is empty", file=sys.stderr)
        return 2
    include_mu = bool(mu_list)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    if include_mu:
        seen: set[tuple[str, str, str, str, str]] = set()
    else:
        seen: set[tuple[str, str, str, str]] = set()
    extra_cases = _parse_extra_cases(args.extra_cases, expected_columns=5 if include_mu else 4)
    with args.out.open("w", encoding="utf-8") as f:
        for t_val in t_list:
            for eps_val in eps_list:
                for tau_val in tau_list:
                    for i0_val in i0_list:
                        if include_mu:
                            for mu_val in mu_list:
                                key = (t_val, eps_val, tau_val, i0_val, mu_val)
                                if key in seen:
                                    continue
                                seen.add(key)
                                f.write(f"{t_val} {eps_val} {tau_val} {i0_val} {mu_val}\n")
                                rows += 1
                        else:
                            key = (t_val, eps_val, tau_val, i0_val)
                            if key in seen:
                                continue
                            seen.add(key)
                            f.write(f"{t_val} {eps_val} {tau_val} {i0_val}\n")
                            rows += 1
        for extra in extra_cases:
            if include_mu:
                if len(extra) == 4:
                    mu_val = mu_list[0]
                    t_val, eps_val, tau_val, i0_val = extra
                else:
                    t_val, eps_val, tau_val, i0_val, mu_val = extra[:5]
                key = (t_val, eps_val, tau_val, i0_val, mu_val)
                if key in seen:
                    continue
                seen.add(key)
                f.write(f"{t_val} {eps_val} {tau_val} {i0_val} {mu_val}\n")
                rows += 1
            else:
                t_val, eps_val, tau_val, i0_val = extra[:4]
                key = (t_val, eps_val, tau_val, i0_val)
                if key in seen:
                    continue
                seen.add(key)
                f.write(f"{t_val} {eps_val} {tau_val} {i0_val}\n")
                rows += 1
    print(f"[info] sweep list rows={rows} out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
