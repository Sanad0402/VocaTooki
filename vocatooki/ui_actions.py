"""Finding, pressing and reading UI objects by NAME - the layer every flow builds on.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import re
import time
from alttester import By
from alttester.exceptions import ComponentNotFoundException


def call_method(altdriver, component_name, method_name, parameters=None, parameter_types=None,
                game_object=None, game_object_name="AltTesterPrefab", assembly="Assembly-CSharp"):
    """
    Wrapper to call a method on a game object.
    # Example usage
    result = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
    Methods :PlayClickSound,LoadPreviousScene,GetCurrentActivity,LoadMapScene,Logout,LoadStartScene
    """
    parameters = parameters or []
    parameter_types = parameter_types or []

    if not game_object:
        game_object = altdriver.find_object(By.NAME, game_object_name)

    try:
        return game_object.call_component_method(
            assembly=assembly,
            component_name=component_name,
            method_name=method_name,
            parameters=parameters,
            type_of_parameters=parameter_types
        )
    except ComponentNotFoundException as e:
        # The object exists but the component isn't attached in the current
        # app state. Most often this means the app is on the login/start
        # screen (or a scene is still loading), where components like
        # 'AltTesterUtils' don't exist yet. Re-raise with actionable context.
        raise ComponentNotFoundException(
            f"Component '{component_name}' not found on game object "
            f"'{game_object_name}' when calling '{method_name}'. "
            f"This usually means the app is not in the expected state "
            f"(e.g. not logged in, or the scene is still loading). "
            f"Original error: {e}"
        ) from e


# UI Interactions
def click_by_name(altdriver, name):
    try:
        altdriver.find_object(By.NAME, name).click()
        time.sleep(2)
    except:
        print(f"[WARN] Failed to click element by name: {name}")


def click_by_path(altdriver, path):
    try:
        altdriver.wait_for_object(By.PATH, path).click()
        time.sleep(2)
    except:
        print(f"[WARN] Failed to click element by path: {path}")


def assert_text_by_name(altdriver, name, expected_text):
    actual = altdriver.wait_for_object(By.NAME, name).get_text()
    time.sleep(2)
    assert actual == expected_text, f"[ASSERT FAIL] '{actual}' != '{expected_text}'"


def assert_text_by_path(altdriver, path, expected_text):
    actual = altdriver.wait_for_object(By.PATH, path).get_text()
    time.sleep(2)
    assert actual == expected_text, f"[ASSERT FAIL] '{actual}' != '{expected_text}'"


def get_text_by_name(altdriver, name):
    return altdriver.wait_for_object(By.NAME, name).get_text()


def get_text_by_path(altdriver, path):
    return altdriver.wait_for_object(By.PATH, path).get_text()


def find_element(altdriver, name):
    try:
        return altdriver.find_object(By.NAME, name)
    except:
        return None


def capture_failure_screenshot(altdriver, label):
    """Save a PNG of the screen a step GAVE UP on. Returns the bare filename.

    Called only after something has already been retried and still cannot
    proceed, because that screen is the evidence and it does not survive: by
    the time the run ends the app has been navigated on, recovered, or logged
    out. The bare filename is what the report, the panel and the Rally upload
    all expect (they resolve it against REPORTS_DIR/screenshots).
    """
    import os as _os                              # local: os is imported late below
    try:
        reports = _os.getenv("REPORTS_DIR", _os.path.expanduser("~/Downloads/reports"))
        shots = _os.path.join(reports, "screenshots")
        _os.makedirs(shots, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", str(label or ""))[:60].strip("_") or "failure"
        name = f"failed_{safe}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        altdriver.get_png_screenshot(_os.path.join(shots, name))
        logging.info(f"[Shot] gave up — saved {name}")
        return name
    except Exception as e:                        # noqa: BLE001 - never fail a run
        logging.warning(f"[Shot] could not capture '{label}': {e}")
        return ""


def find_any(altdriver, name, enabled=True):
    """``find_object`` that returns None instead of raising.

    ``enabled=False`` also matches INACTIVE objects — the difference between
    "this build has no such control" and "the control exists but is not active
    yet", which are two different failures to report.
    """
    try:
        return altdriver.find_object(By.NAME, name, enabled=enabled)
    except Exception:
        return None


def wait_for_any(altdriver, names, timeout=20, poll=0.25):
    """First of ``names`` to become active, or "" on timeout."""
    if isinstance(names, str):
        names = (names,)
    end = time.time() + timeout
    while True:
        for n in names:
            if n and find_any(altdriver, n) is not None:
                return n
        if time.time() >= end:
            return ""
        time.sleep(poll)


def _text_variants(label):
    """Casing/apostrophe spellings of a printed label. By.TEXT is exact."""
    base = (label or "").strip()
    out = [base, base.title(), base.upper(), base.lower(), base.capitalize()]
    for a, b in (("'", "’"), ("’", "'")):
        if a in base:
            out.append(base.replace(a, b))
    seen, uniq = set(), []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _find_by_text(altdriver, label):
    """The object printing ``label``, or None. Clicking a label works because
    Unity's raycast resolves it to the row/button that owns it."""
    for variant in _text_variants(label):
        try:
            obj = altdriver.find_object(By.TEXT, variant)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def _press_confirmed(altdriver, expect=(), gone=(), timeout=10):
    """Did the press actually move the UI? No expectation given -> assume yes."""
    if not expect and not gone:
        return True
    end = time.time() + timeout
    while True:
        if expect and wait_for_any(altdriver, expect, timeout=0.1):
            return True
        if gone and all(find_any(altdriver, g) is None for g in gone):
            return True
        if time.time() >= end:
            return False
        time.sleep(0.25)


