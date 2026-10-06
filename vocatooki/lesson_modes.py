"""The lesson-run modes (full, express, express-hard, levels only) built on the runner.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import activity_runner, exam_solver, level_completion, map_navigation


def _after_level(altdriver, level_name, class_id, lesson_num, opened):
    """Leave the level like a user and prove the map still works (one report row)."""
    level_completion.finish_level(altdriver, level_name, class_id=class_id,
                                  lesson_num=lesson_num, other_levels=tuple(opened))


def _level_failed(altdriver, level_name, lesson_num, error):
    """A level that raised is a FAILED row, not a log line. (The completion
    contract writes its own row, so its error is not written twice.)"""
    logging.error(f"[solve_lesson_levels] Error solving {level_name} level: {error}")
    if not isinstance(error, level_completion.LevelCompletionError):
        activity_runner.record_failure(altdriver, f"{level_name} level (lesson {lesson_num})",
                                       error, difficulty=level_name)


def solve_lesson_levels(altdriver, class_id, lesson_num):
    difficulties = [("easy", 0), ("medium", 1), ("hard", 2)]
    opened = []

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            activity_runner.record_failure(
                altdriver, f"{level_name} level (lesson {lesson_num})",
                "the level could not be entered: no icon for it, or the press on its icon "
                "did not open it (see the input findings)", difficulty=level_name)
            continue

        try:
            solve_level(altdriver, diff)
            _after_level(altdriver, level_name, class_id, lesson_num, opened)
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

    # Normalize difficulty to a numeric value
    difficulty_map = {"easy": 0, "medium": 1, "hard": 2}
    difficulty_value = difficulty_map.get(difficulty.lower(), -1)

    if difficulty_value == -1:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        return

    # Number of repetitions based on difficulty
    repetitions = {0: 3, 1: 2, 2: 1}[difficulty_value]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    # Loop through the repetitions and handle each level flow
    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)

    logging.info(f"[solve_level] Finished solving level with difficulty {difficulty}")
    time.sleep(4)  # Wait before continuing to the next level


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

    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)


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

    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            activity_runner.handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")
            activity_runner.record_failure(altdriver, f"level flow {i + 1}/{repetitions}", e)

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)


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
            activity_runner.record_failure(
                altdriver, f"{level_name} level (lesson {lesson_num})",
                "the level could not be entered: no icon for it, or the press on its icon "
                "did not open it (see the input findings)", difficulty=level_name)
            continue

        try:
            time.sleep(2)
            solve_level_express(altdriver, diff)
            _after_level(altdriver, level_name, class_id, lesson_num, opened)
            opened.append(map_navigation.LAST_LEVEL_INDEX)
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)


def solve_lesson_levels_express_hard(altdriver, class_id, lesson_num):
    difficulties = [("hard", 2)]

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            activity_runner.record_failure(
                altdriver, f"{level_name} level (lesson {lesson_num})",
                "the level could not be entered: no icon for it, or the press on its icon "
                "did not open it (see the input findings)", difficulty=level_name)
            continue

        try:
            time.sleep(2)
            solve_level_express_hard(altdriver, diff)
            # Only the hard level is played in this mode, so the probe re-opens
            # the level just finished: that is still a map touch after the gift.
            _after_level(altdriver, level_name, class_id, lesson_num, opened=())
        except Exception as e:
            _level_failed(altdriver, level_name, lesson_num, e)
