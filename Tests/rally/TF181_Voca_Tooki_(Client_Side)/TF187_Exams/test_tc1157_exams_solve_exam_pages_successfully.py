"""
TC1157 — Exams- Solve exam pages successfully

Auto-generated from Rally (Method = Automated).

Description:
    Test Type: Functional Priority: Normal Feature: exam Level: 40 (Exam) Preconditions: - User is logged in with username: vt233624 - Password: 3690

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Login with username: vt233624, password: 3690 2. Open the Tetris game 3. Progress to level 40 4. Start the exam pages 5. Complete all exam pages
    Expected: User is able to complete all exam pages at level 40 successfully without errors or crashes
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1157"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

MAP_LEVEL = 40          # the exam node, from the Rally description
USERNAME = "vt233624"
PASSWORD = "3690"


def test_tc1157_exams_solve_exam_pages_successfully(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description (skipped when a
    #    previous case in this run already logged this user in).
    utilsdemo.ensure_logged_in(driver, USERNAME, PASSWORD)
    time.sleep(2)

    # 2. Open the exam level named in the description. An exam sits on the map
    #    like any other level, so this is the same self-recovering navigation as
    #    an activity: back out to the map from wherever the app is, re-login if
    #    the session dropped, then click the level.
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL,
                                        username=USERNAME, password=PASSWORD), \
        f"{TC_ID}: could not open level {MAP_LEVEL} on the map"

    # 3. Get past the intro to the exam pages themselves
    assert utilsdemo.open_exam(driver), \
        f"{TC_ID}: the exam did not open at level {MAP_LEVEL}"

    # 4. Solve every page (type is detected per page) and submit. On a failed
    #    assert the test stays on the failing screen, so the failure screenshot
    #    (conftest hook) shows the actual state.
    result = utilsdemo.solve_exam_pages(driver, label=f"{TC_ID} level {MAP_LEVEL}")
    # Exams are not always 3 pages — check every page the exam actually has.
    assert result["total"] and result["parts"] == result["total"], (
        f"{TC_ID}: answered {result['parts']}/{result['total']} exam pages. "
        f"Expected: User is able to complete all exam pages at level 40 successfully without errors or crashes")
    assert not result["problems"], (
        f"{TC_ID}: exam pages failed — " + " | ".join(result["problems"]))
    assert result["submitted"], \
        f"{TC_ID}: the exam was solved but never submitted/collected"

    # 5. Clean state for the next test case: back to the level map
    utilsdemo.return_to_map(driver)