def _press(obj):
    """Deliver a press to an object. Returns True when the call went through."""
    for action in ("click", "tap"):
        try:
            getattr(obj, action)()
            return True
        except Exception:
            continue
    return False


# How long to give the OUTER press before trying the child that owns the
# raycast. Measured on the live app: for the buttons that need the child
# ('Free Trial', "Let's Start") the outer press never lands, so a full
# confirmation window here is dead time — it cost ~20s per button, twice per
# guest run, waiting for a UI change that was never going to come.
PRESS_PROBE_SECONDS = 4.0


# Objects whose OUTER press is NEVER delivered: the interactive component lives
# in a layout child. Measured live — both of these needed the //Fitter child on
# every single run, so the outer press was pure cost (~5s each while its probe
# window ran down). For these the child is pressed FIRST and the outer object is
# only a fallback. Every other object keeps the original order, because it is
# the outer press that works for them.
PRESS_CHILD_FIRST = ("Free Trial", "Button")


_PRESS_CHILD_PATHS = ("//Fitter", "//Button", "//Btn")


def _press_candidates(altdriver, name):
    """The things to press for ``name``, in the order worth trying."""
    obj = find_any(altdriver, name)
    children = []
    for path in _PRESS_CHILD_PATHS:
        try:
            child = obj.find_object_from_object(By.PATH, path) if obj else None
        except Exception:                            # noqa: BLE001
            child = None
        if child is not None:
            children.append((f"via its {path} child", child))
    outer = [("", obj)] if obj is not None else []
    return (children + outer) if name in PRESS_CHILD_FIRST else (outer + children)


def press_object(altdriver, name, timeout=12, settle=1.0, expect=(), gone=(),
                 confirm=10):
    """Press the object called ``name`` and, when told what to expect, verify it.

    Some VocaTooki buttons wrap their interactive component in a ``Fitter``
    layout child, so a press on the outer object is delivered but ignored —
    those are listed in ``PRESS_CHILD_FIRST`` and their child is pressed first.

    Each candidate gets a SHORT probe except the last, which gets the full
    window; and before pressing the next one the confirmation is re-read, so a
    press that worked but was merely slow is never fired twice.
    """
    if not wait_for_any(altdriver, name, timeout=timeout):
        inactive = find_any(altdriver, name, enabled=False)
        logging.error(f"[Guest] '{name}' "
                      + ("exists but is inactive" if inactive is not None else "not found"))
        return False

    candidates = _press_candidates(altdriver, name)
    for index, (how, target) in enumerate(candidates):
        last = index == len(candidates) - 1
        if index and (expect or gone) and _press_confirmed(altdriver, expect, gone,
                                                           timeout=0.1):
            return True                              # a previous press landed late
        if not _press(target):
            continue
        logging.info(f"[Guest] pressed '{name}'" + (f" {how}" if how else ""))
        time.sleep(0.3 if (expect or gone) else settle)
        if _press_confirmed(altdriver, expect, gone,
                            timeout=confirm if last else min(confirm, PRESS_PROBE_SECONDS)):
            return True

    logging.error(f"[Guest] '{name}' did not move the UI "
                  f"(expected {list(expect) or 'anything'})")
    return False


def press_label(altdriver, label, timeout=8, settle=1.0, expect=(), gone=()):
    """Press the control that PRINTS ``label`` (e.g. "Arabic")."""
    end = time.time() + timeout
    while True:
        obj = _find_by_text(altdriver, label)
        if obj is not None:
            if _press(obj):
                logging.info(f"[Guest] pressed label '{label}'")
                time.sleep(settle)
                if _press_confirmed(altdriver, expect, gone):
                    return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


