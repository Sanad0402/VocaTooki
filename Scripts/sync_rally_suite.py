#!/usr/bin/env python3
"""Rally Sync Orchestrator — Auto-generate pytest from Rally test cases.

Usage:
    python scripts/sync_rally_suite.py
    python scripts/sync_rally_suite.py --dry-run
    python scripts/sync_rally_suite.py --verbose
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from runner.test_generator import RallyTestGenerator


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main():
    """Sync Rally suite → pytest tests."""
    parser = argparse.ArgumentParser(
        description="Auto-generate pytest from Rally test cases"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Keep stale/orphaned generated tests instead of deleting them",
    )
    parser.add_argument(
        "--project-root",
        default=str(project_root),
        help="Project root directory",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("🚀 Rally Test Sync Started")

    try:
        generator = RallyTestGenerator(args.project_root)
        suite = generator.load_rally_suite()

        test_cases = suite.get("test_cases", [])
        logger.info(f"📋 Loaded {len(test_cases)} test cases from Rally suite")

        if args.dry_run:
            logger.info("📋 DRY RUN — Not writing files")
            for tc in test_cases:
                tc_id = tc["id"]
                tc_name = tc["name"]
                logger.info(f"  • {tc_id}: {tc_name}")
            return 0

        logger.info("✨ Generating pytest files...")
        generated_files = generator.generate_all_tests(prune=not args.no_prune)

        logger.info(f"✅ Successfully generated {len(generated_files)} test files")
        for file_path in generated_files:
            logger.info(f"  • {file_path}")

        logger.info("🎉 Rally Sync Complete!")
        return 0

    except FileNotFoundError as e:
        logger.error(f"❌ File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
