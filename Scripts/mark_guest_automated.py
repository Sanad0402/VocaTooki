"""Set Method = "Automated" on every test case in Rally's Guest Test Folder.

The Automated flag is what the team uses to say "generate and run code for this
case" — the local sync only fetches Method = "Automated" cases
(``rally_api.get_test_cases``). Guest cases are written manually first, so this
flips the whole folder in one go.

This WRITES to Rally. Run --dry-run first: it lists every case and the change it
would make, and touches nothing.

Usage:
    python Scripts/mark_guest_automated.py --project 622679112169 --dry-run
    python Scripts/mark_guest_automated.py --project 622679112169
    python Scripts/mark_guest_automated.py --project 622679112169 --method Manual
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner.rally_api import create_client_from_env  # noqa: E402

logger = logging.getLogger("mark_guest_automated")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True, help="Rally project ObjectID")
    ap.add_argument("--folder", default="guest",
                    help="Test Folder name to match, case-insensitive (default: guest)")
    ap.add_argument("--method", default="Automated",
                    help='Value to set (default: Automated; use "Manual" to undo)')
    ap.add_argument("--env-file", default="rally.env")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would change, write nothing")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client = create_client_from_env(args.env_file)
    if not client or not client.test_connection():
        logger.error("could not connect to Rally — check RALLY_API_URL/RALLY_API_TOKEN")
        return 1

    cases = client.get_test_cases(args.project, automated_only=False)
    wanted = args.folder.strip().lower()
    guest = [tc for tc in cases
             if wanted in str((tc.get("TestFolder") or {}).get("_refObjectName") or "").lower()]
    if not guest:
        logger.warning(f"no cases in a Test Folder matching '{args.folder}'")
        return 0

    todo = [tc for tc in guest if (tc.get("Method") or "") != args.method]
    logger.info(f"{len(guest)} case(s) in the folder; {len(todo)} need Method -> {args.method}")
    for tc in guest:
        state = "already set" if tc not in todo else f"{tc.get('Method') or '(unset)'} -> {args.method}"
        logger.info(f"  {tc.get('FormattedID'):8} {state:24} {(tc.get('Name') or '')[:48]}")

    if args.dry_run:
        logger.info("--dry-run: nothing written to Rally")
        return 0

    ok, failed = [], []
    for tc in todo:
        ref = tc.get("_ref")
        fid = tc.get("FormattedID")
        if not ref:
            failed.append((fid, "no _ref on the fetched object"))
            continue
        try:
            r = client.session.post(ref, json={"TestCase": {"Method": args.method}})
            body = r.json() if r.content else {}
            errors = (body.get("OperationResult") or {}).get("Errors") or []
            if r.status_code >= 400 or errors:
                failed.append((fid, f"HTTP {r.status_code} {errors}"))
            else:
                ok.append(fid)
                logger.info(f"  ✅ {fid} -> {args.method}")
        except Exception as e:                     # noqa: BLE001
            failed.append((fid, str(e)[:120]))

    logger.info(f"updated {len(ok)}: {ok}")
    if failed:
        logger.error(f"failed {len(failed)}:")
        for fid, why in failed:
            logger.error(f"  {fid}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
