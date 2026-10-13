"""Offline pins for reconnecting after AltTester drops the driver mid-run
(vocatooki/alt_connection.py, the panel's lesson loop in runner/core.py).

Run:  python -m pytest Tests/unit/test_reconnect.py --noconftest -q
"""

import logging
from collections import deque

import pytest
from alttester import exceptions as alt_exc

logging.disable(logging.WARNING)

from runner import core  # noqa: E402
from runner.modes import MODES  # noqa: E402
from Utilities import utilsdemo  # noqa: E402
from vocatooki import alt_connection  # noqa: E402


class FakeConnection:
    """The bits of alttester's WebsocketConnection that a reconnect touches."""

    def __init__(self, fail_connects=0):
        self._is_open = True
        self._close_message = None
        self._errors = deque()
        self._driver_registered_called = True
        self.fail_connects = fail_connects
        self.connects = 0

    def drop(self):
        """What the server's close does: closed, with a close message left behind."""
        self._is_open = False
        self._close_message = (1006, "gone")
        self._driver_registered_called = False

    def close(self):
        self._is_open = False

    def connect(self):
        assert self._close_message is None, "a stale close message makes connect() fail at once"
        self.connects += 1
        if self.fail_connects:
            self.fail_connects -= 1
            raise alt_exc.ConnectionTimeoutError("server not back yet")
        self._is_open = True


class FakeDriver:
    platform = "WindowsEditor"

    def __init__(self, conn):
        self._connection = conn

    def get_current_scene(self):
        if not self._connection._is_open:
            raise alt_exc.ConnectionError("Connection closed. An unexpected error ocurred.")
        return "MainMap"

    def stop(self):
        self._connection.close()


# ------------------------------------------------------------- alt_connection

def test_alive_follows_the_connection():
    conn = FakeConnection()
    driver = FakeDriver(conn)
    assert alt_connection.alive(driver)
    conn.drop()
    assert not alt_connection.alive(driver)


def test_alive_is_not_fooled_by_an_ordinary_error():
    class Busy(FakeDriver):
        def get_current_scene(self):
            raise alt_exc.WaitTimeOutException("slow scene")
    assert alt_connection.alive(Busy(FakeConnection()))


def test_revive_reconnects_the_same_driver_after_failed_attempts():
    conn = FakeConnection(fail_connects=2)
    driver = FakeDriver(conn)
    conn.drop()
    waited = []
    assert alt_connection.revive(driver, sleep=waited.append, log=lambda m: None)
    assert conn.connects == 3 and alt_connection.alive(driver)
    assert waited == list(alt_connection.RECONNECT_WAITS[:3])


def test_revive_gives_up_after_every_wait():
    conn = FakeConnection(fail_connects=99)
    conn.drop()
    assert not alt_connection.revive(FakeDriver(conn), sleep=lambda s: None, log=lambda m: None)
    assert conn.connects == len(alt_connection.RECONNECT_WAITS)


def test_revive_stops_when_the_run_is_stopped():
    conn = FakeConnection(fail_connects=99)
    conn.drop()
    assert not alt_connection.revive(FakeDriver(conn), sleep=lambda s: None,
                                     stopped=lambda: True, log=lambda m: None)
    assert conn.connects == 0


# ------------------------------------------------------- the panel lesson loop

@pytest.fixture
def panel(monkeypatch, tmp_path):
    """A RunManager whose app side is fake; lesson 2 loses the connection once."""
    monkeypatch.setattr(core.RunManager, "RUN_LOG_DIR", str(tmp_path / "run_logs"))
    conn = FakeConnection()
    driver = FakeDriver(conn)
    rm = core.RunManager()
    calls = {"lessons": [], "back_to_map": 0, "drop_on": {2}, "reconnect_fails": False}

    def run_lesson(mp, drv, cid, lesson):
        calls["lessons"].append(lesson)
        assert drv is driver                     # the same driver object throughout
        if lesson in calls["drop_on"]:
            calls["drop_on"].discard(lesson)
            conn.drop()
            if calls["reconnect_fails"]:
                conn.fail_connects = 99
            utilsdemo.activity_report.append({"activity": f"L{lesson}", "status": "FAILED",
                                              "error": "Connection closed"})
            return
        utilsdemo.activity_report.append({"activity": f"L{lesson}", "status": "PASSED"})

    monkeypatch.setitem(MODES, "fake", {"label": "", "description": "", "run": run_lesson})
    for name, fake in {
        "_preflight": lambda *a, **k: True,
        "_connect": lambda *a, **k: driver,
        "_login_and_open_map": lambda *a, **k: None,
        "_build_reports": lambda *a, **k: None,
        "_record_run_history": lambda *a, **k: None,
        "_shoot": lambda *a, **k: None,
        "_capture_screenshot": lambda *a, **k: "",
        "_framework_stamp": lambda *a, **k: "test",
        "_sleep": lambda *a, **k: None,
    }.items():
        monkeypatch.setattr(rm, name, fake)

    def back(*a, **k):
        calls["back_to_map"] += 1
        return True
    monkeypatch.setattr(rm, "_back_to_lessons", back)

    cfg = {"users": [{"username": "u", "password": "p", "class_id": "1"}],
           "lesson_from": 1, "lesson_to": 3, "mode": "fake", "shots_enabled": False}
    return rm, cfg, calls, conn


