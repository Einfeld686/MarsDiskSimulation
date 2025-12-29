from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts" / "runsets" / "windows" / "preflight_checks.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("preflight_checks", PREFLIGHT_PATH)
    assert spec and spec.loader, f"Failed to load {PREFLIGHT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_overrides(path: Path, archive_dir: str) -> None:
    _write_text(
        path,
        "\n".join(
            [
                "io.archive.enabled=true",
                f"io.archive.dir={archive_dir}",
                "io.archive.merge_target=external",
                "io.archive.verify_level=standard_plus",
                "io.archive.keep_local=metadata",
                "",
            ]
        ),
    )


def _run_main(module: object, argv: list[str], monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", argv)
    return module.main()


def test_unc_warning_not_duplicated(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    config = tmp_path / "config.yml"
    overrides = tmp_path / "overrides.txt"
    cmd = tmp_path / "noop.cmd"
    _write_text(config, "dummy: 1\n")
    _write_overrides(overrides, r"E:\archive")
    _write_text(cmd, "echo ok\n")

    argv = [
        "preflight_checks.py",
        "--repo-root",
        str(tmp_path),
        "--config",
        str(config),
        "--overrides",
        str(overrides),
        "--out-root",
        r"\\server\share",
        "--cmd",
        str(cmd),
        "--skip-env",
        "--skip-repo-scan",
    ]
    rc = _run_main(module, argv, monkeypatch)
    out = capsys.readouterr().out

    assert rc == 0
    assert out.count("out_root is a UNC path") == 1


def test_comment_only_delayed_expansion_is_ignored(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    config = tmp_path / "config.yml"
    overrides = tmp_path / "overrides.txt"
    cmd = tmp_path / "comment_only.cmd"
    _write_text(config, "dummy: 1\n")
    _write_overrides(overrides, r"E:\temp!dir")
    _write_text(
        cmd,
        "\n".join(
            [
                "@echo off",
                "rem enabledelayedexpansion should be ignored",
                ":: cmd /v:on should be ignored",
                "rem setlocal enabledelayedexpansion should be ignored",
                "@rem cmd /v:on should also be ignored",
                "echo ok",
                "",
            ]
        ),
    )

    argv = [
        "preflight_checks.py",
        "--repo-root",
        str(tmp_path),
        "--config",
        str(config),
        "--overrides",
        str(overrides),
        "--cmd",
        str(cmd),
        "--skip-env",
        "--skip-repo-scan",
    ]
    rc = _run_main(module, argv, monkeypatch)
    out = capsys.readouterr().out

    assert rc == 0
    assert "contains '!': E:\\temp!dir" in out
    assert "[error]" not in out


def test_collect_cmd_paths_includes_bat_and_uppercase(tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path / "cmds"
    root.mkdir()
    _write_text(root / "a.CMD", "echo ok\n")
    _write_text(root / "b.bat", "echo ok\n")
    _write_text(root / "c.txt", "echo ok\n")

    errors: list[str] = []
    paths = module._collect_cmd_paths([], [str(root)], errors, [])
    names = {path.name for path in paths}

    assert not errors
    assert "a.CMD" in names
    assert "b.bat" in names
    assert "c.txt" not in names


def test_scan_cmd_file_handles_bom_first_line(tmp_path: Path) -> None:
    module = _load_module()
    cmd_path = tmp_path / "bom.cmd"
    cmd_path.write_bytes(b"\xef\xbb\xbfset FOO=C:\\temp!dir\r\n")
    errors: list[str] = []
    warnings: list[str] = []

    module._scan_cmd_file(cmd_path, errors, warnings, cmd_unsafe_error=True)

    assert any("contains '!'" in err for err in errors)


def test_cmd_unsafe_issue_flags_literal_bang_even_with_percent() -> None:
    module = _load_module()
    errors: list[str] = []
    warnings: list[str] = []

    module._cmd_unsafe_issue(
        "value",
        r"%TEMP%\bang!dir",
        errors,
        warnings,
        cmd_unsafe_error=True,
        allow_expansion=True,
    )

    assert any("contains '!'" in err for err in errors)


def test_cmd_unsafe_issue_allows_bang_tokens() -> None:
    module = _load_module()
    errors: list[str] = []
    warnings: list[str] = []

    module._cmd_unsafe_issue(
        "value",
        r"C:\!TEMP!\ok",
        errors,
        warnings,
        cmd_unsafe_error=True,
        allow_expansion=True,
    )

    assert not errors


def test_check_python_accepts_py(monkeypatch) -> None:
    module = _load_module()

    def fake_which(name: str):
        if name == "python":
            return None
        if name == "py":
            return "C:\\Windows\\py.exe"
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)
    errors: list[str] = []
    warnings: list[str] = []

    module._check_python(errors, warnings, warn_only=False)

    assert not errors
    assert any("python not found" in warning for warning in warnings)


def test_check_cmd_warn_only(monkeypatch) -> None:
    module = _load_module()

    def fake_which(_name: str):
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)
    errors: list[str] = []
    warnings: list[str] = []

    module._check_cmd("git", errors, warnings, warn_only=True)

    assert not errors
    assert any("git not found" in warning for warning in warnings)


def test_has_invalid_windows_chars_allows_extended_prefix() -> None:
    module = _load_module()
    assert not module._has_invalid_windows_chars(r"\\?\C:\temp\file.txt")
    assert module._has_invalid_windows_chars(r"\\?\C:\temp?bad\file.txt")


def test_check_name_component_rejects_backslash() -> None:
    module = _load_module()
    errors: list[str] = []

    module._check_name_component(r"bad\\name", r"bad\\name", errors)

    assert any("contains '\\\\'" in err for err in errors)
