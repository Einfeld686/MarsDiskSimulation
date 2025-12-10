#!/usr/bin/env python3
"""
figure_tasks.json と resolved_manifest.json を読み込み、
run_id→outdir を解決した上で図再生成コマンドのスケッチを出力する。

実際の描画スクリプトのCLIはプロジェクト固有なので、本スクリプトは
「推奨コマンド」を commands.txt に書き出すのみ（自動実行はしない）。
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any, Dict, List

try:
    from paper.plot_style import apply_default_style
except Exception:  # pragma: no cover - optional dependency path
    def apply_default_style(_: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_command(script: str, fig_id: str, run_paths: List[str], params: Dict[str, Any]) -> str:
    cmd_parts = [
        "python",
        script,
        "--fig-id",
        fig_id,
    ]
    if run_paths:
        cmd_parts.append("--runs")
        cmd_parts.extend(run_paths)
    if params:
        params_json = json.dumps(params, ensure_ascii=False)
        cmd_parts.append("--params-json")
        cmd_parts.append(params_json)
    return " ".join(shlex.quote(part) for part in cmd_parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render suggested commands from figure_tasks.json")
    parser.add_argument("--tasks", required=True, type=Path, help="figure_tasks.json from paper_manifest")
    parser.add_argument("--resolved-manifest", type=Path, help="resolved_manifest.json to map run_id->outdir")
    parser.add_argument("--commands-out", type=Path, help="path to write suggested commands (default: tasks dir/figure_commands.txt)")
    args = parser.parse_args()

    apply_default_style()  # ensure downstream scripts share unified style if they import this module

    tasks_data = load_json(args.tasks)
    resolved = load_json(args.resolved_manifest) if args.resolved_manifest else {}
    run_dir_map = {r["run_id"]: r.get("outdir") for r in resolved.get("runs", []) if r.get("outdir")}

    commands: List[str] = []
    for task in tasks_data:
        fig_id = task.get("fig_id", "UNKNOWN")
        script = task.get("script", "")
        params = task.get("params", {}) or {}
        run_paths = []
        for rid in task.get("runs", []):
            run_paths.append(run_dir_map.get(rid, rid))
        commands.append(build_command(script, fig_id, run_paths, params))

    out_path = args.commands_out or (args.tasks.parent / "figure_commands.txt")
    out_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
    print(f"[render_figures_from_tasks] wrote {out_path} ({len(commands)} commands)")


if __name__ == "__main__":
    main()
