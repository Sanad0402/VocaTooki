"""After the last activity of a lesson level: what a USER sees and can do next.

2026-10-06: in production, finishing a HARD level (all three activities)
awards a gift, and after the gift the map no longer takes touches. Every run
had passed, because the framework pressed objects directly and never looked
at the map after a level. This module is the contract a level now ends with,
driven and checked through the screen like a finger:

  1. LEAVE  the activity list with its Back button. Anything covering Back is
            a popup the user sees first (the gift is one): its wording is
            read, it is recorded, dismissed the way a user would, and Back is
            tried again.
  2. MAP    the map scene is back and its level icons are there.
  3. TOUCH  a touch on a level icon reaches the icon — nothing is left
            covering the map.
  4. PROBE  tapping a level opens it, and the map comes back after leaving
            it. This is the step that fails on the post-gift lock: the icons
            are there, the raycast reaches them, and the map still does not
            react. Another level already opened in this run is preferred;
            otherwise the level just played is re-opened.

Every outcome is one ``LEVEL COMPLETION`` row in the activity report, with the
popups seen and the input findings recorded on the way. What this cannot check
yet is said in the row too (the next level's lock state, the gift on the
backend) — a PASS here never claims more than it saw.
"""

import logging
import time

from vocatooki import activity_runner, map_navigation, scene_names, scenes, ui_actions


class LevelCompletionError(AssertionError):
    """The level ended, but the app is not where a user would be afterwards."""


# The activity list's own back button.
BACK_FROM_LEVEL = "Back"


# How a user gets past whatever the game shows after a level: the button on
# it. Tried in this order, ON SCREEN only, and only if the touch reaches it.
POPUP_BUTTONS = ("Claim", "ClaimButton", "Collect", "CollectButton", "OK", "OKButton",
                 "Ok", "Continue", "ContinueButton", "Yes", "YesButton", "CloseButton",
                 "Close", "X", "x", "ExitButton", "nextButton", "prev")


# Popups animate in; a press that arrives with them is swallowed.
POPUP_SETTLE = 1.5
# Rounds of "press Back / dismiss what is in the way" before giving up.
LEAVE_ROUNDS = 5
# How long one screen change may take after a delivered press.
SCENE_CHANGE_TIMEOUT = 12
# The map scene plus its icons, after leaving the level.
MAP_TIMEOUT = 30
# How many on-screen icons are checked for a clear touch path.
TOUCH_CHECKS = 3


NOT_COVERED = ("the next level's lock state (icon state property not surveyed)",
               "the gift / score on the backend (no user-state reader wired)")


def finish_level(altdriver, difficulty, class_id=None, lesson_num=None, probe=True,
                 other_levels=()):
    """Leave the level like a user and prove the map still works. Writes one row.

    ``other_levels``: icon indices opened earlier in this run (the easy and
    medium levels in a full run) — the probe prefers one of them, so that it
    is ANOTHER level that is shown to open. Raises ``LevelCompletionError``
    after writing a FAILED row; returns the summary dict on success.
    """
    start = time.time()
    since = len(ui_actions.INPUT_FINDINGS)
    label = f"{difficulty} level" + (f", lesson {lesson_num}" if lesson_num is not None else "")
    played = map_navigation.LAST_LEVEL_INDEX
    summary = {"popups": [], "touch_checked": 0, "covers": [], "probe": "not run",
               "not_covered": list(NOT_COVERED)}
    try:
        _leave_level(altdriver, summary)
        _wait_for_map(altdriver, summary)
        icons = map_navigation._find_level_icons(altdriver)
        _map_touchable(altdriver, icons, summary)
        if probe:
            _probe_navigation(altdriver, icons, played, other_levels, summary)
        else:
            summary["not_covered"].append("navigation probe switched off")
    except Exception as e:                           # noqa: BLE001 - every failure is a row
        shot = ui_actions.capture_failure_screenshot(altdriver, f"level-completion-{difficulty}")
        error = f"{e}; {_trail(summary, since)}"
        _row(altdriver, "FAILED", label, difficulty, start, error=error, screenshot=shot)
        print(f"LEVEL COMPLETION [{label}] RESULT: FAILED — {error}")
        raise LevelCompletionError(error) from e

    note = _trail(summary, since)
    _row(altdriver, "PASSED", label, difficulty, start, note=note)
    print(f"LEVEL COMPLETION [{label}] RESULT: PASSED — {note}")
    return summary


