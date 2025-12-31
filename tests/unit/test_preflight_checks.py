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


def _scan_cmd_text(
    module: object,
    tmp_path: Path,
    text: str,
    cmd_unsafe_error: bool = False,
    profile: str = "default",
    debug: bool = False,
):
    path = tmp_path / "scan.cmd"
    path.write_text(text, encoding="utf-8", newline="\r\n")
    errors: list[object] = []
    warnings: list[object] = []
    infos: list[object] = []
    module._scan_cmd_file(path, errors, warnings, infos, cmd_unsafe_error, profile, None, debug)
    return errors, warnings, infos


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


def test_cmd_v_on_triggers_cmd_unsafe_error(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    config = tmp_path / "config.yml"
    overrides = tmp_path / "overrides.txt"
    cmd = tmp_path / "delayed.cmd"
    _write_text(config, "dummy: 1\n")
    _write_overrides(overrides, r"E:\temp!dir")
    _write_text(cmd, "cmd /v:on /c echo ok\n")

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

    assert rc == 1
    assert "contains '!': E:\\temp!dir" in out
    assert "[error]" in out


def test_validate_python_exe_tokens_rejects_dash_arg(tmp_path: Path) -> None:
    module = _load_module()
    errors: list[object] = []
    warnings: list[object] = []

    ok = module._validate_python_exe_tokens(
        "python_exe",
        "py",
        ["-"],
        errors,
        warnings,
        warn_only=False,
    )

    assert not ok
    assert any(err.rule == "tool.python_exe_arg_dash" for err in errors)


def test_validate_python_exe_tokens_rejects_version_arg_non_py(tmp_path: Path) -> None:
    module = _load_module()
    errors: list[object] = []
    warnings: list[object] = []

    ok = module._validate_python_exe_tokens(
        "python_exe",
        "python",
        ["-3.11"],
        errors,
        warnings,
        warn_only=False,
    )

    assert not ok
    assert any(err.rule == "tool.python_exe_version_arg_non_py" for err in errors)


def test_allowlist_missing_rules_warns(tmp_path: Path) -> None:
    module = _load_module()
    allowlist = tmp_path / "allowlist.txt"
    _write_text(allowlist, "scripts/foo.cmd\n")
    warnings: list[object] = []

    entries = module._load_cmd_allowlist(allowlist, warnings)

    assert not entries
    assert any(warn.rule == "cmd.allowlist.missing_rules" for warn in warnings)


def test_collect_cmd_paths_includes_bat_and_uppercase(tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path / "cmds"
    root.mkdir()
    _write_text(root / "a.CMD", "echo ok\n")
    _write_text(root / "b.bat", "echo ok\n")
    _write_text(root / "c.txt", "echo ok\n")

    errors: list[object] = []
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
    errors: list[object] = []
    warnings: list[object] = []

    infos: list[object] = []

    module._scan_cmd_file(
        cmd_path,
        errors,
        warnings,
        infos,
        cmd_unsafe_error=True,
        profile="default",
        allowlist_rules=None,
    )

    assert any("contains '!'" in err.message for err in errors)


def test_cmd_utf16_bom_errors(tmp_path: Path) -> None:
    module = _load_module()
    cmd_path = tmp_path / "utf16.cmd"
    cmd_path.write_bytes(b"\xff\xfe@\x00e\x00c\x00h\x00o\x00\r\x00\n\x00")
    errors: list[object] = []
    warnings: list[object] = []
    infos: list[object] = []

    module._scan_cmd_file(
        cmd_path,
        errors,
        warnings,
        infos,
        cmd_unsafe_error=False,
        profile="default",
        allowlist_rules=None,
    )

    assert any(err.rule == "cmd.encoding.utf16" for err in errors)


def test_cmd_nul_bytes_warns(tmp_path: Path) -> None:
    module = _load_module()
    cmd_path = tmp_path / "nul.cmd"
    cmd_path.write_bytes(b"@\x00e\x00c\x00h\x00o\x00\r\x00\n\x00")
    errors: list[object] = []
    warnings: list[object] = []
    infos: list[object] = []

    module._scan_cmd_file(
        cmd_path,
        errors,
        warnings,
        infos,
        cmd_unsafe_error=False,
        profile="default",
        allowlist_rules=None,
    )

    assert any(warn.rule == "cmd.encoding.nul" for warn in warnings)


def test_for_single_percent_is_error(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "@echo off\nfor %i in (a b) do echo %i\n",
    )

    assert any(err.rule == "cmd.for.single_percent" for err in errors)
    assert not warnings


def test_set_space_around_equals_warns(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "set VAR =value\n",
    )

    assert not errors
    assert any(warn.rule == "cmd.set.space_around_equals" for warn in warnings)


def test_setlocal_missing_warns(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "set VAR=value\n",
    )

    assert not errors
    assert any(warn.rule == "cmd.setlocal.missing" for warn in warnings)


def test_interactive_pause_in_ci_is_error(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "pause\n",
        profile="ci",
    )

    assert any(err.rule == "cmd.interactive.pause" for err in errors)
    assert not warnings


def test_delayed_expansion_info(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, infos = _scan_cmd_text(
        module,
        tmp_path,
        "setlocal enabledelayedexpansion\n",
    )

    assert not errors
    assert not warnings
    assert any(info.rule == "cmd.delayed_expansion.enabled" for info in infos)


def test_delayed_expansion_debug_info(tmp_path: Path) -> None:
    module = _load_module()
    errors, warnings, infos = _scan_cmd_text(
        module,
        tmp_path,
        "cmd /v:on /c echo !FOO!\n",
        debug=True,
    )

    assert not errors
    assert not warnings
    assert any(info.rule == "cmd.delayed_expansion.cmd_v_on" for info in infos)
    assert any(info.rule == "cmd.delayed_expansion.token" for info in infos)


def test_pathext_missing_is_error_in_ci(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("PATHEXT", raising=False)
    errors: list[object] = []
    warnings: list[object] = []

    module._check_pathext(errors, warnings, profile="ci")

    assert any(err.rule == "env.pathext.missing_or_suspicious" for err in errors)


def test_delayed_expansion_before_enabled_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "echo !FOO!\nsetlocal enabledelayedexpansion\n",
    )

    assert any(warn.rule == "cmd.delayed_expansion.before_enabled" for warn in warnings)


def test_errorlevel_zero_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "if errorlevel 0 echo ok\n",
    )

    assert any(warn.rule == "cmd.errorlevel.zero" for warn in warnings)


def test_errorlevel_ascending_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "if errorlevel 1 echo bad\nif errorlevel 2 echo worse\n",
    )

    assert any(warn.rule == "cmd.errorlevel.ascending" for warn in warnings)


def test_setx_ci_is_error(tmp_path: Path) -> None:
    module = _load_module()
    errors, _warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "setx FOO bar\n",
        profile="ci",
    )

    assert any(err.rule == "cmd.env.setx" for err in errors)


