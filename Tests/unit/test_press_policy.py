"""The press goes through the screen (2026-10-06), pinned with fake drivers.

A production bug — the gift after a hard level locks the map — got past every
run because AltTester's object click fires the object's handlers directly.
These tests lock the new behaviour:

  * a press is a tap at the object's LIVE position, whatever is on top;
  * what the touch hits instead of the object is recorded, never hidden;
  * a level icon counts as entered only when the map scene is GONE;
  * a level ends with the completion contract, and the contract fails on a
    map that no longer reacts to a touch — with "post-reward lock" in the row.

Run:  python -m pytest Tests/unit --noconftest -q
"""

import logging

import pytest

logging.disable(logging.WARNING)

from Utilities import utilsdemo as U  # noqa: E402,F401  (installs the guard)
from vocatooki import (activity_runner, level_completion, map_navigation,  # noqa: E402
                       parrot_guard, scenes, ui_actions)


# ------------------------------------------------------------------ fakes
class FakeObj:
    """A stand-in AltObject: a name, an id, a position, a parent, click/tap counters."""

    _next_id = 1

    def __init__(self, name, x=100.0, y=100.0, parent=None, driver=None):
        self.name, self.x, self.y, self.parent = name, x, y, parent
        self.id = FakeObj._next_id
        FakeObj._next_id += 1
        self.transformId = self.id
        self._altdriver = driver
        self.clicks = self.taps = 0

    def update_object(self):
        return self

    def get_parent(self):
        if self.parent is None:
            raise RuntimeError("root")
        return self.parent

    def click(self):
        self.clicks += 1

    def tap(self):
        self.taps += 1


class FakeDriver:
    """A screen with objects by name, a raycast answer per point, and a scene."""

    def __init__(self, size=(1280.0, 720.0)):
        self.size, self.objects, self.taps, self.scene = size, {}, [], "MapScene"
        self.hit = None                 # what find_object_at_coordinates answers
        self.on_tap = None              # callback(point) -> may change the scene
        self.icons = []

    def get_application_screensize(self):
        return self.size

    def find_object_at_coordinates(self, point):
        return self.hit(point) if callable(self.hit) else self.hit

    def tap(self, point, *a, **k):
        self.taps.append(point)
        if self.on_tap:
            self.on_tap(point)

    def get_current_scene(self):
        return self.scene

    def find_object(self, by, name, enabled=True):
        obj = self.objects.get(name)
        if obj is None:
            raise RuntimeError(f"no {name}")
        return obj

    def find_objects(self, by, path, enabled=True):
        return list(self.icons) if "level_icons" in str(path) else []

    def get_png_screenshot(self, path):
        pass


@pytest.fixture
def quiet(monkeypatch):
    """No real waiting, no parrot guard hooks, a clean findings list."""
    for module in (ui_actions, level_completion, map_navigation, scenes):
        monkeypatch.setattr(module.time, "sleep", lambda s: None)
    monkeypatch.setattr(ui_actions, "BEFORE_SCREEN_PRESS", [])
    monkeypatch.setattr(ui_actions, "INPUT_FINDINGS", [])
    monkeypatch.setattr(map_navigation, "MAP_SETTLE_SECONDS", 0)
    monkeypatch.setattr(map_navigation, "LEVEL_OPEN_TIMEOUT", 0.05)
    monkeypatch.setattr(level_completion, "SCENE_CHANGE_TIMEOUT", 0.05)
    monkeypatch.setattr(level_completion, "MAP_TIMEOUT", 0.3)
    monkeypatch.setattr(level_completion, "POPUP_SETTLE", 0)
    monkeypatch.setattr(ui_actions, "capture_failure_screenshot", lambda d, l: "")
    monkeypatch.delenv(ui_actions.PRESS_POLICY_ENV, raising=False)
    yield


def kinds():
    return [f["kind"] for f in ui_actions.INPUT_FINDINGS]


# ----------------------------------------------------------- press_on_screen
def test_press_is_a_tap_at_the_live_position(quiet):
    d = FakeDriver()
    btn = FakeObj("Back", 300, 200, driver=d)
    d.hit = btn
    assert ui_actions._press(btn, d) is True
    assert d.taps == [(300.0, 200.0)]
    assert btn.clicks == 0 and kinds() == []


