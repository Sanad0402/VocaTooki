"""Which game a run drives: Voca Tooki (the default, unchanged) or Kideo Land.

The activity and exam solvers are shared by both games; what differs is the
login, the way to a lesson and the lesson flow itself, so each game names its
own lesson modes and lesson numbering here. The panel asks for the game in the
Run dialog, next to the API question, before every run.
"""

from .modes import MODES as VT_MODES, DEFAULT_MODE as VT_DEFAULT_MODE

DEFAULT_GAME = "vt"

GAMES = {
    "vt": {
        "label": "Voca Tooki",
        "hint": "Class map from the chosen API; lessons are 0-based class-map lessons.",
        "lesson_min": 0,
        "lesson_max": None,
        "uses_api": True,
    },
    "kl": {
        "label": "Kideo Land",
        "hint": "Islands on the start scene, 5 lessons each: lesson 1-5 = island 1, "
                "6-10 = island 2 ... A lesson's exam unlocks the next lesson.",
        "lesson_min": 1,
        "lesson_max": 45,
        "uses_api": False,
    },
}


def normalise(game):
    return str(game or DEFAULT_GAME).strip().lower()


def game_list():
    return [{"key": k, **v} for k, v in GAMES.items()]


def modes_for(game):
    """key -> {label, description, ...} for the game's lesson runs."""
    if normalise(game) == "kl":
        from kideoland import lessons as kl_lessons
        return kl_lessons.MODES
    return VT_MODES


def default_mode(game):
    if normalise(game) == "kl":
        from kideoland import lessons as kl_lessons
        return kl_lessons.DEFAULT_MODE
    return VT_DEFAULT_MODE


def mode_list(game):
    return [{"key": k, "label": m["label"], "description": m["description"]}
            for k, m in modes_for(game).items()]


def lesson_errors(game, lesson_from, lesson_to):
    """Range problems specific to the game's lesson numbering."""
    spec = GAMES[normalise(game)]
    errors = []
    if lesson_from < spec["lesson_min"]:
        errors.append(f"{spec['label']} lessons start at {spec['lesson_min']}.")
    if spec["lesson_max"] is not None and lesson_to > spec["lesson_max"]:
        errors.append(f"{spec['label']} has {spec['lesson_max']} lessons.")
    return errors
