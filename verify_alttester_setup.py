#!/usr/bin/env python
"""
AltTester Setup Verification Script

Checks if your environment is ready for AltTester MCP automation.
Run this before starting your test session.

Usage:
    python verify_alttester_setup.py
"""

import subprocess
import sys
import os
from pathlib import Path


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def check_pass(msg):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def check_fail(msg):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def check_warning(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def check_command(cmd, name):
    """Check if a command is available."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            shell=True
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, None


def verify_alttester_cli():
    """Check if AltTester CLI is installed and in PATH."""
    print_header("1. AltTester CLI Installation")

    success, output = check_command("alttester --version", "AltTester CLI")

    if success and output:
        check_pass(f"AltTester CLI found: {output}")
        return True
    else:
        check_fail("AltTester CLI not found in PATH")
        print(f"   > Install: Launch AltTester Desktop and click 'Download'")
        print(f"   > Or: Settings > Configure AltTester AI Extension > Setup")
        print(f"   > Then restart your terminal (PATH updates apply to new sessions)")
        return False


def verify_python_environment():
    """Check Python version and key packages."""
    print_header("2. Python Environment")

    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    check_pass(f"Python {python_version}")

    # Check pytest
    try:
        import pytest
        check_pass(f"pytest {pytest.__version__} installed")
    except ImportError:
        check_fail("pytest not installed")
        return False

    # Check key packages
    required = ["pytest"]
    for pkg in required:
        try:
            __import__(pkg)
            check_pass(f"{pkg} available")
        except ImportError:
            check_fail(f"{pkg} not installed")

    return True


def verify_project_files():
    """Check if required project files exist."""
    print_header("3. Project Files")

    files_to_check = {
        ".mcp.json": "MCP server configuration",
        ".claude/settings.json": "Claude Code settings",
        "Utilities/alttester_mcp.py": "AltTester MCP wrapper",
        "Tests/test_alttester_mcp_example.py": "Example tests",
        "ALTTESTER_MCP_SETUP.md": "Setup documentation",
    }

    project_root = Path(__file__).parent
    all_present = True

    for file_path, description in files_to_check.items():
        full_path = project_root / file_path
        if full_path.exists():
            check_pass(f"{file_path}")
        else:
            check_fail(f"{file_path} — {description}")
            all_present = False

    return all_present


def verify_mcp_server():
    """Check if MCP server is running."""
    print_header("4. AltTester MCP Server Status")

    print("Checking if MCP server is running on localhost:3000...")
    success, output = check_command("alttester status --port 3000", "MCP Server")

    if success:
        check_pass("MCP server is running")
        return True
    else:
        check_warning("MCP server is not running")
        print(f"   > Start it in a separate terminal:")
        print(f"   > Run: alttester mcp")
        print(f"   > Keep that terminal open during tests")
        return False


def verify_game_connection():
    """Check if a game is accessible via AltTester."""
    print_header("5. Game Connection")

    print("Checking if any game is registered with AltTester...")
    success, output = check_command("alttester apps --timeout 5", "Game Connection")

    if success and output:
        check_pass("Game detected")
        print(f"   {output}")
        return True
    else:
        check_warning("No game detected")
        print(f"   > Start your game with AltTester SDK enabled")
        print(f"   > Ensure it's listening on port 13000")
        print(f"   > Then run: alttester apps")
        return False


def verify_test_structure():
    """Check if test files are correctly structured."""
    print_header("6. Test File Structure")

    project_root = Path(__file__).parent
    test_file = project_root / "Tests" / "test_alttester_mcp_example.py"

    if test_file.exists():
        check_pass(f"Example test file found")

        # Try to parse it
        try:
            with open(test_file) as f:
                content = f.read()
                if "AltTesterMCP" in content:
                    check_pass("Test file contains AltTesterMCP imports")
                if "def test_" in content:
                    check_pass("Test functions defined")
                    return True
        except Exception as e:
            check_fail(f"Could not read test file: {e}")
    else:
        check_fail("Example test file not found")

    return False


def print_summary(results):
    """Print test summary and next steps."""
    print_header("Summary")

    passed = sum(1 for r in results if r)
    total = len(results)

    status_color = Colors.GREEN if passed == total else Colors.YELLOW
    print(f"{status_color}{passed}/{total} checks passed{Colors.RESET}\n")

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}SUCCESS: Your environment is ready!{Colors.RESET}\n")
        print("Next steps:")
        print("  1. Ensure your game is running with AltTester SDK")
        print("  2. Start MCP server: alttester mcp (in separate terminal)")
        print("  3. Run tests: pytest Tests/test_alttester_mcp_example.py -v -s")
        print()
    else:
        print(f"{Colors.YELLOW}NOTE: Some checks failed. Fix issues above before proceeding.{Colors.RESET}\n")


def main():
    """Run all verification checks."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}AltTester MCP Setup Verification{Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

    results = [
        verify_alttester_cli(),
        verify_python_environment(),
        verify_project_files(),
        verify_mcp_server(),
        verify_game_connection(),
        verify_test_structure(),
    ]

    print_summary(results)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
