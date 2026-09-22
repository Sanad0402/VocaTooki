"""EvidenceTrail - the ordered picture walkthrough every test case leaves.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging

from vocatooki import ui_actions


# The most frames one test case may leave behind. The user set this (2026-08-17):
# enough to review a run without having watched it, few enough to actually look
# at. When a flow takes more, the LEAST important are dropped, never the ends.
EVIDENCE_MAX_PER_CASE = 7


# Lower = more important. KEY frames are never dropped.
EVIDENCE_KEY = 1        # the state the case is ABOUT: start, end, a failure


EVIDENCE_PROOF = 2      # proof a step really happened (progress moved)


EVIDENCE_STEP = 3       # useful context: a screen opened, a board played


class EvidenceTrail:
    """A numbered, BUDGETED walkthrough of a run, in pictures.

    **Use this in EVERY flow the framework tests, not just one.** The rule the
    user set (2026-08-17): someone who had no time to watch the execution must
    be able to review the whole case from the pictures afterwards — so a frame
    is taken at every step that MATTERS, in order, named for what it shows.

    At most ``EVIDENCE_MAX_PER_CASE`` survive. Take frames generously and say
    how important each one is; when the budget is exceeded the least important
    are deleted, and among equals the MIDDLE of a repeated kind goes first, so
    the first and last of anything are still there to compare. A KEY frame is
    never dropped.

    The number is part of the filename because the panel lists a run's frames
    by name: without it "missions-after-Reading" sorts above "Sentences-island"
    and the story is scrambled. Frames identical to an earlier one are dropped
    by ``runner.screenshots``, so instrumenting generously costs nothing.

    Usage in any flow helper::

        trail = EvidenceTrail(tc_id)
        trail.shot(driver, "missions-BEFORE", EVIDENCE_KEY)
        trail.shot(driver, f"{skill}-island")                    # EVIDENCE_STEP
        trail.shot(driver, f"missions-after-{skill}", EVIDENCE_PROOF)
        trail.shot(driver, "missions-FINAL", EVIDENCE_KEY)
        report["screenshots"] = trail.names
    """

    def __init__(self, tc_id="", limit=EVIDENCE_MAX_PER_CASE):
        self.tc_id = tc_id
        self.limit = max(1, int(limit))
        self.step = 0
        self._kept = []                              # [{path, priority, order}]

    @property
    def names(self):
        """The frames that SURVIVED, in the order they were taken."""
        return [k["path"].name for k in sorted(self._kept, key=lambda k: k["order"])]

    def shot(self, altdriver, label, priority=EVIDENCE_STEP):
        """Capture one step. Returns the file name, or ""."""
        self.step += 1
        path = None
        try:
            from runner import screenshots as _shots   # local: avoids a cycle
            path = _shots.evidence(altdriver, f"{self.step:02d}-{label}",
                                   tc_id=self.tc_id)
        except Exception as e:                       # noqa: BLE001
            logging.debug(f"[Shot] evidence unavailable: {e}")
        if path is None:
            self.step -= 1                           # nothing was written
            return ""
        # A duplicate frame comes back as the EARLIER file; it is already kept.
        if any(k["path"] == path for k in self._kept):
            self.step -= 1
            return path.name
        self._kept.append({"path": path, "priority": priority, "order": self.step})
        self._enforce_budget()
        return path.name

    def _enforce_budget(self):
        """Delete the least important frames until the budget is met."""
        while len(self._kept) > self.limit:
            worst = max(k["priority"] for k in self._kept
                        if k["priority"] != EVIDENCE_KEY)                 if any(k["priority"] != EVIDENCE_KEY for k in self._kept) else None
            if worst is None:
                return                               # all KEY: keep them all
            group = sorted((k for k in self._kept if k["priority"] == worst),
                           key=lambda k: k["order"])
            # The middle of a repeated kind goes first: the first and the last
            # are what a reader compares.
            victim = group[len(group) // 2]
            self._kept.remove(victim)
            try:
                victim["path"].unlink(missing_ok=True)
                logging.info(f"[Shot] budget {self.limit}: dropped "
                             f"{victim['path'].name}")
            except OSError:
                pass


# One trail per test case, so EVERY flow obeys the same budget — including the
# ones that call capture_evidence() directly instead of holding a trail.
_EVIDENCE_TRAILS = {}


def evidence_trail(tc_id=""):
    """The EvidenceTrail for this test case, created on first use.

    Shared so that a case which takes evidence from several helpers (the guest
    walk's gates, an event's levels) still lands inside ONE budget of
    ``EVIDENCE_MAX_PER_CASE`` — the cap is per TEST CASE, not per helper.
    """
    return _EVIDENCE_TRAILS.setdefault(str(tc_id or "run"), EvidenceTrail(tc_id))


def reset_evidence_trail(tc_id=""):
    """Start a fresh budget (a new run of the same case)."""
    _EVIDENCE_TRAILS.pop(str(tc_id or "run"), None)


def capture_evidence(altdriver, label, tc_id="", priority=None):
    """A screenshot kept on purpose, not as a failure artefact. Returns a name.

    Goes through this case's EvidenceTrail, so it is numbered in order, freed
    of duplicates, and counted against the per-case budget the user set: at
    most ``EVIDENCE_MAX_PER_CASE`` frames survive, and when a flow takes more
    the LEAST important are dropped rather than the newest or the oldest.
    """
    name = evidence_trail(tc_id).shot(altdriver, label,
                                      priority or EVIDENCE_PROOF)
    return name or ui_actions.capture_failure_screenshot(altdriver, label)
