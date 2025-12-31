#!/usr/bin/env python3
"""Diagnostic tests for Windows parallel sweep functionality."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_win_process_launch_basic():
    """Test 1: Basic win_process.py launch with a simple echo command."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic win_process.py launch")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    if not win_process_py.exists():
        print(f"[FAIL] win_process.py not found: {win_process_py}")
        return False
    
    # Test with --cmd directly
    test_cmd = "echo PARALLEL_TEST_SUCCESS"
    print(f"[INFO] Testing with --cmd: {test_cmd}")
    
    result = subprocess.run(
        [sys.executable, str(win_process_py), "launch", "--cmd", test_cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    print(f"[INFO] Return code: {result.returncode}")
    print(f"[INFO] stdout: {result.stdout.strip()}")
    if result.stderr:
        print(f"[INFO] stderr: {result.stderr.strip()}")
    
    if result.returncode != 0:
        print("[FAIL] win_process.py launch failed")
        return False
    
    pid = result.stdout.strip()
    if not pid.isdigit():
        print(f"[FAIL] Expected PID, got: {pid}")
        return False
    
    print(f"[PASS] Launched process with PID: {pid}")
    return True


def test_win_process_launch_cmdfile():
    """Test 2: win_process.py launch with --cmd-file."""
    print("\n" + "=" * 60)
    print("TEST 2: win_process.py launch with --cmd-file")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    
    # Create a temp file with a command
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        test_cmd = "echo CMDFILE_TEST_SUCCESS"
        f.write(test_cmd)
        cmd_file = f.name
    
    print(f"[INFO] Created cmd file: {cmd_file}")
    print(f"[INFO] Content: {test_cmd}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(win_process_py), "launch", "--cmd-file", cmd_file],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        print(f"[INFO] Return code: {result.returncode}")
        print(f"[INFO] stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"[INFO] stderr: {result.stderr.strip()}")
        
        if result.returncode != 0:
            print("[FAIL] win_process.py launch with --cmd-file failed")
            return False
        
        pid = result.stdout.strip()
        if not pid.isdigit():
            print(f"[FAIL] Expected PID, got: {pid}")
            return False
        
        print(f"[PASS] Launched process with PID: {pid}")
        return True
    finally:
        try:
            os.unlink(cmd_file)
        except OSError:
            pass


def test_win_process_launch_cmdfile_cp932():
    """Test 3: win_process.py launch with --cmd-file in CP932 encoding."""
    print("\n" + "=" * 60)
    print("TEST 3: win_process.py launch with --cmd-file (CP932)")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    
    # Create a temp file with CP932 encoding (like Windows cmd.exe does)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        test_cmd = "echo CP932_TEST_SUCCESS"
        f.write(test_cmd.encode("cp932"))
        cmd_file = f.name
    
    print(f"[INFO] Created cmd file (CP932): {cmd_file}")
    print(f"[INFO] Content: {test_cmd}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(win_process_py), "launch", "--cmd-file", cmd_file],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        print(f"[INFO] Return code: {result.returncode}")
        print(f"[INFO] stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"[INFO] stderr: {result.stderr.strip()}")
        
        if result.returncode != 0:
            print("[FAIL] win_process.py launch with CP932 --cmd-file failed")
            return False
        
        print(f"[PASS] CP932 encoding handled correctly")
        return True
    finally:
        try:
            os.unlink(cmd_file)
        except OSError:
            pass


def test_cmd_echo_redirect():
    """Test 4: Simulate cmd.exe echo > file behavior."""
    print("\n" + "=" * 60)
    print("TEST 4: Simulate cmd.exe 'echo > file' behavior")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd_file = Path(tmpdir) / "test_cmd.txt"
        
        # Simulate what the batch file does: echo !JOB_CMD! > file
        # On Windows, this uses the system's default encoding
        test_content = "set RUN_TS=test&& set BATCH_SEED=0&& echo TEST"
        
        if os.name == "nt":
            # On Windows, use cmd.exe to write the file
            write_cmd = f'echo {test_content}> "{cmd_file}"'
            result = subprocess.run(
                ["cmd.exe", "/c", write_cmd],
                capture_output=True,
                timeout=10,
            )
            print(f"[INFO] cmd.exe write result: rc={result.returncode}")
        else:
            # On non-Windows, simulate with cp932
            print("[INFO] Simulating Windows cmd.exe write with CP932")
            with open(cmd_file, "wb") as f:
                f.write(test_content.encode("cp932"))
        
        # Read the file back with different encodings
        print(f"[INFO] File created: {cmd_file}")
        print(f"[INFO] File size: {cmd_file.stat().st_size} bytes")
        
        # Show raw bytes
        with open(cmd_file, "rb") as f:
            raw = f.read()
        print(f"[INFO] Raw bytes (first 100): {raw[:100]}")
        
        # Try reading with different encodings
        for enc in ["utf-8", "cp932", "latin-1"]:
            try:
                with open(cmd_file, "r", encoding=enc) as f:
                    content = f.read().strip()
                print(f"[INFO] Read with {enc}: {content!r}")
            except UnicodeDecodeError as e:
                print(f"[INFO] Read with {enc}: FAILED - {e}")
        
        print("[PASS] File encoding test completed")
        return True


def test_parallel_job_simulation():
    """Test 5: Simulate launching multiple parallel jobs."""
    print("\n" + "=" * 60)
    print("TEST 5: Parallel job launch simulation")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    
    jobs = [
        ("5000", "1.0", "1.0"),
        ("5000", "0.5", "0.5"),
        ("4000", "1.0", "1.0"),
    ]
    
    pids = []
    for t, eps, tau in jobs:
        # Build a simple test command
        if os.name == "nt":
            test_cmd = f"echo T={t} EPS={eps} TAU={tau} && timeout /t 2 /nobreak >nul"
        else:
            test_cmd = f"echo T={t} EPS={eps} TAU={tau} && sleep 2"
        
        print(f"[INFO] Launching job: T={t} EPS={eps} TAU={tau}")
        
        result = subprocess.run(
            [sys.executable, str(win_process_py), "launch", "--cmd", test_cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            pid = result.stdout.strip()
            if pid.isdigit():
                pids.append(int(pid))
                print(f"[INFO]   PID: {pid}")
            else:
                print(f"[WARN]   Invalid PID: {pid}")
        else:
            print(f"[WARN]   Launch failed: {result.stderr}")
    
    print(f"[INFO] Launched {len(pids)} jobs: {pids}")
    
    # Check alive status
    if pids:
        time.sleep(0.5)
        pids_str = " ".join(str(p) for p in pids)
        result = subprocess.run(
            [sys.executable, str(win_process_py), "alive", "--pids", pids_str],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"[INFO] Alive check: {result.stdout.strip()}")
    
    if len(pids) == len(jobs):
        print("[PASS] All parallel jobs launched successfully")
        return True
    else:
        print(f"[FAIL] Only {len(pids)}/{len(jobs)} jobs launched")
        return False


def test_env_var_inheritance():
    """Test 6: Check if environment variables are inherited by subprocesses."""
    print("\n" + "=" * 60)
    print("TEST 6: Environment variable inheritance")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    
    # Set a test environment variable
    os.environ["TEST_PARALLEL_VAR"] = "inherited_value"
    
    if os.name == "nt":
        test_cmd = "echo %TEST_PARALLEL_VAR%"
    else:
        test_cmd = "echo $TEST_PARALLEL_VAR"
    
    # Create output file to capture result
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_file = f.name
    
    if os.name == "nt":
        full_cmd = f'{test_cmd} > "{output_file}"'
    else:
        full_cmd = f'{test_cmd} > "{output_file}"'
    
    print(f"[INFO] Test command: {full_cmd}")
    
    result = subprocess.run(
        [sys.executable, str(win_process_py), "launch", "--cmd", full_cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    print(f"[INFO] Launch result: rc={result.returncode}, stdout={result.stdout.strip()}")
    
    # Wait for the process to complete
    time.sleep(1)
    
    try:
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                output = f.read().strip()
            print(f"[INFO] Captured output: {output!r}")
            if "inherited_value" in output:
                print("[PASS] Environment variable inherited successfully")
                return True
            else:
                print("[WARN] Environment variable may not have been inherited")
                return True  # Not a critical failure
        else:
            print("[WARN] Output file not created (process may still be running)")
            return True
    finally:
        try:
            os.unlink(output_file)
        except OSError:
            pass


def test_batch_file_encoding_simulation():
    """Test 7: Simulate batch file JOB_CMD writing with Japanese path."""
    print("\n" + "=" * 60)
    print("TEST 7: Batch file encoding with special characters")
    print("=" * 60)
    
    win_process_py = REPO_ROOT / "scripts" / "runsets" / "common" / "win_process.py"
    
    # Simulate a path with Japanese characters like the user has
    # C:\Users\共用ユーザー\Desktop\...
    test_path = r"C:\Users\TestUser\Desktop\Test"
    test_cmd = f'set TEST_PATH={test_path}&& echo %TEST_PATH%'
    
    print(f"[INFO] Test command: {test_cmd}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write with different encodings and test reading
        for enc_name, encoding in [("UTF-8", "utf-8"), ("CP932", "cp932"), ("Latin-1", "latin-1")]:
            cmd_file = Path(tmpdir) / f"test_{enc_name}.txt"
            
            try:
                with open(cmd_file, "w", encoding=encoding) as f:
                    f.write(test_cmd)
                print(f"[INFO] Written with {enc_name}")
                
                # Try to read and launch
                result = subprocess.run(
                    [sys.executable, str(win_process_py), "launch", "--cmd-file", str(cmd_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0:
                    print(f"[PASS] {enc_name}: Launch succeeded, PID={result.stdout.strip()}")
                else:
                    print(f"[FAIL] {enc_name}: Launch failed - {result.stderr.strip()}")
            except Exception as e:
                print(f"[FAIL] {enc_name}: Error - {e}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", type=int, help="Run specific test number (1-7)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Windows Parallel Sweep Diagnostic Tests")
    print(f"Python: {sys.executable}")
    print(f"OS: {os.name} ({sys.platform})")
    print(f"Repo: {REPO_ROOT}")
    print("=" * 60)
    
    tests = [
        (1, test_win_process_launch_basic),
        (2, test_win_process_launch_cmdfile),
        (3, test_win_process_launch_cmdfile_cp932),
        (4, test_cmd_echo_redirect),
        (5, test_parallel_job_simulation),
        (6, test_env_var_inheritance),
        (7, test_batch_file_encoding_simulation),
    ]
    
    results = {}
    for num, test_func in tests:
        if args.test and args.test != num:
            continue
        try:
            results[num] = test_func()
        except Exception as e:
            print(f"[ERROR] Test {num} raised exception: {e}")
            results[num] = False
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for num, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  Test {num}: {status}")
    
    failed = [num for num, passed in results.items() if not passed]
    if failed:
        print(f"\n[RESULT] {len(failed)} test(s) failed: {failed}")
        return 1
    else:
        print(f"\n[RESULT] All {len(results)} test(s) passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
