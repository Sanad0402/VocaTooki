"""Kideo Land navigation: start scene islands -> island map -> lessons, levels and exams.

Lessons are numbered 1..(islands x 5) across the whole game: lesson 1-5 are the
first island's five lessons, 6-10 the second island's, and so on. Inside an
island each lesson is three levels (easy, medium, hard) and its exam, read off
the map icons' own ``levelInfo`` -- never off their position on the screen.

How things open -- located by object, pressed THROUGH THE SCREEN (2026-10-06):
  island  -> a tap on ``IslandIcon`` where it is (an EventTrigger wired to
             CivilizationIslandIcon.Click)
  level   -> a tap on the icon where it is. The icon's own Button has an EMPTY
             onClick in Kideo Land -- a real tap goes through the map's
             pan-and-zoom raycast, which is exactly what a finger does. Only if
             the tap is delivered and the map stays is ``IconClicked()`` called
             on the component, and that is RECORDED as a bypass: the row then
             says the map's own touch handling was not what opened the level.
  cutscene-> its ``BackButton`` object goes on to the island map.
"""

import logging
import time

from alttester import By

from kideoland import names
from kideoland.login import back_to_start, current_scene, wait_for_scene
from vocatooki import scenes, ui_actions


# A tapped level icon loads its scene inside this; the map still showing after
# it means the touch did nothing.
ICON_OPEN_TIMEOUT = 10


# How the map's icons were opened in this process: by a touch, or through the
# component. Once a touch has opened one, a touch that does nothing is no
# longer "maybe the map eats taps" — it is the map not responding, which is
# the post-reward lock, and it fails instead of falling back.
OPENED_BY = {"touch": 0, "component": 0}


class LessonLocked(AssertionError):
    """The lesson (or its island) is locked for this account."""


# ------------------------------------------------------------------ islands
def read_islands(driver):
    """The active islands in game order: [{name, index, locked, obj}]."""
    elements = driver.get_all_elements(enabled=False)
    children = {}
    for o in elements:
        children.setdefault(o.transformParentId, []).append(o)
    islands = []
    for island in [o for o in elements if o.name.startswith(names.ISLAND_PREFIX) and o.enabled]:
        kids = {c.name: c for c in children.get(island.transformId, [])}
        icon = kids.get(names.ISLAND_ICON)
        if icon is None:
            continue
        try:
            index = int(icon.get_component_property(names.ISLAND_ICON_COMPONENT, "civilIndex_",
                                                    names.ASSEMBLY))
        except Exception as e:
            raise AssertionError(f"could not read the island index of {island.name}: {e}")
        lock = kids.get(names.ISLAND_LOCK)
        islands.append({"name": island.name, "index": index,
                        "locked": bool(lock is not None and lock.enabled), "obj": island})
    return sorted(islands, key=lambda i: i["index"])


def island_label(island):
    return island["name"].replace(names.ISLAND_PREFIX, "").replace("(Clone)", "")


def go_to_start(driver, max_steps=8):
    """Back to the start scene by pressing the screen's own back buttons. Returns bool."""
    return back_to_start(driver, max_steps=max_steps)


