"""Offline pins for the panel's run modes (runner/modes.py): which levels each
mode enters, in what order, how many activities it plays in each, and whether
it sits the exam — on a normal class map and on a 3rd-grade one.

The game side is replaced by recorders (entering a level, playing an activity,
the completion contract, the exam); the mode functions, the level resolver
(map_navigation.get_level) and the class-map shapes are real. The maps below
copy the shapes served by vtbe2027 on 2026-10-12: class 28 (normal) and class
2774 (3rd grade).

Run:  python -m pytest Tests/unit/test_run_modes.py --noconftest -q
"""

import logging

import pytest

logging.disable(logging.WARNING)

from Pages.map_page import MapPage  # noqa: E402
from Utilities import utilsdemo  # noqa: E402
from runner.modes import MODES  # noqa: E402
from vocatooki import (activity_runner, backend_api, exam_solver,  # noqa: E402
                       lesson_modes, level_completion, map_navigation)


def _class_map(shapes):
    """[['easy', 'medium', 'exam'], ...] -> a get-class-map payload, levels numbered in order."""
    levels, n = [], 0
    for shape in shapes:
        lesson = []
        for kind in shape:
            if kind == "letters":
                lesson.append({"type": "character", "difficulty": "easy", "level": n, "letter": "A"})
            elif kind in ("exam", "dialogue", "reading_comp"):
                lesson.append({"type": kind, "level": n})
            else:
                lesson.append({"type": "lesson", "difficulty": kind, "level": n})
            n += 1
        levels.append(lesson)
    return {"map": {"levels": levels}}


NORMAL = ["easy", "medium", "hard", "exam"]
MAPS = {
    # class 28: easy/medium/hard/exam, some lessons add a dialogue or reading level
    "normal": _class_map([NORMAL, NORMAL + ["dialogue"], NORMAL + ["reading_comp"]]),
    # class 2774: lessons 0-33 letters/vocabulary/exam, 34-38 easy/medium/exam, 39-43 full trio
    "third": _class_map([["letters", "medium", "exam"],
                         ["easy", "medium", "exam"],
                         NORMAL]),
}


@pytest.fixture
def game(monkeypatch):
    """Record what a mode does instead of doing it. Returns (trace, use_map)."""
    trace = []
    current = {}

    monkeypatch.setattr(backend_api, "get_class_map", lambda cid, map_id=1: current["map"])

    def enter(altdriver, class_id, lesson, type="lesson", difficulty=-1):
        level = map_navigation.get_level(class_id, lesson, type, difficulty)
        if level < 0:
            return False
        map_navigation.LAST_LEVEL_INDEX = level
        kind = {"letters": "letters", "exam": "exam"}.get(type, difficulty)
        trace.append(("enter", kind, level))
        return True

    def exam(altdriver, class_id, lesson):
        if not map_navigation.enter_to_level(altdriver, class_id, lesson, type="exam"):
            raise RuntimeError("no exam level")
        trace.append(("exam solved",))

    monkeypatch.setattr(map_navigation, "enter_to_level", enter)
    monkeypatch.setattr(map_navigation, "return_to_map", lambda d, *a, **k: trace.append(("back to map",)))
    monkeypatch.setattr(activity_runner, "handle_level_flow", lambda d, *a, **k: trace.append(("activity",)))
    monkeypatch.setattr(activity_runner, "record_failure",
                        lambda d, label, error, difficulty=None: trace.append(("FAILED", label, str(error))))
    monkeypatch.setattr(level_completion, "finish_level",
                        lambda d, name, **k: trace.append(("level done", name)))
    monkeypatch.setattr(exam_solver, "solve_exam", exam)
    monkeypatch.setattr(utilsdemo, "solve_exam", exam)
    monkeypatch.setattr(lesson_modes.time, "sleep", lambda s: None)

    def use_map(name):
        current["map"] = MAPS[name]
    return trace, use_map


def run(game, mode, map_name, lesson):
    trace, use_map = game
    use_map(map_name)
    del trace[:]
    MODES[mode]["run"](MapPage(object()), object(), 2774, lesson)
    return list(trace)


def plays(trace):
    """The trace boiled down: ['easy x1', 'medium x1', 'exam'] (+ 'FAILED: ...' rows)."""
    out, level = [], None
    for event in trace:
        if event[0] == "enter":
            level = event[1]
            out.append([level, 0])
        elif event[0] == "activity":
            out[-1][1] += 1
        elif event[0] == "FAILED":
            out.append(f"FAILED: {event[2]}")
    return [x if isinstance(x, str) else (x[0] if x[0] == "exam" else f"{x[0]} x{x[1]}") for x in out]


def test_every_mode_is_covered_here():
    assert set(MODES) == {"express_hard", "express", "full", "levels_only", "exam_only", "third_grade"}


