"""Parrot guard: clear the instructions parrot before ANY action, on every screen.

The parrot arrives on its own schedule — when a scene opens (the full-screen
`BlockScreenWithoutClick` first, then a bubble that types its words out), and
again mid-game as an idle hint (measured on BEE_CAREFUL, 2026-09-14: the bubble
came back and dimmed the board). While it is up, every press lands on it. Until
now only a few flows cleared it (activity start, exam pages, the guest walk);
everything else pressed straight into it.

So instead of asking each flow to remember, this module wraps the AltTester
actions themselves. Before a click / tap / swipe / touch begins:

  * the scene has CHANGED since the last action -> wait for the new scene to
    finish building, then keep clearing the parrot until it has stayed away for
    a quiet moment (the intro is a sequence, one knock is not enough);
  * same scene -> one quick check, throttled, clearing whatever is up.

How it clears: the full-screen blocker is clicked as an OBJECT; the bubble is
closed by clicking the parrot ICON (`HelpButton`), and only when the icon is
missing or did not close it is an empty point tapped as the fallback — a point
the app itself reports holds no object. `HelpButton` is pressed only while the
bubble is really shown (it toggles). It never touches the wizard's
`TookiCloudText`, which is a prompt, not the parrot's bubble.

Mid-gesture calls (move_touch, end_touch, pointer_up) are NOT wrapped: pressing
HelpButton in the middle of a held drag would break it (Sharks steers that way).

Switch it off with the environment variable ``VT_PARROT_GUARD=0``, or around a
block with ``with parrot_guard.paused(): ...``.
"""

import contextlib
import functools
import logging
import os
import threading
import time

from vocatooki import instructions_parrot, scenes

# Seconds between two quick checks on the same scene. An action loop (a
# crossword typing letters) would otherwise pay a check per press.
CHECK_INTERVAL = 0.75
# Clearing a fresh scene's intro: give up after this long ...
INTRO_TIMEOUT = 15.0
# ... and count it over once nothing has needed clearing for this long. The
# bubble scales up a beat AFTER the blocker goes.
INTRO_QUIET = 1.5
# How long a fresh scene is watched for an intro that has not shown yet.
ARRIVAL_GRACE = 0.6
POLL = 0.3

# Objects that ARE the parrot's controls — an action aimed at one of them is
# the clearing itself, and must not trigger another round of it.
PARROT_CONTROLS = ("BlockScreenWithoutClick", "HelpButton", "left_bubble", "right_bubble")

_OBJECT_ACTIONS = ("click", "tap", "pointer_down")
_DRIVER_ACTIONS = ("click", "tap", "swipe", "multipoint_swipe", "begin_touch", "hold_button")

_local = threading.local()          # re-entrancy: the guard's own presses are actions too
# Extra callbacks run before every wrapped action, after the parrot check —
# e.g. the mid-activity evidence frame. Each gets the driver; errors are ignored.
ACTION_HOOKS = []
_state = {}                         # id(driver) -> {"scene": str, "checked": float}
_installed = False


def enabled():
    """Off when VT_PARROT_GUARD is 0/false/off, or inside ``paused()``."""
    if getattr(_local, "paused", 0):
        return False
    return os.getenv("VT_PARROT_GUARD", "1").strip().lower() not in ("0", "false", "off", "no")


@contextlib.contextmanager
def paused():
    """Run a block with the guard off (e.g. a test that ASSERTS the parrot shows)."""
    _local.paused = getattr(_local, "paused", 0) + 1
    try:
        yield
    finally:
        _local.paused -= 1


def _clear_once(driver):
    """One pass: knock the blocker away, close a SHOWN bubble. True if it acted."""
    acted = bool(instructions_parrot.dismiss_screen_blocker(driver, tries=1, settle=0.3))
    # `is True`, not truthy: None means "could not read the bubble", and pressing
    # HelpButton blind OPENS the bubble on a screen where it was down.
    if instructions_parrot.parrot_bubble_shown(driver) is True:
        # The parrot ICON first ('HelpButton', the parrot's face in the corner);
        # an empty point is tapped only if the icon is missing or did not close
        # it (user, 2026-09-22).
        acted = bool(instructions_parrot.dismiss_help_popup(driver, allow_tap=True)) or acted
    return acted


