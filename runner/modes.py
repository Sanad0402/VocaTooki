"""Run-mode registry for the HTML runner.

Each mode maps a UI key to a callable ``run(map_page, driver, class_id, lesson)``
that reuses the existing solver functions. No solver logic lives here.
"""

from Utilities import utilsdemo
from vocatooki import lesson_modes


# key -> {label, description, run}
# `run(map_page, driver, class_id, lesson)` executes one lesson.
MODES = {
    "express_hard": {
        "label": "Express - Hard only",
        "description": "Solve the hard level for each lesson (no exam).",
        "run": lambda mp, drv, cid, lesson: mp.solve_lesson_levels_express_hard(cid, lesson),
    },
    "express": {
        "label": "Express - Easy/Medium/Hard",
        "description": "Solve one activity per difficulty + exam for each lesson.",
        "run": lambda mp, drv, cid, lesson: mp.solve_lesson_express(cid, lesson),
    },
    "full": {
        "label": "Full lesson",
        "description": "Solve all levels (3/2/1 activities) + exam for each lesson.",
        "run": lambda mp, drv, cid, lesson: mp.solve_lesson(cid, lesson),
    },
    "levels_only": {
        "label": "Levels only (express)",
        "description": "Solve levels (express) for each lesson, skip the exam.",
        "run": lambda mp, drv, cid, lesson: mp.solve_lesson_levels_express(cid, lesson),
    },
    "third_grade": {
        "label": "3rd grade - Letters/Vocabulary",
        "description": "3rd-grade lessons: the letters level, then the vocabulary level "
                       "(one activity each), then the exam. Lessons without a letters level "
                       "play their own easy/medium/hard levels.",
        "run": lambda mp, drv, cid, lesson: lesson_modes.solve_lesson_third_grade(drv, cid, lesson),
    },
    "exam_only": {
        "label": "Exam only",
        "description": "Solve just the exam for each lesson.",
        "run": lambda mp, drv, cid, lesson: utilsdemo.solve_exam(drv, cid, lesson),
    },
}

DEFAULT_MODE = "express_hard"


def mode_list():
    """Return UI-friendly metadata for all modes (no callables)."""
    return [
        {"key": key, "label": m["label"], "description": m["description"]}
        for key, m in MODES.items()
    ]
