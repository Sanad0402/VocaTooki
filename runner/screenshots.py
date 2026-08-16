"""Capped run screenshots: a few useful frames per run, never a flood.

Every run gets its own folder under ``reports/screenshots/<run_id>/`` and a
BUDGET: 5 frames for a mode run, 3 for a single test case. ``Shooter.shoot()``
becomes a no-op once the budget is spent, so a long run (a mode over 40 lessons)
cannot fill the disk, and the caller never has to count.

The failure screenshot the conftest hook takes is deliberately NOT budgeted —
call ``shoot(..., mandatory=True)`` for it. A spent budget suppressing the one
frame that shows why a test failed would be exactly backwards.

Usage:
    shooter = Shooter.for_test("TC1160")           # budget 3
    shooter.shoot(driver, "after-entry")
    ...
    shooter.shoot(driver, "failure", mandatory=True)

    Shooter.for_mode("express_hard")               # budget 5
    delete_screenshots()                           # all runs
    delete_screenshots("TC1160-20260813-141530")   # one run
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
# MUST match runner.core.REPORTS_DIR (same expression, same default): the flat
# failure screenshots and these per-run folders live side by side, and the
# panel serves both out of one directory. The panel exports REPORTS_DIR into
# the pytest subprocess, so the child agrees with the parent.
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports")))
SHOTS_DIR = REPORTS_DIR / "screenshots"

TEST_BUDGET = 3      # frames per test-case run
MODE_BUDGET = 5      # frames per mode run
# Keep only the most recent runs so the folder cannot grow forever.
KEEP_RUNS = 40

# The panel decides per run WHICH cases may shoot (the dialog on Run), and the
# pytest subprocess learns it through the environment — there is no other
# channel into a child process that pytest itself does not own.
ENV_ENABLED = "RUN_SHOTS"        # "0" -> no milestone frames at all
ENV_CASES = "RUN_SHOT_CASES"     # comma-separated TC ids allowed to shoot
ENV_STAMP = "RUN_SHOT_STAMP"     # shared by every case of one panel run

# A bare `pytest` run (no panel) still gets its own grouping stamp.
_FALLBACK_STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")


def _slug(text, limit=40):
    """A file-name-safe fragment ('after entry!' -> 'after-entry')."""
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(text or "")).strip("-").lower()
    return (s[:limit] or "shot")


def run_stamp():
    """The stamp that groups every folder of one run."""
    return (os.environ.get(ENV_STAMP) or "").strip() or _FALLBACK_STAMP


def wants(tc_id):
    """Should this test case capture milestone frames?

    Unset environment = yes: someone running pytest by hand still gets the
    3 capped frames. The panel always sets it explicitly from the run dialog.
    """
    if os.environ.get(ENV_ENABLED, "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    picked = [p.strip().lower() for p in os.environ.get(ENV_CASES, "").split(",") if p.strip()]
    if not picked:
        return True
    return str(tc_id or "").strip().lower() in picked


class Shooter:
    """Takes up to ``budget`` screenshots for one run, then stops."""

    def __init__(self, run_id, budget, label="", kind="test", stamp=""):
        self.run_id = _slug(run_id, 80)
        self.budget = int(budget)
        self.label = str(label or run_id)
        self.kind = kind
        self.stamp = stamp
        self.taken = []
        self._n = 0

    @classmethod
    def for_test(cls, tc_id, stamp=None):
        stamp = _slug(stamp or run_stamp())
        return cls(f"{tc_id}-{stamp}", TEST_BUDGET, label=str(tc_id),
                   kind="test", stamp=stamp)

    @classmethod
    def for_mode(cls, mode_key, stamp=None):
        stamp = _slug(stamp or run_stamp())
        return cls(f"mode-{mode_key}-{stamp}", MODE_BUDGET, label=str(mode_key),
                   kind="mode", stamp=stamp)

    def _write_meta(self):
        """Record what this folder belongs to, so the panel maps folder -> case
        by reading it instead of guessing from the folder name."""
        try:
            (self.folder / "meta.json").write_text(json.dumps({
                "run_id": self.run_id, "label": self.label,
                "kind": self.kind, "stamp": self.stamp,
            }), encoding="utf-8")
        except OSError as e:
            logger.debug(f"[shots] could not write meta.json: {e}")

    @property
    def folder(self):
        return SHOTS_DIR / self.run_id

    @property
    def remaining(self):
        return max(0, self.budget - self._n)

    def shoot(self, driver, label="", mandatory=False):
        """Save one frame. Returns the Path, or None when skipped/failed.

        ``mandatory`` ignores the budget — for the failure frame, which must
        never be dropped because earlier milestones used the allowance up.
        """
        if driver is None:
            return None
        if not mandatory and self.remaining == 0:
            logger.debug(f"[shots] budget spent ({self.budget}); skipping '{label}'")
            return None

        self._n += 1
        path = self.folder / f"{self._n:02d}-{_slug(label)}.png"
        try:
            first = not path.parent.is_dir()
            path.parent.mkdir(parents=True, exist_ok=True)
            if first:
                self._write_meta()
            driver.get_png_screenshot(str(path))
        except Exception as e:                      # noqa: BLE001 - never fail a run
            logger.warning(f"[shots] could not capture '{label}': {e}")
            self._n -= 1
            return None
        self.taken.append(path)
        logger.info(f"[shots] {self.run_id}/{path.name}")
        return path


def evidence(driver, label, tc_id="", stamp=None):
    """Save a frame that must ALWAYS be kept, whatever the budget has spent.

    Some frames are the point of the run rather than a sample of it — the guest
    flow's two gates and the map behind them are looked at deliberately, to see
    which levels are locked. They land beside the budgeted frames of the same
    run, under a name of their own so they cannot collide with them.

    Returns the Path, or None; never raises.
    """
    if driver is None:
        return None
    run_id = _slug(f"{tc_id or 'run'}-{stamp or run_stamp()}", 80)
    path = SHOTS_DIR / run_id / f"evidence-{_slug(label)}.png"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not (path.parent / "meta.json").exists():
            (path.parent / "meta.json").write_text(json.dumps({
                "run_id": run_id, "label": str(tc_id or "run"),
                "kind": "test", "stamp": str(stamp or run_stamp()),
            }), encoding="utf-8")
        driver.get_png_screenshot(str(path))
        logger.info(f"[shots] evidence {run_id}/{path.name}")
        return path
    except Exception as e:                          # noqa: BLE001 - never fail a run
        logger.warning(f"[shots] could not capture evidence '{label}': {e}")
        return None


def list_runs():
    """[{run_id, label, kind, stamp, count, files, modified}], newest first.

    ``files`` are bare names inside the run folder — the panel builds its URLs
    from run_id + name, so no path ever crosses the wire.
    """
    if not SHOTS_DIR.is_dir():
        return []
    runs = []
    for folder in SHOTS_DIR.iterdir():
        if not folder.is_dir():
            continue
        shots = sorted(p.name for p in folder.glob("*.png"))
        if not shots:
            continue
        meta = {}
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        runs.append({
            "run_id": folder.name,
            "label": meta.get("label") or folder.name,
            "kind": meta.get("kind") or "test",
            "stamp": meta.get("stamp") or "",
            "count": len(shots),
            "files": shots,
            "modified": folder.stat().st_mtime,
        })
    return sorted(runs, key=lambda r: r["modified"], reverse=True)


def delete_screenshots(run_id=None):
    """Delete one run's screenshots, or all of them. Returns files removed.

    Only ever touches ``reports/screenshots``: the resolved target must stay
    inside it, so a crafted run_id ("../..") cannot delete anything else.
    """
    if not SHOTS_DIR.is_dir():
        return 0

    if run_id:
        target = (SHOTS_DIR / str(run_id)).resolve()
        if SHOTS_DIR.resolve() not in target.parents:
            logger.error(f"[shots] refusing to delete outside the shots folder: {run_id}")
            return 0
        targets = [target] if target.is_dir() else []
    else:
        targets = [p for p in SHOTS_DIR.iterdir() if p.is_dir()]

    removed, stuck = 0, []
    for folder in targets:
        before = len(list(folder.glob("*.png")))
        shutil.rmtree(folder, ignore_errors=True)
        if folder.exists():
            # A frame still being served holds a lock on Windows; a second pass
            # right after normally succeeds.
            shutil.rmtree(folder, ignore_errors=True)
        left = len(list(folder.glob("*.png"))) if folder.exists() else 0
        removed += before - left
        if left:
            stuck.append(folder.name)
    if stuck:
        # Report what actually happened — claiming a delete that did not happen
        # is worse than admitting the file is in use.
        logger.warning(f"[shots] still in use, not deleted: {', '.join(stuck)}")
    logger.info(f"[shots] deleted {removed} screenshot(s) from {len(targets)} run(s)")
    return removed


def resolve_file(run_id, name):
    """Absolute path of one frame, or None when it would escape the folder.

    ``run_id`` and ``name`` arrive from a URL: both must be bare names and the
    resolved file must sit directly inside ``reports/screenshots``.
    """
    run_id, name = str(run_id or ""), str(name or "")
    if not run_id or not name:
        return None
    if Path(run_id).name != run_id or Path(name).name != name:
        return None
    if not name.lower().endswith(".png"):
        return None
    path = (SHOTS_DIR / run_id / name).resolve()
    if SHOTS_DIR.resolve() not in path.parents or not path.is_file():
        return None
    return path


def prune_old_runs(keep=KEEP_RUNS):
    """Drop the oldest run folders beyond ``keep``. Returns runs removed."""
    runs = list_runs()
    stale = runs[keep:]
    for run in stale:
        shutil.rmtree(SHOTS_DIR / run["run_id"], ignore_errors=True)
    if stale:
        logger.info(f"[shots] pruned {len(stale)} old run folder(s)")
    return len(stale)