def test_a_label_inside_the_button_counts_as_the_button(quiet):
    d = FakeDriver()
    btn = FakeObj("Back", driver=d)
    d.hit = FakeObj("Text", parent=FakeObj("Fitter", parent=btn))
    assert ui_actions.press_on_screen(d, btn)
    assert kinds() == []


def test_a_cover_is_recorded_and_the_tap_still_goes_through(quiet):
    """A finger taps whatever is on top; the step after the press decides."""
    d = FakeDriver()
    icon = FakeObj("LessonLevelIcon(Clone) 7", driver=d)
    d.hit = FakeObj("GiftPopup(Clone)")
    outcome = ui_actions.press_on_screen(d, icon)
    assert outcome and outcome.blocker == "GiftPopup(Clone)"
    assert d.taps and icon.clicks == 0
    assert ui_actions.INPUT_FINDINGS[-1]["kind"] == "covered"
    assert ui_actions.INPUT_FINDINGS[-1]["blocker"] == "GiftPopup(Clone)"


def test_nothing_under_the_finger_taps_then_bypasses_and_says_so(quiet):
    d = FakeDriver()
    tile = FakeObj("Tile", driver=d)
    d.hit = None
    assert ui_actions._press(tile, d) is True
    assert d.taps and tile.clicks == 1
    assert kinds() == ["untouchable", "bypassed"]


def test_off_screen_object_is_not_tapped(quiet):
    d = FakeDriver()
    row = FakeObj("Row", -50, 900, driver=d)
    assert ui_actions._press(row, d) is True          # the object press, recorded
    assert d.taps == [] and row.clicks == 1
    assert kinds() == ["off-screen", "bypassed"]


def test_object_policy_restores_the_old_click(quiet, monkeypatch):
    monkeypatch.setenv(ui_actions.PRESS_POLICY_ENV, "object")
    d = FakeDriver()
    btn = FakeObj("Back", driver=d)
    assert ui_actions._press(btn, d) is True
    assert d.taps == [] and btn.clicks == 1 and kinds() == []


def test_click_by_name_returns_whether_a_press_was_delivered(quiet):
    d = FakeDriver()
    d.objects["GO-Map"] = FakeObj("GO-Map", driver=d)
    d.hit = d.objects["GO-Map"]
    assert ui_actions.click_by_name(d, "GO-Map") is True
    assert ui_actions.click_by_name(d, "Nope") is False


def test_the_guard_routes_altobject_click_through_the_screen():
    """Every .click()/.tap() in the code base — solvers included — is a screen press."""
    from alttester.altobject import AltObject
    assert getattr(AltObject.click, "_screen_press", False)
    assert getattr(AltObject.tap, "_screen_press", False)
    assert parrot_guard.before_action in ui_actions.BEFORE_SCREEN_PRESS
    assert set(ui_actions.ORIGINAL_OBJECT_ACTIONS) >= {"click", "tap"}


# ------------------------------------------------------------- level icons
def test_level_icon_counts_as_entered_only_when_the_map_is_gone(quiet):
    d = FakeDriver()
    icon = FakeObj("LessonLevelIcon(Clone) 3", driver=d)
    d.hit = icon
    d.on_tap = lambda p: setattr(d, "scene", "ActivitySelectionScene")
    assert map_navigation._open_level_icon(d, icon, "level 3", index=2) is True
    assert map_navigation.LAST_LEVEL_INDEX == 2


def test_a_tap_that_leaves_the_map_on_screen_is_a_no_effect_finding(quiet):
    d = FakeDriver()
    icon = FakeObj("LessonLevelIcon(Clone) 3", driver=d)
    d.hit = icon
    assert map_navigation._open_level_icon(d, icon, "level 3") is False
    assert kinds() == ["no-effect"]


