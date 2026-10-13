"""Offline pins: every activity PLAY files its frames in its own folder, and its
report row names that folder and the level really played (user, 2026-10-12:
the medium and hard rows showed the easy level's screenshots).

Run:  python -m pytest Tests/unit/test_activity_frames.py --noconftest -q
"""

import json
import logging
import os

import pytest

logging.disable(logging.WARNING)

from runner import screenshots  # noqa: E402
from vocatooki import activity_runner as ar  # noqa: E402


def test_each_play_gets_its_own_key():
    with ar.level_context(5, "hard"):
        a = ar.play_key("PUZZLES")
        b = ar.play_key("PUZZLES")
    assert a != b
    assert a.startswith("PUZZLES-hard-L5-") and b.startswith("PUZZLES-hard-L5-")


def test_the_key_and_row_follow_the_level_being_played():
    keys = {}
    for level in ("easy", "medium", "hard"):
        with ar.level_context(3, level):
            keys[level] = ar.play_key("RADAR")
            fields = ar.play_fields(keys[level])
        assert fields["difficulty"] == level.title()
        assert fields["shots_run"] == screenshots.evidence_run_id(keys[level])
    assert len({screenshots.evidence_run_id(k) for k in keys.values()}) == 3   # three folders


def test_outside_a_level_nothing_is_claimed():
    key = ar.play_key("RADAR")
    assert key.startswith("RADAR-") and "-L" not in key
    assert "difficulty" not in ar.play_fields(key)       # the report keeps its old fallback


def test_the_context_is_restored_after_a_level_even_on_error():
    with pytest.raises(RuntimeError):
        with ar.level_context(1, "easy"):
            raise RuntimeError("solver blew up")
    assert ar._LEVEL == {"lesson": None, "level": ""}


def test_report_label_uses_the_real_level(monkeypatch):
    """A hard-only run used to label an activity's first play [Easy]."""
    import io
    monkeypatch.setattr(ar, "activity_report", [
        {"activity": "PUZZLES", "status": "PASSED", "error": "", "duration": "1s",
         "platform": "x", "difficulty": "Hard"},
    ])
    out = io.StringIO()
    ar.write_activity_report(out)
    assert "PUZZLES[Hard]" in out.getvalue() and "[Easy]" not in out.getvalue()


def _folder(root, run_id, stamp):
    d = root / run_id
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"run_id": run_id, "label": run_id,
                                             "kind": "test", "stamp": stamp}))
    (d / "evidence-1-start.png").write_bytes(b"png")
    return d


def test_pruning_keeps_whole_runs_not_a_folder_count(tmp_path, monkeypatch):
    monkeypatch.setattr(screenshots, "SHOTS_DIR", tmp_path)
    old = _folder(tmp_path, "radar-old", "20261001-100000")
    os.utime(old, (1, 1))
    os.utime(old / "evidence-1-start.png", (1, 1))
    # One newer run with more folders than the keep limit.
    new = [_folder(tmp_path, f"play-{i:03d}-new", "20261012-182226") for i in range(5)]
    screenshots.prune_old_runs(keep=1)
    assert all(d.exists() for d in new)                  # the run that just finished is whole
    assert not old.exists()