def _visible_text_object(altdriver, label):
    """An ON-SCREEN object printing ``label``, or None. Hidden panels print too."""
    for variant in _text_variants(label):
        try:
            objs = altdriver.find_objects(By.TEXT, variant)
        except Exception:                            # noqa: BLE001
            continue
        for obj in objs:
            if is_on_screen(altdriver, obj):
                return obj
    return None


def toggle_label(altdriver, toggle_obj):
    """The text printed on a toggle ("Male", "Arabic"), or ""."""
    for path in ("//Text - RTLTMP", "//Text", "//Label", "//Title - RTLTMP"):
        try:
            return (toggle_obj.find_object_from_object(By.PATH, path)
                    .get_text() or "").strip()
        except Exception:
            continue
    try:
        return (toggle_obj.get_text() or "").strip()
    except Exception:
        return ""


# Leaving an open activity: the activity LIST is ONE press away ('prev'), and
# the list is exactly where the next thumb is. return_to_map must not be used
# for this — its goal is the MAP, so after 'prev' has already landed on the
# list it presses 'Back' as well, leaves the level entirely, and the walk then
# has to re-open the level from the map. Measured live: ~13s of round trip per
# activity, three activities per level, three levels — about two minutes a run.
def tap_empty_area(altdriver, tries=6):
    """Tap a point that holds NO object — how this app dismisses the parrot's
    speech bubble (the instruction popup on every exam page, the "gray levels
    are locked" tip on the map).

    The candidate points are FRACTIONS of the live screen, and each one is
    checked with ``find_object_at_coordinates`` before it is tapped: the tap
    only happens where the app itself reports nothing, so no control is ever
    pressed by accident and no point is assumed to be empty at a resolution it
    was not measured at. Returns True when a tap was delivered.
    """
    try:
        width, height = altdriver.get_application_screensize()
        width, height = float(width), float(height)
    except Exception as e:                           # noqa: BLE001
        logging.warning(f"[Popup] could not read the screen size: {e}")
        return False

    # Edges and corners first: the middle of the screen is where the content is.
    for fx, fy in ((0.5, 0.94), (0.06, 0.5), (0.94, 0.5), (0.5, 0.06),
                   (0.06, 0.94), (0.94, 0.06)):
        point = (width * fx, height * fy)
        try:
            occupant = altdriver.find_object_at_coordinates(point)
        except Exception:                            # noqa: BLE001 - "nothing there"
            occupant = None
        if occupant is not None:
            continue
        try:
            altdriver.tap(point)
            logging.info(f"[Popup] tapped an empty point at "
                         f"({fx:.0%}, {fy:.0%}) of the screen to dismiss a popup")
            return True
        except Exception as e:                       # noqa: BLE001
            logging.debug(f"[Popup] tap at {point} failed: {e}")
    logging.warning("[Popup] found no empty point to tap")
    return False


def is_on_screen(altdriver, target, margin=0.0):
    """Is this object actually VISIBLE, or merely present in the hierarchy?

    "It answers a find" proves nothing here — the app keeps hidden UI alive and
    parked: a language row sat at y=-216, off screen, and still answered a find
    by text (pressing it did nothing, which is how a Turkish case registered an
    Arabic guest). So three independent signals are checked, and any one of
    them saying "not shown" is enough:

      * INSIDE THE VIEWPORT, measured against the app's own reported screen
        size, so it holds at any resolution
      * ACTIVE in the hierarchy
      * NOT FADED OUT by a CanvasGroup (alpha 0 is a normal way to hide a panel
        while leaving it in place, and it stays findable and positioned)

    A signal the object does not carry is skipped rather than assumed.
    """
    obj = find_any(altdriver, target) if isinstance(target, str) else target
    if obj is None:
        return False
    try:
        x, y = float(obj.x), float(obj.y)
    except (TypeError, ValueError):
        return False

    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:                                # noqa: BLE001
        width = height = 0.0
    if width and height:
        mx, my = width * margin, height * margin
        if not (mx <= x <= width - mx and my <= y <= height - my):
            return False

    try:
        active = obj.get_component_property("UnityEngine.GameObject",
                                            "activeInHierarchy", "UnityEngine.CoreModule")
        if active is False or str(active).strip().lower() == "false":
            return False
    except Exception:                                # noqa: BLE001
        pass

    try:
        alpha = obj.get_component_property("UnityEngine.CanvasGroup", "alpha", "UnityEngine")
        if alpha is not None and float(alpha) <= 0.01:
            return False
    except Exception:                                # noqa: BLE001
        pass
    return True


