"""Running activities: opening them, the solver table, finish-to-pass, evidence frames.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

from datetime import datetime
import logging
import time
from alttester import By

from vocatooki import instructions_parrot, login_session, scene_names, scenes, ui_actions


FAILED_ACTIVITIES = set()


activity_report = []


def handle_level_flow(altdriver):
    """Manages both opened and not-yet-opened level flows."""
    time.sleep(2)
    current_scene = altdriver.get_current_scene()

    if current_scene == 'ActivitySelectionScene':
        print("[INFO] Executing opened level flow")
    else:
        print("[INFO] Handling not-yet-opened level flow")
        ui_actions.click_by_name(altdriver, "nextButton")
        time.sleep(3)
        assert altdriver.get_current_scene() == 'VendingMachineScene', "[FAIL] Expected vending scene"
        ui_actions.click_by_name(altdriver, "Toggle")
        time.sleep(15)
        assert altdriver.get_current_scene() == 'ActivitySelectionScene', "[FAIL] Expected activity selection"

    activities = altdriver.find_objects(By.NAME, "ActivityThumb")
    assert len(activities) == 3, f"[FAIL] Expected 3 activities, found {len(activities)}"

    for i in range(len(activities)):
        run_activity(altdriver, activities[i])
        time.sleep(4)
        when_finish_activity(altdriver)
        time.sleep(2)
        activities = altdriver.find_objects(By.NAME, "ActivityThumb")


def _get_current_activity_with_retry(altdriver, prev_scene=None, max_attempts=10, waits=(2,5,10,15,30,45)):
    """
    Polls AltTesterUtils.GetCurrentActivity until it returns a non-empty value
    and (optionally) different from prev_scene. Returns the scene string or None.
    """
    import time

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            scene = ui_actions.call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
            if scene:
                # If we know what we were before, ensure it changed
                if prev_scene is None or scene != prev_scene:
                    print(f"[DEBUG] GetCurrentActivity attempt {attempt}: '{scene}'")
                    return scene
                else:
                    print(f"[DEBUG] attempt {attempt}: scene still '{scene}' (same as before), retrying...")
            else:
                print(f"[DEBUG] attempt {attempt}: empty scene, retrying...")
        except Exception as e:
            last_err = e
            print(f"[WARN] GetCurrentActivity attempt {attempt} failed: {e}")

        # wait before next attempt
        wait = waits[attempt - 1] if attempt - 1 < len(waits) else waits[-1]
        time.sleep(wait)

    print(f"[ERROR] Could not obtain a new activity after {max_attempts} attempts.")
    if last_err:
        print(f"[ERROR] Last error: {last_err}")
    return None


# How long to keep clearing an activity's intro before giving up on it.
ACTIVITY_INTRO_TIMEOUT = 20


# How long nothing may need clearing before the intro counts as over. The bubble
# can scale up a beat AFTER the blocker goes, so "nothing right now" is not the
# same as "nothing coming".
ACTIVITY_INTRO_QUIET = 1.5


# How long an activity is given to fetch its lesson files and build its board.
ACTIVITY_LOAD_TIMEOUT = 60


def wait_for_activity_board(altdriver, scene="", timeout=ACTIVITY_LOAD_TIMEOUT):
    """Wait until the activity's OWN board exists, not just its scene name.

    An activity reports its scene about a second after it is opened and then
    sits on a loading screen -- "טוען... מוריד קבצי שיעור" with a download size,
    measured live entering SEARCH -- while it fetches the lesson files. Nothing
    of the activity is on screen yet, so anything that asks "is the parrot up?"
    in that window is answered "no" about a screen that has not been built, and
    the intro then arrives AFTER the check has passed.

    The activity's own distinctive objects are the honest signal. An activity
    with no entry in ACTIVITY_UI_MARKERS falls back to the scene settling.
    """
    markers = ACTIVITY_UI_MARKERS.get(scene or "")
    if markers and ui_actions.wait_for_any(altdriver, markers, timeout=timeout):
        return True
    return scenes.wait_for_scene_ready(altdriver, label=scene or "activity")


def clear_activity_intro(altdriver, scene="", timeout=ACTIVITY_INTRO_TIMEOUT,
                         quiet_for=ACTIVITY_INTRO_QUIET, poll=0.3):
    """Get the instructions parrot off the board BEFORE a solver touches it.

    Two separate things arrive with an opening activity and they do NOT arrive
    together: the full-screen `BlockScreenWithoutClick`, and the parrot's own
    bubble, which can scale up a second or two after the blocker has gone.
    Clearing once on entry therefore hands the solver a board with the parrot
    still on it -- every press lands on the intro and the activity scores
    nothing, which reads exactly like a solver that cannot play.

    Waits for the BOARD first (see wait_for_activity_board): declaring the intro
    over while the activity is still downloading is the same mistake in a
    different coat.

    Then keeps clearing until the blocker, the bubble AND the instruction WORDS
    have all stayed away for `quiet_for` seconds -- the parrot speaks its
    instructions and only then goes, so a solver must not start while there is
    still text on the board (user, 2026-09-01).
    Returns True when it had to clear something.
    """
    wait_for_activity_board(altdriver, scene)
    deadline = time.time() + timeout
    acted, quiet_since = False, None
    while time.time() < deadline:
        busy = bool(instructions_parrot.dismiss_screen_blocker(altdriver))
        words = instructions_parrot.parrot_instructions_text(altdriver)
        if words:
            logging.info(f"[Activity] the parrot is still saying "
                         f"{words[:60]!r} — waiting it out")
        if words or instructions_parrot.parrot_bubble_shown(altdriver) is True:
            instructions_parrot.dismiss_help_popup(altdriver)
            busy = True
        if busy:
            acted, quiet_since = True, None
        else:
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since >= quiet_for:
                if acted:
                    logging.info("[Activity] intro cleared — the board is free")
                return acted
        time.sleep(poll)
    logging.warning(f"[Activity] the intro was still appearing after {timeout}s; "
                    f"solving anyway")
    return acted


# The three frames every solved activity leaves behind: the board as it opened,
# the board once the solver finished with it, and the result screen. Three is
# enough to see WHAT was played and that the game accepted it, and few enough
# that a ten-lesson run does not bury the report.
ACTIVITY_FRAMES = ("1-start", "2-mid", "3-feedback")


# The MID frame is taken while the solver plays, not after it: before every
# click/tap (parrot_guard.ACTION_HOOKS) the progress counter is read, at most
# once a second, and the first time it reaches HALF (4/8) the frame is shot.
# An activity with no counter gets it 15s into the solve instead. (User,
# 2026-09-22: frames 2 and 3 used to be taken seconds apart at the end.)
MID_FRAME_FALLBACK_SECONDS = 15.0


_MID = {"driver": None, "scene": "", "taken": False, "checked": 0.0, "since": 0.0}


def _mid_activity_frame(driver):
    """ACTION_HOOK: shoot the mid frame once the activity is half done."""
    st = _MID
    if st["taken"] or st["driver"] is None or st["driver"] is not driver:
        return
    now = time.time()
    if now - st["checked"] < 1.0:
        return
    st["checked"] = now
    done, total = read_activity_progress(driver)
    halfway = bool(total) and done >= max(1, total // 2)
    no_counter_late = not total and now - st["since"] >= MID_FRAME_FALLBACK_SECONDS
    if halfway or no_counter_late:
        st["taken"] = True
        activity_frame(driver, st["scene"], ACTIVITY_FRAMES[1])
        logging.info(f"[shots] mid frame for {st['scene']}"
                     + (f" at {done}/{total}" if total else " (no counter, 15s in)"))


def _watch_mid_frame(driver, scene):
    """Arm (scene given) or disarm (scene None) the mid-frame hook."""
    _MID.update(driver=driver if scene else None, scene=scene or "",
                taken=False, checked=0.0, since=time.time())


# What proves the game itself accepted the activity. FeedbackPopup(Clone) is the
# shared result screen; "prev" is the older marker and is kept as a fallback,
# though it is weak -- the side toolbar carries one during play too.
ACTIVITY_RESULT_MARKERS = ("FeedbackPopup(Clone)", "ResultPanel", "WinDialog")


# Short on purpose: this is only used to LABEL the last frame, so a long wait
# would add dead time to every activity that ends some other way.
ACTIVITY_RESULT_TIMEOUT = 8


def activity_frame(altdriver, scene, phase):
    """Save one numbered frame for an activity. Never raises, never blocks."""
    try:
        from runner import screenshots as _screenshots   # local: runner imports us
        return _screenshots.evidence(altdriver, phase, tc_id=scene)
    except Exception as e:                              # noqa: BLE001
        logging.debug(f"[shots] frame '{phase}' for {scene} not taken: {e}")
        return None


def wait_for_activity_result(altdriver, timeout=25, poll=1.0):
    """True once the activity's result screen is up.

    The solver returning only says the SOLVER finished; this says the GAME
    accepted it. An activity that never reaches its result screen is not a pass
    (see the never-pass-without-verifying rule).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for marker in ACTIVITY_RESULT_MARKERS:
            if ui_actions.find_any(altdriver, marker) is not None:
                return True
        time.sleep(poll)
    return False


