"""Logging in and out, the first-entry gender popup, and the logged-in user.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import guest_flow, map_navigation, scene_names, scenes, ui_actions


def login(altdriver, username=None, password=None, timeout=30):
    # Only log out if we're not already on the login screen.
    # The "Logout" method lives on the AltTesterUtils component, which only
    # exists once logged in. Calling it on the login/start screen raises
    # ComponentNotFoundException, so we guard the call.
    if not scenes._login_screen_visible(altdriver):
        try:
            ui_actions.call_method(altdriver, "AltTesterUtils", "Logout")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Logout skipped: {e}")

    # Wait for the login screen to actually render before typing. A fixed sleep
    # after logout is not enough — the login UI (NewStartScene) can take longer,
    # and if we never reach it we want a clear error, not a bare WaitTimeOut on
    # a single field.
    if not scenes._wait_for_login_screen(altdriver, timeout=timeout):
        try:
            current_scene = altdriver.get_current_scene()
        except Exception:
            current_scene = "<unknown>"
        raise AssertionError(
            f"Login screen did not appear within {timeout}s "
            f"(current scene: '{current_scene}'). "
            f"Expected fields: {', '.join(scenes.LOGIN_SCREEN_FIELDS)}."
        )

    altdriver.wait_for_object(By.NAME, "UserInputField", enabled=True).set_text(username)
    altdriver.wait_for_object(By.NAME, "PasswordInputField", enabled=True).set_text(password)
    altdriver.wait_for_object(By.NAME, "LoginButton").click()
    time.sleep(7)


def return_to_start(altdriver, max_steps=10):
    """Back out all the way to the start screen.

    The app's reliable anchor: pressing back from the MAP leads here, and from
    here GO-Map opens the map again. So when backing out one screen at a time
    has not found the map, keep going until the start screen shows and come
    back down the known path. Never raises.
    """
    for step in range(max_steps):
        if scenes._current_scene(altdriver) == scene_names.START_SCENE:
            logging.info("[Map Navigation] Reached the start screen.")
            return True
        clicked = None
        for name in map_navigation._BACK_BUTTON_NAMES:
            obj = ui_actions.find_element(altdriver, name)
            if obj is None:
                continue
            try:
                obj.click()
                clicked = name
                break
            except Exception:
                continue
        if not clicked:
            logging.info("[Map Navigation] No back/close button on this screen.")
            break
        logging.info(f"[Map Navigation] back step {step + 1}: clicked '{clicked}'")
        time.sleep(3)
    return scenes._current_scene(altdriver) == scene_names.START_SCENE


def logout_via_ui(altdriver, timeout=45):
    """Reach the logged-out welcome screen.

    ``AltTesterUtils.Logout`` FIRST — it is the fastest and safest way out of a
    session, and it is what every other logout in this module uses. The UI route
    (LogoutButton -> YesButton) is only a fallback, for the one case that call
    cannot serve: a guest session, where the component may not exist at all.

    (The name is historical: this did press the UI first, and the order was
    turned around once the component proved both quicker and more reliable.)
    """
    global _LAST_LOGIN_USER
    # Log out through the AltTesterPrefab, the way the rest of this module does
    # (``AltTesterUtils.Logout``). "Free Trial is findable" is NOT proof we are
    # already logged out — the welcome panel can be present while the login form
    # is what's on screen, and the trial entry then does nothing at all
    # (verified live: the press reported success and the UI never moved).
    try:
        ui_actions.call_method(altdriver, "AltTesterUtils", "Logout")
        time.sleep(2)
        logging.info("[Guest] logged out via AltTesterUtils")
    except Exception as e:                       # noqa: BLE001
        logging.info(f"[Guest] AltTesterUtils.Logout unavailable ({e}); using the UI")

    if ui_actions.wait_for_any(altdriver, guest_flow.GUEST_ENTRY["trial"], timeout=15):
        _LAST_LOGIN_USER = None
        return True

    # Fallback: press the UI logout (start screen -> confirm popup).
    return_to_start(altdriver)
    if ui_actions.find_any(altdriver, "LogoutButton") is not None:
        ui_actions.press_object(altdriver, "LogoutButton", settle=2.0, expect=("YesButton",))
        if ui_actions.wait_for_any(altdriver, "YesButton", timeout=12):
            ui_actions.press_object(altdriver, "YesButton", settle=4.0,
                         expect=guest_flow.GUEST_WELCOME_MARKERS)

    ok = bool(ui_actions.wait_for_any(altdriver, guest_flow.GUEST_ENTRY["trial"], timeout=timeout))
    if ok:
        # A guest session belongs to nobody: clear the cache or the next
        # ensure_logged_in() would decide it is "already logged in".
        _LAST_LOGIN_USER = None
    else:
        logging.error(f"[Guest] no trial entry after logout (state "
                      f"{scenes.app_state(altdriver)}, scene {scenes._current_scene(altdriver)})")
    return ok


# The hub appears before its buttons are listening; a feature pressed inside
# this window is swallowed. Asked for by the user (2026-08-17).
LOGIN_SETTLE_SECONDS = 7.0


# First entry only: the app asks which avatar the user is before it will let
# them do anything, and answering navigates INTO the avatar builder — so a run
# that ignores it is left on the wrong scene with every later press missing.
# Route verified live 2026-08-18: NewStartScene -> GenderSelectPopup(Clone) ->
# Male/Female -> AvatarBuilderScene -> BackButton -> NewStartScene.
GENDER_POPUP = "GenderSelectPopup(Clone)"


GENDER_OPTIONS = ("Male", "Female")


AVATAR_BUILDER_SCENE = scene_names.AVATAR_SCENE                  # renamed in 4.6.0, see there


# The LONGEST a login waits to see whether this is a first entry. It polls and
# returns the moment the popup shows, so a first entry is handled at once; only
# an account that has already answered pays the full wait.
GENDER_POPUP_TIMEOUT = 20.0


def handle_gender_select(altdriver, choose="Male", timeout=GENDER_POPUP_TIMEOUT):
    """Answer the first-entry "You are" popup and come back. Returns bool.

    True when the popup was there and was dealt with, False when this account
    had already answered it — which is not a failure, just not a first entry.
    Never raises: no run should die because a one-off popup moved.
    """
    if not ui_actions.wait_for_any(altdriver, (GENDER_POPUP,), timeout=timeout):
        return False                                 # not a first entry

    wanted = choose if choose in GENDER_OPTIONS else GENDER_OPTIONS[0]
    picked = ""
    for option in (wanted,) + GENDER_OPTIONS:        # the asked-for one first
        if ui_actions.find_any(altdriver, option) is not None and ui_actions.press_object(altdriver, option,
                                                                    settle=2.0):
            picked = option
            break
    if not picked:
        logging.error(f"[Login] the gender popup is up but neither "
                      f"{GENDER_OPTIONS} could be pressed")
        return False
    logging.info(f"[Login] first entry: chose '{picked}' on the gender popup")

    # Answering it opens the AVATAR BUILDER. Leaving is not optional: the run
    # would otherwise carry on pressing start-screen buttons from another scene.
    if scenes.wait_for_scene(altdriver, AVATAR_BUILDER_SCENE, timeout=20):
        if not ui_actions.press_object(altdriver, "BackButton", settle=2.0):
            logging.warning("[Login] could not press Back in the avatar builder")
        scenes.wait_for_scene(altdriver, scene_names.START_SCENE, timeout=20)
    if scenes._current_scene(altdriver) != scene_names.START_SCENE:
        logging.warning(f"[Login] after the gender popup the app is on "
                        f"{scenes._current_scene(altdriver)}, not the start screen")
    return True


def fresh_login(altdriver, username, password):
    """Log OUT and back in, so a run starts from a known account. Returns bool.

    Never trusts "we are already logged in": a leaderboard row is matched by
    the player's NAME, so a leftover session quietly measures somebody else —
    which is exactly what a stale session did on 2026-08-16, scoring an event
    under 'spy 6' while the case was written for another account.

    Logging out goes through ``AltTesterUtils.Logout``: it is the fastest and
    safest way out of a session, and it is what every other logout here uses.
    """
    global _LAST_LOGIN_USER
    try:
        ui_actions.call_method(altdriver, "AltTesterUtils", "Logout")
        time.sleep(2)
        logging.info(f"[Login] logged out before signing in as {username}")
    except Exception as e:                           # noqa: BLE001
        logging.info(f"[Login] AltTesterUtils.Logout unavailable ({e})")
    _LAST_LOGIN_USER = None                          # force a real login
    try:
        login(altdriver, username, password)
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Login] could not sign in as {username}: {e}")
        return False

    # PROVE we are in before saying so. ensure_logged_in() skips the login
    # whenever _LAST_LOGIN_USER matches, so marking a login that did not happen
    # makes every later step run against the login screen — which is exactly
    # how a card walk reported "GO-Events is not on the start screen".
    if not ui_actions.wait_for_any(altdriver, scenes.HUB_MARKERS, timeout=30):
        logging.error(f"[Login] {username}: the hub never appeared after login "
                      f"(still on {scenes._current_scene(altdriver)})")
        return False
    # A FIRST entry stops here to ask which avatar the user is, and answering
    # walks into the avatar builder — so it is dealt with before anything else
    # tries to press a start-screen button.
    #
    # This poll doubles as the settle below: it returns the moment the popup
    # shows, and the hub is building its buttons meanwhile either way, so an
    # account that has already answered is not charged twice for waiting.
    settle_from = time.time()

    # Let the screen finish building FIRST. It grows a few buttons at a time,
    # so waiting for that to stop is what proves it is ready — a fixed sleep is
    # guesswork in both directions.
    scenes.wait_for_start_scene_ready(altdriver)

    # The popup is part of that build, so by now it is either up or not coming.
    # It still gets whatever is left of its own budget rather than a single
    # look, but an account that has already answered no longer pays the full
    # wait on top of the wait it just did.
    spent = time.time() - settle_from
    handle_gender_select(altdriver,
                         timeout=max(3.0, GENDER_POPUP_TIMEOUT - spent))

    waited = time.time() - settle_from
    if waited < LOGIN_SETTLE_SECONDS:
        time.sleep(LOGIN_SETTLE_SECONDS - waited)
    _LAST_LOGIN_USER = username
    logging.info(f"[Login] signed in as {username}")
    return True


_LAST_LOGIN_USER = None


def ensure_logged_in(altdriver, username, password):
    """Login only when needed.

    Several generated test cases often run in one pytest session with the same
    user; logging out/in between them wastes ~40s each. Skip the login when
    this session already logged that user in and we are not on the login
    screen. A different user (or a logged-out app) gets the full login flow.
    """
    global _LAST_LOGIN_USER
    if _LAST_LOGIN_USER == username and not scenes._login_screen_visible(altdriver):
        logging.info(f"[Login] already logged in as {username} — skipping login")
        return
    login(altdriver, username, password)
    # A brand-new user is asked which avatar they are before anything else, and
    # answering opens the avatar builder. Only ever on a FIRST entry: an
    # account that has answered already just carries on. Checked here as well
    # as in fresh_login, because this is the other way a run signs in — and it
    # costs nothing on the path above, which does not log in at all.
    handle_gender_select(altdriver)
    _LAST_LOGIN_USER = username
