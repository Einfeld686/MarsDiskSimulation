#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


EXCLUDE_START = "<!-- TEX_EXCLUDE_START -->"
EXCLUDE_END = "<!-- TEX_EXCLUDE_END -->"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_UNORDERED_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
LIST_ORDERED_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^:?-{3,}:?$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
INLINE_MATH_PAREN_RE = re.compile(r"\\\((.+?)\\\)")
INLINE_MATH_DOLLAR_RE = re.compile(r"(?<!\\)\$([^$]+?)\$")
LATEX_CMD_RE = re.compile(r"\\(cite|ref|eqref|label)\{[^}]+\}")
CITE_BRACKET_RE = re.compile(r"\[@([^\]]+)\]")

SUBSCRIPT_MAP = {
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
}

UNICODE_SYMBOLS = {
    "→": r"\ensuremath{\rightarrow}",
    "←": r"\ensuremath{\leftarrow}",
    "↔": r"\ensuremath{\leftrightarrow}",
    "≤": r"\ensuremath{\le}",
    "≥": r"\ensuremath{\ge}",
    "≲": r"\ensuremath{\lesssim}",
    "≳": r"\ensuremath{\gtrsim}",
    "×": r"\ensuremath{\times}",
}

INTRO_START = "% === AUTOGEN INTRODUCTION START ==="
INTRO_END = "% === AUTOGEN INTRODUCTION END ==="
ABSTRACT_START = "% === AUTOGEN ABSTRACT START ==="
ABSTRACT_END = "% === AUTOGEN ABSTRACT END ==="
RELATED_WORK_START = "% === AUTOGEN RELATED WORK START ==="
RELATED_WORK_END = "% === AUTOGEN RELATED WORK END ==="
METHODS_START = "% === AUTOGEN METHODS START ==="
METHODS_END = "% === AUTOGEN METHODS END ==="
RESULTS_START = "% === AUTOGEN RESULTS START ==="
RESULTS_END = "% === AUTOGEN RESULTS END ==="
DISCUSSION_START = "% === AUTOGEN DISCUSSION START ==="
DISCUSSION_END = "% === AUTOGEN DISCUSSION END ==="
APPENDIX_START = "% === AUTOGEN APPENDIX START ==="
APPENDIX_END = "% === AUTOGEN APPENDIX END ==="


@dataclass
class Block:
    kind: str
    data: object


def strip_yaml_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[idx + 1 :])
    return text


