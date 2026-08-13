"""
TC1187 — Guest - test guest guestTr - Turkish - Advanced Proficiency

Auto-generated from Rally (Method = Automated).

Description:
    Guest Flow Test — Turkish / Advanced Proficiency Verifies that a guest user can complete the registration flow, enter the map, access activities, solve the first exam, and that levels greater than 5 are locked in guest mode. Language: Turkish Difficulty: Advanced Proficiency Avatar Gender: Female Test Type: Functional | Priority: High | Severity: Major

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Launch the app and tap Start Free Trial button. 2. Tap Let's Start button. 3. Enter test guest in the First Name field. 4. Enter guestTr in the Last Name field. 5. In the 'Choose Your Native Language' screen, select Turkish. 6. Tap Next. 7. On the difficulty selection screen, select Advanced Proficiency. 8. Wait for the 'You Are' (gender) screen to appear, then select Female. 9. On the avatar customization screen, tap the Back button. 10. Tap anywhere on screen to dismiss the parrot. 11. Enter the map. 12. ℹ️ Activities were already solved in the Beginning Literacy test for Turkish. Verify levels load correctly. 13. Navigate to the first exam on the map and complete it. 14. After the exam, tap on any level greater than 5 — verify it is locked (guest restriction). 15. Perform Clear Data to reset app state for the next test.
    Expected: - Guest registration completes successfully with correct name and language. - Difficulty 'Advanced Proficiency' is correctly applied. - Avatar gender 'Female' is selected and displayed correctly. - Map loads; levels 1–5 are accessible. - Activities launch and run correctly inside map levels. - First exam is accessible and completable. - Levels greater than 5 display a lock icon and cannot be entered (guest restriction enforced). - Clear Data resets app to the login/start screen.

Guest flow — this test NEVER logs in.

Route walked on the live app (2026-08-13) and encoded in utilsdemo.GUEST_ENTRY:
    log out (LogoutButton -> YesButton)  ->  "Free Trial"  ->  "Let's Start"
    ->  child's name  ->  gender toggles  ->  native language  ->  English level
    ->  GenderSelectPopup(Clone) on the hub  ->  GO-Map
The app asks these in a different ORDER from the Rally steps, so the option
labels below are matched per screen rather than in sequence.

Parsed from Rally Validation Input. Steps this generator could not
derive from prose are listed as TODO in the body.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1187"
# Regenerated from the Rally case on every sync so the guest details stay current
# with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

# The child this case registers. No USERNAME/PASSWORD: a guest has no account.
# LAST_NAME is derived from the two choices below — "guest" + the language's
# first two letters + the difficulty's initials — so the registered guest can be
# identified afterwards by what it selected (Rally said "guestTr").
FIRST_NAME = "test guest"
LAST_NAME = "guestTuAP"
# What this case picks on the onboarding option screens, in any order.
OPTIONS = ["Turkish", "Advanced Proficiency", "Female"]
# Rally: "tap on any level greater than 5 — verify it is locked". A guest's
# accessible band is levels 1-4 on the live map; 5 is the exam (locked too, so
# this case does not attempt it) and everything above it is locked.
GUEST_LOCKED_LEVEL = 6
# What the app must say when that level is pressed:
#   "You've completed all free levels. Please subscribe to open more levels."
# Kept as fragments so a typographic apostrophe or a re-wrap does not fail the
# case, while a missing or different gate does.
LOCKED_MESSAGE_FRAGMENTS = ["completed all free levels", "subscribe"]


def test_tc1187_guest_test_guest_guesttr_turkish_advanced_proficiency(altdriver):
    driver, _platform = altdriver

    # 1. Register as a guest. Logs the current user out first — the trial entry
    #    only EXISTS while nobody is logged in — and never types credentials.
    result = utilsdemo.enter_guest_mode(driver, FIRST_NAME, LAST_NAME,
                                        options=OPTIONS)
    assert result["ok"], (
        f"{TC_ID}: guest onboarding failed at '{result['failed_at']}' — "
        f"{result['note']}. Got as far as: {result['trace']}. "
        f"Expected: - Guest registration completes successfully with correct name and language. - Difficulty 'Advanced Proficiency' is correctly applied. - Avatar gender 'Female' is selected and displayed correctly. - Ma...")

    # 2. Prove we are really inside the app. The login overlay sits ON the start
    #    screen with the hub live behind it, so a findable GO-Map is not evidence.
    state = utilsdemo.app_state(driver)
    assert utilsdemo.in_app(driver), \
        f"{TC_ID}: onboarding ended on the {state} screen, not in the app"

    # 3. Enter the map (Rally: "Enter the map").
    assert utilsdemo.press_object(driver, "GO-Map", settle=12.0), \
        f"{TC_ID}: GO-Map did not respond on the hub"
    assert utilsdemo.wait_for_scene(driver, utilsdemo.MAP_SCENE, timeout=60), \
        f"{TC_ID}: the map did not load for the guest"

    # 4. The guest's map: icons are there and an exam node exists. WHICH level
    #    carries the first exam moves with the language and level the guest
    #    picked (Turkish/Advanced does not have it at 5), so it is read off the
    #    live map instead of hardcoded.
    icons = utilsdemo._find_level_icons(driver)
    assert icons, f"{TC_ID}: no level icons on the guest's map"
    first_exam = utilsdemo.guest_first_exam_level(driver)
    assert first_exam, f"{TC_ID}: no exam node on the guest's map"

    # 5. Levels (1, 2, 3): open each one, open EVERY activity in it and
    #    prove it really starts, check the app never goes to an error state, and
    #    play one activity through to completion.
    walk = utilsdemo.guest_walk_levels(driver, levels=(1, 2, 3),
                                       complete_one=True)
    # Report the WALK's own problems first. A crash or an offline popup ends the
    # walk where it stands, so the levels after it were never attempted — and a
    # per-level assertion would then blame the level that never ran ("no
    # activity opened in level 2") instead of naming what actually stopped it.
    assert not walk["problems"], \
        f"{TC_ID}: the guest level walk hit problems: {walk['problems']}"
    for level in (1, 2, 3):
        detail = walk["levels"].get(level, {})
        assert detail.get("opened"), (
            f"{TC_ID}: no activity opened in level {level} — it offered "
            f"{detail.get('activities')}, problems: {detail.get('problems')}")
    assert walk["completed"], \
        f"{TC_ID}: no activity was completed as a guest (opened: {walk['opened']})"


    # 6. The first exam on the map (Rally: "Navigate to the first exam on
    #    the map and complete it"). This case is a 'Advanced Proficiency'
    #    one, so the exam is the point of it — the Beginning Literacy case is
    #    what proves the activities. WHICH level carries the exam was read off
    #    the live map above (it moves with the language and level the guest
    #    picked), and its icon is pressed BY NAME, never by coordinates.
    exam = utilsdemo.guest_take_exam(driver, level=first_exam)
    assert exam["ok"], (
        f"{TC_ID}: the first exam (level {first_exam}) was not completed — "
        f"{exam.get('note')}. Answered {exam.get('parts')}/{exam.get('total')} "
        f"page(s), submitted={exam.get('submitted')}, "
        f"problems={exam.get('problems')}")

    # 7. The guest restriction: a level past the accessible band must not
    #    open. Locked levels keep their icon, so the check is behavioural: press
    #    it and require the app stays on the map (a paywall/sign-up prompt counts
    #    as positive evidence and is reported).
    lock = utilsdemo.guest_level_locked(driver, level=GUEST_LOCKED_LEVEL)
    assert lock["locked"],         f"{TC_ID}: a level past the guest band was not locked — {lock['note']}"

    # ...and it must SAY so. Read from the app's own message label
    # (MessageText) once it stops typing itself out, and matched as FRAGMENTS:
    # the apostrophe is typographic in some builds and the sentence wraps, but
    # a gate that goes quiet — or offers something else — is a real regression.
    # This is the proof that finishing the exam did not unlock anything.
    shown = lock.get("text") or ""
    missing = [f for f in LOCKED_MESSAGE_FRAGMENTS if f.lower() not in shown.lower()]
    assert not missing, (
        f"{TC_ID}: the locked level did not show the subscribe message "
        f"(missing {missing}) — MessageText said {shown!r}")

    # 8. Rally steps that cannot be derived from the description — implement
    #    against the live app, then set MANUAL_EDIT = True to keep the code:
    #   1. Enter the map.
    #   2. ℹ️ Activities were already solved in the Beginning Literacy test for Turkish. Verify levels load correctly.
    #   3. Perform Clear Data to reset app state for the next test.

    # 9. Reset for the next run (Rally: "Perform Clear Data"). Order matters:
    #    log out FIRST, then clear Unity's data — clearing while the guest
    #    session is live leaves it in memory and the next run resumes that guest
    #    instead of registering a new one.
    assert utilsdemo.reset_guest_data(driver),         f"{TC_ID}: could not reset the app (logout + clear data) after the run"
