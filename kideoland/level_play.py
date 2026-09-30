"""Playing one Kideo Land level: word list -> slot machine -> activity selection -> activities.

The difference from Voca Tooki that matters: this build has no AltTesterUtils,
so ``GetCurrentActivity`` cannot say which activity opened. Kideo Land does not
need it -- every activity slot on the selection screen carries its own
``activityInfo_`` (the ActivityID), so the solver is chosen BEFORE the slot is
opened, from the slot itself.

Everything after that is Voca Tooki's rule for a lesson run (user, 2026-09-22):
an activity is PASSED only when the game reached its end -- the success screen
or ProgressText at its total. A lost game is retried (Retry), three attempts,
then FAILED with the reason and a screenshot.
"""

import logging
import time
import traceback
from datetime import datetime

from alttester import By

from kideoland import names
from kideoland.login import current_scene
from vocatooki import activity_runner, parrot_guard, ui_actions
from vocatooki.solvers.registry import SOLVERS


def _ensure_mid_frame_hook():
    """The mid-activity frame fires from the parrot guard's action hook.

    utilsdemo registers it on import (the panel always imports utilsdemo); doing
    the same here, idempotently, keeps a Kideo Land run that did not come in
    through utilsdemo from silently losing its mid frames.
    """
    parrot_guard.install()
    if activity_runner._mid_activity_frame not in parrot_guard.ACTION_HOOKS:
        parrot_guard.ACTION_HOOKS.append(activity_runner._mid_activity_frame)


def _feedback_frame(driver, key, timeout=15.0):
    """Frame 3: the result popup, shot 2s after it appears so it is fully drawn."""
    popups = activity_runner.SUCCESS_POPUPS + activity_runner.FAILURE_POPUPS
    if ui_actions.wait_for_any(driver, popups, timeout=timeout):
        time.sleep(activity_runner.FEEDBACK_FRAME_DELAY)
    else:
        logging.info(f"[KL Activity] {key}: no result popup seen -- feedback frame taken as is")
    activity_runner.activity_frame(driver, key, activity_runner.ACTIVITY_FRAMES[2])


def open_level_to_selection(driver, timeout=150):
    """From a just-opened level, reach the activity selection screen. Returns bool."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        scene = current_scene(driver)
        if scene != last:
            logging.info(f"[KL Level] on {scene}")
            last = scene
        if scene == names.SELECTION_SCENE:
            if ui_actions.wait_for_any(driver, (names.ACTIVITY_SLOT,), timeout=20):
                time.sleep(2)
                return True
        elif scene == names.SLOT_MACHINE_SCENE:
            if ui_actions.find_any(driver, names.SPIN_BUTTON) is not None:
                ui_actions.click_by_name(driver, names.SPIN_BUTTON)
                time.sleep(8)
                continue
        elif ui_actions.find_any(driver, names.NEXT_BUTTON) is not None:
            ui_actions.click_by_name(driver, names.NEXT_BUTTON)
            time.sleep(3)
            continue
        time.sleep(2)
    logging.error(f"[KL Level] the activity selection never appeared (on {current_scene(driver)})")
    return False


def _slot_field(slot, field, max_depth=1):
    """A slot field, read through the base class first (it owns the private fields)."""
    for component in (names.ACTIVITY_SLOT_BASE_COMPONENT, names.ACTIVITY_SLOT_COMPONENT):
        try:
            value = slot.get_component_property(component, field, names.ASSEMBLY,
                                                max_depth=max_depth)
            if value not in (None, {}, ""):
                return value
        except Exception:
            continue
    return None


def _slot_info(slot):
    return _slot_field(slot, "activityInfo_") or {}


def read_slots(driver):
    """The level's activities in screen-list order: [{key, title, finished, obj}]."""
    slots = []
    for slot in driver.find_objects(By.NAME, names.ACTIVITY_SLOT):
        info = _slot_info(slot)
        toggle = _slot_field(slot, "finishedToggle")
        finished = bool(toggle.get("isOn")) if isinstance(toggle, dict) else None
        key = names.ACTIVITY_IDS.get(info.get("id"), f"ACTIVITY_{info.get('id')}")
        slots.append({"key": key, "title": info.get("name") or "", "scene": info.get("scenePath"),
                      "finished": finished, "obj": slot})
    return slots


def _press_slot(driver, slot):
    """Open an activity by pressing its slot's own Button."""
    try:
        slot["obj"].find_object_from_object(By.NAME, names.ACTIVITY_SLOT_BUTTON).click()
    except Exception:
        slot["obj"].click()


def _wait_activity_open(driver, timeout=90):
    """Wait until the selection screen has given way to the activity. Returns the scene or ''."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        scene = current_scene(driver)
        if scene and scene not in (names.SELECTION_SCENE, names.MAP_SCENE):
            return scene
        time.sleep(1)
    return ""


def _last_attempt_popup(driver):
    """The 'last attempt' question some activities open with -- answer Yes."""
    if ui_actions.find_any(driver, "PlaceHolder") is not None and \
            ui_actions.find_any(driver, "Yes") is not None:
        ui_actions.click_by_name(driver, "Yes")
        logging.info("[KL Activity] answered the last-attempt popup")


def _exit_activity(driver, timeout=45):
    """Close the result and get back to the activity selection. Returns bool."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        scene = current_scene(driver)
        if scene == names.SELECTION_SCENE:
            return True
        pressed = False
        for popup in (names.FEEDBACK_POPUP, names.FAILURE_FEEDBACK_POPUP,
                      "FeedbackPopup(Clone)", "FailureFeedbackPopup(Clone)"):
            try:
                driver.find_object(By.NAME, popup).find_object_from_object(
                    By.NAME, "ExitButton").click()
                pressed = True
                break
            except Exception:
                continue
        if not pressed and ui_actions.find_any(driver, "prev") is not None:
            ui_actions.click_by_name(driver, "prev")
            pressed = True
        time.sleep(3 if pressed else 2)
    return current_scene(driver) == names.SELECTION_SCENE


