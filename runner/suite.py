"""Rally test suite: Test Folders (TF) + Test Cases (TC), stored in data/rally_suite.json.

Rally is the source of truth, so TF/TC ids and names are kept identical to Rally. Each
test case carries its own hard-coded user, so the Test Folder / Test Case run modes don't
need a user picked in the UI. The suite is editable both by hand (the JSON) and from the UI
(add / edit / delete folders and cases via runner.suite CRUD functions).

A test case:
    {"id","name","folder","user":{username,password,class_id}, "action":{"kind": ...}}
Action kinds (reuse existing solvers in runner.core):
    login  -> log in as the user and verify the start screen (default)
    lesson -> log in, run one lesson via a mode  {"kind":"lesson","lesson":N,"mode":"express"}
"""

import os
import datetime as _dt
import json
import threading

from runner import rally_naming

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE_PATH = os.path.join(_ROOT, "data", "rally_suite.json")
ACTION_KINDS = ("pytest", "login", "lesson", "code")

_lock = threading.Lock()


class SuiteError(Exception):
    """Raised for invalid suite edits (bad id, missing name, etc.)."""


# ---- load / save -----------------------------------------------------------

def load():
    """Return {'folders': [...], 'test_cases': [...]} (empty scaffold if missing)."""
    try:
        with open(SUITE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"folders": [], "test_cases": []}
    data.setdefault("folders", [])
    data.setdefault("test_cases", [])
    return data


