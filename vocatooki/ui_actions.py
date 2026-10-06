"""Finding, pressing and reading UI objects by NAME - the layer every flow builds on.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import os
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
    """Press the object called ``name`` the way a finger would (see ``_press``).

    Returns True when a press was delivered. A missing object is a WARN and
    False, as before. Whatever covered the object, or had to be bypassed, is
    in ``INPUT_FINDINGS`` — the step after the press decides what it meant.
    """
    try:
        obj = altdriver.find_object(By.NAME, name)
    except Exception:                                # noqa: BLE001
        print(f"[WARN] Failed to click element by name: {name}")
        return False
    delivered = _press(obj, altdriver)
    time.sleep(2)
    return delivered


def click_by_path(altdriver, path):
    """``click_by_name`` for a path. Returns True when the press was delivered."""
    try:
        obj = altdriver.wait_for_object(By.PATH, path)
    except Exception:                                # noqa: BLE001
        print(f"[WARN] Failed to click element by path: {path}")
        return False
    delivered = _press(obj, altdriver)
    time.sleep(2)
    return delivered


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


# ------------------------------------------------------------ the press
# 2026-10-06. A production bug got past every run: after a HARD level's three
# activities the game gives a gift, and after the gift the map no longer
# reacts to touches. The framework never noticed because AltTester's object
# click (``tapElement``) hands the press to the object's handlers DIRECTLY —
# no raycast, no EventSystem, nothing that covers the object gets a say. A
# finger goes through the screen, so from now on so does every press:
#
#   1. the object's position is read LIVE, from the object itself (the
#      no-hardcoded-pixel rule still holds: nothing here is a number that
#      was measured once);
#   2. the app is asked what a touch at that point would hit
#      (``find_object_at_coordinates``). When that is not the object, or
#      something inside it, the cover is RECORDED — the gift popup over the
#      map is exactly such a finding — but the tap is still delivered,
#      because that is what a finger does: whatever is on top gets it, and
#      whether anything happened is for the step AFTER the press to verify;
#   3. a real tap is delivered at that point.
#
# Only when the app reports nothing at all under the finger, or the object is
# off screen, is the old object click used as well — recorded as ``bypassed``.
# ``parrot_guard.install`` routes AltObject.click()/tap() through here too, so
# the solvers get the same treatment without a code change each.
# ``VT_PRESS=object`` restores the old object click for a comparison run.
PRESS_POLICY_ENV = "VT_PRESS"


# Every press that did not go cleanly through the screen, in order:
# {"kind", "target", "blocker", "note", "time"}. Kinds:
#   covered     another object sits between the finger and the target (tapped anyway)
#   untouchable nothing at all receives a touch where the target is
#   off-screen  the target's position is outside the screen (or unreadable)
#   bypassed    an object click was used (after untouchable / off-screen)
#   no-effect   a delivered tap changed nothing (recorded by the step that knows)
#   popup-dismissed  a popup was closed on the way somewhere (what, and its text)
# The lesson flows put these in the report; a test can assert on them.
INPUT_FINDINGS = []


# Hooks run before the raycast check of every screen press — the parrot guard
# registers itself here, so the check sees a screen it has already cleared.
BEFORE_SCREEN_PRESS = []


# The UNWRAPPED AltObject.click / .tap, filled in by parrot_guard.install():
# the bypass must call the real object press, not the screen wrapper again.
ORIGINAL_OBJECT_ACTIONS = {}


class PressOutcome:
    """What ``press_on_screen`` did. Truthy only when a tap was delivered."""

    __slots__ = ("status", "blocker", "point")

    def __init__(self, status, blocker="", point=None):
        self.status, self.blocker, self.point = status, blocker, point

    def __bool__(self):
        return self.status == "delivered"

    def __repr__(self):
        return f"PressOutcome({self.status}, blocker={self.blocker!r}, point={self.point})"


def press_policy():
    """``"screen"`` (the default) or ``"object"`` (``VT_PRESS=object``)."""
    return (os.getenv(PRESS_POLICY_ENV, "screen") or "screen").strip().lower()


def record_finding(kind, target, blocker="", note=""):
    """Remember an input finding and say it out loud. Returns the entry."""
    entry = {"kind": kind, "target": str(target or ""), "blocker": str(blocker or ""),
             "note": note, "time": time.time()}
    INPUT_FINDINGS.append(entry)
    level = logging.error if kind == "no-effect" else logging.warning
    level(f"[Press] {kind}: '{entry['target']}'"
          + (f" — '{entry['blocker']}' is in the way" if blocker else "")
          + (f" ({note})" if note else ""))
    return entry


def findings_since(index):
    """The findings recorded after ``index`` (``len(INPUT_FINDINGS)`` taken earlier)."""
    return list(INPUT_FINDINGS[index:])


def _same_object(a, b):
    """Two AltObject handles for the same game object?"""
    if a is None or b is None:
        return False
    for field in ("id", "transformId"):
        va, vb = getattr(a, field, None), getattr(b, field, None)
        if va is not None and vb is not None and va == vb:
            return True
    return False


# How far up from the raycast hit the target is looked for (a Button's Text
# child is the usual hit, two levels is the usual distance).
HIT_ANCESTOR_DEPTH = 6
# How far up from the TARGET the hit may be: a child image pressed through the
# Button that owns the raycast. Short on purpose — a full-screen ancestor is
# not "the target", it is what covers it.
TARGET_ANCESTOR_DEPTH = 2


def _parent_of(obj):
    try:
        return obj.get_parent()
    except Exception:                                # noqa: BLE001 - the root, or gone
        return None


def _reaches(hit, target):
    """Would a touch that the raycast gives to ``hit`` reach ``target``?

    Yes when ``hit`` IS the target, sits INSIDE it (a label inside a button),
    or is the near ancestor that owns the target's raycast.
    """
    if _same_object(hit, target):
        return True
    node = hit
    for _ in range(HIT_ANCESTOR_DEPTH):
        node = _parent_of(node)
        if node is None:
            break
        if _same_object(node, target):
            return True
    node = target
    for _ in range(TARGET_ANCESTOR_DEPTH):
        node = _parent_of(node)
        if node is None:
            break
        if _same_object(node, hit):
            return True
    return False


def _live_position(obj):
    """The object's CURRENT screen position, re-read from the app. None if unreadable."""
    try:
        obj = obj.update_object()
    except Exception:                                # noqa: BLE001 - keep the handle's values
        pass
    try:
        return float(obj.x), float(obj.y)
    except (TypeError, ValueError, AttributeError):
        return None