def _clear_intro(driver, scene=""):
    """Keep clearing a fresh scene's intro until it has stayed away. True if it acted."""
    start = time.time()
    deadline = start + INTRO_TIMEOUT
    acted, quiet_since = False, None
    while time.time() < deadline:
        if _clear_once(driver):
            acted, quiet_since = True, None
        elif not acted:
            if time.time() - start >= ARRIVAL_GRACE:
                return False                    # no intro on this screen
        else:
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since >= INTRO_QUIET:
                logging.info(f"[Parrot] cleared on entering {scene or 'the scene'}")
                return True
        time.sleep(POLL)
    logging.warning(f"[Parrot] still appearing on {scene or 'the scene'} "
                    f"after {INTRO_TIMEOUT:.0f}s — carrying on")
    return acted


def on_scene_entered(driver, scene=None, built=False):
    """Clear the parrot on a scene that has just been entered.

    ``built=True`` when the caller has already waited for the scene to finish
    building (``scenes.wait_for_scene`` does), so it is not waited for twice.
    Never raises.
    """
    if not enabled() or getattr(_local, "busy", False):
        return False
    _local.busy = True
    try:
        scene = scene or scenes._current_scene(driver)
        st = _state.setdefault(id(driver), {"scene": None, "checked": 0.0})
        st["scene"] = scene
        if not built:
            scenes.wait_for_scene_ready(driver, label=scene or "scene")
        acted = _clear_intro(driver, scene)
        st["checked"] = time.time()
        return acted
    except Exception as e:                      # noqa: BLE001 - never break an action
        logging.debug(f"[Parrot] scene-entry check failed: {e}")
        return False
    finally:
        _local.busy = False


def before_action(driver, target=""):
    """What runs ahead of every wrapped action. Never raises."""
    if not enabled() or getattr(_local, "busy", False) or target in PARROT_CONTROLS:
        return
    st = _state.setdefault(id(driver), {"scene": None, "checked": 0.0})
    if time.time() - st["checked"] < CHECK_INTERVAL:
        return
    _local.busy = True
    try:
        scene = scenes._current_scene(driver)
        if scene and scene != st["scene"]:
            _local.busy = False                 # on_scene_entered takes the flag itself
            on_scene_entered(driver, scene)
            return
        if _clear_once(driver):
            logging.info(f"[Parrot] cleared on {scene or 'the screen'} before "
                         f"pressing {target or 'the next control'}")
        st["checked"] = time.time()
    except Exception as e:                      # noqa: BLE001
        logging.debug(f"[Parrot] check before '{target}' failed: {e}")
    finally:
        _local.busy = False


def _wrap(method, get_driver, get_target):
    @functools.wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            driver = get_driver(self)
            before_action(driver, get_target(self))
            if not getattr(_local, "busy", False):
                for hook in list(ACTION_HOOKS):
                    try:
                        hook(driver)
                    except Exception:            # noqa: BLE001
                        pass
        except Exception:                        # noqa: BLE001
            pass
        return method(self, *args, **kwargs)
    guarded._parrot_guarded = True
    return guarded


def install():
    """Wrap the AltTester action methods once, process-wide. Idempotent."""
    global _installed
    if _installed:
        return
    from alttester import AltDriver
    from alttester.altobject import AltObject

    for name in _OBJECT_ACTIONS:
        method = getattr(AltObject, name, None)
        if method is not None and not getattr(method, "_parrot_guarded", False):
            setattr(AltObject, name, _wrap(method, lambda o: o._altdriver,
                                           lambda o: getattr(o, "name", "")))
    for name in _DRIVER_ACTIONS:
        method = getattr(AltDriver, name, None)
        if method is not None and not getattr(method, "_parrot_guarded", False):
            setattr(AltDriver, name, _wrap(method, lambda d: d, lambda d: ""))
    _installed = True
    logging.debug("[Parrot] guard installed on AltObject/AltDriver actions")
