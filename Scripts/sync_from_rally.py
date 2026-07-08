#!/usr/bin/env python3
"""Sync test cases from Rally to local JSON, then generate pytest.

Usage:
    python scripts/sync_from_rally.py --project YOUR_PROJECT_ID
    python scripts/sync_from_rally.py --project YOUR_PROJECT_ID --dry-run
"""

import sys
import os
import argparse
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from runner.rally_api import create_client_from_env
from runner.test_generator import RallyTestGenerator


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main():
    """Sync from Rally → JSON → generate pytest."""
    parser = argparse.ArgumentParser(
        description="Sync test cases from Rally and generate pytest"
    )
    parser.add_argument(
        "--project", required=True, help="Rally project ID (e.g., 12345678)"
    )
    parser.add_argument(
        "--env-file",
        default="rally.env",
        help="Path to rally.env file (default: rally.env)",
    )
    parser.add_argument(
        "--output",
        default="data/rally_suite.json",
        help="Output JSON file (default: data/rally_suite.json)",
    )
    parser.add_argument(
        "--automated-only",
        action="store_true",
        default=True,
        help="Only sync test cases marked as automated",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without syncing",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Only sync, don't generate pytest",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("🚀 Rally Sync Started")

    try:
        # Create Rally client
        logger.info("📡 Connecting to Rally...")
        client = create_client_from_env(args.env_file)

        if not client:
            logger.error("❌ Could not create Rally client")
            return 1

        # Test connection
        if not client.test_connection():
            logger.error("❌ Failed to connect to Rally")
            logger.info("💡 Check RALLY_API_URL and RALLY_API_TOKEN in rally.env")
            return 1

        logger.info("✅ Connected to Rally")

        if args.dry_run:
            logger.info("📋 DRY RUN — Not syncing data")
            logger.info(f"Would sync project: {args.project}")
            logger.info(f"Would save to: {args.output}")
            return 0

        # Sync from Rally to JSON
        logger.info(f"📥 Syncing from Rally project {args.project}...")
        success = client.sync_to_json(
            project_id=args.project,
            output_file=args.output,
            automated_only=args.automated_only,
        )

        if not success:
            logger.error("❌ Rally sync failed")
            return 1

        logger.info(f"✅ Synced to {args.output}")

        if args.skip_generate:
            logger.info("⏭️  Skipping test generation (--skip-generate)")
            return 0

        # Generate pytest from synced JSON
        logger.info("✨ Generating pytest from Rally test cases...")
        generator = RallyTestGenerator(str(project_root))
        generated_files = generator.generate_all_tests()

        logger.info(f"✅ Generated {len(generated_files)} test files")
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
