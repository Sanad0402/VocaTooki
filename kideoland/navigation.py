"""Kideo Land navigation: start scene islands -> island map -> lessons, levels and exams.

Lessons are numbered 1..(islands x 5) across the whole game: lesson 1-5 are the
first island's five lessons, 6-10 the second island's, and so on. Inside an
island each lesson is three levels (easy, medium, hard) and its exam, read off
the map icons' own ``levelInfo`` -- never off their position on the screen.

How things open, all by object:
  island  -> ``IslandIcon.click()`` (an EventTrigger wired to CivilizationIslandIcon.Click)
  level   -> ``LevelMapIcon.IconClicked()`` / exam -> ``TestMapIcon.IconClicked()``.
             The icon's own Button has an EMPTY onClick in Kideo Land -- real taps
             go through the map's pan-and-zoom raycast -- so ``click()`` on it
             does nothing and the component method is the object-level press.
  cutscene-> its ``BackButton`` object goes on to the island map.
"""

import logging
import time

from alttester import By

from kideoland import names
from kideoland.login import back_to_start, current_scene, wait_for_scene
from vocatooki import ui_actions


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
    driver.find_object(By.PATH, f"//{island['name']}/{names.ISLAND_ICON}").click()
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
    """Open a level or exam icon through its own IconClicked(). Raises LessonLocked if locked."""
    if row["state"] == names.ICON_LOCKED:
        raise LessonLocked(f"map level {row['number']} is locked")
    row["obj"].call_component_method(row["component"], "IconClicked", names.ASSEMBLY,
                                     parameters=[], type_of_parameters=[])
    logging.info(f"[KL Map] opened map level {row['number']} "
                 f"({row['difficulty'] if row['type'] == names.LEVEL_TYPE_LESSON else 'exam'})")


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
