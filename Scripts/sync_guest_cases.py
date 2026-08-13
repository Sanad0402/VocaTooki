"""Bring the Guest Test Folder into the local suite and generate its tests.

Why a separate script
---------------------
The normal sync only fetches ``Method = "Automated"`` cases
(``rally_api.get_test_cases(automated_only=True)``), so a Rally folder full of
guest cases arrives as whichever ones happen to be flagged. Guest cases are
written before they are flagged, and the flag is what the team uses to say
"generate code for this" — so this script fetches the guest folder REGARDLESS of
Method, merges those cases into ``data/rally_suite.json`` (leaving everything
else alone) and generates a test for each.

Every case in the folder is generated the same way TC1160 is: the guest type is
inferred from the case text, the entry route and the language/difficulty/gender
come from the Rally Description + Validation Input, and the guest's last name is
derived from the selections (``guestArBL``).

Usage:
    python Scripts/sync_guest_cases.py --project 622679112169
    python Scripts/sync_guest_cases.py --project 622679112169 --folder Guest
    python Scripts/sync_guest_cases.py --project 622679112169 --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import rally_naming                     # noqa: E402
from runner.rally_api import create_client_from_env  # noqa: E402
from runner.test_generator import RallyTestGenerator  # noqa: E402

logger = logging.getLogger("sync_guest_cases")
ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "data" / "rally_suite.json"


def _folder_of(tc):
    return str((tc.get("TestFolder") or {}).get("_refObjectName") or "")


def _as_local_case(tc, client, folder_id):
    """Rally case -> the local suite's case shape (same fields the sync writes)."""
    tc_id = tc.get("FormattedID") or ""
    name = tc.get("Name") or ""
    description = client._html_to_text(tc.get("Description") or "")
    validation = {
        "input": client._html_to_text(tc.get("ValidationInput") or ""),
        "expected": client._html_to_text(tc.get("ValidationExpectedResult") or ""),
    }
    nodeid = rally_naming.nodeid(tc_id, name, folder_id) \
        if hasattr(rally_naming, "nodeid") else ""
    case = {
        "id": tc_id,
        "name": name,
        "folder": folder_id,
        "description": description,
        "owner": str((tc.get("Owner") or {}).get("_refObjectName") or ""),
        "status": tc.get("Status") or "",
        "user": {},                       # a guest has no credentials, ever
        "steps": [],
        "validation": validation,
        "method": tc.get("Method") or "",
    }
    if nodeid:
        case["action"] = {"kind": "pytest", "nodeid": nodeid}
    return case


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True, help="Rally project ObjectID")
    ap.add_argument("--folder", default="guest",
                    help="Test Folder name to match, case-insensitive (default: guest)")
    ap.add_argument("--env-file", default="rally.env")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be added/generated, write nothing")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client = create_client_from_env(args.env_file)
    if not client or not client.test_connection():
        logger.error("could not connect to Rally — check RALLY_API_URL/RALLY_API_TOKEN")
        return 1

    cases = client.get_test_cases(args.project, automated_only=False)
    logger.info(f"fetched {len(cases)} cases (all methods)")
    wanted = args.folder.strip().lower()
    guest = [tc for tc in cases if wanted in _folder_of(tc).lower()]
    if not guest:
        logger.warning(f"no cases in a Test Folder matching '{args.folder}'")
        return 0

    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    folders = {f["name"].strip().lower(): f["id"] for f in suite.get("folders", [])}
    by_id = {c["id"]: i for i, c in enumerate(suite.get("test_cases", []))}

    added, updated = [], []
    for tc in guest:
        folder_name = _folder_of(tc)
        folder_id = folders.get(folder_name.strip().lower(), folder_name)
        local = _as_local_case(tc, client, folder_id)
        logger.info(f"  {local['id']:8} Method={local['method'] or '(unset)':10} "
                    f"folder={folder_name:12} {local['name'][:52]}")
        if args.dry_run:
            continue
        if local["id"] in by_id:
            existing = suite["test_cases"][by_id[local["id"]]]
            local.setdefault("action", existing.get("action", {}))
            # keep the recorded nodeid: it is what the runner executes
            if existing.get("action"):
                local["action"] = existing["action"]
            suite["test_cases"][by_id[local["id"]]] = local
            updated.append(local["id"])
        else:
            suite.setdefault("test_cases", []).append(local)
            added.append(local["id"])

    if args.dry_run:
        logger.info("--dry-run: nothing written")
        return 0

    SUITE.write_text(json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"suite updated — added {added or 'none'}, refreshed {updated or 'none'}")

    # Generate only the guest cases; pruning stays off so nothing else is touched.
    gen = RallyTestGenerator(str(ROOT))
    ids = {tc.get("FormattedID") for tc in guest}
    for case in suite["test_cases"]:
        if case["id"] not in ids:
            continue
        try:
            path = gen.generate_test(case)
            logger.info(f"generated {case['id']} -> {path}")
        except Exception as e:                     # noqa: BLE001
            logger.error(f"{case['id']}: generation failed — {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
