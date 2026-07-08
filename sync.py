#!/usr/bin/env python3
"""Quick-start Rally sync — run from project root.

Usage:
    python sync.py              # Generate all tests
    python sync.py --dry-run    # Preview what would be generated
    python sync.py --help       # Show help
"""

import subprocess
import sys

result = subprocess.run(
    [sys.executable, "scripts/sync_rally_suite.py"] + sys.argv[1:],
    cwd=".",
)
sys.exit(result.returncode)
