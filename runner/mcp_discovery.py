"""Read the LIVE game through the AltTester MCP CLI.

The panel's "generate" button uses this: generation looks at the running game
through the very same ``alttester`` binary that serves the MCP server, so the
code it writes is based on what is actually on screen — real object names, the
real scene, and (in a level) the real activity titles printed on the thumbs.

Nothing here needs the game: every call raises :class:`McpError` when the CLI
or the game is missing, and callers fall back to AltDriver / offline templates.

CLI facts this relies on (verified against the installed build):
  * ``status``           -> current daemon session (may be stale after a restart)
  * ``apps``             -> games registered on the server, with their app-id
  * ``connect --app-id`` -> (re)binds the session
  * ``scene``            -> ``{"data": {"current_scene": ...}}``
  * ``get-all-elements`` -> active objects of the current scene
  * ``find X --by TEXT`` -> CASE-SENSITIVE exact text match, fails fast
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[1]

# Same heuristics as the AltDriver path: this build leaves AltObject.type empty,
# so inputs/buttons are classified by name.
_INPUT_HINTS = ("inputfield", "input", "username", "password", "email", "textbox", "textfield")
_BUTTON_HINTS = ("button", "btn")

ACTIVITY_SELECTION_SCENE = "ActivitySelectionScene"


class McpError(Exception):
    """The AltTester CLI is missing, or the game is not reachable through it."""


def cli_path():
    """Absolute path of the ``alttester`` CLI, or raise McpError.

    Checked in order: ``ALTTESTER_CLI`` env var, the project's ``.mcp.json``
    (so the panel uses exactly the binary the MCP server runs), ``PATH``, then
    the default install location.
    """
    override = os.environ.get("ALTTESTER_CLI", "").strip()
    if override and Path(override).exists():
        return override

    try:
        cfg = json.loads((_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        cmd = cfg.get("mcpServers", {}).get("alttester", {}).get("command", "")
        if cmd and Path(cmd).exists():
            return cmd
    except (OSError, ValueError, AttributeError):
        pass

    found = shutil.which("alttester")
    if found:
        return found

    default = Path.home() / ".alttester" / "CLI" / ("alttester.exe" if os.name == "nt" else "alttester")
    if default.exists():
        return str(default)

    raise McpError("alttester CLI not found (set ALTTESTER_CLI or install it with "
                   "`alttester install-cli`).")


def run(*args, timeout=90):
    """Run one CLI command and return its parsed JSON (or a raw-text dict).

    Output goes to temp FILES, never to pipes. ``connect`` (and any command
    that has to auto-relaunch the session) spawns a long-lived ``alttester
    daemon`` process which INHERITS the handles it was given: with pipes,
    ``subprocess.run`` blocks in communicate() waiting for an EOF that only
    arrives when the daemon exits — minutes later — even though the command
    itself finished in under a second. With files we wait for the command
    process alone and the daemon may keep the handle as long as it likes.
    """
    exe = cli_path()
    argv = [exe, *[str(a) for a in args]]
    out_fd, out_path = tempfile.mkstemp(prefix="alttester-out-")
    err_fd, err_path = tempfile.mkstemp(prefix="alttester-err-")
    try:
        with os.fdopen(out_fd, "w") as out_f, os.fdopen(err_fd, "w") as err_f:
            try:
                proc = subprocess.run(argv, stdout=out_f, stderr=err_f, timeout=timeout)
            except subprocess.TimeoutExpired as e:
                raise McpError(f"alttester {' '.join(str(a) for a in args)} timed out") from e
        out = _read_text(out_path).strip()
        err = _read_text(err_path).strip()
    finally:
        # The daemon may still hold these handles; deleting is best effort.
        for path in (out_path, err_path):
            try:
                os.unlink(path)
            except OSError:
                pass

    try:
        return json.loads(out)
    except ValueError:
        return {"success": proc.returncode == 0, "raw": out, "stderr": err}


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def ensure_session(host="127.0.0.1", port=13000, app_id=""):
    """Make sure the CLI has a live session bound to the running game.

    The daemon's session goes stale whenever the game restarts (it keeps the
    old app-id), so a bare ``status`` is not enough — when it is not connected
    we look the game up in ``apps`` and reconnect to its current app-id.

    Returns ``(status, owned)``; ``owned`` is True when this call opened the
    session, meaning the caller must close it again (see ``disconnect``).
    """
    status = run("status", timeout=30)
    if status.get("connected"):
        return status, False

    wanted = (app_id or "").strip()
    if not wanted:
        apps = run("apps", "--host", host, "--port", port, timeout=30)
        registered = apps.get("apps") or []
        if not registered:
            raise McpError(f"no game registered on {host}:{port} — start the app first")
        wanted = registered[0].get("app_id") or ""

    args = ["connect", "--host", host, "--port", port]
    if wanted:
        args += ["--app-id", wanted]
    res = run(*args, timeout=120)
    if res.get("success") is False:
        raise McpError(res.get("error") or res.get("message") or "connect failed")
    return res, True


def disconnect():
    """Close the CLI session, freeing its driver slot.

    The AltTester licence allows only 2 connected drivers at a time, and a
    session left open by generation would otherwise block the pytest run that
    follows it. Failures here are not interesting — never raise.
    """
    try:
        run("disconnect", timeout=30)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[mcp] disconnect failed: {e}")


def current_scene():
    res = run("scene", timeout=30)
    return (res.get("data") or {}).get("current_scene")


def object_names():
    """Names of the active objects in the current scene."""
    res = run("get-all-elements", timeout=120)
    names, seen = [], set()
    for o in res.get("objects") or []:
        n = o.get("name")
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    return names


def find_text(text):
    """The object whose visible text is exactly ``text`` (case-sensitive), or None."""
    res = run("find", text, "--by", "TEXT", timeout=30)
    if res.get("found"):
        return res.get("alt_object")
    return None


def _casings(word):
    """Casing variants to try for a UI label ("break out" -> "Break Out", ...)."""
    w = (word or "").strip()
    if not w:
        return []
    out = [w, w.title(), w.capitalize(), w.upper(), w.lower()]
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def read_activity_titles(candidates):
    """On ActivitySelectionScene, confirm which of ``candidates`` is on screen.

    ``candidates`` are the aliases a Rally case might use for its activity
    ("brickout", "break out", ...). ``find --by TEXT`` is exact and
    case-sensitive, so each alias is tried in a few casings; a miss fails fast.

    Returns ``{"title": <exact label on screen>, "x": <thumb column>}`` for the
    first hit, or ``{}`` when none of them is on this screen.
    """
    for alias in candidates:
        for variant in _casings(alias):
            obj = find_text(variant)
            if obj:
                return {"title": variant, "x": obj.get("x")}
    return {}


def discover(host="127.0.0.1", port=13000, app_id="", activity_aliases=()):
    """Everything generation needs to know about the app right now.

    Returns ``{scene, inputs, buttons, all, thumbs, activity, source}`` where
    ``activity`` is the confirmed on-screen title for ``activity_aliases``
    (empty when not on an activity-selection screen or not found).
    """
    _status, owned = ensure_session(host=host, port=port, app_id=app_id)
    try:
        scene = current_scene()
        names = object_names()

        def by_hint(hints):
            return [n for n in names if any(h in n.lower() for h in hints)]

        elements = {
            "scene": scene,
            "inputs": by_hint(_INPUT_HINTS),
            "buttons": by_hint(_BUTTON_HINTS),
            "all": names,
            "thumbs": [n for n in names if "activitythumb" in n.lower()],
            "activity": {},
            "source": "mcp",
        }

        if activity_aliases and scene == ACTIVITY_SELECTION_SCENE:
            elements["activity"] = read_activity_titles(activity_aliases)

        return elements
    finally:
        # Hand the driver slot straight back — a test run usually follows.
        if owned:
            disconnect()