@pytest.mark.parametrize("mode, expected", [
    ("express_hard", ["hard x1"]),
    ("express", ["easy x1", "medium x1", "hard x1", "exam"]),
    ("full", ["easy x3", "medium x2", "hard x1", "exam"]),
    ("levels_only", ["easy x1", "medium x1", "hard x1"]),
    ("exam_only", ["exam"]),
    ("third_grade", ["easy x1", "medium x1", "hard x1", "exam"]),
])
@pytest.mark.parametrize("lesson", [0, 1, 2])
def test_normal_class(game, mode, expected, lesson):
    """A normal class: every mode finds every level it asks for; extra levels
    (dialogue, reading) are left alone; no FAILED rows."""
    assert plays(run(game, mode, "normal", lesson)) == expected


def test_normal_class_levels_finish_through_the_contract(game):
    trace = run(game, "express", "normal", 0)
    assert [e[1] for e in trace if e[0] == "level done"] == ["easy", "medium", "hard"]
    assert trace[-1] == ("exam solved",)


def test_third_grade_letters_lesson(game):
    """Letters level, then vocabulary (the medium level), then the exam."""
    trace = run(game, "third_grade", "third", 0)
    assert plays(trace) == ["letters x1", "medium x1", "exam"]
    assert [e[1] for e in trace if e[0] == "level done"] == ["letters", "vocabulary"]
    assert trace[-1] == ("exam solved",)


@pytest.mark.parametrize("lesson, expected", [
    (1, ["easy x1", "medium x1", "exam"]),                 # 2774 lessons 34-38
    (2, ["easy x1", "medium x1", "hard x1", "exam"]),      # 2774 lessons 39-43
])
def test_third_grade_later_lessons_play_their_own_levels(game, lesson, expected):
    assert plays(run(game, "third_grade", "third", lesson)) == expected


@pytest.mark.parametrize("mode", ["express_hard", "express", "full", "levels_only"])
def test_hard_modes_on_a_letters_lesson_fail_and_say_why(game, mode):
    """No hard level in a 3rd-grade letters lesson: a FAILED row that names the
    lesson's real levels — never a silent skip, never a pass."""
    failed = [e for e in run(game, mode, "third", 0) if e[0] == "FAILED"]
    assert len(failed) == 1
    assert "no hard level" in failed[0][2] and "letters, medium, exam" in failed[0][2]


def test_exam_only_on_third_grade(game):
    assert plays(run(game, "exam_only", "third", 0)) == ["exam"]


def test_third_grade_plays_only_the_levels_the_map_lists(game):
    """A lesson whose map has no vocabulary level is not given one."""
    trace, use_map = game
    MAPS["letters_only"] = _class_map([["letters", "exam"]])
    try:
        assert plays(run(game, "third_grade", "letters_only", 0)) == ["letters x1", "exam"]
    finally:
        del MAPS["letters_only"]


@pytest.mark.parametrize("map_name, probe", [("normal", 2), ("third", 1)])
def test_exam_completion_probes_hard_else_vocabulary(game, monkeypatch, map_name, probe):
    """After the exam, the map check opens the lesson's hard level; a 3rd-grade
    lesson has none, so its vocabulary (medium) level — not the exam again."""
    trace, use_map = game
    use_map(map_name)
    seen = {}
    monkeypatch.setattr(level_completion.scenes, "_current_scene",
                        lambda d: level_completion.scene_names.MAP_SCENE)
    monkeypatch.setattr(level_completion, "_wait_for_map", lambda d, s: None)
    monkeypatch.setattr(level_completion, "_map_touchable", lambda d, i, s: None)
    monkeypatch.setattr(level_completion, "_row", lambda *a, **k: None)
    monkeypatch.setattr(map_navigation, "_find_level_icons", lambda d: [])
    monkeypatch.setattr(level_completion, "_probe_navigation",
                        lambda d, icons, played, other, summary, **k: seen.update(other=other))
    level_completion.finish_exam(object(), class_id=2774, lesson_num=0)
    assert seen["other"] == [probe]


@pytest.mark.parametrize("mode, map_name, expected", [
    ("express_hard", "normal", [(0, "hard")]),
    ("express", "normal", [(0, "easy"), (0, "medium"), (0, "hard")]),
    ("full", "normal", [(0, "easy")] * 3 + [(0, "medium")] * 2 + [(0, "hard")]),
    ("levels_only", "normal", [(0, "easy"), (0, "medium"), (0, "hard")]),
    ("third_grade", "third", [(0, "letters"), (0, "vocabulary")]),
])
def test_every_activity_knows_the_level_it_is_played_in(game, monkeypatch, mode, map_name, expected):
    """Each play's frames and report row are filed under the level really
    being played — not guessed from how often the activity appeared."""
    seen = []
    monkeypatch.setattr(activity_runner, "handle_level_flow",
                        lambda d, *a, **k: seen.append((activity_runner._LEVEL["lesson"],
                                                        activity_runner._LEVEL["level"])))
    run(game, mode, map_name, 0)
    assert seen == expected
    assert activity_runner._LEVEL == {"lesson": None, "level": ""}     # cleared after the run
