"""#4 — Generate real test skeletons from the LIVE app.

Connects an AltDriver, uses ``ElementInspector`` to read the current scene's
inputs and buttons, and rewrites a Rally test case's file from an empty stub
into a real (or pre-wired) skeleton via ``RallyTestGenerator.generate_skeleton``.

Requires the game running and AltTester reachable (default 127.0.0.1:13000).
The pure rendering (``RallyTestGenerator._gen_skeleton_from_elements``) is unit
-testable offline; only the discovery step here needs a live app.

CLI:
    python -m runner.live_skeleton TC452 --host 127.0.0.1 --port 13000
"""

import logging
import re
from pathlib import Path

from runner import suite as suite_mod


def _generator(root=None):
    """A generator built from the CODE ON DISK, every time.

    NOT a module-level import of RallyTestGenerator: the panel serves without a
    reloader, so a name bound at import time keeps whatever class the process
    booted with -- and reloading `test_generator` elsewhere does not rebind it.
    That is how a fixed generator kept producing the OLD stub message on the
    live path long after the fix.
    """
    import importlib
    from runner import test_generator as _tg
    importlib.reload(_tg)
    return _tg.RallyTestGenerator(str(root or suite_mod._ROOT))

logger = logging.getLogger(__name__)

# Name heuristics. This AltDriver build leaves AltObject.type empty, so we
# classify by object name (kept precise to avoid false hits like "NewLoginSystem").
_INPUT_HINTS = ("inputfield", "input", "username", "password", "email", "textbox", "textfield")
_BUTTON_HINTS = ("button", "btn")


def discover_elements(driver):
    """Return {'scene', 'inputs', 'buttons'} from the live app.

    Uses ``driver.get_all_elements()`` (the enumeration this AltDriver build
    exposes) and classifies by object name, since ``type`` is not populated."""
    try:
        raw = driver.get_all_elements()
    except Exception as e:  # noqa: BLE001
        logger.error("get_all_elements failed: %s", e)
        raw = []

    names, seen = [], set()
    for e in raw:
        n = getattr(e, "name", None)
        if n and n not in seen:
            seen.add(n)
            names.append(n)

    def _by_hint(hints):
        return [n for n in names if any(h in n.lower() for h in hints)]

    inputs = _by_hint(_INPUT_HINTS)
    buttons = _by_hint(_BUTTON_HINTS)

    try:
        scene = driver.get_current_scene()
    except Exception:
        scene = None

    # 'all' lets the generator match Rally step text to any object on the scene
    # when deriving assertions/interactions (not just inputs/buttons).
    return {"scene": scene, "inputs": inputs, "buttons": buttons, "all": names}


def _discover_with_driver(host, port, platform, app_id="", device_instance_id=""):
    """Element discovery over a short-lived AltDriver connection."""
    from alttester import AltDriver

    kwargs = dict(host=host, port=int(port), platform=platform, enable_logging=False)
    if (app_id or "").strip():
        kwargs["app_id"] = app_id.strip()
    if (device_instance_id or "").strip():
        kwargs["device_instance_id"] = device_instance_id.strip()

    driver = AltDriver(**kwargs)
    try:
        return discover_elements(driver)
    finally:
        try:
            driver.close()
        except Exception:
            try:
                driver.stop()
            except Exception:
                pass


def discover_live(host="127.0.0.1", port=13000, platform="WindowsEditor",
                  app_id="", device_instance_id="", activity_aliases=()):
    """What the app looks like right now — through the MCP CLI when possible.

    The panel's generate button reads the game the same way the MCP tooling
    does: the ``alttester`` CLI. That also answers questions AltDriver's plain
    object list cannot, such as which activity title is printed on each thumb.
    If the CLI is missing or its session cannot be established, this falls back
    to a direct AltDriver connection.

    Returns ``(elements, source)`` with source ``"mcp"`` or ``"altdriver"``.
    """
    from runner import mcp_discovery

    try:
        elements = mcp_discovery.discover(host=host, port=int(port), app_id=app_id,
                                          activity_aliases=activity_aliases)
        logger.info(f"[discovery] via MCP CLI — scene '{elements.get('scene')}', "
                    f"{len(elements.get('all', []))} objects, "
                    f"activity={elements.get('activity') or 'n/a'}")
        return elements, "mcp"
    except Exception as e:  # noqa: BLE001 - the CLI is optional, never fatal
        logger.info(f"[discovery] MCP CLI unavailable ({e}); using AltDriver")

    elements = _discover_with_driver(host, port, platform, app_id, device_instance_id)
    elements.setdefault("activity", {})
    elements["source"] = "altdriver"
    return elements, "altdriver"


