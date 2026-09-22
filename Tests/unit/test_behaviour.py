"""Offline behaviour pins: today's decisions, checked with fake drivers (no app needed).

Each test locks a rule that was proven live, so a reorganisation that changes
what the framework DOES fails here before it ever reaches a run.

Run:  python -m pytest Tests/unit --noconftest -q
"""

import logging
import os
import time

import pytest

logging.disable(logging.WARNING)

from Activities import activitiesDemo as A  # noqa: E402
from Utilities import parrot_guard  # noqa: E402
from Utilities import utilsdemo as U  # noqa: E402


class Obj:
    """A stand-in AltObject: a name, a text and a position."""

    def __init__(self, name="", text="", x=0.0, y=0.0, driver=None):
        self.name, self._text, self.x, self.y = name, text, x, y
        self._altdriver = driver
        self.clicked = 0

    def get_text(self):
        return self._text

    def click(self):
        self.clicked += 1


# ---------------------------------------------------------------- completion
@pytest.mark.parametrize("objs, progress, expected", [
    (set(), (8, 8), True),                                   # counter at its total
    (set(), (12, 12), True),
    (set(), (2, 8), False),                                  # stopped short
    ({"FeedbackPopup(Clone)"}, (0, 0), True),                # success screen
    ({"FailureFeedbackPopup(Clone)"}, (3, 8), False),        # the game was lost
    (set(), (0, 0), None),                                   # nothing to judge by
])
def test_activity_finished(monkeypatch, objs, progress, expected):
    monkeypatch.setattr(U, "find_any", lambda d, n, enabled=True: Obj(n) if n in objs else None)
    monkeypatch.setattr(U, "read_activity_progress", lambda d: progress)
    finished, _note = U.activity_finished(None, settle=0.2)
    assert finished is expected


# -------------------------------------------------------------- mid frame
@pytest.mark.parametrize("total, at", [(4, 2), (5, 2), (6, 3), (8, 4), (11, 5), (12, 6)])
def test_mid_frame_fires_once_at_half(monkeypatch, total, at):
    shots, cur = [], {"v": (0, total)}
    monkeypatch.setattr(U, "activity_frame", lambda d, s, p: shots.append((p, cur["v"])))
    monkeypatch.setattr(U, "read_activity_progress", lambda d: cur["v"])
    driver = object()
    U._watch_mid_frame(driver, "X")
    for done in range(total + 1):
        cur["v"] = (done, total)
        U._MID["checked"] = 0.0
        U._mid_activity_frame(driver)
    U._watch_mid_frame(driver, None)
    assert shots == [(U.ACTIVITY_FRAMES[1], (at, total))]


# ----------------------------------------------------------------- backend
@pytest.fixture
def restore_backend():
    yield
    U.set_backend(U.VT_BACKEND_AUTO)


@pytest.mark.parametrize("name", sorted(U.VT_BACKENDS))
def test_set_backend_points_every_api_at_one_host(restore_backend, name):
    U.set_backend(name)
    base = U.VT_BACKENDS[name]
    assert U.VT_DATA_API == base and U.VT_TASKS_API == base
    assert U._vt_data_bases() == [base]
    assert U.backend_pinned() and os.environ["VT_BACKEND"] == name


def test_auto_backend_keeps_the_host_chain(restore_backend):
    U.set_backend("green")
    U.set_backend(U.VT_BACKEND_AUTO)
    assert not U.backend_pinned()
    assert U._vt_data_bases() == [b.rstrip("/") for b in U._VT_DATA_API_HOSTS_DEFAULT]


def test_unknown_backend_is_refused(restore_backend):
    with pytest.raises(ValueError):
        U.set_backend("nope")


# ------------------------------------------------------------ parrot guard
class ParrotWorld:
    def __init__(self, bubble=False, icon=True, icon_works=True, blocker=0, scene="MapScene"):
        self.bubble, self.icon, self.icon_works = bubble, icon, icon_works
        self.blocker, self.scene, self.presses = blocker, scene, []


@pytest.fixture
def parrot(monkeypatch):
    world = ParrotWorld()
    monkeypatch.setattr(parrot_guard, "INTRO_QUIET", 0.2)
    monkeypatch.setattr(parrot_guard, "POLL", 0.02)
    monkeypatch.setattr(parrot_guard, "ARRIVAL_GRACE", 0.05)
    monkeypatch.setattr(U, "parrot_bubble_shown", lambda d: world.bubble)
    monkeypatch.setattr(U, "_current_scene", lambda d: world.scene)
    monkeypatch.setattr(U, "wait_for_scene_ready", lambda d, **k: True)

    def find_any(d, name, enabled=True):
        if name == "HelpButton" and world.icon:
            return Obj(name)
        if name == U.SCREEN_BLOCKER and world.blocker:
            return Obj(name)
        return None

    def press(obj):
        world.presses.append(obj.name)
        if obj.name == "HelpButton" and world.icon_works:
            world.bubble = False
        if obj.name == U.SCREEN_BLOCKER:
            world.blocker -= 1
        return True

    def tap_empty(d):
        world.presses.append("EMPTY_POINT")
        world.bubble = False
        return True

    monkeypatch.setattr(U, "find_any", find_any)
    monkeypatch.setattr(U, "_press", press)
    monkeypatch.setattr(U, "tap_empty_area", tap_empty)
    return world