def run_activity(altdriver, activity):
    import time
    from datetime import datetime
    import traceback
    # ✅ Lazy import to break circular import
    from Activities import activitiesDemo as A

    # --- capture previous scene before clicking ---
    try:
        prev_scene = ui_actions.call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
    except Exception as e:
        print(f"[WARN] Failed to get previous scene (before click): {e}")
        prev_scene = None

    time.sleep(3)
    activity.click()
    time.sleep(10)  # small settle time before polling

    # --- get new scene with retries ---
    scene = _get_current_activity_with_retry(altdriver, prev_scene=prev_scene, max_attempts=10, waits=(5,8,15,40,120,240))
    if not scene:
        # We never detected a new activity; treat as unmapped/not detected
        activity_report.append({
            "activity": "UNMAPPED_OR_NOT_DETECTED",
            "status": "SKIPPED",
            "error": "Could not detect new activity after click (GetCurrentActivity timed out).",
            "duration": "0s",
            "platform": getattr(altdriver, "platform", "Unknown")
        })
        print("[SKIPPED] No new activity detected after click.")
        return

    start_time = datetime.now()

    if scene in FAILED_ACTIVITIES:
        print(f"[SKIPPED] Previously failed activity: {scene}")
        activity_report.append({
            "activity": scene,
            "status": "SKIPPED",
            "error": "Previously failed",
            "duration": "0s",
            "platform": getattr(altdriver, "platform", "Unknown")
        })
        return

    # ✅ Use function references from activitiesDemo (A.*)
    activity_map = {
        'MEMMORY_CARDS': A.memory,
        'LISTEN_FIND': A.megaphone,
        'SENTENCE_COMPLETION_QUIZ': A.fill_in,
        'SENTENCE_TRANSLATION_QUIZ': A.spiders,
        'SEARCH': A.search,
        'MISSING_BUBBLE': A.bubbels,
        'RADAR': A.radar,
        'UNSCRAMBLE_QUIZ': A.lexi_match,
        'GAP_GURU': A.gap_guru,
        'TYPE_IT_RIGHT': A.type_it_right,
        'TRANSLATION_WIZ': A.translation_wiz,
        'ECHO_ORDER': A.echo_order,
        'FROGGER': A.frogger,
        'HANGWORDS': A.hang_words,
        'WORDS_MATCHING_QUIZ': A.moving,
        'BEE_CAREFUL': A.bee,
        'ISPY': A.ispy,
        'LETTERS_SEARCH': A.search_3rd,
        'LETTERS_BUBBLES': A.bubbels_activity_3rd,
        'LETTERS_SORTING': A.signs,
        'CROSSWORD2': A.crosswords2,
        'CROSSWORD':A.crosswords,
        'PUZZLES':A.solve_puzzles,
        'TURTLE_ISLAND':A.turtle_island,
        'BRICKOUT':A.brickout,
        'PIPES':A.pipes,
        'RINGS':A.rings,
        'PARASHOOT':A.parashoot,
        'TETRIS':A.tetris,
        'LETTERS_TRACING':A.letters_tracing,
        'LETTERS_SLIDER_TRACING':A.letters_slider_tracing,
        'SHARKS':A.sharks
    }

    if scene not in activity_map:
        print(f"[WARN] Unknown activity '{scene}' — marking as UNMAPPED.")
        activity_report.append({
            "activity": scene,
            "status": "SKIPPED",
            "error": "No mapping defined",
            "duration": "0s",
            "platform": getattr(altdriver, "platform", "Unknown")
        })
        return

    print(f"[INFO] Running activity: {scene}")
    # --- Handle optional "Last Attempt" popup (PlaceHolder only) ---
    try:
        placeholder = None
        try:
            placeholder = altdriver.find_object(By.NAME, "PlaceHolder")
        except Exception:
            pass

        if placeholder:
            try:
                is_active = placeholder.get_component_property(
                    "UnityEngine.GameObject", "activeInHierarchy", "UnityEngine.CoreModule"
                )
            except Exception:
                is_active = True  # fallback: if found, assume active

            if is_active:
                print("[INFO] 'Last Attempt' popup detected — clicking 'Yes'.")
                try:
                    altdriver.find_object(By.NAME, "Yes").click()
                    time.sleep(0.3)  # quick settle
                except Exception as e:
                    print(f"[WARN] Could not click 'Yes': {e}")
    except Exception as popup_err:
        print(f"[WARN] Could not process 'Last Attempt' popup: {popup_err}")

    # The instructions parrot covers the board with BlockScreenWithoutClick when
    # an activity opens; until it is clicked away every press lands on it.
    # Wait the parrot OUT, do not just knock once: the bubble can arrive after
    # the blocker leaves, and a solver that starts under it scores nothing.
    clear_activity_intro(altdriver, scene)
    activity_frame(altdriver, scene, ACTIVITY_FRAMES[0])      # the board as it opened
    _watch_mid_frame(altdriver, scene)                        # frame 2 is shot mid-solve

    try:
        if scene == 'CROSSWORD2':
            print("[INFO] Waiting 15 seconds for CROSSWORD2 to load")
            time.sleep(15)

        # THREE attempts before this counts as a failure — the same rule the
        # guest walk and the exams follow. Solvers re-read the board, so a
        # second run finishes what a lost drag left behind instead of failing
        # the whole lesson (and burning the activity into FAILED_ACTIVITIES,
        # which makes every later lesson skip it).
        #
        # A lesson run must play the activity TO THE END (user, 2026-09-22):
        # FROGGER was reported PASSED after 2:06 with blanks still empty,
        # because "the solver returned" was all that was checked. So after each
        # attempt the game itself is asked whether it finished; an unfinished
        # activity is played again, and after three it FAILS with the reason.
        for attempt in range(1, 4):
            try:
                activity_map[scene](altdriver)
            except Exception as solver_error:
                print(f"[WARN] {scene} failed on attempt {attempt}/3: {solver_error}")
                if attempt == 3:
                    raise
                time.sleep(2)
                continue

            finished, note = activity_finished(altdriver)
            if finished is not False:            # True, or no counter to judge by
                if attempt > 1:
                    print(f"[INFO] {scene} solved on attempt {attempt}/3")
                if finished is None:
                    logging.warning(f"[Activity] {scene}: {note} — cannot prove it "
                                    f"was played to the end; not counted as a failure")
                break
            print(f"[WARN] {scene} not finished on attempt {attempt}/3: {note}")
            if attempt == 3:
                raise AssertionError(f"{scene} was not played to the end: {note}")
            retry_lost_activity(altdriver)
            time.sleep(2)


        _watch_mid_frame(altdriver, None)                     # solving is over
        # OBSERVED, NOT ENFORCED -- and that was a hard-won distinction.
        #
        # Requiring a result screen here looked right ("the solver finishing is
        # not the same as the game accepting it") but it FAILED A WORKING
        # ACTIVITY: TURTLE_ISLAND solved for 4m12s, finished normally, and was
        # then failed for not showing any of these three names. It had been
        # passing for months. Worse, the failure put it in FAILED_ACTIVITIES, so
        # every later lesson skipped it untried.
        #
        # The marker list was only ever confirmed for the tracing activities, so
        # it cannot speak for the rest. Until there is a per-activity list built
        # from what each one really shows, a missing result screen is worth
        # SAYING and nothing more.
        if not wait_for_activity_result(altdriver, timeout=ACTIVITY_RESULT_TIMEOUT):
            logging.warning(
                f"[Activity] {scene}: no result screen seen in "
                f"{ACTIVITY_RESULT_TIMEOUT}s (looked for "
                f"{', '.join(ACTIVITY_RESULT_MARKERS)}). The solver finished, so "
                f"this is NOT counted as a failure — but nothing here proves the "
                f"game accepted it.")
        activity_frame(altdriver, scene, ACTIVITY_FRAMES[2])   # the final feedback

        end_time = datetime.now()
        activity_report.append({
            "activity": scene,
            "status": "PASSED",
            "error": "",
            "duration": str(end_time - start_time),
            "platform": getattr(altdriver, "platform", "Unknown")
        })

    except Exception as e:
        error_msg = traceback.format_exc()
        _watch_mid_frame(altdriver, None)
        print(f"[EXCEPTION] Activity {scene} failed: {e}")
        FAILED_ACTIVITIES.add(scene)

        # Three attempts are spent: photograph the screen BEFORE the recovery
        # below navigates away from it.
        shot = ui_actions.capture_failure_screenshot(altdriver, f"activity_{scene}")

        end_time = datetime.now()
        activity_report.append({
            "activity": scene,
            "status": "FAILED",
            "error": error_msg,
            "duration": str(end_time - start_time),
            "screenshot": shot,
            "platform": getattr(altdriver, "platform", "Unknown")
        })

        # --- Recovery flow (unchanged, with safety checks) ---
        try:
            print(f"[INFO] Trying to exit activity '{scene}' after failure...")
            when_finish_activity(altdriver)
        except Exception as exit_err:
            print(f"[WARN] Could not click Back after failure: {exit_err}")
            print(f"[RECOVERY] Attempting full recovery flow...")

            try:
                ui_actions.call_method(altdriver, "AltTesterUtils", "Logout")
                time.sleep(5)
                login_session.login(altdriver)
                time.sleep(5)
                ui_actions.click_by_name(altdriver, "GO-Map")
                time.sleep(5)
                print("[RECOVERY] Recovery flow completed.")
            except Exception as recovery_err:
                print(f"[CRITICAL] Recovery flow failed: {recovery_err}")
                print("[CRITICAL] Attempting to restart the App...")
                try:
                    altdriver.stop()
                    time.sleep(5)
                    if hasattr(altdriver, "start"):
                        altdriver.start()
                    time.sleep(10)
                    login_session.login(altdriver)
                    time.sleep(5)
                    ui_actions.click_by_name(altdriver, "GO-Map")
                    time.sleep(5)
                    print("[RECOVERY] App Restart recovery completed.")
                except Exception as restart_err:
                    print(f"[FATAL] App Restart failed: {restart_err}")
                    print("[FATAL] Test execution cannot proceed after multiple recovery attempts.")


