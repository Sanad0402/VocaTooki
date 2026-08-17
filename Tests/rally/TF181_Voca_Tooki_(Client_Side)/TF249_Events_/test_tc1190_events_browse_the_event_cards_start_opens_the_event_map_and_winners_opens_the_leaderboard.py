"""
TC1190 — Events - Browse the event cards, Start opens the event map and Winners opens the leaderboard

Auto-generated from Rally (Method = Automated).

Description:
    Test Type: Functional Priority: Important Severity: Major Username: vt233632 password : 6710 Player name: test events automation Objective: Verify the events screen itself: every event card can be brought to the front, a RUNNING event opens its event map from Start, and a FINISHED event opens its winners list from Winners. An event card carries exactly one of the two buttons: Start while the event is running, Winners once it has closed. A finished event with nobody on its board shows 'No Results' - that is a valid outcome, not a failure.

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Launch the app and log in with vt233632. Log out first so the run starts on a known account. 2. On the start screen, tap the Events button to open the events screen. 3. Note how many event cards are stacked on the screen. 4. Swipe vertically over the stack to bring the next card to the front, and repeat until every card has been at the front once. 5. For the card in front, check which button it carries: Start (the event is running) or Winners (the event has closed). 6. On a card with Start: tap it and verify the event map opens, then go back to the events screen. 7. On a card with Winners: tap it and verify the winners list opens over the events screen - either the list of winners or 'No Results' when nobody scored - then go back to the events screen. 8. Verify that every card was visited and that each one opened its own screen.
    Expected: - The events screen opens and shows the event cards stacked. - A vertical swipe brings the next card to the front; every card can be reached. - Each card carries exactly one of Start or Winners, never both. - Start opens that event's own event map (the level map). - Winners opens the winners list over the events screen; when the event has no winners it reads 'No Results'. - Going back from either returns to the events screen with the cards still browsable.

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
TC_ID = "TC1190"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "vt233632"
PASSWORD = "6710"
# The leaderboard lists players by NAME, never by username.
PLAYER_NAME = "test events automation"
# () = whatever the event has OPENED when the test runs.
EVENT_LEVELS = (1, 2, 3)
# Solve every activity in a level, or just one?
SOLVE_ALL_ACTIVITIES = False


def test_tc1190_events_browse_the_event_cards_start_opens_the_event_map_and_winners_opens_the_leaderboard(altdriver):
    driver, _platform = altdriver

    # Browse the event cards ONLY: bring each card to the front, and open what
    # it offers — Start must open that event's map, Winners must open its
    # winners list. Nothing is played here; this case is about the events
    # screen itself.
    result = utilsdemo.event_cards_check(
        driver, username=USERNAME, password=PASSWORD, tc_id=TC_ID)

    assert result["cards"], f"{TC_ID}: no event cards on the events screen — {result['note']}"
    assert not result["problems"], (
        f"{TC_ID}: browsing the event cards hit problems: {result['problems']}. "
        f"Visited: {result['visited']}")
    assert len(result["visited"]) == result["cards"], (
        f"{TC_ID}: only {len(result['visited'])} of {result['cards']} card(s) "
        f"could be opened — {result['visited']}")
    return

    # Log out and back in first, open the running event, solve one activity in
    # each level, then read the leaderboard. Never raises: the whole picture
    # comes back in the report so a failure says which level scored what.
    result = utilsdemo.event_score_check(
        driver, levels=EVENT_LEVELS, player_name=PLAYER_NAME,
        username=USERNAME, password=PASSWORD, solve_all=SOLVE_ALL_ACTIVITIES,
        tc_id=TC_ID)

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
