"""The placement pretest in front of the map, and taking its Skip.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time

from vocatooki import activity_runner, scene_names, scenes, ui_actions


# example : exam = get_user_exam_by_userid_examid("49295_3", class_id=2336)

# ---------------------------------------------------------------------------
# The placement PRETEST
#
# When the account's CLASS is configured for a pretest in the CRM, GO-Map lands
# on PretestScene instead of the map (see PRETEST_SCENE above). The scene is a
# ship's cabin with seven glowing objects, one per skill:
#
#   listening1/2/3   Reading   speaking1   writing1/2
#
# Tapping one opens an ordinary activity (LISTEN_FIND, RADAR, UNSCRAMBLE_QUIZ,
# TaskScene, ...), which is why the pretest needs no solver of its own -- but a
# whole placement test does not have to be sat to get past it. After FIVE node
# entries the scene offers a Skip, which is what a case wanting the map behind
# the gate actually needs.
#
# Two traps, both found live on 2026-08-30:
#   * A node that has already been played WILL NOT REOPEN. Tapping it does
#     nothing, so the five entries have to walk across the nodes rather than
#     hammering one, and "it did not open" is how a played node is recognised --
#     nothing in the hierarchy marks it.
#   * The scene takes POSITIONAL taps, not object clicks: `AltObject.click()` on
#     a node or on SkipButton is swallowed. The confirm popup that follows is
#     ordinary UI, and its YesButton does take an object click.
# ---------------------------------------------------------------------------
PRETEST_NODES = ("listening1", "listening2", "listening3", "Reading",
                 "speaking1", "writing1", "writing2")


PRETEST_ENTRIES_FOR_SKIP = 5


def _pretest_object(altdriver, name):
    """A pretest object by name whether or not it is active, or None."""
    try:
        for obj in altdriver.get_all_elements(enabled=False):
            if obj.name == name:
                return obj
    except Exception:
        pass
    return None


def pretest_skip_ready(altdriver):
    """True once the pretest is offering its Skip."""
    button = _pretest_object(altdriver, "SkipButton")
    return bool(button and button.enabled)


def _pretest_wait_scene(altdriver, wanted, timeout, equal=True):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            scene = altdriver.get_current_scene()
        except Exception:
            scene = None
        if scene and ((scene == wanted) if equal else (scene != wanted)):
            return scene
        time.sleep(0.6)
    return None


def pretest_skip(altdriver, entries=PRETEST_ENTRIES_FOR_SKIP, open_timeout=18,
                 timeout=60):
    """Get past the placement pretest onto the map. Returns True on the map.

    Enters and leaves glowing nodes until the Skip appears, then takes it. The
    nodes are NOT solved -- the point is to reach the map, and a case that needs
    the pretest itself played should drive the activities instead.
    """
    scene = scenes._current_scene(altdriver)
    if scene != scene_names.PRETEST_SCENE:
        logging.info(f"[Pretest] not on the pretest (scene: {scene}) — nothing to skip")
        return scene == scene_names.MAP_SCENE

    used = 0
    for node in PRETEST_NODES:
        if pretest_skip_ready(altdriver):
            break
        if used >= entries:
            break
        target = _pretest_object(altdriver, node)
        if target is None:
            continue
        altdriver.tap((float(target.x), float(target.y)))
        opened = _pretest_wait_scene(altdriver, scene_names.PRETEST_SCENE, open_timeout, equal=False)
        if opened is None:
            # Already played: a finished node simply does not respond, and
            # nothing in the hierarchy says so.
            logging.info(f"[Pretest] '{node}' did not open — already played")
            continue
        activity_runner.when_finish_activity(altdriver)
        back = _pretest_wait_scene(altdriver, scene_names.PRETEST_SCENE, timeout)
        used += 1
        logging.info(f"[Pretest] entered '{node}' ({opened}) and left again "
                     f"[{used}/{entries}]{'' if back else ' — did NOT return'}")

    if not pretest_skip_ready(altdriver):
        logging.error(f"[Pretest] the Skip never appeared after {used} node "
                      f"entries; the map is still behind the pretest")
        return False

    button = _pretest_object(altdriver, "SkipButton")
    altdriver.tap((float(button.x), float(button.y)))   # object clicks are swallowed here

    # The confirm popup is ordinary UI and DOES take an object click.
    deadline = time.time() + 15
    while time.time() < deadline:
        yes = ui_actions.find_element(altdriver, "YesButton")
        if yes is not None:
            try:
                yes.click()
                logging.info("[Pretest] confirmed the skip")
            except Exception as e:
                logging.warning(f"[Pretest] could not press YesButton: {e}")
            break
        time.sleep(0.5)
    else:
        logging.warning("[Pretest] no confirmation popup appeared after Skip")

    if _pretest_wait_scene(altdriver, scene_names.MAP_SCENE, timeout):
        logging.info("[Pretest] skipped — the map is open")
        return True
    logging.error(f"[Pretest] skip did not reach the map "
                  f"(scene: {scenes._current_scene(altdriver)})")
    return False