def when_finish_activity(altdriver, retries=3, delay=1):
    """
    Attempts to exit the activity screen by clicking the Exit button.

    Args:
        altdriver (AltDriver): The AltTester driver instance.
        retries (int): Number of retries in case ExitButton is not immediately found.
        delay (float): Delay between retries in seconds.
    """
    logging.info("Attempting to exit activity")

    for attempt in range(1, retries + 1):
        try:
            exit_button = altdriver.find_object(By.NAME, "prev")
            exit_button.click()
            logging.info("Exit button clicked successfully.")
            return
        except Exception as e:
            logging.warning(f"Attempt {attempt}: Failed to click ExitButton - {e}")
            time.sleep(delay)

    # Fallback, reached only when "prev" was never found. Some activities
    # (LETTERS_TRACING) put their result screen up as FeedbackPopup(Clone) and
    # the SideToolbar holding "prev" is gone behind it, so the loop above can
    # never succeed. The popup carries its own exit. When "prev" IS found the
    # behaviour above is unchanged and this never runs.
    try:
        popup = altdriver.find_object(By.NAME, "FeedbackPopup(Clone)")
        popup.find_object_from_object(By.NAME, "ExitButton").click()
        logging.info("Exit via the result popup's ExitButton.")
        return
    except Exception as e:
        logging.warning(f"Result popup exit not available either - {e}")

    # Having nothing left to exit is not a failure. A solver that closes its own
    # result screen (the tracing activities do) leaves us back on the selection
    # screen before this is called, and then neither "prev" nor the popup is
    # there to click. Logging that as an ERROR puts a red line under an activity
    # that passed, so say what actually happened instead.
    try:
        scene = altdriver.get_current_scene()
    except Exception:
        scene = None
    if scene in ("ActivitySelectionScene", "MapScene"):
        logging.info(f"Already out of the activity (on {scene}) — nothing to exit.")
        return

    logging.error("Failed to exit activity after multiple retries.")


