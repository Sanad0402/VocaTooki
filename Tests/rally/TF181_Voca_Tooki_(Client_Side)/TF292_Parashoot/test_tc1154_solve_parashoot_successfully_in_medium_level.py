"""
TC1154 — Solve Parashoot Successfully in Medium Level

Auto-generated from Rally (Method = Automated).

Description:
    Feature: Parashoot Test Type: Functional Priority: Medium Severity: Medium Description: Verify that a user can successfully solve/complete level 33 in Parashoot. Preconditions: - Username: vt233624 - Password: 3690 - User must be logged in and have access to Parashoot - User must have reached level 33

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Log in with username: vt233624 and password: 3690 2. Navigate to the Parashoot game 3. Open/select level 33 (Medium level) 4. Play through the level 5. Complete the level successfully
    Expected: User successfully completes level 33 in Parashoot. Level is marked as solved/completed. Score and progress are saved correctly.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1154"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

ACTIVITY_SCENE = "PARASHOOT"
# Label printed on the activity's thumb in the level (not confirmed live — utilsdemo matches its known aliases). The test
# clicks that thumb directly instead of opening activities until it finds the
# right one.
ACTIVITY_TITLE = ""
MAP_LEVEL = 33          # from the Rally description
USERNAME = "vt233624"
PASSWORD = "3690"


def test_tc1154_solve_parashoot_successfully_in_medium_level(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description. When several
    #    cases run in one session with the same user, the login is skipped and
    #    the test continues from the map the previous case returned to.
    utilsdemo.ensure_logged_in(driver, USERNAME, PASSWORD)
    time.sleep(2)

    # 2. Open the map level named in the description. Self-recovering: whatever
    #    screen the app is on, it backs out to the map (and logs in again if the
    #    session dropped) before clicking the level.
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL,
                                        username=USERNAME, password=PASSWORD), \
        f"{TC_ID}: could not open level {MAP_LEVEL} on the map"

    # 3. Get into the level's activity selection (handles intro/vending flow)
    assert utilsdemo.open_level_to_activities(driver), \
        f"{TC_ID}: activity selection screen was not reached"

    # 4. Find the PARASHOOT activity in this level and play it to completion.
    #    The thumb is chosen by its printed title (ACTIVITY_TITLE), so the test
    #    never plays a different activity by mistake.
    #    On any failed assert below the test stays on the failing screen, so
    #    the failure screenshot (conftest hook) shows the actual state.
    result = utilsdemo.solve_activity_in_level(driver, ACTIVITY_SCENE,
                                               title_hint=ACTIVITY_TITLE)
    assert result["found"], \
        f"{TC_ID}: PARASHOOT activity was not found in level {MAP_LEVEL}"
    assert result["total"] > 0 and result["done"] >= result["total"], (
        f"{TC_ID}: PARASHOOT did not complete — progress "
        f"{result['done']}/{result['total']}. Expected: User successfully completes level 33 in Parashoot. Level is marked as solved/completed. Score and progress are saved correctly.")
    assert result["feedback"], \
        f"{TC_ID}: PARASHOOT reached {result['done']}/{result['total']} but the final feedback screen never appeared"

    # 5. Clean state for the next test case: back to the level map (no logout —
    #    the next case in this run reuses the session and just clicks its level)
    utilsdemo.return_to_map(driver)