def finish_exam(altdriver, class_id=None, lesson_num=None, probe=True):
    """After an exam was submitted: the map is back, and a level still opens by touch.

    The exam's own exit (Collect, then its back button) has been pressed by the
    exam solver; anything still in the way is walked out of like a user and
    recorded. The probe opens the lesson's HARD level (from the class map) so
    it is a lesson level, not the submitted exam, that is shown to open.
    Writes one ``LEVEL COMPLETION [exam, ...]`` row; raises on failure.
    """
    start = time.time()
    since = len(ui_actions.INPUT_FINDINGS)
    label = "exam" + (f", lesson {lesson_num}" if lesson_num is not None else "")
    summary = {"popups": [], "touch_checked": 0, "covers": [], "probe": "not run",
               "not_covered": list(NOT_COVERED) + ["the next lesson's unlock state"]}
    try:
        if scenes._current_scene(altdriver) != scene_names.MAP_SCENE:
            dismissed = len(ui_actions.INPUT_FINDINGS)
            map_navigation.return_to_map(altdriver)
            summary["popups"] += [f"'{f['target']}' ({f['note']})"
                                  for f in ui_actions.findings_since(dismissed)
                                  if f["kind"] == "popup-dismissed"]
        _wait_for_map(altdriver, summary)
        icons = map_navigation._find_level_icons(altdriver)
        _map_touchable(altdriver, icons, summary)
        if probe:
            other = []
            if class_id is not None and lesson_num is not None:
                try:
                    index = map_navigation.get_level(class_id, lesson_num, "lesson", "hard")
                except Exception:                    # noqa: BLE001 - the class map is a network call
                    index = -1
                if index is not None and index >= 0:
                    other.append(index)
            # The lesson's hard level is the probe; the exam's own icon only
            # when the class map could not name one.
            _probe_navigation(altdriver, icons,
                              None if other else map_navigation.LAST_LEVEL_INDEX, other, summary,
                              why_other="the lesson's hard level, from the class map")
        else:
            summary["not_covered"].append("navigation probe switched off")
    except Exception as e:                           # noqa: BLE001 - every failure is a row
        shot = ui_actions.capture_failure_screenshot(altdriver, "level-completion-exam")
        error = f"{e}; {_trail(summary, since)}"
        _row(altdriver, "FAILED", label, "exam", start, error=error, screenshot=shot)
        print(f"LEVEL COMPLETION [{label}] RESULT: FAILED — {error}")
        raise LevelCompletionError(error) from e

    note = _trail(summary, since)
    _row(altdriver, "PASSED", label, "exam", start, note=note)
    print(f"LEVEL COMPLETION [{label}] RESULT: PASSED — {note}")
    return summary


# ------------------------------------------------------------------ steps
def _leave_level(altdriver, summary):
    """Press Back until the map scene is reached, dismissing what is in the way."""
    scene = scenes._current_scene(altdriver)
    for _ in range(LEAVE_ROUNDS):
        if scene == scene_names.MAP_SCENE:
            return
        back = ui_actions.find_any(altdriver, BACK_FROM_LEVEL)
        if back is None:
            cover = _whats_on_top(altdriver)
            if cover is None:
                raise LevelCompletionError(
                    f"no '{BACK_FROM_LEVEL}' on screen and nothing to dismiss "
                    f"(scene {scene}; on screen: {_texts(altdriver)})")
            _dismiss(altdriver, cover, summary)
            scene = scenes._current_scene(altdriver)
            continue
        outcome = ui_actions.press_on_screen(altdriver, back, label=BACK_FROM_LEVEL)
        if not outcome and outcome.status != "untouchable":
            raise LevelCompletionError(
                f"'{BACK_FROM_LEVEL}' could not be touched ({outcome.status})")
        if scenes._wait_leaves_scene(altdriver, scene, timeout=SCENE_CHANGE_TIMEOUT):
            time.sleep(2)
            scene = scenes._current_scene(altdriver)
            continue
        # The tap landed and nothing moved. Whatever the touch hit instead of
        # Back is what the user is looking at (the gift): get past it, retry.
        cover = (ui_actions.what_is_at(altdriver, outcome.point) if outcome.blocker
                 else _whats_on_top(altdriver))
        if cover is None or ui_actions._reaches(cover, back):
            raise LevelCompletionError(
                f"'{BACK_FROM_LEVEL}' was tapped and {scene} stayed on screen "
                f"(on screen: {_texts(altdriver)})")
        _dismiss(altdriver, cover, summary, blocking=BACK_FROM_LEVEL)
        scene = scenes._current_scene(altdriver)
    if scenes._current_scene(altdriver) != scene_names.MAP_SCENE:
        raise LevelCompletionError(
            f"still not on the map after {LEAVE_ROUNDS} rounds of Back "
            f"(scene {scenes._current_scene(altdriver)}; popups seen: "
            f"{summary['popups'] or 'none'})")


def _whats_on_top(altdriver):
    """The object a touch at the screen centre would hit — what covers the screen."""
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:                                # noqa: BLE001
        return None
    return ui_actions.what_is_at(altdriver, (width / 2, height / 2))


