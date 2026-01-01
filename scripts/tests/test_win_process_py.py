"""
Simple test to verify win_process.py functionality.
Run this directly with Python to test the launcher.
"""
__test__ = False

import subprocess
import sys
import os
from pathlib import Path

# Find repo root
script_dir = Path(__file__).parent
repo_root = script_dir.parent.parent
win_process_py = repo_root / "scripts" / "runsets" / "common" / "win_process.py"

print(f"Repo root: {repo_root}")
print(f"win_process.py: {win_process_py}")
print(f"win_process.py exists: {win_process_py.exists()}")
print()

def _launch(name: str, args: list, input_data: str = None):
    """Run win_process.py with given args and optional stdin input."""
    cmd = [sys.executable, str(win_process_py)] + args
    print(f"=== {name} ===")
    print(f"Command: {' '.join(cmd)}")
    if input_data:
        print(f"Stdin: {input_data}")
    
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root)
        )
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"Stderr: {result.stderr.strip()}")
        
        # Check if PID was returned
        stdout = result.stdout.strip()
        if stdout.isdigit():
            print(f"✓ Valid PID returned: {stdout}")
        elif result.returncode == 0:
            print(f"✓ Command succeeded (output: {stdout})")
        else:
            print(f"✗ Failed")
        print()
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Exception: {e}")
        print()
        return False

def main():
    print("=" * 60)
    print("win_process.py Test Suite (Python)")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Help
    results.append(("Help", _launch("Test 1: --help", ["--help"])))
    
    # Test 2: Simple command
    results.append(("Simple cmd", _launch(
        "Test 2: Simple echo command",
        ["launch", "--cmd", "echo Hello", "--window-style", "hidden", "--cwd", str(repo_root)]
    )))
    
    # Test 3: Command via stdin
    results.append(("Stdin cmd", _launch(
        "Test 3: Command via stdin",
        ["launch", "--cmd-stdin", "--window-style", "hidden", "--cwd", str(repo_root)],
        input_data="echo Test from stdin"
    )))
    
    # Test 4: Command with special characters
    results.append(("Special chars", _launch(
        "Test 4: Command with && ",
        ["launch", "--cmd", "set FOO=bar&& echo FOO set", "--window-style", "hidden", "--cwd", str(repo_root)]
    )))
    
    # Test 5: Command with quotes
    results.append(("Quotes", _launch(
        "Test 5: Command with quotes",
        ["launch", "--cmd", 'echo "Hello World"', "--window-style", "hidden", "--cwd", str(repo_root)]
    )))
    
    # Test 6: Call statement
    results.append(("Call stmt", _launch(
        "Test 6: Call statement",
        ["launch", "--cmd", "call echo Test call", "--window-style", "hidden", "--cwd", str(repo_root)]
    )))
    
    # Test 7: Complex batch-like command
    complex_cmd = 'set RUN_TS=20251231&& set BATCH_SEED=0&& echo Variables set'
    results.append(("Complex cmd", _launch(
        "Test 7: Complex batch command",
        ["launch", "--cmd", complex_cmd, "--window-style", "hidden", "--cwd", str(repo_root)]
    )))
    
    # Test 8: Visible window (optional - comment out for automated testing)
    if os.environ.get("TEST_VISIBLE"):
        results.append(("Visible", _launch(
            "Test 8: Visible window",
            ["launch", "--cmd", "echo Test visible && pause", "--window-style", "normal", "--cwd", str(repo_root)]
        )))
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    print()
    print(f"Total: {passed_count}/{total} passed")
    
    return 0 if passed_count == total else 1

if __name__ == "__main__":
    sys.exit(main())
