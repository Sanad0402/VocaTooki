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

from runner import suite as suite_mod
from runner.test_generator import RallyTestGenerator

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

    return {"scene": scene, "inputs": inputs, "buttons": buttons}


def generate_live_skeleton(tc_id, host="127.0.0.1", port=13000, platform="WindowsEditor",
                           app_id="", device_instance_id=""):
    """Discover elements on the live app and (re)write ``tc_id``'s test skeleton.

    Returns (written_path, elements). Raises if the case is unknown or the app
    is unreachable. A file locked with ``MANUAL_EDIT = True`` is left untouched.
    """
    from alttester import AltDriver

    data = suite_mod.load()
    tc = next((c for c in data["test_cases"] if c.get("id") == tc_id), None)
    if not tc:
        raise ValueError(f"Test case {tc_id} not found in the suite (data/rally_suite.json).")

    kwargs = dict(host=host, port=port, platform=platform, enable_logging=False)
    if (app_id or "").strip():
        kwargs["app_id"] = app_id.strip()
    if (device_instance_id or "").strip():
        kwargs["device_instance_id"] = device_instance_id.strip()

    driver = AltDriver(**kwargs)
    try:
        elements = discover_elements(driver)
    finally:
        try:
            driver.close()
        except Exception:
            try:
                driver.stop()
            except Exception:
                pass

    logger.info(f"[{tc_id}] discovered {len(elements['inputs'])} input(s), "
                f"{len(elements['buttons'])} button(s) on scene '{elements['scene']}'")
    path = RallyTestGenerator(str(suite_mod._ROOT)).generate_skeleton(tc, elements)
    logger.info(f"[{tc_id}] wrote skeleton: {path}")
    return str(path), elements


def generate_skeletons_live(tc_ids, host="127.0.0.1", port=13000, platform="WindowsEditor",
                            app_id="", device_instance_id=""):
    """Connect ONCE, discover the current scene's elements, and (re)write the
    skeleton for each case in ``tc_ids``. Efficient for the panel's batch
    "Generate from live app" action.

    Returns (results, elements) where results is a list of per-case dicts:
    ``{"id", "ok", "path"?, "error"?}``. Raises only if the app is unreachable.
    """
    from alttester import AltDriver

    data = suite_mod.load()
    by_id = {c.get("id"): c for c in data["test_cases"]}

    kwargs = dict(host=host, port=int(port), platform=platform, enable_logging=False)
    if (app_id or "").strip():
        kwargs["app_id"] = app_id.strip()
    if (device_instance_id or "").strip():
        kwargs["device_instance_id"] = device_instance_id.strip()

    driver = AltDriver(**kwargs)
    try:
        elements = discover_elements(driver)
    finally:
        try:
            driver.close()
        except Exception:
            try:
                driver.stop()
            except Exception:
                pass

    gen = RallyTestGenerator(str(suite_mod._ROOT))
    results = []
    for tc_id in tc_ids:
        tc = by_id.get(tc_id)
        if not tc:
            results.append({"id": tc_id, "ok": False, "error": "not found in suite"})
            continue
        try:
            path = gen.generate_skeleton(tc, elements)
            results.append({"id": tc_id, "ok": True, "path": str(path)})
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