def _dismiss(altdriver, cover, summary, blocking=""):
    """Get past ``cover`` the way a user would: its button, else a tap on it."""
    name = getattr(cover, "name", "") or "?"
    text = ui_actions.popup_text(altdriver, settle=0.5)
    summary["popups"].append(f"'{name}'" + (f" ({text[:100]})" if text else ""))
    logging.warning(f"[Level] after the level '{name}' is up"
                    + (f" over '{blocking}'" if blocking else "")
                    + (f": {text[:160]!r}" if text else ""))
    time.sleep(POPUP_SETTLE)
    for button in POPUP_BUTTONS:
        obj = ui_actions.find_any(altdriver, button)
        if obj is None or not ui_actions.is_on_screen(altdriver, obj):
            continue
        if ui_actions.press_on_screen(altdriver, obj, label=button):
            logging.info(f"[Level] dismissed '{name}' with '{button}'")
            time.sleep(POPUP_SETTLE)
            return button
    if cover is not None and ui_actions.press_on_screen(altdriver, cover, label=name):
        logging.info(f"[Level] tapped '{name}' itself")
        time.sleep(POPUP_SETTLE)
        return name
    raise LevelCompletionError(f"could not get past '{name}'"
                               + (f" ({text[:120]!r})" if text else ""))


def _wait_for_map(altdriver, summary):
    if not map_navigation._map_ready(altdriver, timeout=MAP_TIMEOUT):
        raise LevelCompletionError(
            f"the map did not come back after the level (scene "
            f"{scenes._current_scene(altdriver)}; on screen: {_texts(altdriver)})")


def _map_touchable(altdriver, icons, summary):
    """What a touch on the map's icons would hit — anything left covering them?

    Recorded, not failed: a cover that still lets touches through is the
    probe's business. A cover that does not is what the probe then fails on,
    and this is the line that says WHAT covered it.
    """
    checked, covers = 0, []
    for icon in icons:
        if checked >= TOUCH_CHECKS:
            break
        if not ui_actions.is_on_screen(altdriver, icon):
            continue
        point = ui_actions._live_position(icon)
        if point is None:
            continue
        hit = ui_actions.what_is_at(altdriver, point)
        if hit is None:
            continue                                  # the probe will tell
        checked += 1
        if not ui_actions._reaches(hit, icon):
            cover = getattr(hit, "name", "?")
            covers.append(cover)
            ui_actions.record_finding("covered", getattr(icon, "name", "?"), blocker=cover,
                                      note="on the map after the level")
    summary["touch_checked"] = checked
    summary["covers"] = sorted(set(covers))


def _probe_index(icons, played, other_levels, why_other="another level opened earlier in this run"):
    for index in other_levels:
        if index is not None and 0 <= index < len(icons) and index != played:
            return index, why_other
    if played is not None and 0 <= played < len(icons):
        return played, "the level just played, re-opened"
    return None, ""


def _probe_navigation(altdriver, icons, played, other_levels, summary,
                      why_other="another level opened earlier in this run"):
    index, why = _probe_index(icons, played, other_levels, why_other)
    if index is None:
        summary["probe"] = "skipped: no level index known"
        summary["not_covered"].append("navigation probe (no level index to open)")
        return
    icon = icons[index]
    name = getattr(icon, "name", "") or f"icon {index}"
    if not map_navigation._open_level_icon(altdriver, icon, f"probe ({why})"):
        raise LevelCompletionError(
            f"after the level the map did not respond to a touch on '{name}' "
            f"({why}): the post-reward lock"
            + (f"; the touch hits {summary['covers']}" if summary.get("covers") else ""))
    summary["probe"] = f"opened '{name}' ({why})"
    if not scenes.wait_for_scene(altdriver, scene_names.ACTIVITY_SELECTION_SCENE,
                                 timeout=SCENE_CHANGE_TIMEOUT * 2):
        summary["probe"] += f", landed on {scenes._current_scene(altdriver)}"
    if not map_navigation.return_to_map(altdriver):
        raise LevelCompletionError(
            f"the probe opened '{name}' but the map did not come back "
            f"(scene {scenes._current_scene(altdriver)})")
    _wait_for_map(altdriver, summary)


# ---------------------------------------------------------------- reporting
def _texts(altdriver, limit=8):
    try:
        return ui_actions.screen_texts(altdriver, limit=limit)
    except Exception:                                # noqa: BLE001
        return []


def _trail(summary, since):
    findings = [f"{f['kind']} '{f['target']}'" + (f" by '{f['blocker']}'" if f['blocker'] else "")
                for f in ui_actions.findings_since(since)]
    return (f"popups: {'; '.join(summary['popups']) or 'none'}. "
            f"touch path checked on {summary['touch_checked']} icon(s)"
            + (f", covered by {summary['covers']}" if summary.get("covers") else "") + ". "
            f"probe: {summary['probe']}. "
            f"input findings: {'; '.join(findings) or 'none'}. "
            f"Not covered: {'; '.join(summary['not_covered'])}.")


def _row(altdriver, status, label, difficulty, start, error="", note="", screenshot=""):
    activity_runner.activity_report.append({
        "activity": f"LEVEL COMPLETION [{label}]",
        "status": status,
        "error": error,
        "note": note,
        "duration": f"{time.time() - start:.0f}s",
        "screenshot": screenshot,
        "platform": getattr(altdriver, "platform", "Unknown"),
        "difficulty": str(difficulty).title(),
    })
