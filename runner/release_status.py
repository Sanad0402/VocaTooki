"""Release (regression) status across platforms.

The runner drives ONE platform at a time and only the cases that AltTester can
automate; the rest of a release folder is covered by hand on iOS, Android and
Web. This keeps a single picture of both: automated runs record themselves, and
anything manual is ticked off in the panel.

Stored in ``data/release_status.json``:

    {
      "release":  "2026.08",
      "platform": "web",                     # what the runner is currently testing
      "folder":   "TF181",                   # the release folder in scope ("" = whole suite)
      "cases": {"TC1151": {"web": {"verdict": "passed",
                                   "at": "...", "source": "run", "note": ""}}}
    }

Verdicts are the four states a release tracker needs: ``passed``, ``failed``,
``blocked`` and — implicitly, by absence — not run. Nothing here talks to the
game or to Rally; it is a record of outcomes.
"""

import json
import os
import threading
from datetime import datetime, timezone

PLATFORMS = ("ios", "android", "web")
VERDICTS = ("passed", "failed", "blocked")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "release_status.json")
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _blank():
    return {"release": "", "platform": "web", "folder": "", "cases": {}}


def load():
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _blank()
    base = _blank()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("cases"), dict):
        base["cases"] = {}
    return base


def _save(data):
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _PATH)


def configure(release=None, platform=None, folder=None):
    """Set the release being tested, the runner's platform, and the scope folder."""
    with _lock:
        data = load()
        if release is not None:
            data["release"] = str(release).strip()
        if platform is not None and str(platform).strip().lower() in PLATFORMS:
            data["platform"] = str(platform).strip().lower()
        if folder is not None:
            data["folder"] = str(folder).strip()
        _save(data)
        return data


def record(tc_id, verdict, platform=None, source="run", note=""):
    """Record one case's outcome on one platform.

    ``platform`` defaults to the platform the runner is currently testing, so a
    suite run needs to know nothing about release tracking.
    """
    tc_id = str(tc_id or "").strip()
    verdict = str(verdict or "").strip().lower()
    if not tc_id:
        return None
    with _lock:
        data = load()
        plat = (platform or data.get("platform") or "web").strip().lower()
        if plat not in PLATFORMS:
            return None
        entry = data["cases"].setdefault(tc_id, {})
        if verdict in VERDICTS:
            entry[plat] = {"verdict": verdict, "at": _now(),
                           "source": source, "note": str(note or "")[:400]}
        else:
            entry.pop(plat, None)          # anything else clears it back to "not run"
            if not entry:
                data["cases"].pop(tc_id, None)
        _save(data)
        return data


def record_run(tc_id, run_status, platform=None):
    """Map a runner status (PASSED/FAILED/...) onto a release verdict.

    SKIPPED and CANCELLED deliberately do NOT count as covered — a case that
    did not execute has not been tested, and recording it as anything else
    would inflate the release progress.
    """
    mapping = {"PASSED": "passed", "FAILED": "failed", "ERROR": "failed"}
    verdict = mapping.get(str(run_status or "").upper())
    if not verdict:
        return None
    return record(tc_id, verdict, platform=platform, source="run")


def summary(suite_tree):
    """Progress per platform, plus a per-folder breakdown.

    ``suite_tree`` is ``runner.suite.tree()`` — the release scope comes from the
    suite itself, so the tab counts the same cases the panel manages, including
    the ones only a human can test.
    """
    data = load()
    scope = (data.get("folder") or "").strip()

    folders = []
    for folder in suite_tree.get("folders", []):
        cases = folder.get("cases", [])
        if not cases:
            continue
        if scope and scope not in (folder.get("id"), folder.get("parent")):
            continue
        folders.append(folder)

    def counts_for(case_ids):
        out = {}
        for plat in PLATFORMS:
            tally = {"passed": 0, "failed": 0, "blocked": 0, "not_run": 0}
            for tc_id in case_ids:
                verdict = ((data["cases"].get(tc_id) or {}).get(plat) or {}).get("verdict")
                tally[verdict if verdict in VERDICTS else "not_run"] += 1
            total = max(1, len(case_ids))
            # "Complete" means the case was actually exercised — a failure is a
            # tested case, a blocked or unrun one is not.
            tally["total"] = len(case_ids)
            tally["tested"] = tally["passed"] + tally["failed"]
            tally["percent"] = round(100.0 * tally["tested"] / total, 1)
            tally["pass_rate"] = round(100.0 * tally["passed"] / max(1, tally["tested"]), 1)
            out[plat] = tally
        return out

    rows = []
    all_ids = []
    for folder in folders:
        ids = [c["id"] for c in folder.get("cases", [])]
        all_ids += ids
        rows.append({
            "id": folder.get("id"),
            "name": folder.get("name") or folder.get("id"),
            "total": len(ids),
            "platforms": counts_for(ids),
        })

    return {
        "release": data.get("release", ""),
        "platform": data.get("platform", "web"),
        "folder": scope,
        "platforms": PLATFORMS,
        "overall": counts_for(all_ids),
        "folders": rows,
        "total_cases": len(all_ids),
        "cases": data.get("cases", {}),
    }
