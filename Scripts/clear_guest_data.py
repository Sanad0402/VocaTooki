"""Clear the app's GUEST data so the next run is offered registration again.

Why this exists
---------------
Once a guest has registered, pressing "Start FREE trial" RESUMES that guest and the
onboarding wizard never appears — so a guest test can only register on an app whose
guest data is gone. Two things that do NOT achieve that (both tried live 2026-08-13):

* ``AltDriver.delete_player_pref()`` — the guest is not in Unity's PlayerPrefs. That
  key (``HKCU\\Software\\Unity\\UnityEditor\\Kideo Tech\\Voca Tooki``) holds only Unity
  analytics ids and the AltTester host/port.
* clearing anything while the app is RUNNING — the session lives in memory and is
  written back out, so the guest reappears.

The guest actually lives in the app's persistent data:
``%USERPROFILE%/AppData/LocalLow/Kideo Tech/Voca Tooki/loggedUsersData.json``
as an entry in ``loggedUsers`` with ``id == 0`` (firstName/lastName are the ones the
test typed). That same file holds every REAL account that has logged in on this
machine, so this script removes only the guest entry and leaves the rest alone.

Usage
-----
    python Scripts/clear_guest_data.py            # remove the guest entry (backs up first)
    python Scripts/clear_guest_data.py --dry-run  # show what would change
    python Scripts/clear_guest_data.py --all      # also drop the guest's data folder

Run it while the app is STOPPED (exit Play mode), then start the app again with
AltTester instrumentation before running the guest test.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

APP_DATA = Path(os.environ.get("USERPROFILE", str(Path.home()))) / \
    "AppData" / "LocalLow" / "Kideo Tech" / "Voca Tooki"
USERS_FILE = APP_DATA / "loggedUsersData.json"
# The guest is stored as user id 0 (a real account always has a positive id).
GUEST_ID = 0


def _is_guest(entry):
    if not isinstance(entry, dict):
        return False
    if entry.get("id") == GUEST_ID:
        return True
    # Belt and braces: an unverified account with no email and no org is not a real user.
    return (not entry.get("email") and not entry.get("org_id")
            and str(entry.get("firstName", "")).lower().startswith("guest"))


def clear_guest(dry_run=False, drop_folder=False):
    if not USERS_FILE.exists():
        print(f"[clear-guest] nothing to do — {USERS_FILE} does not exist")
        return True

    raw = USERS_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[clear-guest] {USERS_FILE} is not valid JSON ({e}); leaving it alone")
        return False

    users = data.get("loggedUsers") or []
    guests = [u for u in users if _is_guest(u)]
    keep = [u for u in users if not _is_guest(u)]
    if not guests:
        print(f"[clear-guest] no guest entry found ({len(users)} logged users kept)")
        return True

    for g in guests:
        print(f"[clear-guest] guest: id={g.get('id')} "
              f"{g.get('firstName')!r} {g.get('lastName')!r}")
    print(f"[clear-guest] {len(keep)} real account(s) will be kept")
    if dry_run:
        print("[clear-guest] --dry-run: nothing written")
        return True

    backup = USERS_FILE.with_suffix(".json.bak")
    shutil.copy2(USERS_FILE, backup)
    data["loggedUsers"] = keep
    # The app points loggedUserId at the active session; the guest is gone now.
    if data.get("loggedUserId") == GUEST_ID:
        data["loggedUserId"] = keep[0].get("id", 0) if keep else 0
    USERS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"[clear-guest] rewrote {USERS_FILE.name} (backup: {backup.name})")

    if drop_folder:
        folder = APP_DATA / str(GUEST_ID)
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
            print(f"[clear-guest] removed the guest's data folder {folder}")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be removed, write nothing")
    ap.add_argument("--all", dest="drop_folder", action="store_true",
                    help="also delete the guest's per-user data folder")
    args = ap.parse_args(argv)
    return 0 if clear_guest(args.dry_run, args.drop_folder) else 1


if __name__ == "__main__":
    sys.exit(main())
