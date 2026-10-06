"""Kideo Land lesson runs.

The game's structure (live + source, 2026-09-29):
  * the start scene shows the islands; each island holds 5 lessons;
  * a lesson is 3 levels -- level 1 easy, 2 medium, 3 hard -- and then its exam;
  * the NEXT lesson unlocks when this lesson's exam is submitted
    (KideoLandUserData.IsAreaEnabled checks the previous exam's isCompleted);
    the levels inside an unlocked lesson are all open, in any order.

So lessons are run in order, and a mode that plays the exam is what opens the
next lesson. A lesson that is still locked is reported as FAILED with that
reason -- never skipped quietly, never passed.

Lesson numbers are global and 1-based: 1-5 = island 1, 6-10 = island 2, ...

What a lesson run does NOT do, said in its RESULT line: the game wants each
activity played 3 times on easy and 2 on medium (1 on hard) before it marks the
LEVEL done. The unlock does not depend on that, so -- like Voca Tooki's lesson
runs -- every activity is played once.
"""

import logging

from kideoland import exam, level_play, names, navigation

# key -> label, description, the levels to play, whether to sit the exam.
# The keys match Voca Tooki's so the panel's mode choice carries over.
MODES = {
    "express_hard": {
        "label": "Express - Hard level + exam",
        "description": "Play the hard level (level 3), then the exam, which unlocks the next lesson.",
        "levels": ("hard",), "exam": True,
    },
    "express": {
        "label": "Express - Easy/Medium/Hard + exam",
        "description": "Play levels 1, 2 and 3 (each activity once), then the exam.",
        "levels": names.DIFFICULTIES, "exam": True,
    },
    "full": {
        "label": "Full lesson",
        "description": "Same as Express - Easy/Medium/Hard + exam (each activity once).",
        "levels": names.DIFFICULTIES, "exam": True,
    },
    "levels_only": {
        "label": "Levels only",
        "description": "Play levels 1, 2 and 3, skip the exam (the next lesson stays locked).",
        "levels": names.DIFFICULTIES, "exam": False,
    },
    "exam_only": {
        "label": "Exam only",
        "description": "Sit just the exam, which unlocks the next lesson.",
        "levels": (), "exam": True,
    },
}

DEFAULT_MODE = "express_hard"

MAX_LESSON = 9 * names.LESSONS_PER_ISLAND       # 9 islands on the start scene


def mode_list():
    return [{"key": k, "label": m["label"], "description": m["description"]}
            for k, m in MODES.items()]


def locate(lesson):
    """Global lesson number (1-based) -> (island index, lesson within the island), 0-based."""
    if lesson < 1:
        raise ValueError(f"Kideo Land lessons start at 1 (got {lesson})")
    return divmod(lesson - 1, names.LESSONS_PER_ISLAND)


def run_lesson(driver, lesson, mode=DEFAULT_MODE):
    """Play one lesson in ``mode``. Raises on a lesson that cannot be played (locked, no map)."""
    spec = MODES[mode]
    island_index, unit = locate(lesson)
    label = f"lesson {lesson} (island {island_index + 1}, lesson {unit + 1})"

    island = navigation.open_island(driver, island_index)
    row = navigation.lesson_on_map(driver, unit)
    if row["locked"]:
        raise navigation.LessonLocked(
            f"{label} is locked -- the exam of the lesson before it has not been submitted "
            f"for this account")

    levels_played, not_covered = [], []
    for difficulty in spec["levels"]:
        icon = row["levels"].get(difficulty)
        if icon is None:
            not_covered.append(f"{difficulty} level missing on the map")
            continue
        navigation.open_icon(driver, icon)
        passed, failed, skipped = level_play.play_level(driver, f"{label} {difficulty}",
                                                        difficulty)
        levels_played.append(f"{difficulty}: {passed} passed, {failed} failed, {skipped} skipped")
        if skipped:
            not_covered.append(f"{skipped} activit{'y' if skipped == 1 else 'ies'} with no solver "
                               f"on {difficulty}")
        if not navigation.back_to_map(driver):
            raise AssertionError(f"{label} {difficulty}: the island map did not come back "
                                 f"after the level (on {navigation.current_scene(driver)})")
        row = navigation.lesson_on_map(driver, unit)      # handles go stale on a new map

    exam_note = "not played in this mode"
    if spec["exam"]:
        submitted = exam.solve_exam(driver, row, label)
        exam_note = {"already_solved": "already solved earlier (entered and left)",
                     True: "submitted"}.get(submitted, "NOT submitted")
        if submitted and unit + 1 < names.LESSONS_PER_ISLAND:
            nxt = navigation.lesson_on_map(driver, unit + 1)
            unlocked = not nxt["locked"]
            exam_note += (f"; lesson {lesson + 1} is now "
                          f"{'unlocked' if unlocked else 'STILL LOCKED'}")
            if not unlocked:
                logging.error(f"[KL Lesson] the exam of {label} was submitted but lesson "
                              f"{lesson + 1} did not unlock")
                level_play._report(f"Lesson {lesson + 1} unlock", "FAILED",
                                   f"the exam of {label} was submitted but lesson "
                                   f"{lesson + 1} is still locked on the map")

    not_covered.append("each activity played once (the game wants 3 plays on easy and "
                       "2 on medium to mark a level done; the unlock does not need it)")
    if navigation.OPENED_BY["component"] and not navigation.OPENED_BY["touch"]:
        not_covered.append("the map's own touch handling: every icon opened through "
                           "IconClicked() because a touch on it did nothing")
    print(f"KL {label} RESULT: island {navigation.island_label(island)}; mode {mode}; "
          f"levels [{'; '.join(levels_played) or 'none'}]; exam {exam_note}. "
          f"Not covered: {'; '.join(not_covered)}.")
    navigation.go_to_start(driver)
