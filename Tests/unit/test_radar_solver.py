"""Offline pins for the RADAR solver, from the live hard-level bugs of 2026-10-13.

Run:  python -m pytest Tests/unit/test_radar_solver.py --noconftest -q
"""

import logging

import pytest

logging.disable(logging.WARNING)

from vocatooki.solvers import radar as R  # noqa: E402


class Gone(Exception):
    """What AltTester raises for a destroyed RadarObjectController."""


class Blip:
    """A radarObj: `taken` = the game destroyed its controller (right answer)."""

    def __init__(self, word, hidden=True, takes_on_tap=1):
        self.name, self.word, self.hidden = "radarObj", word, hidden
        self.taps, self.taken_after, self.taken = 0, takes_on_tap, False
        self.x, self.y = 100.0, 200.0

    def get_component_property(self, comp, field, asm):
        if self.taken:
            raise Gone("ComponentNotFoundException")
        return {"word": self.word, "hidden": self.hidden, "selected": self.taps > 0}[field]

    def get_parent(self):
        raise Gone("no parent in the fake")          # no bush: the blip itself is tapped

    def update_object(self):
        return self


class Board:
    def __init__(self, blips, events):
        self.blips, self.events = blips, events

    def tap(self, point):
        blip = self.current
        blip.taps += 1
        self.events.append(("tap", blip.word, id(blip)))
        if blip.taps >= blip.taken_after:
            blip.taken = True
            self.events.append(("taken", blip.word, id(blip)))


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R, "_TAKE_TIMEOUT", 0.05)


def _press_all(blips, word):
    events = []
    board = Board(blips, events)

    def tap(altdriver, obj):
        board.current = obj
        board.tap((obj.x, obj.y))
    R._tap, orig = tap, R._tap
    try:
        results = [R.press_blip(board, b, word=word) for b in blips]
    finally:
        R._tap = orig
    return results, events


def test_the_pair_is_pressed_one_at_a_time():
    """Both lowered blips tapped at once soft-locks the game; the second tap
    must come only after the first blip was TAKEN."""
    a, b = Blip("boot"), Blip("boot")
    results, events = _press_all([a, b], "boot")
    assert results == [True, True]
    assert [e[0] for e in events] == ["tap", "taken", "tap", "taken"]


def test_a_blip_popping_up_by_itself_is_not_a_success():
    """On hard blips pop up on their own; hidden=False must not count."""
    blip = Blip("zoo", hidden=False, takes_on_tap=99)    # never taken
    results, events = _press_all([blip], "zoo")
    assert results == [False]
    assert blip.taps == R._PRESS_ATTEMPTS                # retried, then reported


def test_a_missed_tap_is_retried():
    blip = Blip("shoe", takes_on_tap=2)
    results, _ = _press_all([blip], "shoe")
    assert results == [True] and blip.taps == 2


def test_reading_the_board_skips_taken_blips_instead_of_crashing():
    taken = Blip("boot")
    taken.taken = True
    alive = Blip("town")

    class D:
        def find_objects(self, by, name):
            return [taken, alive]
    assert [w for _, w in R._read_blips(D())] == ["town"]
