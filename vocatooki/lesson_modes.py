"""The lesson-run modes (full, express, express-hard, levels only) built on the runner.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import activity_runner, backend_api, exam_solver, level_completion, map_navigation


def _after_level(altdriver, level_name, class_id, lesson_num, opened, finished=True):
    """After the level: the completion contract when it FINISHED (one report
    row); after a level that did not, just back to the map for the next lesson
    — the contract on a half-played level only proves what is already known."""
    if finished:
        level_completion.finish_level(altdriver, level_name, class_id=class_id,
                                      lesson_num=lesson_num, other_levels=tuple(opened))
    else:
        logging.warning(f"[solve_lesson_levels] the {level_name} level did not finish — "
                        f"skipping its completion check, returning to the map")
        map_navigation.return_to_map(altdriver)


def _level_failed(altdriver, level_name, lesson_num, error):
    """A level that raised is a FAILED row, not a log line. (The completion
    contract writes its own row, so its error is not written twice.)"""
    logging.error(f"[solve_lesson_levels] Error solving {level_name} level: {error}")
    if not isinstance(error, level_completion.LevelCompletionError):
        activity_runner.record_failure(altdriver, f"{level_name} level (lesson {lesson_num})",
                                       error, difficulty=level_name)


def _not_entered(altdriver, class_id, level_name, lesson_num):
    """A level that could not be entered is a FAILED row. When the class map has
    no such level for the lesson (a 3rd-grade lesson has no hard level), say so,
    so the row points at the wrong mode rather than at the map."""
    shape = map_navigation.lesson_levels_summary(class_id, lesson_num)
    in_map = "medium" if level_name == "vocabulary" else level_name   # vocabulary = the medium level
    if shape and in_map not in shape.split(", "):
        reason = (f"this lesson has no {level_name} level (its levels: {shape}) — "
                  f"pick the mode that matches the class")
    else:
        reason = ("the level could not be entered: no icon for it, or the press on its icon "
                  "did not open it (see the input findings)")
    activity_runner.record_failure(altdriver, f"{level_name} level (lesson {lesson_num})",
                                   reason, difficulty=level_name)


def solve_lesson_levels(altdriver, class_id, lesson_num):
    difficulties = [("easy", 0), ("medium", 1), ("hard", 2)]
    opened = []

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            _not_entered(altdriver, class_id, level_name, lesson_num)
            continue

        try:
            with activity_runner.level_context(lesson_num, level_name):
                finished = solve_level(altdriver, diff)
            _after_level(altdriver, level_name, class_id, lesson_num, opened, finished)
            opened.append(map_navigation.LAST_LEVEL_INDEX)
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)


def solve_level(altdriver, difficulty):
    """
    Executes the level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (str): "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Solving level with difficulty: {difficulty}")

    # Normalize difficulty to a numeric value. solve_lesson_levels passes the
    # number (0/1/2): a .lower() on it crashed every level of a Full run.
    difficulty_map = {"easy": 0, "medium": 1, "hard": 2}
    if isinstance(difficulty, str):
        difficulty_value = difficulty_map.get(difficulty.lower(), -1)
    else:
        difficulty_value = difficulty if difficulty in (0, 1, 2) else -1

    if difficulty_value == -1:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        return

    # Number of repetitions based on difficulty
    repetitions = {0: 3, 1: 2, 2: 1}[difficulty_value]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    # Loop through the repetitions and handle each level flow
    ok = True
    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)
            ok = False

    logging.info(f"[solve_level] Finished solving level with difficulty {difficulty}")
    time.sleep(4)  # Wait before continuing to the next level
    return ok


def solve_lesson(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels(altdriver, class_id, lesson_num)
        time.sleep(2)
        exam_solver.solve_exam(altdriver, class_id, lesson_num)
        time.sleep(2)
    except Exception as e:
        _exam_failed(altdriver, lesson_num, e)


def _exam_failed(altdriver, lesson_num, error):
    print(f"[ERROR] Failed to solve lesson {lesson_num}: {error}")
    if not isinstance(error, level_completion.LevelCompletionError):   # has its own row
        activity_runner.record_failure(altdriver, f"lesson {lesson_num} exam", error)


def solve_level_express(altdriver, difficulty):
    """
    Executes opened level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (int or str): 0, 1, 2 or "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Starting level solving for difficulty: {difficulty}")

    # Normalize difficulty
    if isinstance(difficulty, str):
        difficulty = {"easy": 0, "medium": 1, "hard": 2}.get(difficulty.lower(), -1)

    if difficulty not in [0, 1, 2]:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        raise ValueError(f"Unknown difficulty: {difficulty}")

    repetitions = {0: 1, 1: 1, 2: 1}[difficulty]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    ok = True
    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)
            ok = False

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)
    return ok


def solve_level_express_hard(altdriver, difficulty):
    """
    Executes opened level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (int or str): 0, 1, 2 or "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Starting level solving for difficulty: {difficulty}")

    # Normalize difficulty
    if isinstance(difficulty, str):
        difficulty = {"hard": 2}.get(difficulty.lower(), -1)

    if difficulty not in [2]:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        raise ValueError(f"Unknown difficulty: {difficulty}")

    repetitions = {2: 1}[difficulty]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    ok = True
    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)
            ok = False

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)
    return ok


