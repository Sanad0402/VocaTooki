"""
TC1189 — Events - Solving ALL activities in 3 event levels matches the leaderboard score

Auto-generated from Rally (Method = Automated).

Description:
    Test Type: Functional Priority: Important Severity: Major Username: vt233634 password : 8019 Player name: test events 3 Objective: Verify that when EVERY activity of an event level is solved, the total score of those activities is the score shown for the player on the event leaderboard. In an event only ACTIVITY levels award score - exams award coins only and must not change the score. The leaderboard lists players by their NAME, not by username: vt233632 appears there as 'test events automation'.

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Launch the app and log in with vt233632. Log out first so the run starts on a known account. 2. On the start screen, tap the Events button to open the events screen. 3. On the event selection screen, tap Start on the active event card to open the event map. 4. Open event level 1 and solve EVERY activity it offers, returning to the level's activity list after each one. 5. On the activity list read every activity's score (earned/max, e.g. 80/240) and note the level total. 6. Return to the event map and repeat steps 4 and 5 for event level 2. 7. Return to the event map and repeat steps 4 and 5 for event level 3. 8. Back on the event map, tap the leaderboard (cup) button at the top right. The leaderboard opens over the event map. 9. Read the player's row on the leaderboard. The leaderboard identifies players by FIRST NAME, not by username. 10. Verify that the score on the player's row equals the sum of the three level totals. 11. Tap Back to close the leaderboard. It returns to the event cards view, not to the event map.
    Expected: - The events screen opens and the active event starts on its own event map. - Each of the 3 event levels opens and EVERY activity in it is completed successfully. - Every completed activity shows a score on the activity list (earned out of the maximum). - The leaderboard opens over the event map and lists the player by FIRST NAME. - The score on that row equals the SUM of the three level totals. - Exams award coins only and do not change the leaderboard score. - The score is cumulative: a level solved on an earlier run still counts towards the leaderboard total. - Back from the leaderboard returns to the event cards view.

Event flow, surveyed on the live app (2026-08-16):
    GO-Events -> EventSelectionScene -> StartButton -> EventScene (the map)
    level icon "LessonLevelIcon Variant(Clone) N" -> the level's activity list
    each activity shows its score there as "earned/max" (e.g. "80/240")
    LeaderboardButton opens the leaderboard AS AN OVERLAY on the event map
    a leaderboard row is a PlayerName next to a Score
Only ACTIVITY levels award event score; exams award coins and must not change it.
"""

import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1189"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "vt233634"
PASSWORD = "8019"
# The leaderboard lists players by NAME, never by username.
PLAYER_NAME = "test events 3"
# () = whatever the event has OPENED when the test runs.
EVENT_LEVELS = (1, 2, 3)
# Solve every activity in a level, or just one?
SOLVE_ALL_ACTIVITIES = True


def test_tc1189_events_solving_all_activities_in_3_event_levels_matches_the_leaderboard_score(altdriver):
    driver, _platform = altdriver

    # Log out and back in first, open the running event, solve one activity in
    # each level, then read the leaderboard. Never raises: the whole picture
    # comes back in the report so a failure says which level scored what.
    result = utilsdemo.event_score_check(
        driver, levels=EVENT_LEVELS, player_name=PLAYER_NAME,
        username=USERNAME, password=PASSWORD, solve_all=SOLVE_ALL_ACTIVITIES)

    # With no levels named the test plays what the event opened, so the report
    # says which ones those were.
    played_levels = result.get("levels_played") or list(EVENT_LEVELS)
    assert played_levels, f"{TC_ID}: the event had no open levels to play — {result['note']}"

    # Every level had to open and be played, or the sum below means nothing.
    for level in played_levels:
        detail = result["levels"].get(level, {})
        assert detail.get("opened"), (
            f"{TC_ID}: event level {level} did not open — {detail.get('note') or result['note']}")
        assert detail.get("played"), (
            f"{TC_ID}: nothing was completed in event level {level} — {result['note']}")
        assert detail.get("score"), (
            f"{TC_ID}: event level {level} awarded no score for "
            f"'{detail.get('played')}' — an activity level must award score")

    # The player has to BE on the leaderboard before its score can be compared.
    assert result["leaderboard"] is not None, (
        f"{TC_ID}: {PLAYER_NAME!r} is not on the event leaderboard — {result['note']}")

    # The point of the case: what the activities scored is what the leaderboard
    # shows. Exams award coins only, so nothing else may move this number.
    assert result["ok"], (
        f"{TC_ID}: the leaderboard shows {result['leaderboard']} for {PLAYER_NAME!r} "
        f"but the activities scored {result['earned']} "
        f"({ {lvl: d.get('score') for lvl, d in result['levels'].items()} }). "
        f"{result['note']}")