def _within_screen(altdriver, point):
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:                                # noqa: BLE001 - cannot tell: allow
        return True
    x, y = point
    return 0 <= x <= width and 0 <= y <= height


def what_is_at(altdriver, point):
    """The object a touch at ``point`` would hit, or None (the app says nothing is there)."""
    try:
        return altdriver.find_object_at_coordinates(point)
    except Exception:                                # noqa: BLE001 - "nothing there"
        return None


def _rounded(point):
    return tuple(int(round(v)) for v in point)


# Where to look for the object's touchable area when its pivot misses it:
# rings around the pivot, as fractions of the SHORTER screen side (so the
# search is the same at every resolution), nearest first; up before down,
# because a pivot is far more often at an object's bottom than its top.
TOUCH_SEARCH_RADII = (0.03, 0.06, 0.10, 0.15)
TOUCH_SEARCH_DIRECTIONS = ((0, 1), (0, -1), (1, 0), (-1, 0),
                           (1, 1), (-1, 1), (1, -1), (-1, -1))


def _touchable_point(altdriver, obj, origin):
    """A point near ``origin`` where a touch reaches ``obj``: ``(point, hit)`` or None."""
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:                                # noqa: BLE001
        return None
    unit = min(width, height)
    x0, y0 = origin
    for radius in TOUCH_SEARCH_RADII:
        for dx, dy in TOUCH_SEARCH_DIRECTIONS:
            point = (x0 + dx * radius * unit, y0 + dy * radius * unit)
            if not (0 <= point[0] <= width and 0 <= point[1] <= height):
                continue
            hit = what_is_at(altdriver, point)
            if hit is not None and _reaches(hit, obj):
                return point, hit
    return None


