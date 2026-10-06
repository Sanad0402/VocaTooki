"""RADAR: find the target words on the radar.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.

How a blip is pressed (RadarObjectController.cs): every `radarObj` hides under a
`cover` (the bush), a sibling under the same parent, and it is the COVER's
PointerClick that calls `CheckObject()` -- which reveals the blip and, when its
word is the target, counts it. One tap on the cover is the whole move.

Until 2026-10-06 the solver pressed the blip object twice through AltTester's
object click, which fires the blip's own handler and never touches the screen,
so neither the cover nor the second press mattered. With real taps (the
screen-first presses of 2026-10-06) the second tap landed 0.5s later, while
the blip was animating 130px upward -- on a NEIGHBOURING bush: a wrong answer
and a lost life, every word. So: tap the cover once, then wait for the game to
say the blip was checked, and only fall back to the blip itself when the cover
cannot be pressed.
"""

import logging
import time

from alttester import By

from vocatooki import ui_actions

_CONTROLLER = "com.kideo.learn.english.RadarObjectController"
_ASSEMBLY = "Assembly-CSharp"
_COVER = "cover"

# How long the game gets to react to the tap: the blip scales up and moves
# before `selected`/`hidden` change (ShowForCheckTwean).
_CHECK_TIMEOUT = 4.0


def _blip_flag(blip, field):
    try:
        return bool(blip.get_component_property(_CONTROLLER, field, _ASSEMBLY))
    except Exception:                                # noqa: BLE001
        return None


def _blip_checked(blip, timeout=_CHECK_TIMEOUT, poll=0.25):
    """True once the game marked the blip selected (or revealed it)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        selected, hidden = _blip_flag(blip, "selected"), _blip_flag(blip, "hidden")
        if selected is True or hidden is False:
            return True
        if selected is None and hidden is None:
            return None                              # unreadable: nothing to wait for
        time.sleep(poll)
    return False


def _cover_of(blip):
    """The bush covering this blip: the `cover` child of the blip's parent, or None."""
    try:
        parent = blip.get_parent()
        return parent.find_object_from_object(By.NAME, _COVER)
    except Exception:                                # noqa: BLE001
        return None


def press_blip(altdriver, blip, word=""):
    """Press one blip the way a player does. Returns True once the game checked it."""
    cover = _cover_of(blip)
    target = cover if cover is not None else blip
    where = "its cover" if cover is not None else "the blip itself (no cover found)"
    ui_actions._press(target, altdriver)
    checked = _blip_checked(blip)
    if checked is False:
        # The cover did not take the tap (a hidden cover, a cover already
        # gone): press the blip itself once, which is also what a player
        # does once the bush is away.
        logging.info(f"[RADAR] '{word}': the tap on {where} did not check the blip -- "
                     f"pressing the blip itself")
        ui_actions._press(blip, altdriver)
        checked = _blip_checked(blip)
    logging.info(f"[RADAR] '{word}': pressed {where}; checked={checked}")
    return checked is not False


def radar(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(7)
        # Fetch all radar objects and the target word
        radar_objects = altdriver.find_objects(By.NAME, 'radarObj')
        answer_obj = altdriver.find_object(By.NAME, 'Radar_activity')
        target_word = answer_obj.get_component_property('com.kideo.learn.english.RadarActivityManagement',
                                                        'radarGameManager.targetWord', 'Assembly-CSharp')

        # List to hold the radar text values
        radar_objects_texts = []
        for radar_object in radar_objects:
            radar_text = radar_object.get_component_property('com.kideo.learn.english.RadarObjectController', 'word',
                                                             'Assembly-CSharp')
            radar_objects_texts.append(radar_text)

        # Press the blip(s) carrying the target word -- ONE tap each, on the
        # cover, and the game is asked whether it took it before moving on.
        for index, radar_text in enumerate(radar_objects_texts):
            if radar_text == target_word:
                press_blip(altdriver, radar_objects[index], word=target_word)

    print('Radar activity done')