def _act(driver, world, target="Button"):
    parrot_guard._state[id(driver)] = {"scene": world.scene, "checked": 0.0}
    parrot_guard.before_action(driver, target)


@pytest.mark.parametrize("setup, presses", [
    (dict(bubble=True), ["HelpButton"]),                          # the icon first
    (dict(bubble=True, icon_works=False), ["HelpButton", "EMPTY_POINT"]),   # fallback
    (dict(bubble=True, icon=False), ["EMPTY_POINT"]),
    (dict(bubble=False), []),                                     # nothing up
    (dict(bubble=None), []),                                      # unreadable: never blind
])
def test_parrot_guard_decisions(parrot, monkeypatch, setup, presses):
    monkeypatch.setattr(U, "dismiss_help_popup",
                        lambda d, **k: _real_dismiss(d, verify_timeout=0.1, **k))
    for k, v in setup.items():
        setattr(parrot, k, v)
    _act(object(), parrot)
    assert parrot.presses == presses


_real_dismiss = U.dismiss_help_popup


def test_parrot_guard_skips_its_own_controls_and_when_paused(parrot):
    parrot.bubble = True
    _act(object(), parrot, target="HelpButton")
    with parrot_guard.paused():
        _act(object(), parrot)
    assert parrot.presses == []


def test_parrot_guard_wraps_actions_but_not_mid_drag():
    from alttester import AltDriver
    from alttester.altobject import AltObject
    for name in parrot_guard._OBJECT_ACTIONS:
        assert getattr(getattr(AltObject, name), "_parrot_guarded", False), name
    for name in parrot_guard._DRIVER_ACTIONS:
        assert getattr(getattr(AltDriver, name), "_parrot_guarded", False), name
    for name in ("move_touch", "end_touch"):
        assert not getattr(getattr(AltDriver, name), "_parrot_guarded", False), name


# ----------------------------------------------------------------- frogger
@pytest.mark.parametrize("raw, key", [("summer.", "summer"), ("Town,", "town"),
                                      ("“Hello,”", "hello"), ("zoo", "zoo")])
def test_frog_key_ignores_punctuation_and_case(raw, key):
    assert A._frog_key(raw) == key


class FrogDriver:
    """Sentence bar + backpack of a Frogger board."""

    def __init__(self, bar, bag=()):
        self.bar = [Obj("DummyText(Clone)", t, x=100 * i, y=1321) for i, t in enumerate(bar)]
        self.bag = list(bag)

    def find_objects(self, by, name):
        if name == "DummyText(Clone)":
            return list(self.bar)
        if name == "DummyText(Clone)(Clone)":
            return [Obj(name, w) for w in self.bag]
        return []

    def find_objects_which_contain(self, by, text):
        return [o for o in self.bar if text in o.get_text()]

    def find_object(self, by, name):
        i = int(name.replace("PlaceHolder", "")) if name.startswith("PlaceHolder") else -1
        if not 0 <= i < len(self.bag):
            raise LookupError(name)
        slot, drv = Obj(name), self
        slot.find_object_from_object = lambda b, n: Obj(n, drv.bag[i])
        slot.click = lambda: drv.bag.pop(i)
        return slot


def test_frogger_takes_the_word_at_each_blank_position():
    # blanks = Sandra, shoes, the SECOND pink — the first pink is not a blank
    sentence = "Sandra is wearing pink shoes, and a pink hat."
    bar = ["_____", "is", "wearing", "pink", "_____,", "and", "a", "_____", "hat."]
    assert A._frogger_blank_words(FrogDriver(bar), sentence) == ["sandra", "shoes", "pink"]


def test_frogger_blank_is_empty_until_its_child_holds_a_word():
    bar = ["_____", "and", "_____", "_____."]
    assert A._frogger_has_empty_blank(FrogDriver(bar, bag=["lions", "live"]))
    assert not A._frogger_has_empty_blank(FrogDriver(bar, bag=["lions", "live", "zoo"]))


def test_frogger_fixes_a_wrong_backpack_from_the_end(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    drv = FrogDriver([], bag=["sandra", "pink"])
    left = A._frogger_fix_bag(drv, ["sandra", "shoes", "pink"])
    assert drv.bag == ["sandra"] and left == ["shoes", "pink"]


# ------------------------------------------------------------ guest wizard
def test_guest_gender_is_understood_as_printed_on_4_6_0():
    assert U._option_labels("Male") == ("Male", "Boy")
    assert U._option_labels("female") == ("Female", "Girl")
    assert U._option_labels("Hebrew") == ("Hebrew",)
    # "male" must never match "female"
    assert U._norm_label("Female") not in {U._norm_label(w) for w in U._option_labels("Male")}


def test_avatar_scene_accepts_the_renamed_scene():
    assert "Avatar3DBuilderScene" in U.AVATAR_SCENE and "AvatarBuilderScene" in U.AVATAR_SCENE
