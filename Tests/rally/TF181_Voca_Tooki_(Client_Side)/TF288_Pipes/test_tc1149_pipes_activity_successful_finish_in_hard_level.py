"""
TC1149 — Pipes Activity - Successful finish in Hard level

Auto-generated from Rally (Method = Automated).

Description:
    Test Type: Functional Priority: Important Feature: Pipes Activity Level: Hard Description: Verify that a user can successfully complete the Pipes activity when playing at Hard difficulty level. The activity should register as finished and award appropriate points/progress. Preconditions: - Username: vt233624 - Password: 3690 - Account is at level 44 - Pipes activity is available and unlocked

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Log in with username: vt233624, password: 3690 2. Navigate to the Pipes activity 3. Select Hard level 4. Complete all required steps of the activity 5. Submit/finish the activity
    Expected: The Pipes activity is marked as successfully finished at Hard level. The completion is registered, appropriate feedback/score is shown to the user, and progress/points are updated correctly.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1149"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

ACTIVITY_SCENE = "PIPES"
MAP_LEVEL = 44          # from the Rally description
USERNAME = "vt233624"
PASSWORD = "3690"


def test_tc1149_pipes_activity_successful_finish_in_hard_level(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description
    utilsdemo.login(driver, USERNAME, PASSWORD)
    time.sleep(8)   # let the home screen finish loading after login

    # 2. Open the map level named in the description (navigates to the map first)
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL), \
        f"{TC_ID}: could not open level {MAP_LEVEL} on the map"

    # 3. Get into the level's activity selection (handles intro/vending flow)
    assert utilsdemo.open_level_to_activities(driver), \
        f"{TC_ID}: activity selection screen was not reached"

    # 4. Find the PIPES activity in this level and play it to completion
    assert utilsdemo.solve_activity_in_level(driver, ACTIVITY_SCENE), \
        f"{TC_ID}: expected: The Pipes activity is marked as successfully finished at Hard level. The completion is registered, appropriate feedback/score is shown to the user, and progress/points are updated correctly."

    # 5. Leave the app in a clean state
    utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
    time.sleep(2)