def press_on_screen(altdriver, obj, label=""):
    """Tap ``obj`` where it is on the screen, as a finger would. Never raises.

    Returns a ``PressOutcome``: truthy when the tap was delivered. ``blocker``
    names what the touch hit when that was NOT the object (recorded as a
    ``covered`` finding; the tap is delivered anyway). ``status`` is
    ``off-screen`` / ``error`` when no tap could be delivered, and
    ``untouchable`` when a tap was delivered where the app reports nothing.
    """
    name = label or getattr(obj, "name", "") or "?"
    for hook in list(BEFORE_SCREEN_PRESS):
        try:
            hook(altdriver, name)
        except Exception:                            # noqa: BLE001 - a hook never blocks a press
            pass
    point = _live_position(obj)
    if point is None or not _within_screen(altdriver, point):
        record_finding("off-screen", name, note=f"position {point}")
        return PressOutcome("off-screen", point=point)
    hit = what_is_at(altdriver, point)
    if hit is None or not _reaches(hit, obj):
        # The reported position is the transform's PIVOT, and that can sit
        # outside the object's own touchable area: the vending machine's
        # green button ("Toggle") reports a point 80px below itself, where a
        # touch hits the machine (seen live 2026-10-06). Before deciding
        # that something covers the object, look around the pivot for a
        # point the app gives to the object — where a finger would press.
        better = _touchable_point(altdriver, obj, point)
        if better is not None:
            logging.info(f"[Press] '{name}' is touchable at {_rounded(better[0])}, "
                         f"not at its reported {_rounded(point)}")
            point, hit = better
    blocker = ""
    if hit is None:
        record_finding("untouchable", name,
                       note=f"nothing receives a touch at {_rounded(point)}")
    elif not _reaches(hit, obj):
        blocker = getattr(hit, "name", "") or "?"
        record_finding("covered", name, blocker=blocker, note=f"at {_rounded(point)}")
    try:
        altdriver.tap(point)
    except Exception as e:                           # noqa: BLE001
        record_finding("error", name, note=f"tap failed: {e}")
        return PressOutcome("error", blocker=blocker, point=point)
    logging.info(f"[Press] tapped '{name}' at {_rounded(point)}"
                 + (f" (under '{blocker}')" if blocker else ""))
    return PressOutcome("untouchable" if hit is None else "delivered",
                        blocker=blocker, point=point)


def _object_action(obj, action):
    """The real AltObject press, unwrapped when the guard has wrapped it."""
    original = ORIGINAL_OBJECT_ACTIONS.get(action)
    if original is not None and isinstance(obj, tuple(ORIGINAL_OBJECT_ACTIONS.get("_types", ()))):
        return lambda: original(obj)
    return getattr(obj, action)


def _press(obj, altdriver=None):
    """Deliver a press to an object. Returns True when a press went through.

    Screen first (``press_on_screen``): a tap where the object is, whatever is
    on top. When the app reports NOTHING under the finger, or the object is
    off screen, the object press is used too and recorded as ``bypassed``,
    so the report says the screen was not exercised there.
    ``VT_PRESS=object`` keeps the old behaviour.
    """
    driver = altdriver if altdriver is not None else getattr(obj, "_altdriver", None)
    name = getattr(obj, "name", "") or "?"
    if driver is not None and press_policy() != "object":
        outcome = press_on_screen(driver, obj, label=name)
        if outcome:
            return True
    for action in ("click", "tap"):
        try:
            _object_action(obj, action)()
        except Exception:                            # noqa: BLE001
            continue
        if driver is not None and press_policy() != "object":
            record_finding("bypassed", name, note=f"object {action}() used after the screen press")
        return True
    return False


def _scene_of(altdriver):
    try:
        return altdriver.get_current_scene()
    except Exception:                                # noqa: BLE001
        return None


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
        if not _press(target, altdriver):
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
            if _press(obj, altdriver):
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