def generate_from_live_app(tc_id, host="127.0.0.1", port=13000, platform="WindowsEditor",
                           app_id="", device_instance_id=""):
    """Generate one Rally case's test from the live app (MCP-first).

    Beyond plain element discovery this resolves what the case is *about*: for
    an activity case it asks the running game whether that activity's thumb is
    on screen, and bakes the exact printed label into the test.

    Returns ``(path, elements, source)``.
    """
    data = suite_mod.load()
    tc = next((c for c in data["test_cases"] if c.get("id") == tc_id), None)
    if not tc:
        raise ValueError(f"Test case {tc_id} not found in the suite (data/rally_suite.json).")

    gen = _generator()
    nodeid = (tc.get("action") or {}).get("nodeid") or ""
    scene = gen._infer_activity_scene(tc.get("name", ""), tc.get("description", ""), nodeid)
    aliases = gen.activity_aliases(scene) if scene else []

    elements, source = discover_live(host=host, port=port, platform=platform,
                                     app_id=app_id, device_instance_id=device_instance_id,
                                     activity_aliases=aliases)
    path = gen.generate_skeleton(tc, elements)
    logger.info(f"[{tc_id}] generated {path} from the live app via {source}")
    return str(path), elements, source


def generate_live_skeleton(tc_id, host="127.0.0.1", port=13000, platform="WindowsEditor",
                           app_id="", device_instance_id=""):
    """Discover elements on the live app and (re)write ``tc_id``'s test skeleton.

    Returns (written_path, elements). Raises if the case is unknown or the app
    is unreachable. A file locked with ``MANUAL_EDIT = True`` is left untouched.

    Thin wrapper over :func:`generate_from_live_app` (kept for the CLI and for
    callers that don't care which transport was used).
    """
    path, elements, _source = generate_from_live_app(
        tc_id, host=host, port=port, platform=platform,
        app_id=app_id, device_instance_id=device_instance_id,
    )
    return path, elements


def generate_skeletons_live(tc_ids, host="127.0.0.1", port=13000, platform="WindowsEditor",
                            app_id="", device_instance_id=""):
    """Connect ONCE, discover the current scene's elements, and (re)write the
    skeleton for each case in ``tc_ids``. Efficient for the panel's batch
    "Generate from live app" action.

    Returns (results, elements) where results is a list of per-case dicts:
    ``{"id", "ok", "path"?, "error"?}``. Raises only if the app is unreachable.
    """
    data = suite_mod.load()
    by_id = {c.get("id"): c for c in data["test_cases"]}
    gen = _generator()

    # One discovery pass for the whole batch. Activity titles are probed for
    # every selected activity case, so each of them can still be matched
    # against what is actually on screen.
    aliases = []
    for tc_id in tc_ids:
        tc = by_id.get(tc_id) or {}
        scene = gen._infer_activity_scene(tc.get("name", ""), tc.get("description", ""),
                                          (tc.get("action") or {}).get("nodeid") or "")
        if scene:
            aliases += [a for a in gen.activity_aliases(scene) if a not in aliases]

    elements, _source = discover_live(host=host, port=port, platform=platform,
                                      app_id=app_id, device_instance_id=device_instance_id,
                                      activity_aliases=aliases)

    def _stub_reason(path):
        """``{"stub": bool, "reason": str}`` for a just-generated file.

        A generated test that carries a skip marker is the generator saying
        "the case does not tell me X" — that sentence is the most useful thing
        the panel can show, so it is read back off the file rather than lost.
        """
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            return {}
        match = re.search(r'@pytest\.mark\.skip\(\s*reason\s*=\s*["\'](.+?)["\']\s*\)',
                          text, re.S)
        if not match:
            return {}
        return {"stub": True, "reason": re.sub(r"\s+", " ", match.group(1)).strip()}

    results = []
    for tc_id in tc_ids:
        tc = by_id.get(tc_id)
        if not tc:
            results.append({"id": tc_id, "ok": False, "error": "not found in suite"})
            continue
        try:
            path = gen.generate_skeleton(tc, elements)
            entry = {"id": tc_id, "ok": True, "path": str(path)}
            # Writing a file is not the same as producing a usable test. When
            # the case is missing something the generator needs, the template
            # emits an honest SKIP that says what — surface that reason, or the
            # panel reports "generated 1/1" for a test that cannot run and the
            # generation looks broken instead of under-specified.
            entry.update(_stub_reason(path))
            results.append(entry)
        except Exception as e:  # noqa: BLE001 - report per-case, keep going
            logger.exception("skeleton generation failed for %s", tc_id)
            results.append({"id": tc_id, "ok": False, "error": str(e)})
    return results, elements


def _main(argv=None):
    import argparse

    p = argparse.ArgumentParser(description="Generate a real test skeleton from the live app.")
    p.add_argument("tc_id", help="Rally test case id, e.g. TC452")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=13000)
    p.add_argument("--platform", default="WindowsEditor")
    p.add_argument("--app_id", default="")
    p.add_argument("--device_instance_id", default="")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    path, elements = generate_live_skeleton(
        args.tc_id, host=args.host, port=args.port, platform=args.platform,
        app_id=args.app_id, device_instance_id=args.device_instance_id,
    )
    print(f"Wrote {path}")
    print(f"Scene: {elements['scene']}")
    print(f"Inputs: {elements['inputs']}")
    print(f"Buttons: {elements['buttons']}")


if __name__ == "__main__":
    _main()
