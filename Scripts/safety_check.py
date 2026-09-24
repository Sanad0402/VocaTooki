"""One command that says whether a change broke the framework. No app needed.

    python Scripts/safety_check.py

Runs, in order, and stops at the first failure:
  1. compile   - every project .py file still compiles
  2. unit      - the offline contract + behaviour tests (Tests/unit)
  3. collect   - the whole suite still collects, with no errors, and no fewer
                 tests than the baseline

Run it before and after every refactoring step; a step is only done when it
passes. The live smoke runs (a lesson, an exam, a guest case) come on top.
"""

import pathlib
import py_compile
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Tests collected on 2026-09-22: 82 suite tests + the offline unit tests.
# Raise it when tests are added; never lower it to make a change pass.
BASELINE_TESTS = 186
SKIP_DIRS = {".venv", "__pycache__", "_cleanup_backup", ".claude", ".git", "Web"}
# Known-broken files that are not part of the framework (listed, not hidden).
KNOWN_BROKEN = {"Scripts/generate_plan_docx.py"}


def step(title):
    print(f"\n=== {title} ===", flush=True)


def check_compile():
    step("1/3 compile")
    bad = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if SKIP_DIRS & set(path.relative_to(ROOT).parts) or ".worktrees" in str(path):
            continue
        if rel in KNOWN_BROKEN:
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            bad.append(f"{rel}: {e.msg.strip().splitlines()[-1]}")
    for line in bad:
        print("  FAIL", line)
    print(f"  {'OK' if not bad else len(bad)} ({len(KNOWN_BROKEN)} known-broken file(s) skipped: "
          f"{sorted(KNOWN_BROKEN)})")
    return not bad


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})


def check_unit():
    step("2/3 unit (offline contract + behaviour)")
    # -o addopts= : pytest.ini says --maxfail=1; a safety check must list EVERY failure.
    r = run([sys.executable, "-m", "pytest", "Tests/unit", "--noconftest", "-q",
             "-p", "no:cacheprovider", "-o", "addopts="])
    tail = [l for l in r.stdout.splitlines() if l.strip()][-3:]
    print("  " + "\n  ".join(tail))
    return r.returncode == 0


def check_collect():
    step("3/3 collect (the whole suite)")
    r = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"])
    out = r.stdout + r.stderr
    counts = [int(m) for m in re.findall(r"^\S+\.py: (\d+)$", out, flags=re.M)]
    # pytest reports a module that cannot even be imported as "ERROR ..."
    errors = [l for l in out.splitlines()
              if l.startswith("ERROR") or "errors during collection" in l]
    total = sum(counts)
    ok = r.returncode in (0, 5) and total >= BASELINE_TESTS and not errors
    print(f"  {total} tests in {len(counts)} files (baseline {BASELINE_TESTS})"
          + (f"; errors: {errors[:5]}" if errors else ""))
    return ok


def main():
    for check in (check_compile, check_unit, check_collect):
        if not check():
            print("\nSAFETY CHECK FAILED — do not commit this step.")
            return 1
    print("\nSAFETY CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