def solve_lesson_express(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels_express(altdriver, class_id, lesson_num)
        time.sleep(5)
        exam_solver.solve_exam(altdriver, class_id, lesson_num)
        time.sleep(3)
    except Exception as e:
        _exam_failed(altdriver, lesson_num, e)


def solve_lesson_express_hard(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels_express_hard(altdriver, class_id, lesson_num)
        time.sleep(5)
        exam_solver.solve_exam(altdriver, class_id, lesson_num)
        time.sleep(3)
    except Exception as e:
        _exam_failed(altdriver, lesson_num, e)


def solve_lessons_express_hard(altdriver, class_id, num_lessons, start_lesson=0):
    """
    Solve a range of lessons (hard express flow).

    Args:
        altdriver: AltTester driver instance.
        class_id: Class ID to solve lessons for.
        num_lessons (int): How many lessons to run.
        start_lesson (int): First lesson number to start from (default 0).

    Example:
        # Run lessons 0..6 (7 lessons)
        solve_lessons_express_hard(altdriver, class_id, num_lessons=7)
    """
    end_lesson = start_lesson + num_lessons
    print(f"[INFO] Solving {num_lessons} lesson(s): {start_lesson}..{end_lesson - 1} for class {class_id}")
    for lesson_num in range(start_lesson, end_lesson):
        # solve_lesson_express_hard already guards each lesson with try/except,
        # so a failure in one lesson won't stop the rest of the run.
        solve_lesson_express_hard(altdriver, class_id, lesson_num)


def solve_lesson_levels_express(altdriver, class_id, lesson_num):
    difficulties = [("easy", 0), ("medium", 1), ("hard", 2)]
    opened = []

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            _not_entered(altdriver, class_id, level_name, lesson_num)
            continue

        try:
            time.sleep(2)
            with activity_runner.level_context(lesson_num, level_name):
                finished = solve_level_express(altdriver, diff)
            _after_level(altdriver, level_name, class_id, lesson_num, opened, finished)
            opened.append(map_navigation.LAST_LEVEL_INDEX)
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)


def solve_lesson_levels_express_hard(altdriver, class_id, lesson_num):
    difficulties = [("hard", 2)]

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            _not_entered(altdriver, class_id, level_name, lesson_num)
            continue

        try:
            time.sleep(2)
            with activity_runner.level_context(lesson_num, level_name):
                finished = solve_level_express_hard(altdriver, diff)
            # Only the hard level is played in this mode, so the probe re-opens
            # the level just finished: that is still a map touch after the gift.
            _after_level(altdriver, level_name, class_id, lesson_num, opened=(),
                         finished=finished)
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)


# 3rd grade: a lesson is a letters level (map type "character"), then a
# vocabulary level (the medium "lesson" level), then the exam — no easy/medium/
# hard trio. The class's last lessons (2774: 34-43) drop the letters level and
# are easy/medium(/hard) instead, so the levels are read from the class map.
# (level_name, get_level type, get_level difficulty)
THIRD_GRADE_LEVELS = [("letters", "letters", -1), ("vocabulary", "lesson", "medium")]


def third_grade_levels(class_id, lesson_num):
    """The lesson's playable levels in map order, as (name, type, difficulty).

    A letters+vocabulary lesson gives THIRD_GRADE_LEVELS; any other shape gives
    its own easy/medium/hard levels. Falls back to THIRD_GRADE_LEVELS when the
    map cannot be read, so the failure rows still name the levels expected."""
    try:
        levels = backend_api.get_class_map(class_id, map_id=1)["map"]["levels"][lesson_num]
    except Exception:                                # noqa: BLE001 - network / shape
        return list(THIRD_GRADE_LEVELS)
    plan = []
    for lv in levels:
        difficulty = (lv.get("difficulty") or "").lower()
        if lv.get("type") == "character":
            plan.append(("letters", "letters", -1))
        elif lv.get("type") == "lesson" and difficulty:
            has_letters = any(x.get("type") == "character" for x in levels)
            name = "vocabulary" if has_letters and difficulty == "medium" else difficulty
            plan.append((name, "lesson", difficulty))
    return plan or list(THIRD_GRADE_LEVELS)


def solve_lesson_levels_third_grade(altdriver, class_id, lesson_num):
    """Play the lesson's levels (letters, then vocabulary) — one activity each, like express."""
    opened = []
    plan = third_grade_levels(class_id, lesson_num)
    logging.info(f"[solve_lesson_levels] 3rd-grade lesson {lesson_num}: "
                 f"{', '.join(name for name, _, _ in plan)}, exam")

    for level_name, level_type, difficulty in plan:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num,
                                             type=level_type, difficulty=difficulty):
            _not_entered(altdriver, class_id, level_name, lesson_num)
            continue

        try:
            time.sleep(2)
            with activity_runner.level_context(lesson_num, level_name):
                finished = solve_level_express(altdriver, 0)
            _after_level(altdriver, level_name, class_id, lesson_num, opened, finished)
            opened.append(map_navigation.LAST_LEVEL_INDEX)
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)


def solve_lesson_third_grade(altdriver, class_id, lesson_num):
    """3rd grade lesson: letters level, vocabulary level, then the exam."""
    try:
        print(f"[INFO] Solving 3rd-grade lesson {lesson_num} for class {class_id}")
        solve_lesson_levels_third_grade(altdriver, class_id, lesson_num)
        time.sleep(5)
        exam_solver.solve_exam(altdriver, class_id, lesson_num)
        time.sleep(3)
    except Exception as e:
        _exam_failed(altdriver, lesson_num, e)