# ---------------------------------------------------------------------------
# Reusable primitives for Rally-generated activity tests (additive only —
# nothing above is changed). A generated test composes these:
#   login -> enter_level_number -> open_level_to_activities
#         -> solve_activity_in_level -> Logout
# ---------------------------------------------------------------------------
def get_activity_solver_map():
    """Scene name -> solver function, for callers outside run_activity.

    Mirrors the dispatch table inside run_activity (kept separate on purpose so
    the battle-tested run_activity flow stays untouched). When a new activity is
    mapped there, add it here too.
    """
    from Activities import activitiesDemo as A
    return {
        'MEMMORY_CARDS': A.memory,
        'LISTEN_FIND': A.megaphone,
        'SENTENCE_COMPLETION_QUIZ': A.fill_in,
        'SENTENCE_TRANSLATION_QUIZ': A.spiders,
        'SEARCH': A.search,
        'MISSING_BUBBLE': A.bubbels,
        'RADAR': A.radar,
        'UNSCRAMBLE_QUIZ': A.lexi_match,
        'GAP_GURU': A.gap_guru,
        'TYPE_IT_RIGHT': A.type_it_right,
        'TRANSLATION_WIZ': A.translation_wiz,
        'ECHO_ORDER': A.echo_order,
        'FROGGER': A.frogger,
        'HANGWORDS': A.hang_words,
        'WORDS_MATCHING_QUIZ': A.moving,
        'BEE_CAREFUL': A.bee,
        'ISPY': A.ispy,
        'LETTERS_SEARCH': A.search_3rd,
        'LETTERS_BUBBLES': A.bubbels_activity_3rd,
        'LETTERS_SORTING': A.signs,
        'CROSSWORD2': A.crosswords2,
        'CROSSWORD': A.crosswords,
        'PUZZLES': A.solve_puzzles,
        'TURTLE_ISLAND': A.turtle_island,
        'BRICKOUT': A.brickout,
        'PIPES': A.pipes,
        'RINGS': A.rings,
        'PARASHOOT': A.parashoot,
        'TETRIS': A.tetris,
        'LETTERS_TRACING': A.letters_tracing,
        'LETTERS_SLIDER_TRACING': A.letters_slider_tracing,
        'SHARKS': A.sharks,
    }


