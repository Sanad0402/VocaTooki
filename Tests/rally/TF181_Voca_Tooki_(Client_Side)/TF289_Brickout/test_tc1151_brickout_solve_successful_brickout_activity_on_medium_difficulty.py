"""
TC1151 — Brickout - Solve successful Brickout activity on Medium difficulty

Auto-generated from Rally (Method = Automated).

Description:
    Test Case: Solve Successful Brickout Activity on Medium Difficulty Type: Functional Priority: Important Component: Brickout Activity Test Account: Username: vt233624 / Password: 3690 Level: 43 Preconditions: - User is logged in with account vt233624 - User has access to level 43 - Brickout activity is available at the configured level - Activity difficulty is set to Medium

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Log in to Voca Tooki with username: vt233624 / password: 3690 2. Navigate to level 43 3. Open the Brickout activity 4. Verify the difficulty is set to Medium 5. Start the Brickout activity 6. Control the paddle to bounce the ball and break all the bricks 7. Complete the activity by breaking all bricks without losing all lives 8. Observe the completion/result screen
    Expected: - Brickout activity loads correctly on Medium difficulty - Ball and paddle controls respond properly - Bricks are destroyed on contact with the ball - Activity completes successfully when all bricks are broken - Score/stars are awarded correctly upon completion - Success screen is displayed with correct feedback - Progress is saved and the activity is marked as completed
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1151"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

ACTIVITY_SCENE = "BRICKOUT"
# Label printed on the activity's thumb in the level (not confirmed live — utilsdemo matches its known aliases). The test
# clicks that thumb directly instead of opening activities until it finds the
# right one.
ACTIVITY_TITLE = ""
MAP_LEVEL = 43          # from the Rally description
USERNAME = "vt233624"
PASSWORD = "3690"


def test_tc1151_brickout_solve_successful_brickout_activity_on_medium_difficulty(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description. When several
    #    cases run in one session with the same user, the login is skipped and
    #    the test continues from the map the previous case returned to.
    utilsdemo.ensure_logged_in(driver, USERNAME, PASSWORD)
    time.sleep(2)

    # 2. Open the map level named in the description (navigates to the map first)
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL), \
        f"{TC_ID}: could not open level {MAP_LEVEL} on the map"

    # 3. Get into the level's activity selection (handles intro/vending flow)
    assert utilsdemo.open_level_to_activities(driver), \
        f"{TC_ID}: activity selection screen was not reached"

    # 4. Find the BRICKOUT activity in this level and play it to completion.
    #    The thumb is chosen by its printed title (ACTIVITY_TITLE), so the test
    #    never plays a different activity by mistake.
    #    On any failed assert below the test stays on the failing screen, so
    #    the failure screenshot (conftest hook) shows the actual state.
    result = utilsdemo.solve_activity_in_level(driver, ACTIVITY_SCENE,
                                               title_hint=ACTIVITY_TITLE)
    assert result["found"], \
        f"{TC_ID}: BRICKOUT activity was not found in level {MAP_LEVEL}"
    assert result["total"] > 0 and result["done"] >= result["total"], (
        f"{TC_ID}: BRICKOUT did not complete — progress "
        f"{result['done']}/{result['total']}. Expected: - Brickout activity loads correctly on Medium difficulty - Ball and paddle controls respond properly - Bricks are destroyed on contact with the ball - Activity completes successfully when all bricks are broken - Score/stars are awarded correctly upon completion - Success screen is displayed with correct feedback - Progress is saved and the activity is marked as completed")
    assert result["feedback"], \
        f"{TC_ID}: BRICKOUT reached {result['done']}/{result['total']} but the final feedback screen never appeared"

    # 5. Clean state for the next test case: back to the level map (no logout —
    #    the next case in this run reuses the session and just clicks its level)
    utilsdemo.return_to_map(driver)