# ------------------------------------------------------ completion contract
def _level_world(monkeypatch, locked_after_gift):
    """ActivitySelectionScene with Back; a gift popup over it with a Claim
    button; the map behind, whose icon opens a level unless locked."""
    d = FakeDriver()
    d.scene = "ActivitySelectionScene"
    back = FakeObj("Back", 60, 680, driver=d)
    gift = FakeObj("GiftPopup(Clone)", 640, 360, driver=d)
    claim = FakeObj("Claim", 640, 300, parent=gift, driver=d)
    icon = FakeObj("LessonLevelIcon(Clone) 5", 400, 400, driver=d)
    d.objects = {"Back": back, "Claim": claim}
    d.icons = [icon]
    state = {"gift": True}

    def hit(point):
        if d.scene == "ActivitySelectionScene":
            return claim if (state["gift"] and point == (640.0, 300.0)) else (gift if state["gift"] else back)
        return icon

    def on_tap(point):
        if d.scene == "ActivitySelectionScene":
            if state["gift"]:
                if point == (640.0, 300.0):
                    state["gift"] = False             # Claim pressed: gift gone
                return                                # Back under the gift: nothing
            d.scene = "MapScene"
        elif d.scene == "MapScene" and not locked_after_gift:
            d.scene = "ActivitySelectionScene"
            state["gift"] = False

    d.hit, d.on_tap = hit, on_tap
    monkeypatch.setattr(ui_actions, "is_on_screen", lambda drv, o, margin=0.0: True)
    monkeypatch.setattr(ui_actions, "popup_text", lambda drv, settle=1.5, limit=40: "You won a gift!")
    monkeypatch.setattr(ui_actions, "screen_texts", lambda drv, limit=30: [])
    monkeypatch.setattr(scenes, "wait_for_scene", lambda drv, s, **k: True)
    monkeypatch.setattr(map_navigation, "return_to_map",
                        lambda drv, max_steps=8: setattr(drv, "scene", "MapScene") or True)
    monkeypatch.setattr(activity_runner, "activity_report", [])
    map_navigation.LAST_LEVEL_INDEX = 0
    return d


def test_level_completion_dismisses_the_gift_and_proves_the_map_works(quiet, monkeypatch):
    d = _level_world(monkeypatch, locked_after_gift=False)
    summary = level_completion.finish_level(d, "hard", lesson_num=4)
    row = activity_runner.activity_report[-1]
    assert row["status"] == "PASSED" and row["activity"].startswith("LEVEL COMPLETION")
    assert summary["popups"] == ["'GiftPopup(Clone)' (You won a gift!)"]
    assert "GiftPopup(Clone)" in row["note"] and "re-opened" in row["note"]
    assert "Not covered" in row["note"]


def test_level_completion_fails_on_the_post_reward_lock(quiet, monkeypatch):
    d = _level_world(monkeypatch, locked_after_gift=True)
    with pytest.raises(level_completion.LevelCompletionError) as err:
        level_completion.finish_level(d, "hard", lesson_num=4)
    assert "post-reward lock" in str(err.value)
    row = activity_runner.activity_report[-1]
    assert row["status"] == "FAILED" and "post-reward lock" in row["error"]
    assert "GiftPopup(Clone)" in row["error"]        # what the user saw is in the row


def test_a_level_that_cannot_be_left_is_a_failed_row(quiet, monkeypatch):
    d = _level_world(monkeypatch, locked_after_gift=False)
    d.objects.pop("Claim")                             # the gift has no button we know
    d.hit = lambda p: d.objects["Back"] if d.scene != "ActivitySelectionScene" else FakeObj("Wall")
    d.on_tap = lambda p: None                          # and nothing reacts to any tap
    with pytest.raises(level_completion.LevelCompletionError):
        level_completion.finish_level(d, "hard")
    assert activity_runner.activity_report[-1]["status"] == "FAILED"


# ------------------------------------------------------------ exam contract
def test_exam_completion_probes_a_lesson_level_and_passes(quiet, monkeypatch):
    d = _level_world(monkeypatch, locked_after_gift=False)
    d.scene = "MapScene"
    monkeypatch.setattr(map_navigation, "get_level", lambda c, l, t="lesson", d="": 0)
    summary = level_completion.finish_exam(d, class_id="c", lesson_num=4)
    row = activity_runner.activity_report[-1]
    assert row["status"] == "PASSED" and "[exam, lesson 4]" in row["activity"]
    assert "hard level" in summary["probe"]