ACTIVITY_EXITS = ("prev", "BackButton", "X", "CloseButton", "Close")


# What each activity puts on screen, taken from the objects its own solver
# drives. Only DISTINCTIVE names are listed: "Canvas", "Button" and "Text"
# exist in every scene and would prove nothing. An activity missing from this
# map is checked against the generic marker instead — and never fails a run on
# that basis, because absence of a marker we never established is not evidence.
ACTIVITY_UI_MARKERS = {
    "BEE_CAREFUL": ("BeeCareful_activity", "WordPanel"),
    "BRICKOUT": ("Paddle", "Ball"),
    "CROSSWORD": ("CrosswordActivity", "WordsToFindPanel"),
    "CROSSWORD2": ("FillLetter", "RTLTMPWordPanel"),
    "FROGGER": ("FroggerGameManager", "Frogger"),
    "GAP_GURU": ("QuizWordToggle(Clone)",),
    "LETTERS_BUBBLES": ("LettersBubbles_activity", "LettersBubble(Clone)"),
    "LETTERS_SEARCH": ("LettersSearch_activity", "WordPanel"),
    "LISTEN_FIND": ("ListenFind_activity", "ListenFindGameManager"),
    "MEMMORY_CARDS": ("ImageCardPrefab(Clone)", "TextCardPrefab(Clone)"),
    "MISSING_BUBBLE": ("BubblesGameManager", "bubbles_activity"),
    "PARASHOOT": ("ParashootGameManager", "FireButton"),
    "PUZZLES": ("PuzzlesManager",),
    "RADAR": ("radarObj", "Radar_activity"),
    "SEARCH": ("SearchObj(Clone)", "WordPanel"),
    "SENTENCE_COMPLETION_QUIZ": ("RTLTMPWordPanel",),
    "TETRIS": ("LeftArrow", "DownArrow"),
    "TRANSLATION_WIZ": ("ContextTranslationWizQuiz(Clone)",),
    "TURTLE_ISLAND": ("RTLTMPWordPanel",),
    "TYPE_IT_RIGHT": ("ContextTypingItQuiz(Clone)", "InputField"),
}


# The progress counter ("3/6") is up in nearly every activity, so it stands in
# for the scenes above that have nothing distinctive of their own.
ACTIVITY_GENERIC_MARKERS = ("ProgressText",)


def validate_activity_ui(altdriver, scene, timeout=8):
    """``(ok, known, note)`` — are THIS activity's own elements on screen?

    "The scene changed" only says the app navigated; it does not say the
    activity drew itself. This looks for the objects the activity's own solver
    drives, so a scene that loads empty is caught here rather than as a solver
    failure later.

    ``known`` is False when the scene has no markers established for it — the
    caller must not fail a run on that, since it would be reporting our own
    ignorance as a defect.
    """
    markers = ACTIVITY_UI_MARKERS.get(scene)
    known = markers is not None
    markers = markers or ACTIVITY_GENERIC_MARKERS

    found, deadline = set(), time.time() + timeout
    while True:
        for marker in markers:
            if marker not in found and ui_actions.find_any(altdriver, marker) is not None:
                found.add(marker)
        if found or time.time() >= deadline:
            break
        time.sleep(0.5)

    missing = [m for m in markers if m not in found]
    if not found:
        return False, known, f"none of {list(markers)} are on screen"
    return True, known, (f"found {sorted(found)}"
                         + (f" (missing {missing})" if missing else ""))


def back_to_activity_list(altdriver, timeout=10):
    """Leave the open activity and land back on ITS activity list. Bool.

    Used by BOTH flows — a logged-in user's activity walk pays the same round
    trip as a guest's. Waits on the thumbs rather than a scene name or a flat
    sleep: they are what the next thumb press needs, and they prove the list is
    rebuilt and ready, usually well before a fixed wait would have expired.
    """
    if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is not None:
        return True
    for name in ACTIVITY_EXITS:
        obj = ui_actions.find_any(altdriver, name)
        if obj is None or not ui_actions._press(obj):
            continue
        logging.info(f"[Guest] left the activity via '{name}'")
        if ui_actions.wait_for_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER, timeout=timeout):
            return True
    return ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is not None


