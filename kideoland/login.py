"""Kideo Land login and logout, built on Voca Tooki's login_session.

What is shared and what is not (verified live 2026-09-29):

- Logout: Voca Tooki's ``logout_via_ui`` works unchanged. This build has no
  ``AltTesterUtils`` at all, so its first try fails and it presses
  ``LogoutButton`` -> ``YesButton``.
- Login: Kideo Land first shows a choice screen. Pressing ``Login/Fitter``
  there brings up the very same ``UserInputField`` / ``PasswordInputField`` /
  ``LoginButton`` that Voca Tooki's ``login`` fills in.
- First entry: ``KideoLandGenderSelectPopup(Clone)`` -> Male -> the avatar
  builder -> BackButton -> the start scene. Same route as Voca Tooki, other names.
"""

import logging
import time

from alttester import By

from kideoland import names
from vocatooki import login_session, scenes, ui_actions


def islands_visible(driver):
    """True once the start scene's islands are built -- the logged-in hub."""
    try:
        return any(o.name.startswith(names.ISLAND_PREFIX)
                   for o in driver.get_all_elements())
    except Exception:
        return False


def current_scene(driver):
    try:
        return driver.get_current_scene()
    except Exception:
        return ""


def wait_for_scene(driver, scene, timeout=30, poll=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if current_scene(driver) == scene:
            return True
        time.sleep(poll)
    return False


# The buttons a user presses to leave a screen, tried in this order.
BACK_BUTTONS = ("Back", "BackButton", "prev")


def back_to_start(driver, max_steps=8):
    """Press the screens' own back buttons until the start scene shows. Returns bool."""
    for _ in range(max_steps):
        if current_scene(driver) == names.START_SCENE:
            return True
        for button in BACK_BUTTONS:
            if ui_actions.find_any(driver, button) is not None:
                ui_actions.click_by_name(driver, button)
                time.sleep(3)
                break
        else:
            time.sleep(2)
    return wait_for_scene(driver, names.START_SCENE, timeout=15)


def open_login_form(driver, timeout=90):
    """From wherever the app is, reach the username/password fields. Returns bool."""
    deadline = time.time() + timeout
    logged_out = False
    while time.time() < deadline:
        if scenes._login_screen_visible(driver):
            return True
        # Inside a level, an exam or an island map: walk back to the start
        # scene first -- the logout button and the login choice live there.
        if current_scene(driver) not in ("", names.START_SCENE):
            back_to_start(driver)
            continue
        # Still logged in: leave the session the way a user would.
        if not logged_out and (islands_visible(driver)
                               or ui_actions.find_any(driver, "LogoutButton") is not None):
            logging.info("[KL Login] a session is open -- logging out first")
            login_session.logout_via_ui(driver)
            logged_out = True
            continue
        try:
            driver.find_object(By.PATH, names.LOGIN_CHOICE_BUTTON_PATH).click()
            logging.info("[KL Login] pressed Login on the choice screen")
            time.sleep(2)
            continue
        except Exception:
            pass
        time.sleep(1)
    return scenes._login_screen_visible(driver)


def handle_gender_popup(driver, choose="Male", timeout=15):
    """Answer the first-entry "you are" popup and come back. Returns bool (was it shown)."""
    if not ui_actions.wait_for_any(driver, (names.GENDER_POPUP,), timeout=timeout):
        return False
    options = (choose,) + tuple(o for o in names.GENDER_OPTIONS if o != choose)
    picked = next((o for o in options if ui_actions.press_object(driver, o, settle=2.0)), "")
    if not picked:
        logging.error("[KL Login] the gender popup is up but neither option could be pressed")
        return False
    logging.info(f"[KL Login] first entry: chose '{picked}'")
    if wait_for_scene(driver, names.AVATAR_SCENE, timeout=20):
        ui_actions.press_object(driver, "BackButton", settle=2.0)
        wait_for_scene(driver, names.START_SCENE, timeout=20)
    return True


def login(driver, username, password, timeout=60):
    """Log in as ``username`` and PROVE the hub is showing. Raises AssertionError if not."""
    if not open_login_form(driver):
        raise AssertionError(f"the Kideo Land login fields never appeared "
                             f"(scene: {current_scene(driver)})")
    login_session.login(driver, username, password)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if ui_actions.find_any(driver, names.GENDER_POPUP) is not None:
            handle_gender_popup(driver, timeout=2)
        if islands_visible(driver) and ui_actions.find_any(driver, names.GENDER_POPUP) is None:
            break
        if scenes._login_screen_visible(driver) and time.time() > deadline - timeout + 20:
            raise AssertionError(f"login as {username} was refused -- still on the login form")
        time.sleep(1)
    else:
        raise AssertionError(f"the Kideo Land hub never appeared after logging in as "
                             f"{username} (scene: {current_scene(driver)})")
    # The popup can arrive a beat after the islands.
    handle_gender_popup(driver, timeout=4)
    logging.info(f"[KL Login] signed in as {username}")
    return True


def logout(driver):
    """Log out through the UI. Returns bool."""
    return bool(login_session.logout_via_ui(driver))