def test_a_dropped_lesson_is_replayed_on_the_reconnected_driver(panel):
    rm, cfg, calls, conn = panel
    rm._run(cfg)
    assert calls["lessons"] == [1, 2, 2, 3]
    assert calls["back_to_map"] == 1
    # The rows written on the dead connection are gone; the replay's row stands.
    assert [(r["activity"], r["status"]) for r in utilsdemo.activity_report] == [
        ("L1", "PASSED"), ("L2", "PASSED"), ("L3", "PASSED")]
    assert rm.state == "done"


def test_a_lesson_is_replayed_once_only(panel):
    rm, cfg, calls, conn = panel
    original = MODES["fake"]["run"]

    def always_drop_lesson_2(mp, drv, cid, lesson):
        if lesson == 2:
            calls["drop_on"].add(2)
        original(mp, drv, cid, lesson)
    MODES["fake"] = dict(MODES["fake"], run=always_drop_lesson_2)
    rm._run(cfg)
    assert calls["lessons"] == [1, 2, 2, 3]
    statuses = [(r["activity"], r["status"]) for r in utilsdemo.activity_report]
    assert ("L2", "FAILED") in statuses and statuses[-1] == ("L3", "PASSED")


def test_reconnect_failing_stops_the_run_with_one_clear_row(panel):
    rm, cfg, calls, conn = panel
    calls["reconnect_fails"] = True
    rm._run(cfg)
    assert calls["lessons"] == [1, 2]                     # lesson 3 never ran on a dead driver
    last = utilsdemo.activity_report[-1]
    assert last["status"] == "FAILED" and "reconnect attempts" in last["error"]
    assert rm.state == "error"


def test_rows_written_after_stop_are_skipped_not_failed(panel, monkeypatch):
    """Stop cuts the connection on purpose; the activity in flight then fails
    with 'Connection closed' — that row is the Stop, not a result."""
    rm, cfg, calls, conn = panel
    original = MODES["fake"]["run"]

    def stop_during_lesson_2(mp, drv, cid, lesson):
        if lesson == 2:
            rm.state = "running"
            rm.stop()                                    # severs the driver like the panel's button
            utilsdemo.activity_report.append({"activity": "CROSSWORD2", "status": "FAILED",
                                              "error": "Connection closed. An unexpected error ocurred."})
            return
        original(mp, drv, cid, lesson)
    calls["drop_on"].clear()
    MODES["fake"] = dict(MODES["fake"], run=stop_during_lesson_2)
    built = []
    monkeypatch.setattr(rm, "_build_reports",
                        lambda platform: (rm._relabel_rows_after_stop(), built.append(1)))
    rm._run(cfg)
    rows = [(r["activity"], r["status"]) for r in utilsdemo.activity_report]
    assert rows == [("L1", "PASSED"), ("CROSSWORD2", "SKIPPED")]
    assert "stopped" in utilsdemo.activity_report[-1]["error"]
    assert calls["lessons"] == [1] and rm.state == "stopped" and built   # lesson 3 never ran


def test_close_reason_names_the_close_code():
    conn = FakeConnection()
    conn.drop()
    assert "close code 1006" in alt_connection.close_reason(FakeDriver(conn))
    conn._close_message = None
    conn._errors.append(OSError("connection reset"))
    assert "connection reset" in alt_connection.close_reason(FakeDriver(conn))


def test_revive_logs_why_before_clearing_it():
    conn = FakeConnection()
    conn.drop()
    lines = []
    alt_connection.revive(FakeDriver(conn), sleep=lambda s: None, log=lines.append)
    assert "close code 1006" in lines[0]


def test_every_run_leaves_a_log_file(panel):
    rm, cfg, calls, conn = panel
    rm._run(cfg)
    text = open(rm._log_path, encoding="utf-8").read()
    assert "lesson 2" in text and "[RECONNECT]" in text and "close code 1006" in text


def test_the_status_dot_does_not_probe_altTester_during_a_run(monkeypatch):
    import run_panel
    probes = []
    monkeypatch.setattr(run_panel.manager, "_preflight", lambda *a, **k: probes.append(1) or True)
    client = run_panel.app.test_client()
    monkeypatch.setattr(run_panel.manager, "state", "running")
    assert client.get("/api/preflight?host=127.0.0.1&port=13000").get_json()["ok"] is True
    assert probes == []
    monkeypatch.setattr(run_panel.manager, "state", "idle")
    client.get("/api/preflight?host=127.0.0.1&port=13000")
    assert probes == [1]