def _infer_scene_from_title(title):
    """The activity scene a printed thumb title stands for, or ""."""
    from runner.test_generator import RallyTestGenerator      # local: avoids a cycle
    hay = (title or "").strip().lower()
    best = ""
    for keyword, scene in RallyTestGenerator.ACTIVITY_SCENES.items():
        if keyword in hay and len(keyword) > len(best or ""):
            best, best_scene = keyword, scene
    return best_scene if best else ""


def _solve_open_activity(altdriver, scene, label="", settle_tries=10):
    """Play the activity that is ALREADY open; True once the game shows its
    finish feedback.

    Playing it in place is what avoids ``LastAttempetPopUp``: backing out and
    re-entering the same activity raises the "last attempt" notice over the
    board, the solver then plays against a blocked screen, and the attempt
    scores nothing. Some activities also open on an intro scene
    ("WordsMatchingOpenningScene") before the playable one, so the scene is
    given a chance to settle into something the solver map knows.
    """
    solvers = get_activity_solver_map()
    solver = solvers.get(scene)
    for _ in range(settle_tries):
        if solver is not None:
            break
        time.sleep(2.5)
        now = scenes._current_scene(altdriver)
        if now and now != scene and now in solvers:
            logging.info(f"[Guest] '{scene}' settled into '{now}'")
            scene, solver = now, solvers[now]
    if solver is None:
        logging.warning(f"[Guest] no solver mapped for scene '{scene}' ({label})")
        return False

    instructions_parrot.dismiss_replay_popup(altdriver)
    # The instructions parrot blocks the whole screen until it is clicked, and
    # every press the solver makes would land on the blocker, not the board.
    instructions_parrot.dismiss_screen_blocker(altdriver)
    try:
        solver(altdriver)
    except Exception as e:                       # noqa: BLE001
        logging.error(f"[Guest] the {scene} solver raised: {str(e)[:140]}")
        return False
    return wait_for_finish_feedback(altdriver, timeout=40)


def read_activity_progress(altdriver):
    """(done, total) from the activity's ProgressText, or (0, 0) if unreadable."""
    try:
        a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(a), int(b)
    except Exception:
        return 0, 0


def activity_finished(altdriver, settle=8.0):
    """Did the game reach the END of this activity? Returns (True/False/None, note).

    True  - the success screen is up, or the progress counter reached its total
    False - the game was lost, or the counter stopped short ("stopped at 3/8")
    None  - no counter and no result screen: nothing to judge by (TURTLE_ISLAND
            ends on neither), so the caller must not call that a failure

    Gives the game ``settle`` seconds first: the last answer animates before the
    counter ticks and the feedback screen opens.
    """
    deadline = time.time() + settle
    done = total = 0
    while True:
        if ui_actions.find_any(altdriver, "FailureFeedbackPopup(Clone)") is not None:
            return False, "the game was lost (Try Again screen)"
        if ui_actions.find_any(altdriver, "FeedbackPopup(Clone)") is not None:
            return True, "the success screen is showing"
        done, total = read_activity_progress(altdriver)
        if total and done >= total:
            return True, f"progress {done}/{total}"
        if time.time() >= deadline:
            break
        time.sleep(0.5)
    if total:
        return False, f"stopped at {done}/{total}"
    return None, "no progress counter or result screen"


def retry_lost_activity(altdriver):
    """On the Try Again screen, press Retry so the next attempt has a board."""
    if ui_actions.find_any(altdriver, "FailureFeedbackPopup(Clone)") is not None and \
            ui_actions.find_any(altdriver, "RetryButton") is not None:
        ui_actions.press_object(altdriver, "RetryButton", settle=4.0)
        logging.info("[Activity] the game was lost — pressed Retry for the next attempt")