def strip_html_comments(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_comment = False
    for line in lines:
        if "<!--" in line:
            in_comment = True
        if not in_comment:
            out.append(line)
        if "-->" in line:
            in_comment = False
    return "\n".join(out)


def strip_tex_exclude_blocks(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_exclude = False
    for line in lines:
        stripped = line.strip()
        if stripped == EXCLUDE_START:
            in_exclude = True
            continue
        if stripped == EXCLUDE_END:
            in_exclude = False
            continue
        if not in_exclude:
            out.append(line)
    return "\n".join(out)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    if not cells:
        return False
    for cell in cells:
        if not TABLE_SEP_RE.match(cell):
            return False
    return True


def is_latex_block_start(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith(r"\begin{")
        or stripped.startswith(r"\[")
        or stripped == "$$"
    )


def parse_latex_block(lines: list[str], start: int) -> tuple[Block, int]:
    first = lines[start].rstrip("\n")
    stripped = first.strip()
    collected = [first]
    if stripped.startswith(r"\begin{"):
        env = stripped[len(r"\begin{") :].split("}", 1)[0]
        end_marker = rf"\end{{{env}}}"
        idx = start + 1
        while idx < len(lines):
            collected.append(lines[idx].rstrip("\n"))
            if lines[idx].strip().startswith(end_marker):
                idx += 1
                break
            idx += 1
        return Block("latex", "\n".join(collected)), idx
    if stripped.startswith(r"\["):
        idx = start + 1
        while idx < len(lines):
            collected.append(lines[idx].rstrip("\n"))
            if lines[idx].strip().endswith(r"\]"):
                idx += 1
                break
            idx += 1
        return Block("latex", "\n".join(collected)), idx
    if stripped == "$$":
        idx = start + 1
        while idx < len(lines):
            collected.append(lines[idx].rstrip("\n"))
            if lines[idx].strip() == "$$":
                idx += 1
                break
            idx += 1
        return Block("latex", "\n".join(collected)), idx
    return Block("latex", first), start + 1


def parse_code_block(lines: list[str], start: int) -> tuple[Block, int]:
    idx = start + 1
    collected: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if line.strip().startswith("```"):
            idx += 1
            break
        collected.append(line.rstrip("\n"))
        idx += 1
    return Block("code", "\n".join(collected)), idx


def parse_table(lines: list[str], start: int) -> tuple[Block | None, int]:
    if start + 1 >= len(lines):
        return None, start
    header = split_table_row(lines[start])
    if not header:
        return None, start
    if not is_table_separator(lines[start + 1]):
        return None, start
    rows: list[list[str]] = []
    idx = start + 2
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "" or "|" not in line:
            break
        row = split_table_row(line)
        if len(row) == len(header):
            rows.append(row)
        idx += 1
    return Block("table", (header, rows)), idx


def parse_list(lines: list[str], start: int) -> tuple[Block, int]:
    line = lines[start]
    match_ul = LIST_UNORDERED_RE.match(line)
    match_ol = LIST_ORDERED_RE.match(line)
    if match_ul:
        list_kind = "ul"
        base_indent = len(match_ul.group(1))
        idx = start
        items: list[str] = []
        while idx < len(lines):
            m = LIST_UNORDERED_RE.match(lines[idx])
            if not m or len(m.group(1)) != base_indent:
                break
            item_text = [m.group(2).strip()]
            idx += 1
            while idx < len(lines):
                next_line = lines[idx]
                if next_line.strip() == "":
                    break
                if LIST_UNORDERED_RE.match(next_line) or LIST_ORDERED_RE.match(next_line):
                    break
                indent = len(next_line) - len(next_line.lstrip())
                if indent <= base_indent:
                    break
                item_text.append(next_line.strip())
                idx += 1
            items.append(" ".join(item_text).strip())
            while idx < len(lines) and lines[idx].strip() == "":
                idx += 1
        return Block("list", (list_kind, items)), idx
    if match_ol:
        list_kind = "ol"
        base_indent = len(match_ol.group(1))
        idx = start
        items = []
        while idx < len(lines):
            m = LIST_ORDERED_RE.match(lines[idx])
            if not m or len(m.group(1)) != base_indent:
                break
            item_text = [m.group(2).strip()]
            idx += 1
            while idx < len(lines):
                next_line = lines[idx]
                if next_line.strip() == "":
                    break
                if LIST_UNORDERED_RE.match(next_line) or LIST_ORDERED_RE.match(next_line):
                    break
                indent = len(next_line) - len(next_line.lstrip())
                if indent <= base_indent:
                    break
                item_text.append(next_line.strip())
                idx += 1
            items.append(" ".join(item_text).strip())
            while idx < len(lines) and lines[idx].strip() == "":
                idx += 1
        return Block("list", (list_kind, items)), idx
    return Block("paragraph", line.strip()), start + 1


def parse_blockquote(lines: list[str], start: int) -> tuple[Block, int]:
    idx = start
    collected: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        stripped = line.lstrip()
        if not stripped.startswith(">"):
            break
        collected.append(stripped[1:].lstrip())
        idx += 1
    return Block("quote", "\n".join(collected).strip()), idx


def parse_paragraph(lines: list[str], start: int) -> tuple[Block, int]:
    idx = start
    collected: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "":
            break
        if HEADING_RE.match(line):
            break
        if line.strip().startswith("```"):
            break
        if is_latex_block_start(line):
            break
        if LIST_UNORDERED_RE.match(line) or LIST_ORDERED_RE.match(line):
            break
        if line.lstrip().startswith(">"):
            break
        if "|" in line and idx + 1 < len(lines) and is_table_separator(lines[idx + 1]):
            break
        collected.append(line.strip())
        idx += 1
    return Block("paragraph", " ".join(collected).strip()), idx


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "":
            idx += 1
            continue
        if line.strip() in {"---", "***", "___"}:
            idx += 1
            continue
        if line.strip().startswith("```"):
            block, idx = parse_code_block(lines, idx)
            blocks.append(block)
            continue
        if is_latex_block_start(line):
            block, idx = parse_latex_block(lines, idx)
            blocks.append(block)
            continue
        heading = HEADING_RE.match(line)
        if heading:
            blocks.append(Block("heading", (len(heading.group(1)), heading.group(2).strip())))
            idx += 1
            continue
        if "|" in line and idx + 1 < len(lines) and is_table_separator(lines[idx + 1]):
            block, idx = parse_table(lines, idx)
            if block:
                blocks.append(block)
                continue
        if LIST_UNORDERED_RE.match(line) or LIST_ORDERED_RE.match(line):
            block, idx = parse_list(lines, idx)
            blocks.append(block)
            continue
        if line.lstrip().startswith(">"):
            block, idx = parse_blockquote(lines, idx)
            blocks.append(block)
            continue
        block, idx = parse_paragraph(lines, idx)
        blocks.append(block)
    return blocks


def strip_numbered_prefix(text: str) -> str:
    return re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", text)


def convert_cite_brackets(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        keys: list[str] = []
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith("@"):
                part = part[1:].strip()
            if part:
                keys.append(part)
        if not keys:
            return match.group(0)
        return r"\cite{" + ",".join(keys) + "}"

    return CITE_BRACKET_RE.sub(repl, text)


def escape_latex(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "$": r"\$",
        "_": r"\_\allowbreak{}",
        "/": r"/\allowbreak{}",
        ".": r".\allowbreak{}",
        "-": r"-\allowbreak{}",
        ":": r":\allowbreak{}",
        "=": r"=\allowbreak{}",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = []
    for ch in text:
        out.append(replacements.get(ch, ch))
    return "".join(out)


def escape_latex_code(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "$": r"\$",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out: list[str] = []
    for ch in text:
        if ch == "\\":
            out.append(r"\textbackslash{}")
        else:
            out.append(replacements.get(ch, ch))
    return "".join(out)


def convert_inline(text: str) -> str:
    text = convert_cite_brackets(text)
    tokens: list[tuple[str, str]] = []

    def protect(pattern: re.Pattern[str], kind: str, group: int = 0) -> None:
        nonlocal text

        def repl(match: re.Match[str]) -> str:
            value = match.group(group)
            tokens.append((kind, value))
            return f"@@TOKEN{len(tokens) - 1}@@"

        text = pattern.sub(repl, text)

    protect(INLINE_CODE_RE, "code", 1)
    protect(INLINE_MATH_PAREN_RE, "math", 0)
    protect(INLINE_MATH_DOLLAR_RE, "math", 0)
    protect(LATEX_CMD_RE, "latex", 0)

    text = escape_latex(text)
    text = replace_unicode_subscripts(text)
    text = replace_unicode_symbols(text)

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\\href{\2}{\1}", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\\emph{\1}", text)

    for idx, (kind, value) in enumerate(tokens):
        placeholder = f"@@TOKEN{idx}@@"
        if kind == "code":
            replacement = r"\texttt{" + escape_latex_code(value) + "}"
        elif kind == "math":
            replacement = value.replace(r"\*", "*").replace("\\\\", "\\")
        else:
            replacement = value
        text = text.replace(placeholder, replacement)

    return text


def needs_texorpdfstring(text: str) -> bool:
    if re.search(r"\\\(|\\\[|\$|_|\&", text) or "`" in text:
        return True
    if any(ch in text for ch in SUBSCRIPT_MAP):
        return True
    if any(ch in text for ch in UNICODE_SYMBOLS):
        return True
    return False


def latex_to_plain(text: str) -> str:
    plain = text
    plain = plain.replace(r"\(", "").replace(r"\)", "")
    plain = plain.replace(r"\[", "").replace(r"\]", "")
    plain = plain.replace("$", "")
    plain = re.sub(
        r"\\(mathrm|rm|mathbf|mathit|mathcal|textit|textbf|ensuremath)\b",
        "",
        plain,
    )
    plain = re.sub(r"\\([A-Za-z]+)", r"\1", plain)
    plain = plain.replace("{", "").replace("}", "")
    plain = plain.replace("_", "")
    plain = plain.replace("^", "")
    plain = plain.replace("&", "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def replace_unicode_subscripts(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        digits = "".join(SUBSCRIPT_MAP[ch] for ch in match.group(0))
        return r"\ensuremath{_{" + digits + "}}"

    return re.sub(r"[₀-₉]+", repl, text)


def replace_unicode_symbols(text: str) -> str:
    for symbol, latex in UNICODE_SYMBOLS.items():
        text = text.replace(symbol, latex)
    return text


class MarkdownToLatexConverter:
    def __init__(self, heading_map: dict[int, str]) -> None:
        self.heading_map = heading_map

    def render_heading(self, level: int, title: str) -> str:
        title = strip_numbered_prefix(title)
        title_tex = convert_inline(title)
        cmd = self.heading_map.get(level, "section")
        if needs_texorpdfstring(title):
            plain = latex_to_plain(title)
            title_tex = r"\texorpdfstring{" + title_tex + "}{" + plain + "}"
        return rf"\{cmd}{{{title_tex}}}"

    def render_list(self, list_kind: str, items: list[str]) -> str:
        env = "itemize" if list_kind == "ul" else "enumerate"
        out = [rf"\begin{{{env}}}"]
        for item in items:
            out.append(rf"  \item {convert_inline(item)}")
        out.append(rf"\end{{{env}}}")
        return "\n".join(out)

    def render_table(self, header: list[str], rows: list[list[str]]) -> str:
        col_count = len(header)
        width = 0.96 / col_count if col_count else 1.0
        col_spec = " ".join([f"p{{{width:.2f}\\textwidth}}" for _ in range(col_count)])
        out = [r"\begin{center}", rf"\begin{{tabular}}{{{col_spec}}}", r"\toprule"]
        out.append(" & ".join(convert_inline(cell) for cell in header) + r" \\")
        out.append(r"\midrule")
        for row in rows:
            out.append(" & ".join(convert_inline(cell) for cell in row) + r" \\")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{center}")
        return "\n".join(out)

    def convert(self, text: str) -> str:
        text = strip_yaml_frontmatter(text)
        text = strip_tex_exclude_blocks(text)
        text = strip_html_comments(text)
        blocks = parse_blocks(text.splitlines())
        out: list[str] = []
        for block in blocks:
            if block.kind == "heading":
                level, title = block.data  # type: ignore[misc]
                out.append(self.render_heading(level, title))
            elif block.kind == "paragraph":
                out.append(convert_inline(block.data))  # type: ignore[arg-type]
            elif block.kind == "list":
                list_kind, items = block.data  # type: ignore[misc]
                out.append(self.render_list(list_kind, items))
            elif block.kind == "quote":
                out.append(r"\begin{quote}")
                out.append(convert_inline(block.data))  # type: ignore[arg-type]
                out.append(r"\end{quote}")
            elif block.kind == "code":
                out.append(r"\begin{verbatim}")
                out.append(block.data)  # type: ignore[arg-type]
                out.append(r"\end{verbatim}")
            elif block.kind == "latex":
                out.append(block.data)  # type: ignore[arg-type]
            elif block.kind == "table":
                header, rows = block.data  # type: ignore[misc]
                out.append(self.render_table(header, rows))
            else:
                out.append(convert_inline(str(block.data)))
        return "\n\n".join([chunk for chunk in out if chunk.strip()]) + "\n"


def replace_between_markers(text: str, start: str, end: str, replacement: str) -> str:
    start_idx = text.find(start)
    end_idx = text.find(end)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError(f"markers not found: {start} ... {end}")
    before = text[: start_idx + len(start)]
    after = text[end_idx:]
    return before + "\n" + replacement.rstrip() + "\n" + after


def replace_between_markers_optional(
    text: str, start: str, end: str, replacement: str
) -> str:
    start_idx = text.find(start)
    end_idx = text.find(end)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return text
    return replace_between_markers(text, start, end, replacement)


APPENDIX_CHAPTER_HEADING_RE = re.compile(
    r"^(#{1,6})\s+付録\s*([A-Z])\.\s*(.+?)\s*$"
)


def split_methods_appendices(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+付録\b", line):
            body = "\n".join(lines[:idx]).rstrip() + "\n"
            appendix = "\n".join(lines[idx:]).rstrip() + "\n"
            return body, appendix
    return text, ""


def normalize_appendix_headings(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        match = APPENDIX_CHAPTER_HEADING_RE.match(line)
        if match:
            hashes, _letter, title = match.groups()
            out.append(f"{hashes} {title}")
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, env=env)


def build_pdf(tex_path: Path, out_dir: Path, repo_root: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = tex_path.stem
    tex_arg = str(tex_path)
    run(
        [
            "platex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={out_dir}",
            tex_arg,
        ],
        cwd=tex_path.parent,
    )
    bibtex_env = os.environ.copy()
    bibtex_env["BIBINPUTS"] = (
        str(tex_path.parent) + os.pathsep + bibtex_env.get("BIBINPUTS", "")
    )
    aux_path = out_dir / f"{stem}.aux"
    needs_bibtex = False
    if aux_path.exists():
        aux_text = aux_path.read_text(encoding="utf-8", errors="ignore")
        needs_bibtex = any(
            token in aux_text for token in ("\\bibdata", "\\bibstyle", "\\citation")
        )
    if needs_bibtex:
        bibtex_cmds: list[str] = []
        if shutil.which("upbibtex"):
            bibtex_cmds.append("upbibtex")
        if shutil.which("bibtex"):
            bibtex_cmds.append("bibtex")
        if not bibtex_cmds:
            raise FileNotFoundError("bibtex command not found (upbibtex/bibtex)")
        last_error: subprocess.CalledProcessError | None = None
        for cmd in bibtex_cmds:
            try:
                run([cmd, stem], cwd=out_dir, env=bibtex_env)
                last_error = None
                break
            except subprocess.CalledProcessError as exc:
                print(f"build_pdf: {cmd} failed (exit {exc.returncode}), trying fallback")
                last_error = exc
        if last_error is not None:
            bbl_path = out_dir / f"{stem}.bbl"
            if bbl_path.exists():
                print("build_pdf: bibtex failed, using existing .bbl")
            else:
                raise last_error
    else:
        print("build_pdf: skipping bibtex (no citation/bibliography markers found)")
    try:
        run(
            [
                "platex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={out_dir}",
                tex_arg,
            ],
            cwd=tex_path.parent,
        )
        run(
            [
                "platex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={out_dir}",
                tex_arg,
            ],
            cwd=tex_path.parent,
        )
    except subprocess.CalledProcessError:
        dvi_path = out_dir / f"{stem}.dvi"
        if dvi_path.exists():
            print("build_pdf: platex rerun failed, using existing .dvi")
        else:
            raise
    native_pdf = out_dir / f"{stem}_native.pdf"
    run(["dvipdfmx", "-o", str(native_pdf), str(out_dir / f"{stem}.dvi")], cwd=tex_path.parent)
    run(
        [
            sys.executable,
            str(repo_root / "tools" / "resolve_pdf_links.py"),
            "--in",
            str(native_pdf),
            "--out",
            str(out_dir / f"{stem}.pdf"),
        ],
        cwd=repo_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build thesis_draft.tex from Markdown.")
    parser.add_argument(
        "--abstract", default="analysis/thesis/abstract.md", help="Abstract markdown path."
    )
    parser.add_argument("--intro", default="analysis/thesis/introduction.md", help="Intro markdown path.")
    parser.add_argument(
        "--related-work",
        default="analysis/thesis/related_work.md",
        help="Related work markdown path.",
    )
    parser.add_argument("--methods", default="analysis/thesis/methods.md", help="Methods markdown path.")
    parser.add_argument("--results", default="analysis/thesis/results.md", help="Results markdown path.")
    parser.add_argument(
        "--discussion",
        default="analysis/thesis/discussion.md",
        help="Discussion markdown path.",
    )
    parser.add_argument("--tex", default="paper/thesis_draft.tex", help="TeX file to update.")
    parser.add_argument("--out", default=None, help="Output TeX path (defaults to --tex).")
    parser.add_argument("--pdf", action="store_true", help="Build PDF after updating TeX.")
    parser.add_argument(
        "--outdir", default="paper/out", help="Output directory for PDF build."
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    abstract_path = (repo_root / args.abstract).resolve()
    intro_path = (repo_root / args.intro).resolve()
    related_work_path = (repo_root / args.related_work).resolve()
    methods_path = (repo_root / args.methods).resolve()
    results_path = (repo_root / args.results).resolve()
    discussion_path = (repo_root / args.discussion).resolve()
    tex_path = (repo_root / args.tex).resolve()
    out_path = (repo_root / args.out).resolve() if args.out else tex_path
    out_dir = (repo_root / args.outdir).resolve()

    heading_map = {
        1: "section*",
        2: "section",
        3: "subsection",
        4: "subsubsection",
        5: "paragraph",
        6: "subparagraph",
    }
    converter = MarkdownToLatexConverter(heading_map)

    abstract_text = abstract_path.read_text(encoding="utf-8")
    intro_text = intro_path.read_text(encoding="utf-8")
    related_work_text = related_work_path.read_text(encoding="utf-8")
    methods_text = methods_path.read_text(encoding="utf-8")
    results_text = results_path.read_text(encoding="utf-8")
    discussion_text = discussion_path.read_text(encoding="utf-8")

    abstract_tex = converter.convert(abstract_text)
    intro_tex = converter.convert(intro_text)
    related_work_tex = converter.convert(related_work_text)
    methods_body_text, methods_appendix_text = split_methods_appendices(methods_text)
    methods_tex = converter.convert(methods_body_text)
    results_tex = converter.convert(results_text)
    discussion_tex = converter.convert(discussion_text)

    appendix_tex = ""
    if methods_appendix_text.strip():
        appendix_heading_map = {
            1: "chapter",
            2: "chapter",
            3: "chapter",
            4: "section",
            5: "subsection",
            6: "subsubsection",
        }
        appendix_converter = MarkdownToLatexConverter(appendix_heading_map)
        appendix_md = normalize_appendix_headings(methods_appendix_text)
        appendix_tex = "\\appendix\n" + appendix_converter.convert(appendix_md)

    tex_text = tex_path.read_text(encoding="utf-8")
    tex_text = replace_between_markers(
        tex_text, ABSTRACT_START, ABSTRACT_END, abstract_tex
    )
    tex_text = replace_between_markers(tex_text, INTRO_START, INTRO_END, intro_tex)
    tex_text = replace_between_markers_optional(
        tex_text, RELATED_WORK_START, RELATED_WORK_END, related_work_tex
    )
    tex_text = replace_between_markers(tex_text, METHODS_START, METHODS_END, methods_tex)
    tex_text = replace_between_markers(tex_text, RESULTS_START, RESULTS_END, results_tex)
    tex_text = replace_between_markers(
        tex_text, DISCUSSION_START, DISCUSSION_END, discussion_tex
    )
    if appendix_tex:
        tex_text = replace_between_markers_optional(
            tex_text, APPENDIX_START, APPENDIX_END, appendix_tex
        )
    out_path.write_text(tex_text, encoding="utf-8")

    if args.pdf:
        build_pdf(out_path, out_dir, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