def open_island(driver, island_index, timeout=60):
    """Open island ``island_index`` (0-based) and wait for its map. Returns the island dict."""
    if not go_to_start(driver):
        raise AssertionError(f"could not get back to the start scene (on {current_scene(driver)})")
    time.sleep(2)
    islands = read_islands(driver)
    island = next((i for i in islands if i["index"] == island_index), None)
    if island is None:
        raise LessonLocked(f"island {island_index + 1} is not available to this account "
                           f"(it shows {len(islands)} islands)")
    if island["locked"]:
        raise LessonLocked(f"island {island_index + 1} ({island_label(island)}) is locked "
                           f"for this account")
    icon = driver.find_object(By.PATH, f"//{island['name']}/{names.ISLAND_ICON}")
    if not ui_actions._press(icon, driver):
        raise AssertionError(f"island {island_index + 1} ({island_label(island)}): the press on "
                             f"its icon was refused (see the input findings)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        scene = current_scene(driver)
        if scene == names.CUT_SCENE:
            logging.info("[KL Map] the island opened with its cutscene -- leaving it")
            time.sleep(2)
            ui_actions.click_by_name(driver, "BackButton")
            time.sleep(3)
            continue
        if scene == names.MAP_SCENE and read_map(driver):
            logging.info(f"[KL Map] on island {island_index + 1} ({island_label(island)})")
            return island
        time.sleep(1)
    raise AssertionError(f"island {island_index + 1} did not open its map "
                         f"(scene: {current_scene(driver)})")


# ------------------------------------------------------------------ island map
def _icon_row(icon, component):
    info = icon.get_component_property(component, "levelInfo", names.ASSEMBLY, max_depth=1)
    state = icon.get_component_property(component, "State", names.ASSEMBLY)
    try:
        number = icon.find_object_from_object(By.NAME, names.ICON_NUMBER).get_text()
    except Exception:
        number = ""
    return {"obj": icon, "component": component, "level_index": info.get("levelIndex"),
            "type": info.get("type"), "lesson_index": info.get("lessonIndex"),
            "difficulty": info.get("difficulty"), "state": state, "number": number}


def read_map(driver):
    """The island's lessons in order: [{lesson_index, levels{easy,medium,hard}, exam, locked}]."""
    rows = []
    for name, component in ((names.LEVEL_ICON, names.LEVEL_ICON_COMPONENT),
                            (names.EXAM_ICON, names.EXAM_ICON_COMPONENT)):
        try:
            icons = driver.find_objects(By.NAME, name)
        except Exception:
            icons = []
        for icon in icons:
            try:
                rows.append(_icon_row(icon, component))
            except Exception as e:
                logging.debug(f"[KL Map] an icon could not be read: {e}")
    lessons = {}
    for row in rows:
        lesson = lessons.setdefault(row["lesson_index"], {"lesson_index": row["lesson_index"],
                                                          "levels": {}, "exam": None})
        if row["type"] == names.LEVEL_TYPE_EXAM:
            lesson["exam"] = row
        elif row["difficulty"] in names.DIFFICULTIES:
            lesson["levels"][row["difficulty"]] = row
    ordered = [lessons[k] for k in sorted(k for k in lessons if k is not None and k >= 0)]
    for lesson in ordered:
        icons = list(lesson["levels"].values()) + ([lesson["exam"]] if lesson["exam"] else [])
        lesson["locked"] = any(i["state"] == names.ICON_LOCKED for i in icons)
    return ordered


def lesson_on_map(driver, unit):
    """Lesson ``unit`` (0..4) of the open island, or raise."""
    lessons = read_map(driver)
    if unit >= len(lessons):
        raise AssertionError(f"the island map shows {len(lessons)} lessons, not {unit + 1}")
    return lessons[unit]


def open_icon(driver, row):
    """Open a level or exam icon with a touch where it is. Raises LessonLocked if locked.

    A delivered touch that leaves the map on screen falls back to the icon's
    ``IconClicked()`` -- recorded as a bypass, so the run says the map did not
    open the level by itself (and what the touch hit, if not the icon).
    """
    if row["state"] == names.ICON_LOCKED:
        raise LessonLocked(f"map level {row['number']} is locked")
    label = f"map level {row['number']}"
    kind = row['difficulty'] if row['type'] == names.LEVEL_TYPE_LESSON else 'exam'
    outcome = ui_actions.press_on_screen(driver, row["obj"], label=label)
    if outcome and scenes._wait_leaves_scene(driver, names.MAP_SCENE, timeout=ICON_OPEN_TIMEOUT):
        OPENED_BY["touch"] += 1
        logging.info(f"[KL Map] opened {label} ({kind}) with a touch")
        return
    if outcome and OPENED_BY["touch"]:
        ui_actions.record_finding("no-effect", label,
                                  note="the map stayed after the tap, although touches "
                                       "opened icons earlier in this run")
        raise AssertionError(f"{label} ({kind}): the island map did not respond to a touch "
                             f"on its icon (touches opened {OPENED_BY['touch']} icon(s) "
                             f"earlier in this run): the post-reward lock"
                             + (f"; the touch hit '{outcome.blocker}'" if outcome.blocker else ""))
    ui_actions.record_finding(
        "bypassed", label,
        note=f"the touch {'was delivered and the map stayed' if outcome else outcome.status}; "
             f"opened through IconClicked() instead")
    row["obj"].call_component_method(row["component"], "IconClicked", names.ASSEMBLY,
                                     parameters=[], type_of_parameters=[])
    OPENED_BY["component"] += 1
    logging.info(f"[KL Map] opened {label} ({kind}) through IconClicked()")


def back_to_map(driver, max_steps=6):
    """Back to the island map from a level or exam. Returns bool."""
    for _ in range(max_steps):
        if current_scene(driver) == names.MAP_SCENE:
            return True
        for button in (names.SELECTION_BACK, "BackButton", "prev"):
            if ui_actions.find_any(driver, button) is not None:
                ui_actions.click_by_name(driver, button)
                break
        time.sleep(3)
    return wait_for_scene(driver, names.MAP_SCENE, timeout=15)