def _save(data):
    os.makedirs(os.path.dirname(SUITE_PATH), exist_ok=True)
    with open(SUITE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- read helpers ----------------------------------------------------------

def _norm_id(v):
    return str(v or "").strip()


def tree():
    """UI-friendly view: folders (with depth) + their cases, parents before children."""
    data = load()
    folders = {f["id"]: dict(f) for f in data["folders"]}
    children, roots = {}, []
    for fid, f in folders.items():
        p = f.get("parent")
        if p and p in folders:
            children.setdefault(p, []).append(fid)
        else:
            roots.append(fid)

    cases_by_folder = {}
    for c in data["test_cases"]:
        cases_by_folder.setdefault(c.get("folder"), []).append(c)

    out = []

    def _walk(fid, depth):
        f = folders[fid]
        out.append({
            "id": f["id"], "name": f.get("name", f["id"]), "parent": f.get("parent"),
            "depth": depth, "cases": [_public_case(c) for c in cases_by_folder.get(fid, [])],
        })
        for cid in children.get(fid, []):
            _walk(cid, depth + 1)

    for rid in roots:
        _walk(rid, 0)
    return {"folders": out}


def impl_status(nodeid):
    """Implementation status of a case's linked pytest test:

    'unlinked' -> no nodeid recorded (nothing to run)
    'stub'     -> linked file is an auto-generated, not-yet-implemented stub
                  (``@pytest.mark.stub`` → skips) or the file is missing
    'real'     -> an implemented test that actually runs against the app
    """
    nodeid = _norm_id(nodeid)
    if not nodeid:
        return "unlinked"
    file_part = nodeid.split("::", 1)[0]
    try:
        with open(os.path.join(_ROOT, file_part), "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "stub"  # linked but the file isn't on disk → not runnable yet
    return "stub" if rally_naming.is_stub(text) else "real"


def _public_case(c):
    u = c.get("user") or {}
    nodeid = (c.get("action") or {}).get("nodeid")
    return {
        "id": c["id"], "name": c.get("name", c["id"]), "folder": c.get("folder"),
        "username": u.get("username", ""), "password": u.get("password", ""),
        "class_id": u.get("class_id", ""),
        "action_kind": (c.get("action") or {}).get("kind", "pytest"),
        "lesson": (c.get("action") or {}).get("lesson"),
        "mode": (c.get("action") or {}).get("mode"),
        "ref": (c.get("action") or {}).get("ref"),
        "nodeid": nodeid,
        "impl": impl_status(nodeid),
        # Set by a Rally sync that CHANGED this case's generated code (a new
        # username, say). It stays until the case is generated again, so the
        # panel can show which tests moved and which are still on old data.
        "updated": bool(c.get("updated")),
        "updated_at": c.get("updated_at", ""),
    }


def _descendants(folder_id, folders):
    """folder_id + all folders nested beneath it."""
    children = {}
    for f in folders:
        p = f.get("parent")
        if p:
            children.setdefault(p, []).append(f["id"])
    out, stack = [], [folder_id]
    while stack:
        fid = stack.pop()
        out.append(fid)
        stack.extend(children.get(fid, []))
    return set(out)


def resolve(run_type, selection):
    """Return (cases, warnings) for a run.

    run_type 'test_case'  -> selection is a list of TC ids (kept in that order).
    run_type 'test_folder'-> selection is a list of TF ids; every case in those folders
                             and their descendants, in suite order.
    """
    data = load()
    cases_by_id = {c["id"]: c for c in data["test_cases"]}
    selection = [_norm_id(s) for s in (selection or []) if _norm_id(s)]
    warnings, out = [], []

    if run_type == "test_case":
        for tc in selection:
            c = cases_by_id.get(tc)
            if not c:
                warnings.append(f"Test case not found: {tc}")
            else:
                out.append(c)
    elif run_type == "test_folder":
        valid = {f["id"] for f in data["folders"]}
        wanted = set()
        for tf in selection:
            if tf not in valid:
                warnings.append(f"Test folder not found: {tf}")
                continue
            wanted |= _descendants(tf, data["folders"])
        out = [c for c in data["test_cases"] if c.get("folder") in wanted]
        if selection and not out and not warnings:
            warnings.append("Selected folder(s) contain no test cases.")
    return out, warnings


# ---- validation ------------------------------------------------------------

def _require(cond, msg):
    if not cond:
        raise SuiteError(msg)


def _valid_user(u):
    u = u or {}
    return {
        "username": _norm_id(u.get("username")),
        "password": u.get("password") or "",
        "class_id": _norm_id(u.get("class_id")),
    }


# ---- folder CRUD -----------------------------------------------------------

def add_folder(folder_id, name, parent=None):
    folder_id, name = _norm_id(folder_id), _norm_id(name)
    parent = _norm_id(parent) or None
    _require(folder_id, "Folder ID is required.")
    _require(name, "Folder name is required.")
    with _lock:
        data = load()
        _require(folder_id not in {f["id"] for f in data["folders"]},
                 f"Folder {folder_id} already exists.")
        if parent:
            _require(parent in {f["id"] for f in data["folders"]},
                     f"Parent folder {parent} not found.")
        data["folders"].append({"id": folder_id, "name": name, "parent": parent})
        _save(data)
    return tree()


def update_folder(folder_id, name=None, parent=None):
    folder_id = _norm_id(folder_id)
    with _lock:
        data = load()
        f = next((x for x in data["folders"] if x["id"] == folder_id), None)
        _require(f, f"Folder {folder_id} not found.")
        if name is not None:
            _require(_norm_id(name), "Folder name is required.")
            f["name"] = _norm_id(name)
        if parent is not None:
            parent = _norm_id(parent) or None
            if parent:
                _require(parent in {x["id"] for x in data["folders"]},
                         f"Parent folder {parent} not found.")
                _require(parent != folder_id and folder_id not in _descendants(parent, data["folders"]),
                         "A folder cannot be moved under itself.")
            f["parent"] = parent
        _save(data)
    return tree()


def delete_folder(folder_id, cascade=False):
    folder_id = _norm_id(folder_id)
    with _lock:
        data = load()
        _require(folder_id in {f["id"] for f in data["folders"]}, f"Folder {folder_id} not found.")
        doomed = _descendants(folder_id, data["folders"])
        cases_inside = [c for c in data["test_cases"] if c.get("folder") in doomed]
        child_folders = [f for f in data["folders"] if f["id"] != folder_id and f["id"] in doomed]
        if (cases_inside or child_folders) and not cascade:
            raise SuiteError(
                f"Folder {folder_id} is not empty ({len(child_folders)} subfolder(s), "
                f"{len(cases_inside)} test case(s)). Enable cascade to delete it and its contents.")
        data["folders"] = [f for f in data["folders"] if f["id"] not in doomed]
        data["test_cases"] = [c for c in data["test_cases"] if c.get("folder") not in doomed]
        _save(data)
    return tree()


# ---- case CRUD -------------------------------------------------------------

def _build_action(payload):
    kind = (payload.get("action_kind") or "pytest").lower()
    _require(kind in ACTION_KINDS, f"Unknown action '{kind}'. Use one of: {', '.join(ACTION_KINDS)}.")
    action = {"kind": kind}
    if kind == "pytest":
        nodeid = _norm_id(payload.get("nodeid"))
        action["nodeid"] = nodeid  # may be empty -> the case shows/runs as SKIPPED until linked
    elif kind == "lesson":
        try:
            action["lesson"] = int(payload.get("lesson"))
        except (TypeError, ValueError):
            raise SuiteError("Lesson number is required for a 'lesson' action.")
        action["mode"] = _norm_id(payload.get("mode")) or "express_hard"
    elif kind == "code":
        ref = _norm_id(payload.get("ref"))
        _require(":" in ref, "Code action needs a ref like 'package.module:function'.")
        action["ref"] = ref
    return action


def add_case(payload):
    tc_id = _norm_id(payload.get("id"))
    name = _norm_id(payload.get("name"))
    folder = _norm_id(payload.get("folder"))
    _require(tc_id, "Test case ID is required.")
    _require(name, "Test case name is required.")
    user = _valid_user(payload.get("user") or payload)  # optional; pytest tests hold their own creds
    action = _build_action(payload)
    with _lock:
        data = load()
        _require(tc_id not in {c["id"] for c in data["test_cases"]}, f"Test case {tc_id} already exists.")
        _require(folder in {f["id"] for f in data["folders"]}, f"Folder {folder} not found.")
        data["test_cases"].append({"id": tc_id, "name": name, "folder": folder,
                                    "user": user, "action": action})
        _save(data)
    return tree()


def update_case(tc_id, payload):
    tc_id = _norm_id(tc_id)
    with _lock:
        data = load()
        c = next((x for x in data["test_cases"] if x["id"] == tc_id), None)
        _require(c, f"Test case {tc_id} not found.")
        if payload.get("name") is not None:
            _require(_norm_id(payload["name"]), "Test case name is required.")
            c["name"] = _norm_id(payload["name"])
        if payload.get("folder"):
            _require(_norm_id(payload["folder"]) in {f["id"] for f in data["folders"]},
                     f"Folder {payload['folder']} not found.")
            c["folder"] = _norm_id(payload["folder"])
        if any(k in payload for k in ("user", "username", "password", "class_id")):
            user = _valid_user(payload.get("user") or payload)
            _require(user["username"], "Test case user (username) is required.")
            c["user"] = user
        if payload.get("action_kind"):
            c["action"] = _build_action(payload)
        _save(data)
    return tree()


def delete_case(tc_id):
    tc_id = _norm_id(tc_id)
    with _lock:
        data = load()
        _require(tc_id in {c["id"] for c in data["test_cases"]}, f"Test case {tc_id} not found.")
        data["test_cases"] = [c for c in data["test_cases"] if c["id"] != tc_id]
        _save(data)
    return tree()


def mark_updated(case_ids, when=""):
    """Flag cases whose generated code a sync just changed. Returns the count.

    Stored on the case itself so the mark survives a reload — the user may sync
    now and look at the panel later, which is exactly the situation this is for
    (a username rotation done in Rally weeks after the tests were written).
    """
    ids = {str(i) for i in (case_ids or []) if i}
    if not ids:
        return 0
    data = load()
    stamp = when or _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    hit = 0
    for c in data.get("test_cases", []):
        if c.get("id") in ids:
            c["updated"] = True
            c["updated_at"] = stamp
            hit += 1
    if hit:
        _save(data)
    return hit


def clear_updated(case_id):
    """Drop the mark once the case has been generated again."""
    data = load()
    changed = False
    for c in data.get("test_cases", []):
        if c.get("id") == case_id and c.get("updated"):
            c["updated"] = False
            c["updated_at"] = ""
            changed = True
    if changed:
        _save(data)
    return changed
