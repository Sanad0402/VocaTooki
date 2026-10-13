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

# How long the game gets to TAKE a tapped blip. A lowered blip first pops up
# (ShowForCheckTwean: ~1s, after its bush stops shaking) and only then is it
# judged; a right answer destroys its controller.
_TAKE_TIMEOUT = 3.0
_PRESS_ATTEMPTS = 3

# After both blips of the pair are taken the game animates them together,
# then counts the word and names the next target.
_PAIR_TIMEOUT = 10.0


def _blip_flag(blip, field):
    try:
        return bool(blip.get_component_property(_CONTROLLER, field, _ASSEMBLY))
    except Exception:                                # noqa: BLE001
        return None


def _taken(blip):
    """True once the game took this blip as a right answer: CheckSelectedObjects
    DESTROYS its RadarObjectController, so the component is gone."""
    try:
        blip.get_component_property(_CONTROLLER, "word", _ASSEMBLY)
        return False
    except Exception:                                # noqa: BLE001 - controller destroyed
        return True


def _wait_taken(blip, timeout=_TAKE_TIMEOUT, poll=0.15):
    """True once the blip was taken.

    NOT `selected`: the game sets it the instant it is tapped, before the
    blip is judged -- and a pending judgement can be killed (see radar()).
    NOT `hidden`: on hard the blips pop up on their own every second or two;
    reading "it popped up" as "it was checked" passed a missed tap as a press
    (live, 2026-10-13)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _taken(blip):
            return True
        time.sleep(poll)
    return False


def _cover_of(blip):
    """The bush covering this blip: the `cover` child of the blip's parent, or None."""
    try:
        parent = blip.get_parent()
        return parent.find_object_from_object(By.NAME, _COVER)
    except Exception:                                # noqa: BLE001
        return None


def _tap(altdriver, obj):
    """A real screen tap at ``obj``'s LIVE position, without the generic press's
    search for a better point.

    The generic press asks the app what is under the finger and, when it is not
    the object itself, searches around it for a point that is -- seconds per
    tap. On RADAR the blip and its bush always overlap (the bush is drawn ON
    TOP of a lowered blip, see SetSortingOrder) and either one calls the same
    blip's CheckObject(), so the search never helps and the 7s it took let the
    blip move away before the tap landed (live, 2026-10-13)."""
    point = ui_actions._live_position(obj)
    if point is None:
        raise RuntimeError(f"no live position for '{getattr(obj, 'name', '?')}'")
    altdriver.tap(point)
    logging.info(f"[Press] tapped '{obj.name}' at ({point[0]:.0f}, {point[1]:.0f})")


def press_blip(altdriver, blip, word=""):
    """Press one blip the way a player does. Returns True once the game took it.

    A blip that is UP is tapped itself (it sits ~200px above its bush and on
    top of it; its OnPointerDown checks it at once). A blip that is DOWN is
    tapped through its bush, whose PointerClick pops it up and checks it. The
    bush is re-read every attempt: on hard the blips are moved between bushes
    whenever one hides (RandomizeObjectPositions)."""
    for attempt in range(1, _PRESS_ATTEMPTS + 1):
        up = _blip_flag(blip, "hidden") is False
        cover = None if up else _cover_of(blip)
        target = cover if cover is not None else blip
        where = "its bush" if cover is not None else "the blip itself"
        try:
            _tap(altdriver, target)
        except Exception as e:                       # noqa: BLE001
            logging.info(f"[RADAR] '{word}': press on {where} failed ({e}); retrying")
            time.sleep(0.3)
            continue
        if _wait_taken(blip):
            logging.info(f"[RADAR] '{word}': taken on attempt {attempt} (tapped {where})")
            return True
        logging.info(f"[RADAR] '{word}': tap {attempt}/{_PRESS_ATTEMPTS} on {where} was not taken")
    return False


def _read_blips(altdriver):
    """[(blip, word)] for the blips still in play. A taken blip has lost its
    controller (the game destroys it), so it is skipped instead of crashing
    the whole activity, as it did when a pair was left half-selected.

    A blip that is `selected` but still HAS its controller is kept: its
    judgement was killed (see radar()) and only another tap revives it."""
    out = []
    for blip in altdriver.find_objects(By.NAME, "radarObj"):
        try:
            word = blip.get_component_property(_CONTROLLER, "word", _ASSEMBLY)
        except Exception:                            # noqa: BLE001 - already taken
            continue
        out.append((blip, word))
    return out


def _target_word(altdriver):
    try:
        return altdriver.find_object(By.NAME, "Radar_activity").get_component_property(
            "com.kideo.learn.english.RadarActivityManagement",
            "radarGameManager.targetWord", _ASSEMBLY)
    except Exception:                                # noqa: BLE001
        return None


def _progress(altdriver):
    """(done, total) from ProgressText, or (None, None)."""
    try:
        done, total = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(done), int(total)
    except Exception:                                # noqa: BLE001
        return None, None


def _wait_progress_above(altdriver, done, timeout=_PAIR_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        now, _ = _progress(altdriver)
        if now is not None and now > done:
            return now
        time.sleep(0.3)
    return None


def radar(altdriver):
    """Find every target word's PAIR of blips and select both -- ONE AT A TIME.

    The second blip is tapped only after the game TOOK the first. Tapping both
    lowered blips at once soft-locks the game (live, 2026-10-13): each tap
    starts a 1s pop-up-then-judge coroutine; when the first is judged right,
    HideAllOtherObjectsImmediately() calls StopAllCoroutines() on every other
    blip, killing the second one's pending judgement. It stays `selected`
    forever, the pair never completes, and no blip ever shows again. A new tap
    on that blip restarts its judgement, which is how press_blip recovers it.

    Driven by the game's own counter rather than fixed sleeps: hard has a
    timer, and 7s of waiting before each of 8 words ate most of it."""
    done, total = _progress(altdriver)
    if total is None:
        raise AssertionError("RADAR: no ProgressText on screen")
    deadline = time.time() + 30 + total * 20
    while done < total:
        if time.time() > deadline:
            raise AssertionError(f"RADAR: stuck at {done}/{total}")
        target = _target_word(altdriver)
        pair = [b for b, w in _read_blips(altdriver) if target and w == target][:2]
        if not pair:
            time.sleep(0.5)                          # between words: the next target is not up yet
            continue
        for blip in pair:
            if not press_blip(altdriver, blip, word=target):
                logging.warning(f"[RADAR] '{target}': no tap was taken; re-reading the board")
                break
        now = _wait_progress_above(altdriver, done)
        if now is None:
            # Half a pair selected, or a tap the game took late: re-read the
            # board and press whatever blip of this word is still unselected.
            logging.warning(f"[RADAR] '{target}': progress still {done}/{total}; re-reading")
            continue
        done = now
        logging.info(f"[RADAR] '{target}' found: {done}/{total}")

    print('Radar activity done')
