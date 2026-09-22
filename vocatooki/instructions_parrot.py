"""The instructions parrot: its blocker, its bubble, and how to close them.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import ui_actions


# The text node inside the parrot's bubble. The parrot SPEAKS its instructions
# and the bubble then goes away on its own, so a board is only really free once
# there are no instruction words left on it.
PARROT_TEXT_NODE = "Text - RTLTMP"


def parrot_instructions_text(altdriver):
    """The instruction words on screen right now, or '' when there are none.

    Only counts while the bubble is actually SHOWN: the string can linger in a
    hidden (scaled-to-zero) bubble, and words nobody can see are not in the
    solver's way -- treating those as "still talking" would hang every entry.
    """
    if parrot_bubble_shown(altdriver) is not True:
        return ""
    for name in PARROT_BUBBLES:
        bubble = ui_actions.find_any(altdriver, name)
        if bubble is None:
            continue
        try:
            text = (bubble.find_object_from_object(
                By.NAME, PARROT_TEXT_NODE).get_text() or "").strip()
        except Exception:                            # noqa: BLE001
            continue
        if text:
            return text
    return ""


# The parrot's bubble, whichever side it is on. It is HIDDEN BY SCALING TO ZERO,
# not by going inactive: activeInHierarchy, enabled, position and findability are
# identical either way, so localScale is the only honest reading.
PARROT_BUBBLES = ("left_bubble", "right_bubble")


def parrot_bubble_shown(altdriver):
    """True/False when the bubble can be read, None when it cannot be.

    Measured live (PuzzleScene, 2026-09-01): shown = localScale 5.0 on every
    axis, hidden = 0.0. None means no bubble object was readable at all, which
    is a different thing from "hidden" and is why the caller keeps its old
    behaviour in that case rather than assuming a clean screen.
    """
    readable = False
    for name in PARROT_BUBBLES:
        obj = ui_actions.find_any(altdriver, name)
        if obj is None:
            continue
        try:
            scale = obj.get_component_property(
                "UnityEngine.Transform", "localScale", "UnityEngine.CoreModule")
        except Exception:                            # noqa: BLE001
            continue
        readable = True
        if any(abs(float(scale.get(axis) or 0.0)) > 0.01 for axis in ("x", "y", "z")):
            return True
    return False if readable else None


def dismiss_help_popup(altdriver, settle=0.4, verify_timeout=3.0, allow_tap=True):
    """Close the parrot's instruction bubble. Returns True when it acted.

    ``allow_tap=False`` never falls back to tapping an empty point — the
    automatic parrot guard uses it, because it runs on every screen and must
    only ever press the parrot's own control.

    Closed with 'HelpButton', the instructions icon -- the control the app gives
    for this bubble. It TOGGLES: pressing it blind on a screen where
    the bubble is already down OPENS one over the controls (measured live on
    PuzzleScene, a blind press took localScale from 0.0 to 5.0). So the bubble
    is read first, and the icon is only ever pressed when it is really up.

    Every exam page opens with a bubble ("All you have to do is drag the ...")
    that TYPES ITSELF OUT, so waiting for it to finish costs seconds on every
    page -- the solver can start the moment it is gone.
    """
    shown = parrot_bubble_shown(altdriver)
    if shown is False:
        logging.debug("[Help] no instruction bubble on screen — nothing to "
                      "dismiss (pressing 'HelpButton' here would OPEN one)")
        return False

    def gone():
        deadline = time.time() + verify_timeout
        while time.time() < deadline:
            if parrot_bubble_shown(altdriver) is False:
                return True
            time.sleep(0.3)
        return False

    # 'HelpButton' is the control the app gives for this bubble and is what
    # closes it (user, 2026-09-01). It TOGGLES, which is why it is only reached
    # here, where the bubble is known to be up. Tapping elsewhere is kept only
    # as a fallback: a full board has no empty point to tap, measured live on
    # BEE_CAREFUL ("found no empty point to tap").
    # The parrot ICON first; an empty point only as the fallback (user,
    # 2026-09-22) — when there is no icon, or pressing it left the bubble up.
    pressed = False
    obj = ui_actions.find_any(altdriver, "HelpButton")
    if obj is not None and ui_actions._press(obj):
        pressed = True
        if gone():
            logging.info("[Help] closed the instruction bubble via 'HelpButton'")
            return True
        logging.info("[Help] pressed 'HelpButton'"
                     + ("" if shown is None else " but the bubble is still up"))

    # Never tap blind after a press whose effect could not be read: HelpButton
    # toggles, so an unreadable bubble may already be closed.
    if allow_tap and (not pressed or shown is True) \
            and parrot_bubble_shown(altdriver) is not False \
            and ui_actions.tap_empty_area(altdriver) and gone():
        logging.info("[Help] dismissed the instruction bubble by tapping an empty "
                     "point" + (" (the icon did not close it)" if pressed
                                else " (no 'HelpButton' on this screen)"))
        return True
    if pressed:
        time.sleep(settle)
    return pressed


# The full-screen catcher that comes up with the INSTRUCTIONS PARROT when an
# activity opens. Its name says what it does: it blocks the screen until it is
# clicked. (The user named this object, 2026-08-17.)
SCREEN_BLOCKER = "BlockScreenWithoutClick"


def dismiss_screen_blocker(altdriver, tries=3, settle=1.0):
    """Click the instructions parrot away if it is up. Returns bool.

    An activity opens with the parrot reading out its instructions, over a
    full-screen `BlockScreenWithoutClick`. Until that is clicked away every
    press the solver makes lands on the blocker instead of the board, so the
    activity scores nothing and it looks like a solver that cannot play.

    Any click dismisses it, and the blocker is ITSELF a full-screen object — so
    clicking the object does it without tapping a coordinate (see
    [[no-coordinate-based-clicks]]).
    """
    dismissed = False
    for _ in range(tries):
        blocker = ui_actions.find_any(altdriver, SCREEN_BLOCKER)
        if blocker is None:
            break
        if not ui_actions._press(blocker):
            break
        dismissed = True
        logging.info(f"[Activity] clicked '{SCREEN_BLOCKER}' away (the parrot's bubble)")
        time.sleep(settle)
    return dismissed


def dismiss_replay_popup(altdriver):
    """Close the 'last attempt' notice that blocks a replayed activity.

    Re-entering an already-completed activity shows a popup ("this is your
    last chance to improve your score") over the board; the solver then plays
    against a blocked screen and scores 0. Present = active container found;
    close via its Yes / X button. Inactive popups are invisible to find_object,
    so this is a no-op on a fresh activity.
    """
    for container in ("PlaceHolder", "LastAttempetPopUp"):
        try:
            altdriver.find_object(By.NAME, container)
        except Exception:
            continue
        for btn in ("Yes", "X", "x", "CloseButton", "close", "Close"):
            try:
                altdriver.find_object(By.NAME, btn).click()
                time.sleep(1)
                logging.info(f"[Activity] dismissed replay popup ({container} -> '{btn}')")
                return True
            except Exception:
                continue
        logging.warning(f"[Activity] replay popup '{container}' found but no button worked")
    return False