def wait_for_finish_feedback(altdriver, timeout=25):
    """True once the activity's final feedback screen is showing.

    On successful completion the game plays the score/feedback screen, whose
    exit button is named "prev" — the same one when_finish_activity clicks.
    Its appearance is the observable proof the game REGISTERED the completion,
    which "the solver returned" alone does not prove.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if altdriver.find_object(By.NAME, "prev"):
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


# Unity activity scene -> the title printed on its thumb in
# ActivitySelectionScene. Read off the live app: the thumbs are all named
# "ActivityThumb", but each one has a title label above it, so the target
# activity can be picked directly instead of opening them one by one.
ACTIVITY_UI_TITLES = {
    "PIPES": ("pipes",),
    "BRICKOUT": ("break out", "brickout", "breakout"),
    "RINGS": ("rings",),
    "PARASHOOT": ("parashoot", "parachute"),
    "TURTLE_ISLAND": ("turtle island", "turtle"),
    "PUZZLES": ("puzzle", "puzzles"),
    "CROSSWORD": ("crossword",),
    "CROSSWORD2": ("crossword",),
    "MISSING_BUBBLE": ("missing bubble", "bubble"),
    "GAP_GURU": ("gap guru",),
    "TYPE_IT_RIGHT": ("type it right",),
    "FROGGER": ("frogger", "frog"),
    "RADAR": ("radar",),
    "TETRIS": ("tetris",),
    "MEMMORY_CARDS": ("memory", "memory cards"),
    "LISTEN_FIND": ("listen", "listen & find", "listen and find"),
    "SEARCH": ("search",),
    "HANGWORDS": ("hangwords", "hang words"),
    "BEE_CAREFUL": ("bee careful", "bee"),
    "ISPY": ("i spy", "ispy"),
    "ECHO_ORDER": ("echo order", "echo"),
    "TRANSLATION_WIZ": ("translation wiz", "translation"),
    "UNSCRAMBLE_QUIZ": ("unscramble", "lexi match"),
}


# The lesson title sits well above the thumb row; activity titles are printed
# directly over their own thumb, so a title belongs to the thumb it lines up
# with horizontally.
_TITLE_X_TOLERANCE = 60


def list_level_activities(altdriver):
    """Read ActivitySelectionScene: which activity is on which thumb.

    Every thumb is named "ActivityThumb" and every label "Text - RTLTMP", but
    a label shares its thumb's x position, so they pair up by proximity.

    Returns ``[{"title": "Break Out", "thumb": <AltObject>, "x": 792}, ...]``
    in on-screen (left-to-right) order. Titles that cannot be read come back
    empty rather than raising — the caller falls back to probing.
    """
    try:
        thumbs = altdriver.find_objects(By.NAME, "ActivityThumb")
    except Exception as e:  # noqa: BLE001
        logging.warning(f"[Activity] could not list thumbs: {e}")
        return []

    labels = []
    try:
        for t in altdriver.find_objects(By.NAME, "Text - RTLTMP"):
            try:
                text = (t.get_text() or "").strip()
            except Exception:
                continue
            if text:
                labels.append((t.x, text))
    except Exception as e:  # noqa: BLE001
        logging.warning(f"[Activity] could not read activity titles: {e}")

    out = []
    for th in sorted(thumbs, key=lambda o: o.x):
        best, best_dx = "", None
        for x, text in labels:
            dx = abs(x - th.x)
            if dx <= _TITLE_X_TOLERANCE and (best_dx is None or dx < best_dx):
                best, best_dx = text, dx
        out.append({"title": best, "thumb": th, "x": th.x})
    return out


def find_activity_thumb(altdriver, target_scene, title_hint=None):
    """The thumb whose printed title is ``target_scene``'s activity, or None.

    ``title_hint`` is the exact label seen when the test was generated (e.g.
    "Break Out"); it is tried first, then the aliases in ACTIVITY_UI_TITLES.
    Returning None is normal (older builds, unlabelled thumbs) and makes the
    caller fall back to opening thumbs one by one.
    """
    activities = list_level_activities(altdriver)
    if not activities:
        return None

    wanted = [str(title_hint).strip().lower()] if title_hint else []
    wanted += [a for a in ACTIVITY_UI_TITLES.get(target_scene, ())]
    # Last resort: the scene name itself ("PIPES" -> "pipes").
    wanted.append(str(target_scene).replace("_", " ").lower())

    seen = [a["title"] for a in activities]
    logging.info(f"[Activity] this level offers: {seen}")
    for want in wanted:
        if not want:
            continue
        for a in activities:
            title = (a["title"] or "").strip().lower()
            if not title:
                continue
            if title == want or want in title or title in want:
                logging.info(f"[Activity] '{a['title']}' matches {target_scene} — clicking it directly")
                return a["thumb"]
    logging.info(f"[Activity] no printed title matches {target_scene} ({seen}) — probing thumbs")
    return None


def _play_activity(altdriver, target_scene, solvers, result):
    """Solve the activity that is already open and fill in ``result``.

    Shared by both selection paths (title match / thumb probing) so the
    completion checks are identical either way.
    """
    result["found"] = True
    instructions_parrot.dismiss_replay_popup(altdriver)          # replayed activities are blocked by it
    instructions_parrot.dismiss_screen_blocker(altdriver)        # so is the instructions parrot
    solvers[target_scene](altdriver)
    time.sleep(2)
    done, tot = read_activity_progress(altdriver)
    result["done"], result["total"] = done, tot
    if tot > 0 and done < tot:
        logging.error(f"[Activity] {target_scene} INCOMPLETE at {done}/{tot} "
                      f"— staying on the activity for the failure screenshot")
        return result
    result["feedback"] = wait_for_finish_feedback(altdriver)
    if not result["feedback"]:
        logging.error(f"[Activity] {target_scene} reached {done}/{tot} but the "
                      f"final feedback screen never appeared")
        return result
    when_finish_activity(altdriver)
    time.sleep(2)
    return result


def activity_completed(result):
    """Did this activity really finish? (the one definition, used everywhere)

    A result dict is always truthy, so completion is judged on its fields: the
    activity was reached, its progress ran to the end, and the game showed the
    feedback screen that registers it.
    """
    result = result or {}
    total = result.get("total")
    return bool(result.get("found") and total
                and result.get("done") == total and result.get("feedback"))


def solve_activity_in_level(altdriver, target_scene, title_hint=None, attempts=3):
    """Solve an activity, RETRYING before it counts as a failure.

    Every flow in the project reaches an activity through here — the guest
    walk, the lesson-range modes and the generated Rally tests — so the retry
    rule lives here rather than in any one caller: a lost drag, or a press that
    landed while a screen was still animating, is not the same thing as an
    activity that cannot be completed. Between attempts it goes back to the
    activity list, so the activity is played from the top instead of resuming a
    half-finished board.
    """
    result = {"found": False, "done": 0, "total": 0, "feedback": False}
    for attempt in range(1, max(1, attempts) + 1):
        if attempt > 1:
            logging.warning(
                f"[Activity] '{target_scene}' not completed "
                f"(found={result.get('found')} "
                f"{result.get('done')}/{result.get('total')} "
                f"feedback={result.get('feedback')}) — attempt {attempt}/{attempts}")
            back_to_activity_list(altdriver)
        result = _solve_activity_once(altdriver, target_scene, title_hint=title_hint)
        if activity_completed(result):
            if attempt > 1:
                logging.info(f"[Activity] '{target_scene}' completed on attempt {attempt}")
            return result
    # Out of attempts: photograph the screen it could not get past. Nothing is
    # navigated afterwards, so this is the state a human would need to see.
    result["screenshot"] = ui_actions.capture_failure_screenshot(
        altdriver, f"activity_{target_scene}")
    logging.error(f"[Activity] '{target_scene}' not completed after {attempts} attempts "
                  f"(progress {result.get('done')}/{result.get('total')})")
    return result


def _solve_activity_once(altdriver, target_scene, title_hint=None):
    """One attempt: open ``target_scene``'s activity in the current level,
    solve AND VERIFY it.

    Picks the right activity by the title printed on its thumb (see
    ``find_activity_thumb``). Only when no title matches does it fall back to
    the old behaviour of opening each thumb in turn and asking the game which
    activity it landed on.

    Returns a result dict — callers must assert on its fields, not on
    truthiness (a dict is always truthy):
        found    the target activity was reached
        done/total  the activity's final progress ("6/6"); a solver that stops
                 short (e.g. 1/6) is NOT completion even though it returned
        feedback the final feedback screen appeared (the game registered it)
    On failure nothing is exited/navigated, so a failure screenshot captures
    the actual stuck screen.
    """
    result = {"found": False, "done": 0, "total": 0, "feedback": False}
    solvers = get_activity_solver_map()
    if target_scene not in solvers:
        logging.error(f"[Activity] No solver mapped for '{target_scene}'")
        return result

    # Preferred path: click the thumb whose printed title is the target.
    thumb = find_activity_thumb(altdriver, target_scene, title_hint=title_hint)
    if thumb is not None:
        try:
            prev_scene = ui_actions.call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
        except Exception:
            prev_scene = None
        thumb.click()
        time.sleep(8)
        scene = _get_current_activity_with_retry(altdriver, prev_scene=prev_scene)
        if scene == target_scene:
            return _play_activity(altdriver, target_scene, solvers, result)
        # The label promised one activity and the game opened another: don't
        # solve the wrong game — go back and fall through to probing.
        logging.warning(f"[Activity] title matched but the game opened '{scene}', "
                        f"not {target_scene} — falling back to probing")
        try:
            ui_actions.call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:
            when_finish_activity(altdriver)
        if not ui_actions.wait_for_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER, timeout=8):
            back_to_activity_list(altdriver)

    thumbs = altdriver.find_objects(By.NAME, "ActivityThumb")
    total = len(thumbs)
    logging.info(f"[Activity] {total} activities in this level; hunting {target_scene}")

    for i in range(total):
        thumbs = altdriver.find_objects(By.NAME, "ActivityThumb")
        if i >= len(thumbs):
            break
        try:
            prev_scene = ui_actions.call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
        except Exception:
            prev_scene = None
        thumbs[i].click()
        time.sleep(8)
        scene = _get_current_activity_with_retry(altdriver, prev_scene=prev_scene)
        if scene == target_scene:
            logging.info(f"[Activity] Found {target_scene} at thumb {i}; solving")
            return _play_activity(altdriver, target_scene, solvers, result)
        # Not the one — back out to the activity SELECTION and try the next.
        # Never out to the map: that would cost a level re-entry per thumb.
        logging.info(f"[Activity] thumb {i} opened '{scene}', not {target_scene}; going back")
        try:
            ui_actions.call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception as e:
            logging.warning(f"[Activity] LoadPreviousScene failed: {e}")
            when_finish_activity(altdriver)
        # Wait for the thumbs instead of a flat sleep — the list is usually
        # back well inside a second, and when it is not, pressing the exit
        # ourselves beats sleeping and hoping.
        if not ui_actions.wait_for_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER, timeout=8):
            back_to_activity_list(altdriver)

    logging.error(f"[Activity] {target_scene} not found among {total} thumbs")
    return result


def write_activity_report(f, lesson_num=None, lesson_id=None):
    difficulty_labels = ["Easy", "Medium", "Hard"]
    activity_occurrences = {}  # Tracks occurrence count for each activity

    f.write("📊 ACTIVITY EXECUTION REPORT\n")
    f.write("=" * 40 + "\n\n")

    for entry in activity_report:
        activity = entry['activity']
        platform = entry.get('platform', 'Unknown')
        count = activity_occurrences.get(activity, 0)

        if count < len(difficulty_labels):
            difficulty = difficulty_labels[count]
        else:
            difficulty = f"Attempt {count + 1}"

        activity_occurrences[activity] = count + 1

        # Build activity label with lesson number or ID
        if lesson_num is not None:
            activity_label = f"{activity}[{difficulty}][Lesson {lesson_num}]"
        elif lesson_id is not None:
            activity_label = f"{activity}[{difficulty}][ID: {lesson_id}]"
        else:
            activity_label = f"{activity}[{difficulty}]"

        # Write activity entry
        f.write(f"Platform: {platform}\n")
        f.write(f"Activity: {activity_label}\n")
        f.write(f"Status  : {entry['status']}\n")
        f.write(f"Duration: {entry['duration']}\n")
        if entry['error']:
            f.write(f"Error   :\n{entry['error']}\n")
        f.write("-" * 40 + "\n")