def test_endlocal_before_setlocal_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "endlocal\nsetlocal\n",
    )

    assert any(warn.rule == "cmd.setlocal.order" for warn in warnings)


def test_popd_more_than_pushd_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "pushd C:\\Temp\npopd\npopd\n",
    )

    assert any(warn.rule == "cmd.pushd_popd.unbalanced" for warn in warnings)


def test_cmd_unsafe_issue_flags_literal_bang_even_with_percent() -> None:
    module = _load_module()
    errors: list[object] = []
    warnings: list[object] = []

    module._cmd_unsafe_issue(
        "value",
        r"%TEMP%\bang!dir",
        errors,
        warnings,
        cmd_unsafe_error=True,
        allow_expansion=True,
    )

    assert any("contains '!'" in err.message for err in errors)


def test_cmd_unsafe_issue_allows_bang_tokens() -> None:
    module = _load_module()
    errors: list[object] = []
    warnings: list[object] = []

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
    errors: list[object] = []
    warnings: list[object] = []

    module._check_python(errors, warnings, warn_only=False, python_exe=None)

    assert not errors
    assert any("python not found" in warning.message for warning in warnings)


def test_check_cmd_warn_only(monkeypatch) -> None:
    module = _load_module()

    def fake_which(_name: str):
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)
    errors: list[object] = []
    warnings: list[object] = []

    module._check_cmd("git", errors, warnings, warn_only=True)

    assert not errors
    assert any("git not found" in warning.message for warning in warnings)