def test_exam_completion_fails_when_the_map_stops_taking_touches(quiet, monkeypatch):
    d = _level_world(monkeypatch, locked_after_gift=True)
    d.scene = "MapScene"
    monkeypatch.setattr(map_navigation, "get_level", lambda c, l, t="lesson", d="": 0)
    with pytest.raises(level_completion.LevelCompletionError) as err:
        level_completion.finish_exam(d, class_id="c", lesson_num=4)
    assert "post-reward lock" in str(err.value)
    assert activity_runner.activity_report[-1]["status"] == "FAILED"


# ------------------------------------------------------------- Kideo Land
def test_kideo_land_icon_opens_by_touch_and_fails_once_touches_stop_working(quiet, monkeypatch):
    from kideoland import names, navigation
    monkeypatch.setattr(navigation, "ICON_OPEN_TIMEOUT", 0.05)
    monkeypatch.setattr(navigation, "OPENED_BY", {"touch": 0, "component": 0})
    d = FakeDriver()
    d.scene = names.MAP_SCENE
    icon = FakeObj("KideoLandLevelMapIcon(Clone)", driver=d)
    icon.calls = []
    icon.call_component_method = lambda *a, **k: icon.calls.append(a)
    d.hit = icon
    d.on_tap = lambda p: setattr(d, "scene", "Level")
    row = {"obj": icon, "component": "LevelMapIcon", "state": names.ICON_CURRENT,
           "number": "3", "type": names.LEVEL_TYPE_LESSON, "difficulty": "hard"}
    navigation.open_icon(d, row)
    assert navigation.OPENED_BY["touch"] == 1 and icon.calls == []

    d.scene = names.MAP_SCENE
    d.on_tap = lambda p: None                          # the map no longer reacts
    with pytest.raises(AssertionError) as err:
        navigation.open_icon(d, row)
    assert "post-reward lock" in str(err.value) and icon.calls == []


def test_kideo_land_falls_back_to_the_component_only_before_any_touch_worked(quiet, monkeypatch):
    from kideoland import names, navigation
    monkeypatch.setattr(navigation, "ICON_OPEN_TIMEOUT", 0.05)
    monkeypatch.setattr(navigation, "OPENED_BY", {"touch": 0, "component": 0})
    d = FakeDriver()
    d.scene = names.MAP_SCENE
    icon = FakeObj("KideoLandLevelMapIcon(Clone)", driver=d)
    icon.calls = []
    icon.call_component_method = lambda *a, **k: icon.calls.append(a)
    d.hit = icon
    row = {"obj": icon, "component": "LevelMapIcon", "state": names.ICON_CURRENT,
           "number": "3", "type": names.LEVEL_TYPE_LESSON, "difficulty": "hard"}
    navigation.open_icon(d, row)
    assert len(icon.calls) == 1 and kinds() == ["bypassed"]


# -------------------------------------------------------------- generator
@pytest.fixture
def generator():
    from runner.test_generator import RallyTestGenerator
    return RallyTestGenerator(".")


@pytest.mark.parametrize("name, desc, expected", [
    ("Complete hard level and receive the gift",
     "Level: 12. After completing all three activities a gift is given", "level"),
    ("Navigate to other levels after level completion", "level 7", "level"),
    ("Pipes activity successful finish in hard level", "Map level: 44", "activity"),
    ("Solve exam pages successfully", "Level: 40 (Exam)", "exam"),
])
def test_level_completion_cases_get_their_own_type(generator, name, desc, expected):
    assert generator._infer_test_type(name, desc + " Username: u Password: p",
                                      "Tests/rally/TF181/x.py") == expected


def test_level_template_plays_the_whole_level_then_the_contract(generator):
    code = generator._gen_level_completion(
        "TC9999", "Complete hard level and receive the gift",
        {"username": "vt1", "password": "pw"}, "test_tc9999",
        "Level: 12 hard. After completing all three activities a gift is given", [],
        {"expected": "map still navigable"})
    compile(code, "generated.py", "exec")
    assert "utilsdemo.handle_level_flow(driver)" in code
    assert 'utilsdemo.finish_level(driver, DIFFICULTY' in code
    assert 'DIFFICULTY = "hard"' in code and "MAP_LEVEL = 12" in code
    assert "RESULT:" in code and "Not covered" in code
