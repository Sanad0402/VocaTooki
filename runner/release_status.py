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
    # scope = what counts toward the release percentage. Whole folders and/or
    # individual cases, chosen in the panel. Empty scope = the whole suite.
    return {"release": "", "platform": "web",
            "scope": {"folders": [], "cases": []}, "cases": {}}


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
    scope = base.get("scope")
    if not isinstance(scope, dict):
        scope = {"folders": [], "cases": []}
    scope.setdefault("folders", [])
    scope.setdefault("cases", [])
    # An earlier version scoped to a single folder id.
    legacy = str(data.get("folder") or "").strip()
    if legacy and legacy not in scope["folders"]:
        scope["folders"].append(legacy)
    base["scope"] = scope
    return base


def _save(data):
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _PATH)


def configure(release=None, platform=None):
    """Set the release being tested and the platform the runner is driving."""
    with _lock:
        data = load()
        if release is not None:
            data["release"] = str(release).strip()
        if platform is not None and str(platform).strip().lower() in PLATFORMS:
            data["platform"] = str(platform).strip().lower()
        _save(data)
        return data


def set_scope(kind, value, add=True):
    """Add or remove a folder / test case from what the release percentage counts.

    A folder that is not in the synced suite is still accepted — the regression
    folder can be named before it has been synced from Rally — and simply
    contributes no cases until it is.
    """
    key = "folders" if str(kind).lower().startswith("folder") else "cases"
    value = str(value or "").strip()
    if not value:
        return load()
    with _lock:
        data = load()
        items = data["scope"][key]
        if add:
            if value not in items:
                items.append(value)
        elif value in items:
            items.remove(value)
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
    """What the release tab and the public page render.

    The scope is what YOU chose — whole folders and/or individual cases — not
    the whole suite, so the percentage means "the regression set is N% tested"
    rather than "the project is". An empty scope falls back to everything, so
    the page is never blank before the scope is set.

    A scoped folder that is not in the synced suite (the regression folder can
    be named before it holds anything) is reported with ``in_suite: false`` and
    contributes no cases, instead of silently disappearing.
    """
    data = load()
    scope = data.get("scope") or {"folders": [], "cases": []}
    want_folders = list(scope.get("folders") or [])
    want_cases = list(scope.get("cases") or [])

    by_folder = {}
    case_meta = {}
    for folder in suite_tree.get("folders", []):
        by_folder[folder.get("id")] = folder
        for case in folder.get("cases", []):
            case_meta[case["id"]] = {
                "id": case["id"],
                "name": case.get("name") or case["id"],
                "folder": folder.get("id"),
                "folder_name": folder.get("name") or folder.get("id"),
                "impl": case.get("impl"),
            }

    def folder_case_ids(fid):
        """Cases directly in a folder, plus those in its subfolders."""
        ids = [c["id"] for c in (by_folder.get(fid, {}).get("cases") or [])]
        for f in suite_tree.get("folders", []):
            if f.get("parent") == fid:
                ids += folder_case_ids(f.get("id"))
        return ids

    scoped_ids, seen = [], set()
    for fid in want_folders:
        for cid in folder_case_ids(fid):
            if cid not in seen:
                seen.add(cid)
                scoped_ids.append(cid)
    for cid in want_cases:
        if cid not in seen:
            seen.add(cid)
            scoped_ids.append(cid)

    scoped_from_scope = bool(want_folders or want_cases)
    if not scoped_from_scope:                     # nothing chosen yet
        scoped_ids = list(case_meta.keys())

    def counts_for(case_ids):
        out = {}
        for plat in PLATFORMS:
            tally = {"passed": 0, "failed": 0, "blocked": 0, "not_run": 0}
            for tc_id in case_ids:
                verdict = ((data["cases"].get(tc_id) or {}).get(plat) or {}).get("verdict")
                tally[verdict if verdict in VERDICTS else "not_run"] += 1
            total = max(1, len(case_ids))
            # Tested means exercised: a failure is a result, blocked and not-run
            # are not. Counting them would make the release look further along
            # than it is.
            tally["total"] = len(case_ids)
            tally["tested"] = tally["passed"] + tally["failed"]
            tally["percent"] = round(100.0 * tally["tested"] / total, 1)
            tally["pass_rate"] = round(100.0 * tally["passed"] / max(1, tally["tested"]), 1)
            out[plat] = tally
        return out

    # Folder rows: the scoped folders (even empty ones), else whatever holds cases.
    rows = []
    if scoped_from_scope:
        for fid in want_folders:
            ids = folder_case_ids(fid)
            folder = by_folder.get(fid)
            rows.append({
                "id": fid,
                "name": (folder or {}).get("name") or fid,
                "in_suite": folder is not None,
                "total": len(ids),
                "platforms": counts_for(ids),
            })
    else:
        for folder in suite_tree.get("folders", []):
            ids = [c["id"] for c in folder.get("cases", [])]
            if ids:
                rows.append({"id": folder.get("id"),
                             "name": folder.get("name") or folder.get("id"),
                             "in_suite": True, "total": len(ids),
                             "platforms": counts_for(ids)})

    cases = []
    for cid in scoped_ids:
        meta = case_meta.get(cid) or {"id": cid, "name": cid, "folder": "",
                                      "folder_name": "(not in the synced suite)",
                                      "impl": None}
        entry = data["cases"].get(cid) or {}
        cases.append({**meta, "platforms": {
            plat: {"verdict": (entry.get(plat) or {}).get("verdict", ""),
                   "source": (entry.get(plat) or {}).get("source", ""),
                   "at": (entry.get(plat) or {}).get("at", "")}
            for plat in PLATFORMS}})

    return {
        "release": data.get("release", ""),
        "platform": data.get("platform", "web"),
        "scope": {"folders": want_folders, "cases": want_cases,
                  "explicit": scoped_from_scope},
        "available_folders": [{"id": f.get("id"), "name": f.get("name") or f.get("id"),
                               "cases": len(f.get("cases") or [])}
                              for f in suite_tree.get("folders", [])],
        "available_cases": sorted(case_meta.values(), key=lambda c: c["id"]),
        "platforms": PLATFORMS,
        "overall": counts_for(scoped_ids),
        "folders": rows,
        "cases_detail": cases,
        "total_cases": len(scoped_ids),
    }
