"""The waits that decide a screen is really ready (login, hub, onboarding).

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time

from vocatooki import guest_flow, scene_names, ui_actions


# Login Utility
LOGIN_SCREEN_FIELDS = ("UserInputField", "PasswordInputField", "LoginButton")


def _login_screen_visible(altdriver):
    """True only when all login-screen fields are present (mirrors LoginPage.is_open)."""
    return all(ui_actions.find_element(altdriver, name) is not None for name in LOGIN_SCREEN_FIELDS)


def _wait_for_login_screen(altdriver, timeout=30, poll=0.5):
    """Poll until the login screen is fully shown, or timeout. Returns bool."""
    end = time.time() + timeout
    while time.time() < end:
        if _login_screen_visible(altdriver):
            return True
        time.sleep(poll)
    return False


def _current_scene(altdriver):
    try:
        return altdriver.get_current_scene()
    except Exception:
        return None


# Every scene builds itself over a second or two, and a press into that window
# is swallowed. A scene is "ready" when it has stopped GROWING — counting the
# ACTIVE objects is cheap (about 0.04s for a scene of ~130) and works for any
# scene without knowing a thing about it.
SCENE_READY_TIMEOUT = 12.0        # a ceiling, not a sleep


SCENE_READY_STABLE_SECONDS = 1.5  # no new objects for this long = built


SCENE_READY_POLL_SECONDS = 0.4


def wait_for_scene_ready(altdriver, timeout=SCENE_READY_TIMEOUT,
                         stable_for=SCENE_READY_STABLE_SECONDS, label=""):
    """Wait until the current scene has finished building. Returns bool.

    Watches the number of ACTIVE objects and waits for it to stop RISING.
    Rising means the scene is still spawning; once it stops, what is on screen
    is what there is going to be. Deliberately not "unchanged": a live game
    scene has things appearing and disappearing all the time, and a run should
    not sit out the whole timeout waiting for a board that will never be still.

    Returns as soon as it settles — a fast scene is not punished — and never
    raises: a scene that cannot be counted is simply carried on with.
    """
    deadline = time.time() + timeout
    peak, grew_at = -1, time.time()
    while time.time() < deadline:
        try:
            count = len(altdriver.get_all_elements() or [])
        except Exception:                            # noqa: BLE001
            return False                             # unreadable: carry on
        if count > peak:
            peak, grew_at = count, time.time()
        elif peak > 0 and (time.time() - grew_at) >= stable_for:
            logging.debug(f"[Scene] {label or _current_scene(altdriver)} ready "
                          f"({peak} objects)")
            return True
        time.sleep(SCENE_READY_POLL_SECONDS)
    logging.info(f"[Scene] {label or _current_scene(altdriver)} still growing "
                 f"after {timeout}s ({peak} objects); carrying on")
    return peak > 0


def wait_for_scene(altdriver, scene, timeout=40, poll=0.5, ready=True):
    """Poll until the app is in ``scene`` AND it has finished building.

    Arriving in a scene is not the same as being able to use it: Unity reports
    the scene as soon as it loads, while the objects keep spawning for another
    second or two, and a press into that window is simply swallowed. So every
    entry waits for the scene to stop growing as well (``ready=False`` to skip
    it, e.g. when only the name is being checked).

    ``scene`` may also be a tuple of names — any one of them counts (a scene a
    build renamed, e.g. the avatar builder).

    Returns bool, never raises.
    """
    wanted = (scene,) if isinstance(scene, str) else tuple(scene)
    end = time.time() + timeout
    while True:
        here = _current_scene(altdriver)
        if here in wanted:
            if ready:
                wait_for_scene_ready(altdriver, label=here)
                # A scene that has just been entered is where the parrot's intro
                # plays: clear it now, before the caller's first press.
                from vocatooki import parrot_guard
                parrot_guard.on_scene_entered(altdriver, here, built=True)
            return True
        if time.time() >= end:
            logging.error(f"[Guest] scene {' / '.join(wanted)} not reached "
                          f"(still '{_current_scene(altdriver)}')")
            return False
        time.sleep(poll)


# Objects that only exist while the guest onboarding wizard is on screen.
GUEST_WIZARD_MARKERS = ("Button_2", "Button_1", "InputField - RTLTMP")


def onboarding_visible(altdriver):
    """True while the trial/registration wizard is on screen."""
    return any(ui_actions.find_any(altdriver, n) is not None for n in GUEST_WIZARD_MARKERS)


def in_app(altdriver):
    """True when we are inside the app rather than on login or in onboarding.

    Findability is NOT visibility here: on NewStartScene the login panel, the
    trial panels and the hub are all findable at once, so no positive "is this
    object there" test can tell them apart — "GO-Map exists" does not mean we
    are past login, and "Free Trial exists" does not mean we are not in the app.
    Only three things are decisive: the map scene, the login fields, and the
    wizard's own controls. So this is deliberately a negative test.
    """
    if _current_scene(altdriver) == scene_names.MAP_SCENE:
        return True
    if _login_screen_visible(altdriver):
        return False
    return not onboarding_visible(altdriver)


def app_state(altdriver):
    """'login' | 'onboarding' | 'hub' | 'welcome' | 'elsewhere'.

    Checked most-specific first, because the panels overlap: the login overlay
    sits ON the start screen with the hub live behind it, and the trial panels
    sit on top of the login one.
    """
    if _login_screen_visible(altdriver):
        return "login"
    if onboarding_visible(altdriver):
        return "onboarding"
    if in_app(altdriver):
        return "hub"
    if any(ui_actions.find_any(altdriver, n) is not None for n in guest_flow.GUEST_WELCOME_MARKERS):
        return "welcome"
    return "elsewhere"


# A visible one of these is a crash/blocked run as far as a test is concerned.
GUEST_ERROR_POPUPS = ("ErrorPanel", "ErrorPopUp", "ConnectionIssuePopup",
                      "DrainingQueuePanel", "BlockScreen")


# Proof that a login landed: the hub's own buttons. Checked instead of trusting
# the login call, because ensure_logged_in() then SKIPS the login whenever the
# cached user matches — so a login that silently did not happen sends every
# later step to the login screen.
HUB_MARKERS = ("GO-Events", "GO-Map", "GO-Tasks", "GO-Daily")


# The start screen builds its buttons a few at a time, so "how many are there"
# still rising means it is not finished. Waiting for that count to STOP rising
# is what proves the screen is built — a fixed sleep is both slower than it
# needs to be on a fast load and too short on a slow one.
START_SCENE_BUTTONS = ("GO-Map", "GO-Tasks", "GO-Events", "GO-Audiobook",
                       "GO-Competitions", "GO-Treasure_Island", "GO-Daily",
                       "GO-Dialogue", "GO-Multiplayer", "GO-Avatar_Builder",
                       "SettingsButton", "WordListButton", "LogoutButton")


START_SCENE_READY_TIMEOUT = 15.0     # the LONGEST it waits, not a sleep


START_SCENE_STABLE_SECONDS = 2.5     # unchanged this long = finished building


START_SCENE_POLL_SECONDS = 1.0


def wait_for_start_scene_ready(altdriver, timeout=START_SCENE_READY_TIMEOUT,
                               stable_for=START_SCENE_STABLE_SECONDS):
    """Wait until the start screen has finished loading. Returns bool.

    Counts how many of the hub's buttons are on screen and waits for that
    number to STOP changing — the screen is built when it stops growing, which
    is a different moment on every account and every machine. Returns as soon
    as it settles, so a fast load is not punished; ``timeout`` is a ceiling.

    Not "are all of them there": a new account does not have every feature (a
    fresh user showed no GO-Daily), and demanding the full set would wait out
    the whole timeout on a screen that was ready.
    """
    deadline = time.time() + timeout
    seen, steady_since = -1, time.time()
    while time.time() < deadline:
        count = sum(1 for name in START_SCENE_BUTTONS
                    if ui_actions.find_any(altdriver, name) is not None)
        if count != seen:
            seen, steady_since = count, time.time()
        elif count > 0 and (time.time() - steady_since) >= stable_for:
            logging.info(f"[Login] start screen ready — {count} buttons, "
                         f"steady for {stable_for}s")
            return True
        time.sleep(START_SCENE_POLL_SECONDS)
    logging.warning(f"[Login] start screen still settling after {timeout}s "
                    f"({seen} buttons); carrying on")
    return seen > 0


def _wait_leaves_scene(altdriver, scene, timeout=15, poll=0.5):
    """Wait until the app is no longer in ``scene``. Returns bool.

    Used as PROOF that a press landed: on Treasure Island nothing else
    distinguishes a Play that started an activity from one the panel swallowed.
    """
    end = time.time() + timeout
    while time.time() < end:
        if _current_scene(altdriver) != scene:
            return True
        time.sleep(poll)
    return False


def app_health(altdriver):
    """``('ok', '')`` | ``('error', popup)`` | ``('dead', why)``.

    "No crash happened" in a guest run means two things: the driver still
    answers, and the app is not sitting on an error/connection popup.
    """
    try:
        altdriver.get_current_scene()
    except Exception as e:                       # noqa: BLE001
        return "dead", str(e)[:120]
    for name in GUEST_ERROR_POPUPS:
        if ui_actions.find_any(altdriver, name) is not None:
            return "error", name
    return "ok", ""