def test_has_invalid_windows_chars_allows_extended_prefix() -> None:
    module = _load_module()
    assert not module._has_invalid_windows_chars(r"\\?\C:\temp\file.txt")
    assert module._has_invalid_windows_chars(r"\\?\C:\temp?bad\file.txt")


def test_check_name_component_rejects_backslash() -> None:
    module = _load_module()
    errors: list[object] = []

    module._check_name_component(r"bad\\name", r"bad\\name", errors)

    assert any("invalid Windows name" in err.message for err in errors)


def test_cmd_non_ascii_without_chcp_warns(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, "echo あ\n")

    assert any("non-ASCII without chcp" in warning.message for warning in warnings)


def test_cmd_non_ascii_with_chcp_suppresses_warning(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, "chcp 65001\necho あ\n")

    assert not any("non-ASCII without chcp" in warning.message for warning in warnings)


def test_cmd_cd_checks(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "\n".join(
            [
                "cd C:\\Temp",
                "cd /d D:\\Data",
                "cd \\\\server\\share",
                "",
            ]
        ),
    )

    assert any("cd without /d" in warning.message for warning in warnings)
    assert any("cd uses UNC path" in warning.message for warning in warnings)


def test_cmd_start_title_warning(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "\n".join(
            [
                'start "C:\\\\Program Files\\\\App.exe"',
                'start "" "C:\\\\Program Files\\\\App.exe"',
                "",
            ]
        ),
    )

    assert (
        sum("start uses quoted arg without empty title" in warning.message for warning in warnings) == 1
    )


def test_cmd_call_missing_warning(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "\n".join(
            [
                "scripts\\\\foo.cmd",
                "call scripts\\\\bar.cmd",
                "set SCRIPT=scripts\\\\baz.cmd",
                "",
            ]
        ),
    )

    assert sum("invokes batch without call" in warning.message for warning in warnings) == 1


def test_cmd_line_length_warning(tmp_path: Path) -> None:
    module = _load_module()
    long_arg = "a" * (module.CMD_LINE_WARN_LEN + 10)
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, f"echo {long_arg}\n")

    assert any("cmd line length" in warning.message for warning in warnings)


def test_cmd_line_length_with_caret_continuation_warns(tmp_path: Path) -> None:
    module = _load_module()
    half = module.CMD_LINE_WARN_LEN // 2
    part1 = "a" * half
    part2 = "b" * (half + 10)
    text = f"echo {part1}^\n{part2}\n"
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, text)

    assert any("cmd line length" in warning.message for warning in warnings)


def test_cmd_dash_option_warning_and_error(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, "where -foo\n")

    assert any(warn.rule == "cmd.option.dash" for warn in warnings)

    errors, _warnings, _infos = _scan_cmd_text(
        module,
        tmp_path,
        "findstr -bar\n",
        profile="ci",
    )

    assert any(err.rule == "cmd.option.dash" for err in errors)


def test_cmd_invocation_ignores_cmd_flags(tmp_path: Path) -> None:
    module = _load_module()
    text = (
        '"%PYTHON_EXE%" preflight_checks.py --cmd "scripts\\\\foo.cmd" --cmd-root scripts\n'
    )
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, text)

    assert not any(warn.rule == "cmd.interactive.cmd" for warn in warnings)


def test_cmd_invocation_detects_cmd_without_c(tmp_path: Path) -> None:
    module = _load_module()
    _errors, warnings, _infos = _scan_cmd_text(module, tmp_path, "cmd /k echo ok\n")

    assert any(warn.rule == "cmd.interactive.cmd" for warn in warnings)