def _score_int(text):
    """The number in a score label, or None.

    Scores are PRINTED for humans: past a thousand the app writes "1,592".
    Reading the first run of digits gives 1 — which is why a leaderboard that
    agreed with the activities exactly (1592) still failed the comparison. So
    the separators come out before the number is read.
    """
    if not text:
        return None
    cleaned = re.sub(r"[,  '\s]", "", str(text))
    match = re.search(r"\d+", cleaned)
    return int(match.group()) if match else None


def _text_of(obj):
    """The text an object shows, however it stores it."""
    try:
        text = (obj.get_text() or "").strip()
        if text:
            return text
    except Exception:                                # noqa: BLE001
        pass
    return component_property(obj, "originalText")


SCREEN_TEXT_NAMES = ("Text - RTLTMP", "Text (TMP)", "Text", "MessageText",
                     "Title", "TitleText")


def screen_texts(altdriver, limit=30):
    """Every readable string on screen, found BY NAME.

    Not ``visible_texts``: that walks By.PATH contains() queries, which return
    nothing in this app — the subscribe gate read as empty twice before the
    text was fetched by object name instead.
    """
    out = []
    for name in SCREEN_TEXT_NAMES:
        try:
            objects = altdriver.find_objects(By.NAME, name) or []
        except Exception:                            # noqa: BLE001
            continue
        for obj in objects[:limit]:
            text = _text_of(obj)
            if text:
                out.append(text)
        if len(out) >= limit:
            break
    return out


def _slugish(text, limit=24):
    """A short, filename-safe version of a title."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text or "")).strip("-")[:limit] or "task"


# Text-ish objects, for reading a popup whose object names are not known.
_TEXT_SCAN_PATHS = ("//*[contains(@name,'Text')]", "//*[contains(@name,'TMP')]",
                    "//*[contains(@name,'Label')]", "//*[contains(@name,'Message')]")


def visible_texts(altdriver, limit=40):
    """Every non-empty string on screen right now, in hierarchy order.

    Reads a popup's WORDING without needing its object name: the app's popups
    are not all named consistently, and asserting on a name we guessed would
    prove nothing about what the user was actually shown.
    """
    seen, out = set(), []
    for path in _TEXT_SCAN_PATHS:
        try:
            objects = altdriver.find_objects(By.PATH, path)
        except Exception:                            # noqa: BLE001
            continue
        for obj in (objects or [])[:limit]:
            try:
                text = (obj.get_text() or "").strip()
            except Exception:                        # noqa: BLE001 - not a text object
                continue
            if text and text not in seen:
                seen.add(text)
                out.append(text)
        if len(out) >= limit:
            break
    return out


# The app's own label for a popup's message ("You've completed all free levels.
# Please subscribe to open more levels.").
POPUP_MESSAGE_OBJECT = "MessageText"


# These panels animate in, so a press that arrives with the panel is swallowed.
POPUP_CLICK_DELAY = 1.0


# Where the app keeps a popup's untyped message (confirmed live, and by the
# user): RTLTMPro's text component, whose "originalText" is the WHOLE string —
# the rendered label only holds however much has been typed out so far.
RTL_TEXT_COMPONENTS = (("RTLTMPro.RTLTextMeshPro", "RTLTMPro"),
                       ("RTLTMPro.RTLTextMeshPro3D", "RTLTMPro"))


def component_property(obj, prop):
    """``prop`` from the component on ``obj`` that carries it, or "".

    The known RTLTMPro components are tried first; only if neither answers is
    the object asked what components it has, so a renamed or swapped text class
    still resolves instead of failing silently.
    """
    for name, assembly in RTL_TEXT_COMPONENTS:
        try:
            value = obj.get_component_property(name, prop, assembly)
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    try:
        components = obj.get_all_components() or []
    except Exception:                                # noqa: BLE001
        return ""
    for component in components:
        name = (component.get("componentName") or component.get("name") or "")
        assembly = (component.get("assemblyName") or component.get("assembly") or "")
        if not name:
            continue
        try:
            value = obj.get_component_property(name, prop, assembly)
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def popup_text(altdriver, settle=1.5, limit=40):
    """The wording a popup is showing, as one string. Never raises.

    Reads ``MessageText`` — the label the app puts its message in — and waits
    for it to STOP GROWING before believing it: these panels animate in and the
    text types itself out, so a read taken too early returns a fragment (which
    is exactly what a screenshot of the same moment shows). Falls back to
    scanning the visible text objects when that label is not on screen.
    """
    time.sleep(settle)
    obj = find_any(altdriver, POPUP_MESSAGE_OBJECT)
    if obj is not None:
        previous = ""
        for _ in range(10):
            try:
                current = (obj.get_text() or "").strip()
            except Exception:                        # noqa: BLE001
                break
            if current and current == previous:
                return current
            previous = current
            time.sleep(0.3)
        if previous:
            return previous
    return " ".join(visible_texts(altdriver, limit=limit))