# The difficulty of the level being played, stamped on every report row so the
# report says "Hard" for a hard level instead of guessing from occurrences.
_CURRENT = {"difficulty": ""}


def _report(key, status, error="", started=None):
    duration = str(datetime.now() - started) if started else "0s"
    activity_runner.activity_report.append({"activity": key, "status": status, "error": error,
                                            "duration": duration, "platform": "Kideo Land",
                                            "difficulty": _CURRENT["difficulty"]})


def play_slot(driver, slot, attempts=3):
    """Play one activity to the end. Returns True (passed), False (failed) or None (skipped)."""
    key = slot["key"]
    solver = SOLVERS.get(key)
    if solver is None:
        logging.warning(f"[KL Activity] no solver for {key} ('{slot['title']}') -- skipped")
        _report(key, "SKIPPED", f"No solver mapped for {key} ({slot['scene']})")
        return None

    started = datetime.now()
    logging.info(f"[KL Activity] opening {key} ('{slot['title']}')")
    _press_slot(driver, slot)
    scene = _wait_activity_open(driver)
    if not scene:
        shot = ui_actions.capture_failure_screenshot(driver, f"kl_open_{key}")
        _report(key, "FAILED", f"{key} did not open from the selection screen"
                + (f" [screenshot: {shot}]" if shot else ""), started)
        return False

    try:
        _last_attempt_popup(driver)
        activity_runner.clear_activity_intro(driver, key)
        activity_runner.activity_frame(driver, key, activity_runner.ACTIVITY_FRAMES[0])
        # Frame 2 is shot WHILE the solver plays: the hook reads the progress
        # counter before each press and fires once it reaches half.
        _ensure_mid_frame_hook()
        activity_runner._watch_mid_frame(driver, key)
        for attempt in range(1, attempts + 1):
            try:
                solver(driver)
            except Exception as error:
                logging.warning(f"[KL Activity] {key} failed on attempt {attempt}/{attempts}: {error}")
                if attempt == attempts:
                    raise
                time.sleep(2)
                continue
            finished, note = activity_runner.activity_finished(driver)
            if finished is not False:
                if finished is None:
                    logging.warning(f"[KL Activity] {key}: {note} -- cannot prove it was played "
                                    f"to the end; not counted as a failure")
                break
            logging.warning(f"[KL Activity] {key} not finished on attempt {attempt}/{attempts}: {note}")
            if attempt == attempts:
                raise AssertionError(f"{key} was not played to the end: {note}")
            activity_runner.retry_lost_activity(driver)
            time.sleep(2)
        activity_runner._watch_mid_frame(driver, None)
        _feedback_frame(driver, key)
        _report(key, "PASSED", "", started)
        passed = True
    except Exception as error:
        activity_runner._watch_mid_frame(driver, None)
        shot = ui_actions.capture_failure_screenshot(driver, f"kl_activity_{key}")
        _report(key, "FAILED", f"{error}\n{traceback.format_exc()}"
                + (f" [screenshot: {shot}]" if shot else ""), started)
        passed = False

    if not _exit_activity(driver):
        logging.error(f"[KL Activity] could not get back to the activity selection after {key} "
                      f"(on {current_scene(driver)})")
    return passed


def play_level(driver, label="", difficulty=""):
    """Play every activity of the open level once. Returns (passed, failed, skipped) counts."""
    _CURRENT["difficulty"] = difficulty.capitalize()
    if not open_level_to_selection(driver):
        shot = ui_actions.capture_failure_screenshot(driver, "kl_level_open")
        _report(f"Level {label}", "FAILED", "the activity selection never appeared"
                + (f" [screenshot: {shot}]" if shot else ""))
        return 0, 1, 0

    # The slots exist a moment before their activity is filled in; an empty
    # read would skip every activity as "no solver".
    planned = []
    for _ in range(10):
        planned = read_slots(driver)
        if planned and all(s["key"] in SOLVERS or not s["key"].startswith("ACTIVITY_")
                           for s in planned):
            break
        time.sleep(1.5)
    logging.info(f"[KL Level] {label}: {len(planned)} activities -- "
                 + ", ".join(f"{s['key']}" for s in planned))
    counts = {True: 0, False: 0, None: 0}
    for index, first_read in enumerate(planned):
        # Re-read after every activity: the selection screen is rebuilt when
        # it comes back, so handles from the first read are stale.
        current = read_slots(driver) if index else planned
        slot = next((s for s in current if s["key"] == first_read["key"]), None)
        if slot is None:
            _report(first_read["key"], "FAILED", "the activity slot was gone when its turn came")
            counts[False] += 1
            continue
        counts[play_slot(driver, slot)] += 1
    return counts[True], counts[False], counts[None]
