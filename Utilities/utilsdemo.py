import logging
from alttester import By, AltKeyCode, AltDriver
from alttester.exceptions import ComponentNotFoundException
import random
import re
import requests
import io
import time


FAILED_ACTIVITIES = set()
activity_report = []
# Generic Method Invoker
# The backend the data endpoints talk to. It MOVED from vtbe to green: on
# 2026-09-01 get-class-map answered 404 with "Error 1A001F01A32" on vtbe for
# every class and every map id, while green returned the map. That 404 was
# silent all the way up -- get_level returned -1, enter_to_level returned False,
# and a whole lesson run reported ten lessons "FAILED, 0s".
#
# Kept as ONE overridable name rather than a host repeated per call, which is
# how half the file ended up on green (VT_TASKS_API) and half still on vtbe.
_VT_DATA_API_DEFAULT = "https://green.vocatooki.com/data"
# `os` is imported far below, so read the override the same way VT_TASKS_API
# does rather than moving an import and disturbing the module's load order.
VT_DATA_API = __import__("os").getenv("VT_DATA_API") or _VT_DATA_API_DEFAULT


def call_method(altdriver, component_name, method_name, parameters=None, parameter_types=None,
                game_object=None, game_object_name="AltTesterPrefab", assembly="Assembly-CSharp"):
    """
    Wrapper to call a method on a game object.
    # Example usage
    result = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
    Methods :PlayClickSound,LoadPreviousScene,GetCurrentActivity,LoadMapScene,Logout,LoadStartScene
    """
    parameters = parameters or []
    parameter_types = parameter_types or []

    if not game_object:
        game_object = altdriver.find_object(By.NAME, game_object_name)

    try:
        return game_object.call_component_method(
            assembly=assembly,
            component_name=component_name,
            method_name=method_name,
            parameters=parameters,
            type_of_parameters=parameter_types
        )
    except ComponentNotFoundException as e:
        # The object exists but the component isn't attached in the current
        # app state. Most often this means the app is on the login/start
        # screen (or a scene is still loading), where components like
        # 'AltTesterUtils' don't exist yet. Re-raise with actionable context.
        raise ComponentNotFoundException(
            f"Component '{component_name}' not found on game object "
            f"'{game_object_name}' when calling '{method_name}'. "
            f"This usually means the app is not in the expected state "
            f"(e.g. not logged in, or the scene is still loading). "
            f"Original error: {e}"
        ) from e


# Login Utility
LOGIN_SCREEN_FIELDS = ("UserInputField", "PasswordInputField", "LoginButton")


def _login_screen_visible(altdriver):
    """True only when all login-screen fields are present (mirrors LoginPage.is_open)."""
    return all(find_element(altdriver, name) is not None for name in LOGIN_SCREEN_FIELDS)


def _wait_for_login_screen(altdriver, timeout=30, poll=0.5):
    """Poll until the login screen is fully shown, or timeout. Returns bool."""
    end = time.time() + timeout
    while time.time() < end:
        if _login_screen_visible(altdriver):
            return True
        time.sleep(poll)
    return False


def login(altdriver, username=None, password=None, timeout=30):
    # Only log out if we're not already on the login screen.
    # The "Logout" method lives on the AltTesterUtils component, which only
    # exists once logged in. Calling it on the login/start screen raises
    # ComponentNotFoundException, so we guard the call.
    if not _login_screen_visible(altdriver):
        try:
            call_method(altdriver, "AltTesterUtils", "Logout")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Logout skipped: {e}")

    # Wait for the login screen to actually render before typing. A fixed sleep
    # after logout is not enough — the login UI (NewStartScene) can take longer,
    # and if we never reach it we want a clear error, not a bare WaitTimeOut on
    # a single field.
    if not _wait_for_login_screen(altdriver, timeout=timeout):
        try:
            current_scene = altdriver.get_current_scene()
        except Exception:
            current_scene = "<unknown>"
        raise AssertionError(
            f"Login screen did not appear within {timeout}s "
            f"(current scene: '{current_scene}'). "
            f"Expected fields: {', '.join(LOGIN_SCREEN_FIELDS)}."
        )

    altdriver.wait_for_object(By.NAME, "UserInputField", enabled=True).set_text(username)
    altdriver.wait_for_object(By.NAME, "PasswordInputField", enabled=True).set_text(password)
    altdriver.wait_for_object(By.NAME, "LoginButton").click()
    time.sleep(7)
# API Utilities
def get_user_state(user_id, avatar_version, awards_version, lessons_version, add_is_complete):
    payload = {
        "user_id": user_id,
        "avatar_version": avatar_version,
        "awards_version": awards_version,
        "lessons_version": lessons_version,
        "add_is_complete": add_is_complete
    }
    try:
        response = requests.post(f"{VT_DATA_API}/get-user-state", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[ERROR] Fetching user state failed: {e}")
        return None


def extract_lesson_titles(user_state):
    return [lesson["title"] for lesson in user_state.get("lessons", {}).get("lessons", [])]


# UI Interactions
def click_by_name(altdriver, name):
    try:
        altdriver.find_object(By.NAME, name).click()
        time.sleep(2)
    except:
        print(f"[WARN] Failed to click element by name: {name}")


def click_by_path(altdriver, path):
    try:
        altdriver.wait_for_object(By.PATH, path).click()
        time.sleep(2)
    except:
        print(f"[WARN] Failed to click element by path: {path}")


def assert_text_by_name(altdriver, name, expected_text):
    actual = altdriver.wait_for_object(By.NAME, name).get_text()
    time.sleep(2)
    assert actual == expected_text, f"[ASSERT FAIL] '{actual}' != '{expected_text}'"


def assert_text_by_path(altdriver, path, expected_text):
    actual = altdriver.wait_for_object(By.PATH, path).get_text()
    time.sleep(2)
    assert actual == expected_text, f"[ASSERT FAIL] '{actual}' != '{expected_text}'"


def get_text_by_name(altdriver, name):
    return altdriver.wait_for_object(By.NAME, name).get_text()


def get_text_by_path(altdriver, path):
    return altdriver.wait_for_object(By.PATH, path).get_text()


def find_element(altdriver, name):
    try:
        return altdriver.find_object(By.NAME, name)
    except:
        return None

def handle_level_flow(altdriver):
    """Manages both opened and not-yet-opened level flows."""
    time.sleep(2)
    current_scene = altdriver.get_current_scene()

    if current_scene == 'ActivitySelectionScene':
        print("[INFO] Executing opened level flow")
    else:
        print("[INFO] Handling not-yet-opened level flow")
        click_by_name(altdriver, "nextButton")
        time.sleep(3)
        assert altdriver.get_current_scene() == 'VendingMachineScene', "[FAIL] Expected vending scene"
        click_by_name(altdriver, "Toggle")
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
            scene = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
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

def capture_failure_screenshot(altdriver, label):
    """Save a PNG of the screen a step GAVE UP on. Returns the bare filename.

    Called only after something has already been retried and still cannot
    proceed, because that screen is the evidence and it does not survive: by
    the time the run ends the app has been navigated on, recovered, or logged
    out. The bare filename is what the report, the panel and the Rally upload
    all expect (they resolve it against REPORTS_DIR/screenshots).
    """
    import os as _os                              # local: os is imported late below
    try:
        reports = _os.getenv("REPORTS_DIR", _os.path.expanduser("~/Downloads/reports"))
        shots = _os.path.join(reports, "screenshots")
        _os.makedirs(shots, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", str(label or ""))[:60].strip("_") or "failure"
        name = f"failed_{safe}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        altdriver.get_png_screenshot(_os.path.join(shots, name))
        logging.info(f"[Shot] gave up — saved {name}")
        return name
    except Exception as e:                        # noqa: BLE001 - never fail a run
        logging.warning(f"[Shot] could not capture '{label}': {e}")
        return ""



# The three frames every solved activity leaves behind: the board as it opened,
# the board once the solver finished with it, and the result screen. Three is
# enough to see WHAT was played and that the game accepted it, and few enough
# that a ten-lesson run does not bury the report.
ACTIVITY_FRAMES = ("1-opened", "2-solved", "3-feedback")

# What proves the game itself accepted the activity. FeedbackPopup(Clone) is the
# shared result screen; "prev" is the older marker and is kept as a fallback,
# though it is weak -- the side toolbar carries one during play too.
ACTIVITY_RESULT_MARKERS = ("FeedbackPopup(Clone)", "ResultPanel", "WinDialog")


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
            if find_any(altdriver, marker) is not None:
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
        prev_scene = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
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
        'LETTERS_SLIDER_TRACING':A.letters_slider_tracing
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
    dismiss_screen_blocker(altdriver)
    activity_frame(altdriver, scene, ACTIVITY_FRAMES[0])      # the board as it opened

    try:
        if scene == 'CROSSWORD2':
            print("[INFO] Waiting 15 seconds for CROSSWORD2 to load")
            time.sleep(15)

        # THREE attempts before this counts as a failure — the same rule the
        # guest walk and the exams follow. Solvers re-read the board, so a
        # second run finishes what a lost drag left behind instead of failing
        # the whole lesson (and burning the activity into FAILED_ACTIVITIES,
        # which makes every later lesson skip it).
        for attempt in range(1, 4):
            try:
                activity_map[scene](altdriver)
                if attempt > 1:
                    print(f"[INFO] {scene} solved on attempt {attempt}/3")
                break
            except Exception as solver_error:
                print(f"[WARN] {scene} failed on attempt {attempt}/3: {solver_error}")
                if attempt == 3:
                    raise
                time.sleep(2)

        activity_frame(altdriver, scene, ACTIVITY_FRAMES[1])  # the finished board

        # The solver finishing is not the same as the game accepting it. Without
        # this an activity that was "solved" into a screen the game ignored is
        # reported PASSED, which is the exact false green the project forbids.
        if not wait_for_activity_result(altdriver):
            raise AssertionError(
                f"{scene}: the solver finished but no result screen appeared "
                f"(looked for {', '.join(ACTIVITY_RESULT_MARKERS)}) — the game "
                f"did not accept this as a completed activity")
        activity_frame(altdriver, scene, ACTIVITY_FRAMES[2])   # the result screen

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
        print(f"[EXCEPTION] Activity {scene} failed: {e}")
        FAILED_ACTIVITIES.add(scene)

        # Three attempts are spent: photograph the screen BEFORE the recovery
        # below navigates away from it.
        shot = capture_failure_screenshot(altdriver, f"activity_{scene}")

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
                call_method(altdriver, "AltTesterUtils", "Logout")
                time.sleep(5)
                login(altdriver)
                time.sleep(5)
                click_by_name(altdriver, "GO-Map")
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
                    login(altdriver)
                    time.sleep(5)
                    click_by_name(altdriver, "GO-Map")
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



def get_class_map(class_id, map_id):
    """
    Fetches the class map configuration from the backend.

    Args:
        class_id (int): ID of the class.
        map_id (int): ID of the map (typically 1).

    Returns:
        dict: Map data as JSON, or an empty dict on failure.
    """
    url = f"{VT_DATA_API}/get-class-map/{class_id}/{map_id}"
    logging.info(f"[get_class_map] Fetching map for class_id={class_id}, map_id={map_id}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if "map" not in data:
            logging.warning("[get_class_map] Missing 'map' key in response")
            return {}

        return data

    except requests.exceptions.HTTPError as e:
        logging.error(f"[get_class_map] HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"[get_class_map] Connection error: {e}")
    except ValueError:
        logging.error("[get_class_map] Failed to parse JSON response")

    return {}


def get_level(class_id, lesson_number, type="lesson", difficulty=-1):
    logging.info(f"[Level Resolver] Fetching level for class_id={class_id}, lesson={lesson_number}, type={type}, difficulty={difficulty}")

    # Normalize difficulty to lowercase string
    if isinstance(difficulty, str):
        difficulty = difficulty.lower()

    # Fetch map data
    map_data = get_class_map(class_id, map_id=1)
    if not map_data or "map" not in map_data or "levels" not in map_data["map"]:
        logging.error("[Level Resolver] Invalid or missing map data structure.")
        return -1

    levels = map_data["map"]["levels"]

    if lesson_number >= len(levels):
        logging.error(f"[Level Resolver] Lesson index {lesson_number} is out of range. Total lessons: {len(levels)}")
        return -1

    lesson_levels = levels[lesson_number]
    logging.debug(f"[Level Resolver] Available levels: {lesson_levels}")

    for level in lesson_levels:
        logging.debug(f"[Level Resolver] Checking level: {level}")
        if type == "lesson" and level.get("difficulty", "").lower() == difficulty:
            logging.info(f"[Level Resolver] Found lesson level: {level.get('level')}")
            return level.get("level")
        if type == "exam" and level.get("type") == "exam":
            logging.info(f"[Level Resolver] Found exam level: {level.get('level')}")
            return level.get("level")

    logging.warning(f"[Level Resolver] No matching level found for type='{type}' and difficulty='{difficulty}'")
    return -1


def enter_to_level(altdriver, class_id, lesson_number, type="lesson", difficulty=-1):
    logging.info(
        f"[Map Navigation] Attempting to enter level: class_id={class_id}, lesson={lesson_number}, type={type}, difficulty={difficulty}"
    )

    level_num = get_level(class_id, lesson_number, type, difficulty)
    if level_num < 0:
        logging.error(f"[Map Navigation] Invalid level number: {level_num}. Cannot proceed.")
        return False

    try:
        # Anchored search, so a new map prefab needs no code change. Every map so
        # far (MainMap, 5thMap, Map_4, ...) puts its icons under the same
        # Levels/level_icons node, and _find_level_icons keeps the rooted paths
        # as fallbacks. Hunting prefab by prefab is what made Map_4 a code edit.
        level_objs = _find_level_icons(altdriver)

        if not level_objs:
            logging.error(f"[Map Navigation] No level icons on the current map "
                          f"(scene: {_current_scene(altdriver)})")
            return False

        if level_num >= len(level_objs):
            logging.error(f"[Map Navigation] Level index {level_num} out of range ({len(level_objs)} icons).")
            return False

        # --- Click the target level ---
        level_objs[level_num].click()
        time.sleep(4)
        logging.info(f"[Map Navigation] Entered level index {level_num} successfully.")
        return True

    except Exception as e:
        logging.error(f"[Map Navigation] Exception while clicking level: {e}")
        return False


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
    }


def _find_level_icons(altdriver):
    """Level icons of whichever map is currently loaded.

    The anchored search works for every map prefab (MainMap, 5thMap, ...);
    the two explicit paths are kept as fallbacks.
    """
    for path in ("//Levels/level_icons/*",
                 "/MainMap(Clone)/Map Backgrounds/Levels/level_icons/*",
                 "/5thMap(Clone)/Map Backgrounds/Levels/level_icons/*",
                 "/Map_4(Clone)/Map Backgrounds/Levels/level_icons/*"):
        try:
            objs = altdriver.find_objects(By.PATH, path)
            if objs:
                return objs
        except Exception:
            pass
    return []


# A map node's prefab name says what kind of level it is, and every icon is
# suffixed with the level number it opens ("TestLevelIcon(Clone) 40").
# Read off the live map: 248 nodes, exams every 4-5 levels.
LEVEL_ICON_KINDS = {
    "LessonLevelIcon": "lesson",        # the usual 3-activity level
    "TestLevelIcon": "exam",            # 4, 8, 13, 17, 22, 26, 31, 35, 40, ...
    "DialogueLevelIcon": "dialogue",
    "AiDialogueLevelIcon": "ai_dialogue",
    "RCLevelIcon": "reading",           # reading comprehension
    "TaskLevelIcon": "task",
}


def _level_icon_by_number(altdriver, level_num):
    """The map icon that opens ``level_num``, whatever kind of level it is.

    Icons are named after the level they open, so this beats counting: it
    cannot drift when the map has gaps, a different prefab, or an ordering the
    icon list doesn't reflect. Every prefab kind is tried, because an exam node
    ("TestLevelIcon(Clone) 40") is not a lesson node.

    Returns ``(AltObject|None, name|None, kind|None)``.
    """
    for prefab, kind in LEVEL_ICON_KINDS.items():
        for name in (f"{prefab}(Clone) {level_num}",
                     f"{prefab} Variant(Clone) {level_num}"):
            obj = find_element(altdriver, name)
            if obj is not None:
                return obj, name, kind
    return None, None, None


def level_kind(altdriver, level_num):
    """What kind of level ``level_num`` is on the map ("lesson", "exam", ...).

    Lets a test say out loud what it expects — an exam case pointed at a lesson
    node is a Rally data mistake worth failing on, not a mystery timeout.
    Returns None when the map is not showing or the level does not exist.
    """
    _obj, _name, kind = _level_icon_by_number(altdriver, level_num)
    return kind


START_SCENE = "NewStartScene"   # the screen GO-Map lives on; back from the map lands here
# GO-Map lands HERE instead of the map when the account's class is configured
# for a pretest in the CRM — a placement test that has to be taken before the
# map is reachable. NOT every new user: it depends on the parent class config,
# so two fresh accounts can behave differently (the user explained this on
# 2026-08-18). Nothing is broken when a run sees this scene.
PRETEST_SCENE = "PretestScene"
MAP_SCENE = "MapScene"

# Every feature reachable from the start screen, surveyed on the live app.
# button  - what to click on the start screen
# scene   - the scene it loads ("" when it opens a popup on the start screen)
# markers - objects that prove the feature is really open
# back    - how to leave it (None: no back control exists, needs ensure_on_map)
APP_FEATURES = {
    # NOT BackButton: nearly every screen in the app has one, so it proved
    # nothing — it reported the map "open" while the app was on PretestScene.
    "map":            {"button": "GO-Map", "scene": MAP_SCENE,
                       "markers": ["Levels", "level_icons", "CountersPanel"],
                       "back": "BackButton"},
    "tasks":          {"button": "GO-Tasks", "scene": "TasksSelectionScene",
                       "markers": ["ALL-NavigationTab", "Open-NavigationTab"], "back": "prev"},
    "events":         {"button": "GO-Events", "scene": "EventSelectionScene",
                       "markers": ["EventCard(Clone)", "StartButton", "WinnersButton"],
                       "back": "BackButton"},
    "audiobook":      {"button": "GO-Audiobook", "scene": "AudiobookLibraryScene",
                       "markers": ["BookCard(Clone)", "PlayButton"], "back": "BackButton"},
    "competitions":   {"button": "GO-Competitions", "scene": "TournamentSelectionScene",
                       "markers": ["Toggles"], "back": "BackButton"},
    "treasure island": {"button": "GO-Treasure_Island", "scene": "TreasureIsland",
                        "markers": ["GO-TI-Progress_Bar-Tube (1)"], "back": None},
    "daily games":    {"button": "GO-Daily", "scene": "DailyGamesSelection",
                       "markers": ["WinnersCards", "Ctrl-Card_1st"], "back": "prev"},
    "dialogue":       {"button": "GO-Dialogue", "scene": "DialogueSelectionScene",
                       "markers": ["DialogueSelectionButton(Clone)"], "back": "BackButton"},
    "multiplayer":    {"button": "GO-Multiplayer", "scene": "MultiplayerHub",
                       "markers": ["Head_to_Head-Enter_Button", "DraWin-Enter_Button"],
                       "back": None},
    "avatar builder": {"button": "GO-Avatar_Builder", "scene": "AvatarBuilderScene",
                       "markers": ["Level1_ButtonGroup"], "back": "BackButton"},
    "settings":       {"button": "SettingsButton", "scene": "",
                       "markers": ["SoundOnButton", "MusicOnButton", "LanguageToggleGroup"],
                       "back": "Exit"},
    "word list":      {"button": "WordListButton", "scene": "WordListScene",
                       "markers": ["audioButton", "upButton", "downButton"],
                       "back": "nextButton"},
    "user state":     {"button": "UserStateButton", "scene": "",
                       "markers": ["Button"], "back": "Button"},
}


# The two Daily Games and the scene each one loads. GetCurrentActivity returns
# "Undefined" for them, so the SCENE is the only reliable identifier.
DAILY_GAMES = {
    "wordle": {"entry": "//Wordle/GameIcon", "scene": "VTWordGuess"},
    "word connect": {"entry": "//Word Connect/GameIcon", "scene": "VTWORD_CONNECT"},
}
_WC_CARD_NAMES = ("WordsConnectCard_4 Variant(Clone)", "WordsConnectCard_5 Variant(Clone)",
                  "WordsConnectCard_3 Variant(Clone)", "WordsConnectCard_6 Variant(Clone)")


def _word_connect_cards(altdriver):
    """(card objects, letters) for the Word Connect board, or ([], [])."""
    for name in _WC_CARD_NAMES:
        cards = altdriver.find_objects(By.NAME, name)
        if not cards:
            continue
        letters = []
        for c in cards:
            try:
                letters.append(c.find_object_from_object(By.PATH, "//Letter")
                               .get_text().strip().lower())
            except Exception:
                letters.append("")
        return cards, letters, name
    return [], [], ""


def word_connect_words(altdriver):
    """Today's target words, read from the game itself.

    ``WordConnect.WordsConnect`` on GameCanvas carries the whole puzzle bank as
    ``levels`` (each ``{letters, words}``) plus ``currentLevel``. The level is
    matched by the letters ACTUALLY on the cards rather than trusting the index,
    so an off-by-one or a rolled-over level can't make the solver swipe words
    that aren't on the board. Returns [] when it cannot be determined.
    """
    gc = find_element(altdriver, "GameCanvas")
    if gc is None:
        logging.error("[Daily] GameCanvas not found — not in Word Connect?")
        return []
    try:
        levels = gc.get_component_property(
            "WordConnect.WordsConnect", "levels", "Assembly-CSharp") or []
        index = gc.get_component_property(
            "WordConnect.WordsConnect", "currentLevel", "Assembly-CSharp")
    except Exception as e:  # noqa: BLE001
        logging.error(f"[Daily] could not read the Word Connect puzzle bank: {e}")
        return []

    _cards, letters, _name = _word_connect_cards(altdriver)
    on_board = sorted(l for l in letters if l)
    logging.info(f"[Daily] Word Connect level {index}, letters on board: {on_board}")

    def words_of(entry):
        return [str(w).upper() for w in (entry or {}).get("words", [])]

    if isinstance(index, int) and 0 <= index < len(levels):
        entry = levels[index]
        if not on_board or sorted(str(c).lower() for c in entry.get("letters", [])) == on_board:
            return words_of(entry)
        logging.warning(f"[Daily] level {index} letters {entry.get('letters')} do not match "
                        f"the board {on_board} — searching the bank by letters")

    for entry in levels:
        if sorted(str(c).lower() for c in entry.get("letters", [])) == on_board:
            return words_of(entry)

    logging.error(f"[Daily] no level in the bank matches the board {on_board}")
    return []


def solve_daily_game(altdriver, game, username=None, password=None):
    """Open a Daily Game from the start screen and play it to a win.

    ``game`` is "wordle" or "word connect". Returns
    ``{"opened", "solved", "scene", "note"}`` — never raises, so a test can
    assert on the fields and a failure leaves the app on the failing screen.

    Daily Games are once per day per account: when the game has already been
    played the entry has no Play button, which comes back as opened=False with
    a note saying so, NOT as a pass.
    """
    from Activities import activitiesDemo as A

    key = (game or "").strip().lower()
    spec = DAILY_GAMES.get(key)
    result = {"opened": False, "solved": False, "scene": None, "note": ""}
    if not spec:
        result["note"] = f"unknown daily game '{game}'"
        return result

    if not open_feature(altdriver, "daily games", username=username, password=password):
        result["note"] = "the Daily Games page did not open (already played today?)"
        return result

    icons = altdriver.find_objects(By.PATH, spec["entry"])
    if not icons:
        result["note"] = f"'{game}' is not on the Daily Games page"
        return result
    icons[0].tap()
    time.sleep(4)

    play = find_element(altdriver, "PlayNowButton")
    if play is None:
        result["note"] = f"no Play button for '{game}' — already played today"
        return result
    play.tap()

    deadline = time.time() + 45
    while time.time() < deadline:
        if _current_scene(altdriver) == spec["scene"]:
            break
        time.sleep(2)
    result["scene"] = _current_scene(altdriver)
    if result["scene"] != spec["scene"]:
        result["note"] = f"expected scene {spec['scene']}, got {result['scene']}"
        return result
    result["opened"] = True
    time.sleep(3)

    try:
        if key == "wordle":
            A.wordle(altdriver)                 # reads the answer off GameplayManager
        else:
            words = word_connect_words(altdriver)
            if not words:
                result["note"] = "could not read today's Word Connect words"
                return result
            logging.info(f"[Daily] solving Word Connect with {words}")
            _cards, _letters, card_name = _word_connect_cards(altdriver)
            A.word_connect(altdriver, words=words, card_name=card_name)
    except Exception as e:  # noqa: BLE001 - report, don't mask
        result["note"] = f"solver failed: {e}"
        return result

    time.sleep(5)
    result["solved"] = daily_game_won(altdriver)
    if not result["solved"]:
        result["note"] = "the game did not report a win"
    return result


def daily_game_won(altdriver, timeout=20):
    """True when the daily game shows its win/feedback screen."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_element(altdriver, "DailyGamesFinalFeedback") is not None:
            return True
        for o in altdriver.find_objects(By.NAME, "Text (TMP)"):
            try:
                if "won" in (o.get_text() or "").lower():
                    return True
            except Exception:
                continue
        time.sleep(2)
    return False


# How long a start-screen feature button is waited for before the hub is
# declared to be missing it.
FEATURE_BUTTON_TIMEOUT = 20

# How long to let a feature press work before deciding it was swallowed and
# pressing again. Long enough that a slow scene load is never mistaken for a
# dead press.
FEATURE_PRESS_RETRY_AFTER = 10


def open_feature(altdriver, feature, username=None, password=None, timeout=40):
    """Open a start-screen feature by name ("events", "tasks", ...).

    Goes back to the start screen first (from wherever the app is), clicks the
    feature's button, and waits until its scene loads or one of its marker
    objects appears. Returns True only when the feature is really showing —
    a click that lands nowhere is a failure, not a pass.
    """
    spec = APP_FEATURES.get((feature or "").strip().lower())
    if not spec:
        logging.error(f"[Feature] unknown feature '{feature}'")
        return False

    if username:
        ensure_logged_in(altdriver, username, password)
    if not return_to_start(altdriver):
        ensure_on_map(altdriver, username, password)
        return_to_start(altdriver)

    # WAIT for the button rather than asking once. The hub reports itself ready
    # before it has finished spawning its buttons, so a single lookup here fails
    # a run that is perfectly healthy — seen live: "signed in as vt233632"
    # followed immediately by "'GO-Treasure_Island' is not on the start screen",
    # on the same account that had opened it minutes earlier.
    if not wait_for_any(altdriver, (spec["button"],), timeout=FEATURE_BUTTON_TIMEOUT):
        logging.error(f"[Feature] '{spec['button']}' is not on the start screen "
                      f"after {FEATURE_BUTTON_TIMEOUT}s (scene: {_current_scene(altdriver)})")
        return False
    # A first-run greeting can sit over the hub and eat the press. Clear any
    # blocker we know about before pressing, so the common case needs no retry.
    dismiss_screen_blocker(altdriver)
    click_by_name(altdriver, spec["button"])

    deadline = time.time() + timeout
    swallowed_deadline = time.time() + FEATURE_PRESS_RETRY_AFTER
    retried = False
    while time.time() < deadline:
        here = _current_scene(altdriver)
        # Still sitting on the hub well after the press means the press went
        # nowhere -- on a NEW account Voca's introduction bubble covers the hub
        # and swallows it. Waiting the full timeout just turns that into a slow
        # failure, so press once more with the blocker cleared. Guarded on being
        # on the START scene so this can never double-fire mid-navigation.
        if (not retried and here == START_SCENE
                and time.time() > swallowed_deadline):
            logging.info(f"[Feature] still on {START_SCENE} — the press was "
                         f"swallowed; clearing blockers and pressing "
                         f"'{spec['button']}' again")
            dismiss_screen_blocker(altdriver)
            click_by_name(altdriver, spec["button"])
            retried = True
        if spec["scene"] and here == spec["scene"]:
            # Opened is not the same as ready — let it finish building before
            # anything presses into a half-built screen.
            wait_for_scene_ready(altdriver, label=spec["scene"])
            logging.info(f"[Feature] '{feature}' open (scene {spec['scene']})")
            return True
        # Markers only get a say when the feature has no scene of its own (a
        # popup over the start screen) or the scene cannot be read. Letting an
        # object vouch for a feature while the app sits in a DIFFERENT known
        # scene is how "map is open" came back true on PretestScene.
        if not spec["scene"] or not here:
            for marker in spec["markers"]:
                if find_element(altdriver, marker) is not None:
                    wait_for_scene_ready(altdriver, label=feature)
                    logging.info(f"[Feature] '{feature}' open (found {marker})")
                    return True
        time.sleep(2)

    here = _current_scene(altdriver)
    if here == PRETEST_SCENE:
        # The account's class is configured for a pretest in the CRM, and the
        # map is behind it. Named explicitly so the failure says WHY: nothing is
        # broken and no wait will fix it. Depends on the class config, not on
        # the account being new — so another account may not hit this at all.
        logging.error(f"[Feature] '{feature}' is behind the placement PRETEST: "
                      f"this account's class is configured for a pretest in the "
                      f"CRM and it has not been taken, so the map cannot be "
                      f"reached. Take it, or run the case on an account whose "
                      f"class has no pretest.")
        return False
    logging.error(f"[Feature] '{feature}' did not open (scene: {here})")
    return False


def _current_scene(altdriver):
    try:
        return altdriver.get_current_scene()
    except Exception:
        return None


def return_to_start(altdriver, max_steps=10):
    """Back out all the way to the start screen.

    The app's reliable anchor: pressing back from the MAP leads here, and from
    here GO-Map opens the map again. So when backing out one screen at a time
    has not found the map, keep going until the start screen shows and come
    back down the known path. Never raises.
    """
    for step in range(max_steps):
        if _current_scene(altdriver) == START_SCENE:
            logging.info("[Map Navigation] Reached the start screen.")
            return True
        clicked = None
        for name in _BACK_BUTTON_NAMES:
            obj = find_element(altdriver, name)
            if obj is None:
                continue
            try:
                obj.click()
                clicked = name
                break
            except Exception:
                continue
        if not clicked:
            logging.info("[Map Navigation] No back/close button on this screen.")
            break
        logging.info(f"[Map Navigation] back step {step + 1}: clicked '{clicked}'")
        time.sleep(3)
    return _current_scene(altdriver) == START_SCENE


# ---------------------------------------------------------------------------
# Guest flow ("Start FREE trial") — no account, no login
# ---------------------------------------------------------------------------
# Walked end to end against the live app on 2026-08-13 through the AltTester
# CLI. Every control here is addressed BY OBJECT NAME or by the TEXT it prints —
# never by screen coordinates, which stop landing on the control as soon as the
# resolution or the layout changes.
#
# Three things make this flow unlike the rest of the app:
#
# 1. The entry only EXISTS while nobody is logged in. During a live session
#    "Free Trial" and "PlayAsGuest" are disabled and off-screen, so a guest test
#    has to log the current user out through the UI first
#    (LogoutButton -> YesNoPopup(Clone) -> YesButton).
# 2. The onboarding asks its questions in a DIFFERENT ORDER from the Rally case:
#    child's name -> gender (Toggle/Toggle_1) -> native language -> English
#    level. So the wizard is walked by matching each screen against the labels
#    still outstanding rather than by assuming a fixed order.
# 3. Gender is asked a SECOND time after the wizard, as GenderSelectPopup(Clone)
#    on the hub, whose options are plain objects named "Male" and "Female".
#
# Nothing in this section calls login(), ensure_logged_in() or
# AltTesterUtils.Logout: a guest has no credentials, so a session torn down
# mid-test cannot be recreated.

# Object names read off the live app (scene NewStartScene, 2026-08-13).
GUEST_ENTRY = {
    "trial":        "Free Trial",            # yellow "Start FREE trial"
    "lets_start":   "Button",                # "Let's Start" on the Welcome panel
    "first_name":   "InputField - RTLTMP",   # "What is your child's name?" (top)
    "last_name":    "InputField - RTLTMP_1",
    "next":         "Button_2",
    "prev":         "Button_1",
    "gender_popup": "GenderSelectPopup(Clone)",
}
# Objects that prove the logged-out welcome screen is up.
GUEST_WELCOME_MARKERS = ("Free Trial", "SignUpButton")
# The wizard's option rows are Toggle, Toggle_1, Toggle_2, ... in screen order.
GUEST_TOGGLE_PREFIX = "Toggle"
# Onboarding ends by dropping the guest into avatar customisation.
AVATAR_SCENE = "AvatarBuilderScene"
# Gender labels, so a case asking for "Male" is understood on both screens.
GUEST_GENDERS = ("Male", "Female")


def find_any(altdriver, name, enabled=True):
    """``find_object`` that returns None instead of raising.

    ``enabled=False`` also matches INACTIVE objects — the difference between
    "this build has no such control" and "the control exists but is not active
    yet", which are two different failures to report.
    """
    try:
        return altdriver.find_object(By.NAME, name, enabled=enabled)
    except Exception:
        return None


def wait_for_any(altdriver, names, timeout=20, poll=0.25):
    """First of ``names`` to become active, or "" on timeout."""
    if isinstance(names, str):
        names = (names,)
    end = time.time() + timeout
    while True:
        for n in names:
            if n and find_any(altdriver, n) is not None:
                return n
        if time.time() >= end:
            return ""
        time.sleep(poll)


def _text_variants(label):
    """Casing/apostrophe spellings of a printed label. By.TEXT is exact."""
    base = (label or "").strip()
    out = [base, base.title(), base.upper(), base.lower(), base.capitalize()]
    for a, b in (("'", "’"), ("’", "'")):
        if a in base:
            out.append(base.replace(a, b))
    seen, uniq = set(), []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _find_by_text(altdriver, label):
    """The object printing ``label``, or None. Clicking a label works because
    Unity's raycast resolves it to the row/button that owns it."""
    for variant in _text_variants(label):
        try:
            obj = altdriver.find_object(By.TEXT, variant)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def _press_confirmed(altdriver, expect=(), gone=(), timeout=10):
    """Did the press actually move the UI? No expectation given -> assume yes."""
    if not expect and not gone:
        return True
    end = time.time() + timeout
    while True:
        if expect and wait_for_any(altdriver, expect, timeout=0.1):
            return True
        if gone and all(find_any(altdriver, g) is None for g in gone):
            return True
        if time.time() >= end:
            return False
        time.sleep(0.25)


def _press(obj):
    """Deliver a press to an object. Returns True when the call went through."""
    for action in ("click", "tap"):
        try:
            getattr(obj, action)()
            return True
        except Exception:
            continue
    return False


# How long to give the OUTER press before trying the child that owns the
# raycast. Measured on the live app: for the buttons that need the child
# ('Free Trial', "Let's Start") the outer press never lands, so a full
# confirmation window here is dead time — it cost ~20s per button, twice per
# guest run, waiting for a UI change that was never going to come.
PRESS_PROBE_SECONDS = 4.0

# Objects whose OUTER press is NEVER delivered: the interactive component lives
# in a layout child. Measured live — both of these needed the //Fitter child on
# every single run, so the outer press was pure cost (~5s each while its probe
# window ran down). For these the child is pressed FIRST and the outer object is
# only a fallback. Every other object keeps the original order, because it is
# the outer press that works for them.
PRESS_CHILD_FIRST = ("Free Trial", "Button")
_PRESS_CHILD_PATHS = ("//Fitter", "//Button", "//Btn")


def _press_candidates(altdriver, name):
    """The things to press for ``name``, in the order worth trying."""
    obj = find_any(altdriver, name)
    children = []
    for path in _PRESS_CHILD_PATHS:
        try:
            child = obj.find_object_from_object(By.PATH, path) if obj else None
        except Exception:                            # noqa: BLE001
            child = None
        if child is not None:
            children.append((f"via its {path} child", child))
    outer = [("", obj)] if obj is not None else []
    return (children + outer) if name in PRESS_CHILD_FIRST else (outer + children)


def press_object(altdriver, name, timeout=12, settle=1.0, expect=(), gone=(),
                 confirm=10):
    """Press the object called ``name`` and, when told what to expect, verify it.

    Some VocaTooki buttons wrap their interactive component in a ``Fitter``
    layout child, so a press on the outer object is delivered but ignored —
    those are listed in ``PRESS_CHILD_FIRST`` and their child is pressed first.

    Each candidate gets a SHORT probe except the last, which gets the full
    window; and before pressing the next one the confirmation is re-read, so a
    press that worked but was merely slow is never fired twice.
    """
    if not wait_for_any(altdriver, name, timeout=timeout):
        inactive = find_any(altdriver, name, enabled=False)
        logging.error(f"[Guest] '{name}' "
                      + ("exists but is inactive" if inactive is not None else "not found"))
        return False

    candidates = _press_candidates(altdriver, name)
    for index, (how, target) in enumerate(candidates):
        last = index == len(candidates) - 1
        if index and (expect or gone) and _press_confirmed(altdriver, expect, gone,
                                                           timeout=0.1):
            return True                              # a previous press landed late
        if not _press(target):
            continue
        logging.info(f"[Guest] pressed '{name}'" + (f" {how}" if how else ""))
        time.sleep(0.3 if (expect or gone) else settle)
        if _press_confirmed(altdriver, expect, gone,
                            timeout=confirm if last else min(confirm, PRESS_PROBE_SECONDS)):
            return True

    logging.error(f"[Guest] '{name}' did not move the UI "
                  f"(expected {list(expect) or 'anything'})")
    return False


def press_label(altdriver, label, timeout=8, settle=1.0, expect=(), gone=()):
    """Press the control that PRINTS ``label`` (e.g. "Arabic")."""
    end = time.time() + timeout
    while True:
        obj = _find_by_text(altdriver, label)
        if obj is not None:
            if _press(obj):
                logging.info(f"[Guest] pressed label '{label}'")
                time.sleep(settle)
                if _press_confirmed(altdriver, expect, gone):
                    return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


# Every scene builds itself over a second or two, and a press into that window
# is swallowed. A scene is "ready" when it has stopped GROWING — counting the
# ACTIVE objects is cheap (about 0.04s for a scene of ~130) and works for any
# scene without knowing a thing about it.
SCENE_READY_TIMEOUT = 12.0        # a ceiling, not a sleep
SCENE_READY_STABLE_SECONDS = 1.5  # no new objects for this long = built
SCENE_READY_POLL_SECONDS = 0.4


def wait_for_scene_ready(altdriver, timeout=SCENE_READY_TIMEOUT,
                         stable_for=SCENE_READY_STABLE_SECONDS, label=""):
    """Wait until the current scene has finished building. Returns bool.

    Watches the number of ACTIVE objects and waits for it to stop RISING.
    Rising means the scene is still spawning; once it stops, what is on screen
    is what there is going to be. Deliberately not "unchanged": a live game
    scene has things appearing and disappearing all the time, and a run should
    not sit out the whole timeout waiting for a board that will never be still.

    Returns as soon as it settles — a fast scene is not punished — and never
    raises: a scene that cannot be counted is simply carried on with.
    """
    deadline = time.time() + timeout
    peak, grew_at = -1, time.time()
    while time.time() < deadline:
        try:
            count = len(altdriver.get_all_elements() or [])
        except Exception:                            # noqa: BLE001
            return False                             # unreadable: carry on
        if count > peak:
            peak, grew_at = count, time.time()
        elif peak > 0 and (time.time() - grew_at) >= stable_for:
            logging.debug(f"[Scene] {label or _current_scene(altdriver)} ready "
                          f"({peak} objects)")
            return True
        time.sleep(SCENE_READY_POLL_SECONDS)
    logging.info(f"[Scene] {label or _current_scene(altdriver)} still growing "
                 f"after {timeout}s ({peak} objects); carrying on")
    return peak > 0


def wait_for_scene(altdriver, scene, timeout=40, poll=0.5, ready=True):
    """Poll until the app is in ``scene`` AND it has finished building.

    Arriving in a scene is not the same as being able to use it: Unity reports
    the scene as soon as it loads, while the objects keep spawning for another
    second or two, and a press into that window is simply swallowed. So every
    entry waits for the scene to stop growing as well (``ready=False`` to skip
    it, e.g. when only the name is being checked).

    Returns bool, never raises.
    """
    end = time.time() + timeout
    while True:
        if _current_scene(altdriver) == scene:
            if ready:
                wait_for_scene_ready(altdriver, label=scene)
            return True
        if time.time() >= end:
            logging.error(f"[Guest] scene '{scene}' not reached "
                          f"(still '{_current_scene(altdriver)}')")
            return False
        time.sleep(poll)


# Objects that only exist while the guest onboarding wizard is on screen.
GUEST_WIZARD_MARKERS = ("Button_2", "Button_1", "InputField - RTLTMP")


def onboarding_visible(altdriver):
    """True while the trial/registration wizard is on screen."""
    return any(find_any(altdriver, n) is not None for n in GUEST_WIZARD_MARKERS)


def in_app(altdriver):
    """True when we are inside the app rather than on login or in onboarding.

    Findability is NOT visibility here: on NewStartScene the login panel, the
    trial panels and the hub are all findable at once, so no positive "is this
    object there" test can tell them apart — "GO-Map exists" does not mean we
    are past login, and "Free Trial exists" does not mean we are not in the app.
    Only three things are decisive: the map scene, the login fields, and the
    wizard's own controls. So this is deliberately a negative test.
    """
    if _current_scene(altdriver) == MAP_SCENE:
        return True
    if _login_screen_visible(altdriver):
        return False
    return not onboarding_visible(altdriver)


def app_state(altdriver):
    """'login' | 'onboarding' | 'hub' | 'welcome' | 'elsewhere'.

    Checked most-specific first, because the panels overlap: the login overlay
    sits ON the start screen with the hub live behind it, and the trial panels
    sit on top of the login one.
    """
    if _login_screen_visible(altdriver):
        return "login"
    if onboarding_visible(altdriver):
        return "onboarding"
    if in_app(altdriver):
        return "hub"
    if any(find_any(altdriver, n) is not None for n in GUEST_WELCOME_MARKERS):
        return "welcome"
    return "elsewhere"


def guest_entry_available(altdriver):
    """True when the logged-out welcome screen with the trial entry is showing."""
    return find_any(altdriver, GUEST_ENTRY["trial"]) is not None


def logout_via_ui(altdriver, timeout=45):
    """Reach the logged-out welcome screen.

    ``AltTesterUtils.Logout`` FIRST — it is the fastest and safest way out of a
    session, and it is what every other logout in this module uses. The UI route
    (LogoutButton -> YesButton) is only a fallback, for the one case that call
    cannot serve: a guest session, where the component may not exist at all.

    (The name is historical: this did press the UI first, and the order was
    turned around once the component proved both quicker and more reliable.)
    """
    global _LAST_LOGIN_USER
    # Log out through the AltTesterPrefab, the way the rest of this module does
    # (``AltTesterUtils.Logout``). "Free Trial is findable" is NOT proof we are
    # already logged out — the welcome panel can be present while the login form
    # is what's on screen, and the trial entry then does nothing at all
    # (verified live: the press reported success and the UI never moved).
    try:
        call_method(altdriver, "AltTesterUtils", "Logout")
        time.sleep(2)
        logging.info("[Guest] logged out via AltTesterUtils")
    except Exception as e:                       # noqa: BLE001
        logging.info(f"[Guest] AltTesterUtils.Logout unavailable ({e}); using the UI")

    if wait_for_any(altdriver, GUEST_ENTRY["trial"], timeout=15):
        _LAST_LOGIN_USER = None
        return True

    # Fallback: press the UI logout (start screen -> confirm popup).
    return_to_start(altdriver)
    if find_any(altdriver, "LogoutButton") is not None:
        press_object(altdriver, "LogoutButton", settle=2.0, expect=("YesButton",))
        if wait_for_any(altdriver, "YesButton", timeout=12):
            press_object(altdriver, "YesButton", settle=4.0,
                         expect=GUEST_WELCOME_MARKERS)

    ok = bool(wait_for_any(altdriver, GUEST_ENTRY["trial"], timeout=timeout))
    if ok:
        # A guest session belongs to nobody: clear the cache or the next
        # ensure_logged_in() would decide it is "already logged in".
        _LAST_LOGIN_USER = None
    else:
        logging.error(f"[Guest] no trial entry after logout (state "
                      f"{app_state(altdriver)}, scene {_current_scene(altdriver)})")
    return ok


def _guest_toggles(altdriver, limit=12):
    """The option toggles on the current wizard screen, in screen order."""
    found = []
    for i in range(limit):
        name = GUEST_TOGGLE_PREFIX if i == 0 else f"{GUEST_TOGGLE_PREFIX}_{i}"
        obj = find_any(altdriver, name)
        if obj is not None:
            found.append((name, obj))
    return found


def toggle_label(altdriver, toggle_obj):
    """The text printed on a toggle ("Male", "Arabic"), or ""."""
    for path in ("//Text - RTLTMP", "//Text", "//Label", "//Title - RTLTMP"):
        try:
            return (toggle_obj.find_object_from_object(By.PATH, path)
                    .get_text() or "").strip()
        except Exception:
            continue
    try:
        return (toggle_obj.get_text() or "").strip()
    except Exception:
        return ""


# --- the wizard's SCROLL PICKER (native language, English level) -----------
# These screens are NOT lists of buttons. The option that sits between the two
# guide lines IS the selection, and the only way to change it is to DRAG the
# list: the mouse wheel does nothing, and a press does nothing either. Worse,
# every option exists in the hierarchy even while it is off screen, so
# find-by-text "succeeds" on a row that is nowhere near the viewport and a
# press on it reports success. That is exactly how a Turkish case registered an
# Arabic guest and still PASSED — Arabic is simply what the picker starts on.
#
# Everything below is measured from the LIVE app on every call — the band from
# the line objects, the row position from the row itself, the travel limits
# from the reported screen size. No pixel constant, no assumed resolution, and
# no coordinate is ever typed in: the drag is computed from where the app says
# its own objects are.
GUEST_PICKER_LINE_TOP = "LineTop"
GUEST_PICKER_LINE_BOTTOM = "LineBottom"


def picker_band(altdriver):
    """``(low_y, high_y)`` of the picker's selection band, or None.

    None means this screen is not a picker (the gender screen, for instance),
    which is the signal to fall back to pressing a toggle.
    """
    top = find_any(altdriver, GUEST_PICKER_LINE_TOP)
    bottom = find_any(altdriver, GUEST_PICKER_LINE_BOTTOM)
    if top is None or bottom is None:
        return None
    try:
        low, high = sorted((float(bottom.y), float(top.y)))
    except (TypeError, ValueError):
        return None
    return (low, high) if high > low else None


def _drag_picker(altdriver, x, delta, duration=0.5):
    """Drag the picker list by ``delta`` screen units. Returns what was asked.

    The gesture stays inside the app's own reported screen, with a margin taken
    as a FRACTION of the height, so it holds at any resolution. A drag that
    cannot cover the whole distance in one go covers what it can — the caller
    re-measures and goes again.
    """
    try:
        _width, height = altdriver.get_application_screensize()
        height = float(height)
    except Exception as e:                          # noqa: BLE001
        logging.error(f"[Guest] could not read the screen size: {e}")
        return 0.0

    margin = height * 0.12                          # keep clear of the edges
    lo, hi = margin, height - margin
    if hi <= lo:
        return 0.0
    start = min(max(height / 2.0 - delta / 2.0, lo), hi)
    end = min(max(start + delta, lo), hi)
    start = min(max(end - delta, lo), hi)           # keep the full span if it fits
    if abs(end - start) < 1:
        return 0.0
    try:
        altdriver.swipe({"x": x, "y": start}, {"x": x, "y": end}, duration=duration)
    except Exception as e:                          # noqa: BLE001
        logging.error(f"[Guest] could not drag the option list: {e}")
        return 0.0
    return end - start


def _row_position(altdriver, label):
    """``(x, y)`` of the row printing ``label`` once it has STOPPED moving.

    The list glides and snaps after a drag. A position read mid-glide can still
    be carried past the band, so "it is between the lines" is only meaningful
    once two consecutive readings agree — otherwise the run would accept a row
    that ends up settling one place further on.
    """
    prev = None
    for _ in range(8):
        row = _find_by_text(altdriver, label)
        if row is None:
            return None
        try:
            x, y = float(row.x), float(row.y)
        except (TypeError, ValueError):
            return None
        if prev is not None and abs(y - prev) < 1.0:
            return x, y
        prev = y
        time.sleep(0.25)
    return (x, y) if prev is not None else None


def scroll_option_into_band(altdriver, label, attempts=12):
    """Drag the picker until ``label`` sits between the lines. Returns bool.

    Landing in the band IS selecting: the picker snaps the nearest row to the
    centre and the app reads whatever is there when Next is pressed. Every
    position is taken from a list that has come to rest.
    """
    for attempt in range(attempts):
        band = picker_band(altdriver)
        if band is None:
            return False
        low, high = band
        at = _row_position(altdriver, label)
        if at is None:
            return False
        x, y = at
        if low <= y <= high:
            logging.info(f"[Guest] '{label}' is in the selection band "
                         f"(y={y:.0f} in [{low:.0f},{high:.0f}])")
            return True

        if not _drag_picker(altdriver, x, (low + high) / 2.0 - y):
            logging.error(f"[Guest] could not drag towards '{label}'")
            return False

        # A drag that changes nothing means the list is at its end, or the
        # gesture is not reaching it — stop instead of spinning.
        after = _row_position(altdriver, label)
        if after is None:
            return False
        if abs(after[1] - y) < 1.0:
            logging.error(f"[Guest] the list did not move towards '{label}' "
                          f"(still y={y:.0f}) on attempt {attempt + 1}")
            return False
    logging.error(f"[Guest] '{label}' never reached the selection band")
    return False


def _select_visible_option(altdriver, label, settle=1.0):
    """Choose ``label`` on the current wizard screen, and PROVE it took.

    A picker screen is driven by dragging (the band decides); every other
    screen is driven by pressing its toggle. Never reports success for a press
    that cannot have selected anything.
    """
    if picker_band(altdriver) is not None:
        return scroll_option_into_band(altdriver, label)

    if press_label(altdriver, label, timeout=1.5, settle=settle):
        return True
    want = (label or "").strip().lower()
    for name, obj in _guest_toggles(altdriver):
        text = toggle_label(altdriver, obj).lower()
        if text and want and (want in text or text in want):
            logging.info(f"[Guest] option '{label}' -> {name} ('{text}')")
            if _press(obj):
                time.sleep(settle)
                return True
    return False


def select_guest_option(altdriver, label, settle=1.0, retries=2):
    """Pick the option matching ``label`` on the current wizard screen.

    Both kinds of screen are handled by ``_select_visible_option``: a picker is
    dragged until the row is between the guide lines, anything else has its
    toggle pressed. The retry is for a screen still building itself, not for
    hunting: the mouse wheel was measured against the live app and moves the
    picker not at all, so scrolling with it only cost ~30s per screen and
    jostled the UI.

    Never falls back to "the first option" — on a language or level screen the
    wrong pick silently changes what the rest of the test measures.
    """
    for attempt in range(max(1, retries)):
        if _select_visible_option(altdriver, label, settle=settle):
            return True
        time.sleep(0.8)
        logging.info(f"[Guest] '{label}' not selectable yet "
                     f"(attempt {attempt + 1}/{max(1, retries)})")
    logging.error(f"[Guest] '{label}' is not on this screen")
    return False


def dismiss_gender_popup(altdriver, gender="", timeout=20):
    """The post-wizard "You are" popup, whose options are named Male/Female."""
    if not wait_for_any(altdriver, GUEST_ENTRY["gender_popup"], timeout=timeout):
        return False
    wanted = (gender or "").strip().title()
    for name in ([wanted] if wanted in GUEST_GENDERS else []) + list(GUEST_GENDERS):
        if find_any(altdriver, name) is not None:
            logging.info(f"[Guest] gender popup -> {name}")
            return press_object(altdriver, name, settle=1.0,
                                gone=(GUEST_ENTRY["gender_popup"],))
    return False


def reset_guest_data(altdriver, timeout=45):
    """Leave the app ready for the NEXT guest run: log out, THEN clear data.

    The order matters. Clearing Unity's PlayerPrefs while a guest session is
    still live leaves that session in memory, so the next run RESUMES the old
    guest (landing straight on the hub) instead of being offered the
    registration wizard — "Start FREE trial" only registers when there is no
    guest yet. Verified live 2026-08-13: logout -> welcome screen -> clear.
    """
    ok = logout_via_ui(altdriver, timeout=timeout)
    try:
        altdriver.delete_player_pref()          # Unity "clear data"
        logging.info("[Guest] cleared Unity data (PlayerPrefs)")
    except Exception as e:                      # noqa: BLE001
        logging.error(f"[Guest] clear data failed: {e}")
        return False
    time.sleep(3)
    logging.info("[Guest] data cleared — RESTART the app before the next guest "
                 "registration: the old guest survives in memory until then")
    return ok


def enter_guest_mode(altdriver, first_name="", last_name="", options=(),
                     max_screens=8, timeout=45):
    """Register as a guest and land in the app. Never logs in.

    ``options`` are the labels this case asks for on the wizard's option screens
    ("Male", "Arabic", "Beginning Literacy") in any order: each screen is
    matched against whatever is still outstanding, so the app's own ordering
    (which differs from the Rally step order) does not matter.

    Returns ``{"ok", "failed_at", "note", "picked", "trace"}`` and never raises,
    so the calling test can assert with the whole route in the message.
    """
    trace, picked = [], []
    wanted = [o for o in options if o]
    gender = next((o for o in wanted if o.strip().title() in GUEST_GENDERS), "")

    def result(ok, failed_at="", note=""):
        return {"ok": ok, "failed_at": failed_at, "note": note,
                "picked": picked, "trace": trace}

    if not logout_via_ui(altdriver, timeout=timeout):
        return result(False, "logout", "could not reach the logged-out welcome screen")
    trace.append("welcome screen")

    # A guest already registered on this device is RESUMED rather than
    # registered, so the wizard never appears and the app lands on the hub. The
    # cure is the documented reset — log out, then clear Unity's data — after
    # which the trial entry offers registration again.
    # Confirm with a POSITIVE marker: the trial panel opens ON TOP of the login
    # panel, so "Free Trial" stays findable afterwards and its disappearance is
    # not a signal (that mistake made a working press look like a failure).
    if not press_object(altdriver, GUEST_ENTRY["trial"], settle=0.5,
                        expect=(GUEST_ENTRY["lets_start"],), confirm=20):
        return result(False, "trial",
                      f"'{GUEST_ENTRY['trial']}' did not open the trial flow")
    trace.append("trial entry")
    # The welcome panel needs a moment before it accepts input: its button
    # answers a find straight away but swallows a press that arrives too early.
    time.sleep(5)


    # "Let's Start" on the Welcome panel. Its object is a bare "Button", so the
    # printed label is tried too in case the panel is rebuilt or renamed.
    if not (press_object(altdriver, GUEST_ENTRY["lets_start"], settle=0.5,
                         expect=(GUEST_ENTRY["first_name"],), confirm=20)
            or press_label(altdriver, "Let's Start", settle=0.5,
                           expect=(GUEST_ENTRY["first_name"],))):
        # No name screen. Either a guest is already registered — in which case
        # the trial entry RESUMES it (the app lands in the hub/map and the wizard
        # never appears) and only a data clear plus an app RESTART brings
        # registration back — or the panel genuinely did not take the press.
        if _current_scene(altdriver) == MAP_SCENE or                 find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
            return result(False, "existing_guest",
                          "the trial entry resumed a guest that is already "
                          "registered in this app session. Clear the app data, "
                          "RESTART the app, then run this case again")
        return result(False, "lets_start", "the Let's Start panel did not advance")
    trace.append("Let's Start")

    # "What is your child's name?" — set_text works by name on these fields.
    if first_name or last_name:
        if not wait_for_any(altdriver, GUEST_ENTRY["first_name"], timeout=20):
            return result(False, "name_screen", "the name screen never appeared")
        for key, value in (("first_name", first_name), ("last_name", last_name)):
            if not value:
                continue
            field = find_any(altdriver, GUEST_ENTRY[key])
            if field is None:
                return result(False, key, f"'{GUEST_ENTRY[key]}' is not on the name screen")
            field.set_text(value)
            time.sleep(0.2)
        trace.append(f"name '{first_name} {last_name}'".replace("  ", " "))
        if not press_object(altdriver, GUEST_ENTRY["next"], settle=1.2):
            return result(False, "next_after_name", "Next did not accept the name")

    # Option screens, in whatever order this build presents them.
    for _ in range(max_screens):
        if find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
            break                                   # wizard over, hub popup is up
        if not find_any(altdriver, GUEST_ENTRY["next"]):
            break                                   # no Next -> wizard finished
        # First pass: try every outstanding label on THIS screen WITHOUT
        # scrolling. Scrolling per label cost ~30s per screen and jostled the
        # UI — on the gender screen it hunted for "Turkish" through the whole
        # scroll range before ever trying "Female".
        chosen = ""
        for label in list(wanted):
            if label.strip().title() in GUEST_GENDERS and \
                    find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
                continue                            # handled by the popup below
            if _select_visible_option(altdriver, label, settle=1.0):
                chosen = label
                break

        # Nothing on this screen matched: it may be the language list, which
        # shows only the first few of many, so now it is worth scrolling.
        if not chosen:
            for label in list(wanted):
                if select_guest_option(altdriver, label):
                    chosen = label
                    break

        if chosen:
            wanted.remove(chosen)
            picked.append(chosen)
            trace.append(f"picked '{chosen}'")

        if not press_object(altdriver, GUEST_ENTRY["next"], settle=1.2):
            break
        trace.append("Next")

        # The English level is the last answer: the app then builds the profile
        # and hands over to the hub, which takes far longer than a screen change.
        if chosen and chosen.strip().lower().endswith(("literacy", "proficiency")):
            logging.info("[Guest] level submitted — waiting for the profile build")
            time.sleep(20)

    # The tail of the flow, as the app really plays it (walked live): the wizard
    # hands over to the hub, a SECOND gender prompt appears there, and the app
    # then drops into the avatar builder. Waiting on the popup specifically
    # matters — in_app() goes true the moment the wizard controls vanish, and
    # pressing on while a modal is still arriving means the next press hits it.
    if wait_for_any(altdriver, GUEST_ENTRY["gender_popup"], timeout=40):
        if dismiss_gender_popup(altdriver, gender):
            trace.append(f"gender popup '{gender or 'default'}'")
            if gender in wanted:
                wanted.remove(gender)
                picked.append(gender)
        else:
            return result(False, "gender_popup", "the You-are popup did not close")

    # Avatar customisation opens by itself; the Rally case leaves it with Back.
    if wait_for_scene(altdriver, AVATAR_SCENE, timeout=25):
        if not press_object(altdriver, "BackButton", settle=1.0):
            return result(False, "avatar", "the avatar screen has no usable Back")
        trace.append("avatar screen (Back)")
        wait_for_scene(altdriver, START_SCENE, timeout=30)

    state = app_state(altdriver)
    if not in_app(altdriver):
        return result(False, "not_in_app", f"onboarding ended on the {state} screen")
    if wanted:
        return result(False, "options", f"never offered: {wanted}")
    return result(True, note=f"guest '{first_name} {last_name}'".strip() + f" in the app ({state})")


# --- Guest: play the accessible levels -------------------------------------
# A guest gets levels 1-5 (the 5th being the first exam). These helpers open a
# level, prove EVERY activity in it actually starts, and finish one — all by
# object name, and without AltTesterUtils, which may not exist in a guest
# session (its absence is what makes the account-flow helpers hang).

ACTIVITY_SELECTION_SCENE = "ActivitySelectionScene"
# The thumbs prove the activity list is back without waiting on a scene poll.
ACTIVITY_SELECTION_SCENE_MARKER = "ActivityThumb"
# Scenes that are navigation, not an activity: reaching one of these after a
# thumb press means the activity did NOT open.
_GUEST_NON_ACTIVITY_SCENES = (START_SCENE, MAP_SCENE, ACTIVITY_SELECTION_SCENE,
                              "WordListScene", "VendingMachineScene", "Tests")
# A visible one of these is a crash/blocked run as far as a test is concerned.
GUEST_ERROR_POPUPS = ("ErrorPanel", "ErrorPopUp", "ConnectionIssuePopup",
                      "DrainingQueuePanel", "BlockScreen")


# Leaving an open activity: the activity LIST is ONE press away ('prev'), and
# the list is exactly where the next thumb is. return_to_map must not be used
# for this — its goal is the MAP, so after 'prev' has already landed on the
# list it presses 'Back' as well, leaves the level entirely, and the walk then
# has to re-open the level from the map. Measured live: ~13s of round trip per
# activity, three activities per level, three levels — about two minutes a run.
def tap_empty_area(altdriver, tries=6):
    """Tap a point that holds NO object — how this app dismisses the parrot's
    speech bubble (the instruction popup on every exam page, the "gray levels
    are locked" tip on the map).

    The candidate points are FRACTIONS of the live screen, and each one is
    checked with ``find_object_at_coordinates`` before it is tapped: the tap
    only happens where the app itself reports nothing, so no control is ever
    pressed by accident and no point is assumed to be empty at a resolution it
    was not measured at. Returns True when a tap was delivered.
    """
    try:
        width, height = altdriver.get_application_screensize()
        width, height = float(width), float(height)
    except Exception as e:                           # noqa: BLE001
        logging.warning(f"[Popup] could not read the screen size: {e}")
        return False

    # Edges and corners first: the middle of the screen is where the content is.
    for fx, fy in ((0.5, 0.94), (0.06, 0.5), (0.94, 0.5), (0.5, 0.06),
                   (0.06, 0.94), (0.94, 0.06)):
        point = (width * fx, height * fy)
        try:
            occupant = altdriver.find_object_at_coordinates(point)
        except Exception:                            # noqa: BLE001 - "nothing there"
            occupant = None
        if occupant is not None:
            continue
        try:
            altdriver.tap(point)
            logging.info(f"[Popup] tapped an empty point at "
                         f"({fx:.0%}, {fy:.0%}) of the screen to dismiss a popup")
            return True
        except Exception as e:                       # noqa: BLE001
            logging.debug(f"[Popup] tap at {point} failed: {e}")
    logging.warning("[Popup] found no empty point to tap")
    return False


def is_on_screen(altdriver, target, margin=0.0):
    """Is this object actually VISIBLE, or merely present in the hierarchy?

    "It answers a find" proves nothing here — the app keeps hidden UI alive and
    parked: a language row sat at y=-216, off screen, and still answered a find
    by text (pressing it did nothing, which is how a Turkish case registered an
    Arabic guest). So three independent signals are checked, and any one of
    them saying "not shown" is enough:

      * INSIDE THE VIEWPORT, measured against the app's own reported screen
        size, so it holds at any resolution
      * ACTIVE in the hierarchy
      * NOT FADED OUT by a CanvasGroup (alpha 0 is a normal way to hide a panel
        while leaving it in place, and it stays findable and positioned)

    A signal the object does not carry is skipped rather than assumed.
    """
    obj = find_any(altdriver, target) if isinstance(target, str) else target
    if obj is None:
        return False
    try:
        x, y = float(obj.x), float(obj.y)
    except (TypeError, ValueError):
        return False

    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:                                # noqa: BLE001
        width = height = 0.0
    if width and height:
        mx, my = width * margin, height * margin
        if not (mx <= x <= width - mx and my <= y <= height - my):
            return False

    try:
        active = obj.get_component_property("UnityEngine.GameObject",
                                            "activeInHierarchy", "UnityEngine.CoreModule")
        if active is False or str(active).strip().lower() == "false":
            return False
    except Exception:                                # noqa: BLE001
        pass

    try:
        alpha = obj.get_component_property("UnityEngine.CanvasGroup", "alpha", "UnityEngine")
        if alpha is not None and float(alpha) <= 0.01:
            return False
    except Exception:                                # noqa: BLE001
        pass
    return True


# The parrot's bubble, whichever side it is on. It is HIDDEN BY SCALING TO ZERO,
# not by going inactive: activeInHierarchy, enabled, position and findability are
# identical either way, so localScale is the only honest reading.
PARROT_BUBBLES = ("left_bubble", "right_bubble")


def parrot_bubble_shown(altdriver):
    """True/False when the bubble can be read, None when it cannot be.

    Measured live (PuzzleScene, 2026-09-01): shown = localScale 5.0 on every
    axis, hidden = 0.0. None means no bubble object was readable at all, which
    is a different thing from "hidden" and is why the caller keeps its old
    behaviour in that case rather than assuming a clean screen.
    """
    readable = False
    for name in PARROT_BUBBLES:
        obj = find_any(altdriver, name)
        if obj is None:
            continue
        try:
            scale = obj.get_component_property(
                "UnityEngine.Transform", "localScale", "UnityEngine.CoreModule")
        except Exception:                            # noqa: BLE001
            continue
        readable = True
        if any(abs(float(scale.get(axis) or 0.0)) > 0.01 for axis in ("x", "y", "z")):
            return True
    return False if readable else None


def dismiss_help_popup(altdriver, settle=0.4, verify_timeout=3.0):
    """Close the parrot's instruction bubble. Returns True when it acted.

    'HelpButton' is the app's own control for that bubble -- the instructions
    icon -- but it TOGGLES. Pressing it blind on a screen where the bubble is
    already down OPENS one over the controls; measured live on PuzzleScene, a
    blind press took localScale from 0.0 to 5.0. So the bubble is read first and
    the icon is pressed only when it is really showing.

    Every exam page opens with a bubble ("All you have to do is drag the ...")
    that TYPES ITSELF OUT, so waiting for it to finish costs seconds on every
    page -- the solver can start the moment it is gone.
    """
    shown = parrot_bubble_shown(altdriver)
    if shown is False:
        logging.debug("[Help] no instruction bubble on screen — leaving "
                      "'HelpButton' alone (pressing it would OPEN one)")
        return False

    obj = find_any(altdriver, "HelpButton")
    if obj is not None and _press(obj):
        deadline = time.time() + verify_timeout
        while time.time() < deadline:
            if parrot_bubble_shown(altdriver) is False:
                logging.info("[Help] closed the instruction bubble via 'HelpButton'")
                return True
            time.sleep(0.3)
        # Unreadable bubbles cannot be confirmed either way; the press still
        # happened, and this is the path the old unconditional code always took.
        logging.info("[Help] pressed 'HelpButton'"
                     + ("" if shown is None else " but the bubble is still up"))
        time.sleep(settle)
        return True
    return tap_empty_area(altdriver)


ACTIVITY_EXITS = ("prev", "BackButton", "X", "CloseButton", "Close")

# How long an activity is given to build itself before it is touched. An
# activity takes noticeably longer to settle than an exam page — its board
# animates in — so its instruction bubble is only pressed after this. The exam
# pages keep their own (shorter) timing, which was measured as fine.
GUEST_ACTIVITY_SETTLE_SECONDS = 6.0

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
            if marker not in found and find_any(altdriver, marker) is not None:
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
    if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is not None:
        return True
    for name in ACTIVITY_EXITS:
        obj = find_any(altdriver, name)
        if obj is None or not _press(obj):
            continue
        logging.info(f"[Guest] left the activity via '{name}'")
        if wait_for_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER, timeout=timeout):
            return True
    return find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is not None


# --- Events: play an event's levels and check its leaderboard --------------
# Surveyed on the live app (2026-08-16). The leaderboard is an OVERLAY on the
# event map — get_current_scene() stays "EventScene" while it is open — so
# nothing here may wait on a scene change to know it opened.
EVENT_SELECTION_SCENE = "EventSelectionScene"
EVENT_SCENE = "EventScene"
EVENT_START_BUTTON = "StartButton"          # on the active event card
EVENT_LEADERBOARD_BUTTON = "LeaderboardButton"
EVENT_LEVEL_ICON = "LessonLevelIcon Variant(Clone) {level}"
EVENT_SCORE_OBJECT = "Score"                # "80/240" on a thumb, "80" on a row
EVENT_PLAYER_NAME_OBJECT = "PlayerName"     # a leaderboard row's player


def _score_int(text):
    """The number in a score label, or None.

    Scores are PRINTED for humans: past a thousand the app writes "1,592".
    Reading the first run of digits gives 1 — which is why a leaderboard that
    agreed with the activities exactly (1592) still failed the comparison. So
    the separators come out before the number is read.
    """
    if not text:
        return None
    cleaned = re.sub(r"[,  '\s]", "", str(text))
    match = re.search(r"\d+", cleaned)
    return int(match.group()) if match else None


def _text_of(obj):
    """The text an object shows, however it stores it."""
    try:
        text = (obj.get_text() or "").strip()
        if text:
            return text
    except Exception:                                # noqa: BLE001
        pass
    return component_property(obj, "originalText")


# Proof that a login landed: the hub's own buttons. Checked instead of trusting
# the login call, because ensure_logged_in() then SKIPS the login whenever the
# cached user matches — so a login that silently did not happen sends every
# later step to the login screen.
HUB_MARKERS = ("GO-Events", "GO-Map", "GO-Tasks", "GO-Daily")
# The hub appears before its buttons are listening; a feature pressed inside
# this window is swallowed. Asked for by the user (2026-08-17).
LOGIN_SETTLE_SECONDS = 7.0

# The start screen builds its buttons a few at a time, so "how many are there"
# still rising means it is not finished. Waiting for that count to STOP rising
# is what proves the screen is built — a fixed sleep is both slower than it
# needs to be on a fast load and too short on a slow one.
START_SCENE_BUTTONS = ("GO-Map", "GO-Tasks", "GO-Events", "GO-Audiobook",
                       "GO-Competitions", "GO-Treasure_Island", "GO-Daily",
                       "GO-Dialogue", "GO-Multiplayer", "GO-Avatar_Builder",
                       "SettingsButton", "WordListButton", "LogoutButton")
START_SCENE_READY_TIMEOUT = 15.0     # the LONGEST it waits, not a sleep
START_SCENE_STABLE_SECONDS = 2.5     # unchanged this long = finished building
START_SCENE_POLL_SECONDS = 1.0


def wait_for_start_scene_ready(altdriver, timeout=START_SCENE_READY_TIMEOUT,
                               stable_for=START_SCENE_STABLE_SECONDS):
    """Wait until the start screen has finished loading. Returns bool.

    Counts how many of the hub's buttons are on screen and waits for that
    number to STOP changing — the screen is built when it stops growing, which
    is a different moment on every account and every machine. Returns as soon
    as it settles, so a fast load is not punished; ``timeout`` is a ceiling.

    Not "are all of them there": a new account does not have every feature (a
    fresh user showed no GO-Daily), and demanding the full set would wait out
    the whole timeout on a screen that was ready.
    """
    deadline = time.time() + timeout
    seen, steady_since = -1, time.time()
    while time.time() < deadline:
        count = sum(1 for name in START_SCENE_BUTTONS
                    if find_any(altdriver, name) is not None)
        if count != seen:
            seen, steady_since = count, time.time()
        elif count > 0 and (time.time() - steady_since) >= stable_for:
            logging.info(f"[Login] start screen ready — {count} buttons, "
                         f"steady for {stable_for}s")
            return True
        time.sleep(START_SCENE_POLL_SECONDS)
    logging.warning(f"[Login] start screen still settling after {timeout}s "
                    f"({seen} buttons); carrying on")
    return seen > 0


# First entry only: the app asks which avatar the user is before it will let
# them do anything, and answering navigates INTO the avatar builder — so a run
# that ignores it is left on the wrong scene with every later press missing.
# Route verified live 2026-08-18: NewStartScene -> GenderSelectPopup(Clone) ->
# Male/Female -> AvatarBuilderScene -> BackButton -> NewStartScene.
GENDER_POPUP = "GenderSelectPopup(Clone)"
GENDER_OPTIONS = ("Male", "Female")
AVATAR_BUILDER_SCENE = "AvatarBuilderScene"
# The LONGEST a login waits to see whether this is a first entry. It polls and
# returns the moment the popup shows, so a first entry is handled at once; only
# an account that has already answered pays the full wait.
GENDER_POPUP_TIMEOUT = 20.0


def handle_gender_select(altdriver, choose="Male", timeout=GENDER_POPUP_TIMEOUT):
    """Answer the first-entry "You are" popup and come back. Returns bool.

    True when the popup was there and was dealt with, False when this account
    had already answered it — which is not a failure, just not a first entry.
    Never raises: no run should die because a one-off popup moved.
    """
    if not wait_for_any(altdriver, (GENDER_POPUP,), timeout=timeout):
        return False                                 # not a first entry

    wanted = choose if choose in GENDER_OPTIONS else GENDER_OPTIONS[0]
    picked = ""
    for option in (wanted,) + GENDER_OPTIONS:        # the asked-for one first
        if find_any(altdriver, option) is not None and press_object(altdriver, option,
                                                                    settle=2.0):
            picked = option
            break
    if not picked:
        logging.error(f"[Login] the gender popup is up but neither "
                      f"{GENDER_OPTIONS} could be pressed")
        return False
    logging.info(f"[Login] first entry: chose '{picked}' on the gender popup")

    # Answering it opens the AVATAR BUILDER. Leaving is not optional: the run
    # would otherwise carry on pressing start-screen buttons from another scene.
    if wait_for_scene(altdriver, AVATAR_BUILDER_SCENE, timeout=20):
        if not press_object(altdriver, "BackButton", settle=2.0):
            logging.warning("[Login] could not press Back in the avatar builder")
        wait_for_scene(altdriver, START_SCENE, timeout=20)
    if _current_scene(altdriver) != START_SCENE:
        logging.warning(f"[Login] after the gender popup the app is on "
                        f"{_current_scene(altdriver)}, not the start screen")
    return True


def fresh_login(altdriver, username, password):
    """Log OUT and back in, so a run starts from a known account. Returns bool.

    Never trusts "we are already logged in": a leaderboard row is matched by
    the player's NAME, so a leftover session quietly measures somebody else —
    which is exactly what a stale session did on 2026-08-16, scoring an event
    under 'spy 6' while the case was written for another account.

    Logging out goes through ``AltTesterUtils.Logout``: it is the fastest and
    safest way out of a session, and it is what every other logout here uses.
    """
    global _LAST_LOGIN_USER
    try:
        call_method(altdriver, "AltTesterUtils", "Logout")
        time.sleep(2)
        logging.info(f"[Login] logged out before signing in as {username}")
    except Exception as e:                           # noqa: BLE001
        logging.info(f"[Login] AltTesterUtils.Logout unavailable ({e})")
    _LAST_LOGIN_USER = None                          # force a real login
    try:
        login(altdriver, username, password)
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Login] could not sign in as {username}: {e}")
        return False

    # PROVE we are in before saying so. ensure_logged_in() skips the login
    # whenever _LAST_LOGIN_USER matches, so marking a login that did not happen
    # makes every later step run against the login screen — which is exactly
    # how a card walk reported "GO-Events is not on the start screen".
    if not wait_for_any(altdriver, HUB_MARKERS, timeout=30):
        logging.error(f"[Login] {username}: the hub never appeared after login "
                      f"(still on {_current_scene(altdriver)})")
        return False
    # A FIRST entry stops here to ask which avatar the user is, and answering
    # walks into the avatar builder — so it is dealt with before anything else
    # tries to press a start-screen button.
    #
    # This poll doubles as the settle below: it returns the moment the popup
    # shows, and the hub is building its buttons meanwhile either way, so an
    # account that has already answered is not charged twice for waiting.
    settle_from = time.time()

    # Let the screen finish building FIRST. It grows a few buttons at a time,
    # so waiting for that to stop is what proves it is ready — a fixed sleep is
    # guesswork in both directions.
    wait_for_start_scene_ready(altdriver)

    # The popup is part of that build, so by now it is either up or not coming.
    # It still gets whatever is left of its own budget rather than a single
    # look, but an account that has already answered no longer pays the full
    # wait on top of the wait it just did.
    spent = time.time() - settle_from
    handle_gender_select(altdriver,
                         timeout=max(3.0, GENDER_POPUP_TIMEOUT - spent))

    waited = time.time() - settle_from
    if waited < LOGIN_SETTLE_SECONDS:
        time.sleep(LOGIN_SETTLE_SECONDS - waited)
    _LAST_LOGIN_USER = username
    logging.info(f"[Login] signed in as {username}")
    return True


def open_event(altdriver, username=None, password=None, timeout=60):
    """Open the active event and land on its map. Returns bool.

    The event card carrying ``StartButton`` is the one that is running; the
    finished ones carry ``WinnersButton`` instead, so pressing Start can only
    ever open the live event.
    """
    if _current_scene(altdriver) == EVENT_SCENE:
        return True
    if _current_scene(altdriver) != EVENT_SELECTION_SCENE:
        if not open_feature(altdriver, "events", username, password, timeout=timeout):
            logging.error("[Event] could not open the events screen")
            return False
    if not press_object(altdriver, EVENT_START_BUTTON, settle=3.0):
        logging.error(f"[Event] '{EVENT_START_BUTTON}' did not respond — "
                      f"is any event actually running?")
        return False
    ok = wait_for_scene(altdriver, EVENT_SCENE, timeout=timeout)
    if ok:
        time.sleep(MAP_SETTLE_SECONDS)
    return ok


def event_back_to_map(altdriver, username=None, password=None, timeout=60):
    """Return to the event MAP from wherever the event left us. Returns bool.

    Back from the leaderboard lands on the event CARDS view, not the map, so
    every exit is verified and re-entered through Start when it overshoots.
    """
    for name in ("prev", "Back", "BackButton"):
        if _current_scene(altdriver) == EVENT_SCENE:
            break
        if find_any(altdriver, name) is None:
            continue
        press_object(altdriver, name, settle=2.0)
        time.sleep(2)
    if _current_scene(altdriver) == EVENT_SCENE:
        return True
    return open_event(altdriver, username, password, timeout=timeout)


def open_event_level(altdriver, level, timeout=90):
    """Open one event level and reach its activity list. ``(ok, note)``."""
    icon = EVENT_LEVEL_ICON.format(level=level)
    if find_any(altdriver, icon) is None:
        return False, f"event level {level} has no icon ('{icon}') on the map"
    for attempt in range(1, 4):
        logging.info(f"[Event] opening event level {level} via '{icon}'"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        press_object(altdriver, icon, settle=2.0)
        if open_level_to_activities(altdriver, timeout=timeout):
            return True, ""
        logging.warning(f"[Event] level {level} did not reach its activity list "
                        f"(on {_current_scene(altdriver)}) — pressing again")
        if not event_back_to_map(altdriver):
            break
    return False, (f"event level {level} did not reach its activity list "
                   f"(stuck on {_current_scene(altdriver)})")


# A locked event level carries this countdown ("opens in ...") at its icon.
EVENT_LOCKED_MARKER = "NewLevelLockedTimer(Clone)"


def event_open_levels(altdriver, max_levels=24, tolerance=60):
    """The event levels that are OPEN right now, in order.

    A locked level keeps its icon like every other, so "the icon is there" says
    nothing — what marks it is a ``NewLevelLockedTimer(Clone)`` sitting at that
    icon. Levels open in sequence, so anything at or past the first locked one
    is locked too, which is also the honest fallback when no timer is found.
    """
    icons = {}
    for level in range(1, max_levels + 1):
        obj = find_any(altdriver, EVENT_LEVEL_ICON.format(level=level))
        if obj is None:
            continue
        try:
            icons[level] = (float(obj.x), float(obj.y))
        except (TypeError, ValueError):
            continue
    if not icons:
        return []

    locks = []
    try:
        for obj in altdriver.find_objects(By.NAME, EVENT_LOCKED_MARKER) or []:
            locks.append((float(obj.x), float(obj.y)))
    except Exception as e:                           # noqa: BLE001
        logging.debug(f"[Event] could not read the lock markers: {e}")

    open_levels = []
    for level in sorted(icons):
        x, y = icons[level]
        locked = any(abs(x - lx) < tolerance and abs(y - ly) < tolerance
                     for lx, ly in locks)
        if locked:
            break                                    # the rest are locked too
        open_levels.append(level)
    logging.info(f"[Event] open levels: {open_levels} "
                 f"(of {len(icons)} on the map, {len(locks)} locked marker(s))")
    return open_levels


def event_activity_scores(altdriver):
    """``[(earned, out_of)]`` from every Score tile on the activity screen.

    The activity list is the honest place to read a score: it shows EVERY
    activity in the level with what it scored, and it can be read at any time —
    unlike the finish screen, which is gone as soon as the run moves on.
    """
    found = []
    try:
        objects = altdriver.find_objects(By.NAME, EVENT_SCORE_OBJECT) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not read the score tiles: {e}")
        return found
    for obj in objects:
        text = re.sub(r"[,  '\s]", "", _text_of(obj) or "")
        match = re.match(r"(\d+)/(\d+)", text)
        if match:
            found.append((int(match.group(1)), int(match.group(2))))
    return found


def event_leaderboard(altdriver, timeout=20, tc_id=""):
    """Open the leaderboard and read it: ``[(player_name, score)]``.

    It opens as an OVERLAY, so this waits for the rows themselves rather than
    for a scene change that never comes.
    """
    rows = []
    if not press_object(altdriver, EVENT_LEADERBOARD_BUTTON, settle=2.0):
        logging.error(f"[Event] '{EVENT_LEADERBOARD_BUTTON}' did not respond")
        return rows
    if not wait_for_any(altdriver, EVENT_PLAYER_NAME_OBJECT, timeout=timeout):
        logging.warning("[Event] the leaderboard shows no players "
                        "(it reads 'No Results' until somebody scores)")
        return rows

    rows = _leaderboard_rows(altdriver)
    for name, score in rows:
        logging.info(f"[Event] leaderboard: {name!r} = {score}")
    # Keep the board itself: it is the other half of the comparison, and it is
    # gone as soon as the run closes it.
    capture_evidence(altdriver, "event-leaderboard", tc_id=tc_id)
    return rows


EVENT_WINNERS_BUTTON = "WinnersButton"
EVENT_NO_RESULTS_TEXT = "no results"


def _leaderboard_rows(altdriver):
    """``[(player_name, score)]`` from a leaderboard/winners list on screen.

    A row is a name and a score on the SAME line, so they are paired by y
    rather than by list order — a re-sorted board would otherwise hand a name
    somebody else's score. Shared by the event leaderboard and the winners list
    of a closed event, which are the same widget.
    """
    names, scores = [], []
    try:
        for obj in altdriver.find_objects(By.NAME, EVENT_PLAYER_NAME_OBJECT) or []:
            text = _text_of(obj)
            if text:
                names.append((float(obj.y), text))
        for obj in altdriver.find_objects(By.NAME, EVENT_SCORE_OBJECT) or []:
            value = _score_int(_text_of(obj))
            if value is not None:
                scores.append((float(obj.y), value))
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not read the board: {e}")
        return []

    rows = []
    for y, name in sorted(names):
        nearest = min(scores, key=lambda pair: abs(pair[0] - y), default=None)
        if nearest is not None and abs(nearest[0] - y) < 25:
            rows.append((name, nearest[1]))
    return rows


SCREEN_TEXT_NAMES = ("Text - RTLTMP", "Text (TMP)", "Text", "MessageText",
                     "Title", "TitleText")


def screen_texts(altdriver, limit=30):
    """Every readable string on screen, found BY NAME.

    Not ``visible_texts``: that walks By.PATH contains() queries, which return
    nothing in this app — the subscribe gate read as empty twice before the
    text was fetched by object name instead.
    """
    out = []
    for name in SCREEN_TEXT_NAMES:
        try:
            objects = altdriver.find_objects(By.NAME, name) or []
        except Exception:                            # noqa: BLE001
            continue
        for obj in objects[:limit]:
            text = _text_of(obj)
            if text:
                out.append(text)
        if len(out) >= limit:
            break
    return out


# How long an overlay is given to draw itself before it is read or left. The
# winners list fades in, and reading it too early sees neither a row nor the
# "No Results" notice (user, 2026-08-17).
OVERLAY_SETTLE_SECONDS = 4.0


def event_cards(altdriver):
    """What the events screen is showing: ``[(button_name, y)]`` per card.

    A card carries exactly ONE of ``StartButton`` (the event is running) or
    ``WinnersButton`` (it has closed), so the buttons are the cards for testing
    purposes. The card in front is the one whose button sits at the SMALLEST y.
    The titles ("RAMADAN") are artwork, not text objects, so there is nothing
    readable to identify a card by.
    """
    found = []
    for name in (EVENT_START_BUTTON, EVENT_WINNERS_BUTTON):
        try:
            for obj in altdriver.find_objects(By.NAME, name) or []:
                found.append((name, float(obj.y)))
        except Exception:                            # noqa: BLE001
            continue
    return sorted(found, key=lambda pair: pair[1])


def event_next_card(altdriver, settle=2.0):
    """Bring the next event card to the front. Returns True when it moved.

    A VERTICAL swipe cycles the stack — measured live: horizontal swipes and
    clicking a card behind both do nothing at all.
    """
    before = event_cards(altdriver)
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
        altdriver.swipe({"x": width * 0.5, "y": height * 0.35},
                        {"x": width * 0.5, "y": height * 0.75}, duration=0.6)
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not swipe the card stack: {e}")
        return False
    time.sleep(settle)
    return event_cards(altdriver) != before


def event_cards_check(altdriver, username=None, password=None, tc_id="", timeout=60):
    """Browse every event card and open what it offers. Never raises.

    Start must open that event's MAP; Winners must open the winners list over
    the events screen ("No Results" is a real answer, not a failure — a closed
    event nobody scored in has none). Returns
    ``{"ok", "cards", "visited", "problems", "note"}``.
    """
    report = {"ok": False, "cards": 0, "visited": [], "problems": [], "note": ""}

    if username and not fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not open_feature(altdriver, "events", username, password, timeout=timeout):
        report["note"] = "the events screen did not open"
        return report

    reset_evidence_trail(tc_id)
    trail = evidence_trail(tc_id)
    trail.shot(altdriver, "events-screen", EVIDENCE_KEY)           # the stack as it opens

    cards = event_cards(altdriver)
    report["cards"] = len(cards)
    if not cards:
        report["note"] = "no event cards on the events screen"
        return report
    logging.info(f"[Event] {len(cards)} card(s): {[n for n, _y in cards]}")

    seen = set()
    for _ in range(len(cards)):
        front = event_cards(altdriver)
        if not front:
            break
        kind, _y = front[0]                          # smallest y = the front card
        index = len(seen)

        if kind == EVENT_START_BUTTON:
            opened = press_object(altdriver, EVENT_START_BUTTON, settle=3.0) and \
                wait_for_scene(altdriver, EVENT_SCENE, timeout=timeout)
            time.sleep(OVERLAY_SETTLE_SECONDS)   # let the map finish drawing
            trail.shot(altdriver, f"card-{index}-Start-opened", EVIDENCE_PROOF)
            if opened:
                report["visited"].append(f"card {index}: Start -> event map")
            else:
                report["problems"].append(
                    f"card {index}: Start did not open the event map "
                    f"(on {_current_scene(altdriver)})")
            # Back out to the cards, whichever way it went.
            press_object(altdriver, "BackButton", settle=2.0)
            wait_for_scene(altdriver, EVENT_SELECTION_SCENE, timeout=timeout)
        else:
            press_object(altdriver, EVENT_WINNERS_BUTTON, settle=2.5)
            # The winners list is an OVERLAY: the scene does not change, so it
            # is recognised by its own content instead.
            shown = wait_for_any(altdriver, (EVENT_PLAYER_NAME_OBJECT,), timeout=8)
            # Let the panel finish drawing before reading OR leaving it.
            time.sleep(OVERLAY_SETTLE_SECONDS)
            if not shown:                            # a late row still counts
                shown = find_any(altdriver, EVENT_PLAYER_NAME_OBJECT) is not None
            text = " ".join(screen_texts(altdriver)).lower()
            empty = EVENT_NO_RESULTS_TEXT in text
            trail.shot(altdriver, f"card-{index}-Winners-opened", EVIDENCE_PROOF)
            # Both outcomes are correct, and they mean different things: an
            # event nobody played shows "No Results", one that was played lists
            # its winners. So record WHICH, with the names and scores — a
            # report that only said "it opened" could not tell them apart.
            if shown:
                winners = _leaderboard_rows(altdriver)
                report.setdefault("winners", {})[index] = winners
                listed = ", ".join(f"{n} = {s}" for n, s in winners[:5]) or "unreadable rows"
                logging.info(f"[Event] card {index} winners: {listed}")
                report["visited"].append(
                    f"card {index}: Winners -> {len(winners)} winner(s): {listed}")
            elif empty:
                report.setdefault("winners", {})[index] = []
                report["visited"].append(
                    f"card {index}: Winners -> 'No Results' (nobody played this event)")
            else:
                report["problems"].append(
                    f"card {index}: Winners opened nothing readable — neither a "
                    f"winners row nor a 'No Results' notice")
            # The overlay adds its own BackButton; the topmost one closes it.
            backs = []
            try:
                backs = altdriver.find_objects(By.NAME, "BackButton") or []
            except Exception:                        # noqa: BLE001
                pass
            if len(backs) > 1:
                _press(sorted(backs, key=lambda o: float(o.y))[0])
                time.sleep(2)
            else:
                press_object(altdriver, "BackButton", settle=2.0)

        seen.add(index)
        trail.shot(altdriver, f"card-{index}-back-on-events")   # it really came back
        if len(seen) < len(cards) and not event_next_card(altdriver):
            report["problems"].append("the card stack would not move to the next card")
            break

    report["screenshots"] = trail.names
    report["ok"] = bool(report["visited"]) and not report["problems"] \
        and len(report["visited"]) == report["cards"]
    if not report["ok"] and not report["note"]:
        report["note"] = (f"visited {len(report['visited'])} of {report['cards']} card(s); "
                          f"problems: {report['problems']}")
    return report


def event_score_check(altdriver, levels=(1, 2, 3), player_name="",
                      username=None, password=None, timeout=90, solve_all=True,
                      tc_id=""):
    """Solve one activity in each event level, then check the leaderboard.

    Returns ``{"ok", "levels", "earned", "leaderboard", "player", "note"}`` and
    never raises. ``earned`` is the sum of the scores the solved activities show
    on their own level screens; the leaderboard row for ``player_name`` must
    match it exactly — only activities award event score, exams award coins.
    """
    report = {"ok": False, "levels": {}, "earned": 0, "leaderboard": None,
              "player": player_name, "rows": [], "note": ""}

    # Start from a known account: log out, then log in. The leaderboard is
    # matched by player NAME, so running on somebody else's leftover session
    # would measure the wrong player and still look like a pass.
    if username and not fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report

    if not open_event(altdriver, username, password, timeout=timeout):
        report["note"] = "could not open the event"
        return report

    # No levels named? Then play the ones the event has actually OPENED — the
    # locked ones cannot be entered, and counting their (zero) score against the
    # leaderboard would fail a run for doing exactly what it was told.
    if not levels:
        levels = event_open_levels(altdriver)
        report["levels_played"] = list(levels)
        if not levels:
            report["note"] = "no open levels on the event map"
            return report

    solvers = get_activity_solver_map()
    for level in levels:
        if not event_back_to_map(altdriver, username, password):
            report["note"] = f"could not get back to the event map for level {level}"
            return report
        ok, note = open_event_level(altdriver, level, timeout=timeout)
        if not ok:
            report["levels"][level] = {"opened": False, "note": note, "score": 0}
            report["note"] = note
            return report

        before = sum(e for e, _t in event_activity_scores(altdriver))
        listed = list_level_activities(altdriver)
        offered = [e.get("title") or "" for e in listed]
        played, skipped, failed = [], [], []
        for title in offered:
            scene = _infer_scene_from_title(title)
            if not scene or scene not in solvers:
                # Say which ones this framework cannot drive, rather than
                # quietly leaving their score out of the sum.
                skipped.append(title or "(unlabelled)")
                continue
            # Back to the list between activities: the previous one leaves the
            # app inside its own scene, and the next thumb lives on the list.
            if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is None:
                back_to_activity_list(altdriver)
            outcome = solve_activity_in_level(altdriver, scene, title_hint=title)
            if activity_completed(outcome):
                played.append(f"{title} ({scene})")
                if not solve_all:
                    break                            # one per level is enough
            else:
                failed.append(f"{title}: {outcome.get('done')}/{outcome.get('total')}")
        if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is None:
            back_to_activity_list(altdriver)
        after = sum(e for e, _t in event_activity_scores(altdriver))
        # The activity list with its scores UPDATED — one frame per level, kept
        # whatever the per-run budget has spent, because this is the evidence
        # the leaderboard total is checked against.
        shot = capture_evidence(altdriver, f"event-level-{level}-scores", tc_id=tc_id)
        if shot:
            report.setdefault("shots", []).append(shot)
        gained = after - before
        # Count the level's TOTAL, not what this run added. The leaderboard is
        # cumulative, so a level that was already solved still contributes its
        # score — comparing "earned today" against it would fail every re-run,
        # and would fail hardest on the very state the case is meant to check.
        report["levels"][level] = {"opened": True, "played": played,
                                   "offered": offered, "skipped": skipped,
                                   "failed": failed, "score": after,
                                   "gained": gained, "note": ""}
        report["earned"] += after
        logging.info(f"[Event] level {level}: solved {len(played)}/{len(offered)} "
                     f"{played} -> level total {after} ({gained:+d} this run)"
                     + (f"; no solver for {skipped}" if skipped else "")
                     + (f"; incomplete {failed}" if failed else ""))
        if not played:
            report["note"] = (f"level {level} offered {offered}, none of which "
                              f"this framework can complete")
            return report

    if not event_back_to_map(altdriver, username, password):
        report["note"] = "could not get back to the event map for the leaderboard"
        return report

    rows = event_leaderboard(altdriver, tc_id=tc_id)
    report.setdefault("shots", []).append(f"evidence-event-leaderboard.png")
    report["rows"] = rows
    wanted = (player_name or "").strip().lower()
    for name, score in rows:
        if wanted and " ".join(name.split()).lower() == " ".join(wanted.split()):
            report["leaderboard"] = score
            break
    if report["leaderboard"] is None:
        report["note"] = (f"'{player_name}' is not on the leaderboard — it lists "
                          f"{[n for n, _s in rows] or 'nobody'}")
        return report

    report["ok"] = report["leaderboard"] == report["earned"]
    if not report["ok"]:
        report["note"] = (f"the leaderboard says {report['leaderboard']} but the "
                          f"activities scored {report['earned']} "
                          f"({ {k: v.get('score') for k, v in report['levels'].items()} })")
    return report


# --- Tasks: the teacher's tasks, and answering one -------------------------
#
# Surveyed live 2026-08-19. A task is NOT graded in the app: submitting SENDS it
# to the teacher, which is why the outcome to verify is Open -> Sent and never
# "the answers were right".

TASKS_SCENE = "TasksSelectionScene"
TASK_SCENE = "TaskScene"
TASK_CARD_OPEN = "TaskCard-Open(Clone)"      # answerable
TASK_CARD_CLOSED = "TaskCard-Closed(Clone)"  # no longer answerable
TASK_TABS = ("ALL", "Open", "Sent", "Checked", "Missed")
TASK_TITLE = "TitleText"
TASK_QUESTION_PREFIX = "Question_"
TASK_SUBMIT = "SubmitButton"
TASK_ANSWER_PREFIX = "Answer_Visual"        # Answer_Visual_<shown>_Data_<original>
TASK_MULTIPLE_CHOICE = "MultipleChoiceContent(Clone)"
# Submit only ASKS: it raises a yes/no popup, and the task is not sent
# until Yes is pressed.
TASK_CONFIRM_POPUP = "YesNoPopup(Clone)"
TASK_CONFIRM_YES = "YesButton"
# How long a submitted task is given to appear on the server. The app sits
# on the task uploading it -- measured at about 90 seconds.
TASK_RECORD_TIMEOUT = 120
# After a task is sent, how long to let the app settle back onto the Tasks
# screen before opening the next one. A ceiling, not a sleep: the run goes on
# as soon as the screen is there and has stopped changing.
TASK_NEXT_TIMEOUT = 20
# The task's own status on the server: 2 = the app has CHECKED (scored) it.
TASK_STATUS_CHECKED = 2
# How long to wait for a submitted task to be marked checked before going on
# to the next one. A ceiling, not a sleep.
TASK_CHECKED_TIMEOUT = 20


def task_tab_counts(altdriver):
    """``{"Open": "2 Open", ...}`` — each tab's own count, read off the screen."""
    counts = {}
    for tab in TASK_TABS:
        try:
            obj = altdriver.find_object(By.PATH, f"//{tab}-NavigationTab//NumTasksText")
            counts[tab] = _text_of(obj) or ""
        except Exception:                            # noqa: BLE001
            counts[tab] = ""
    return counts


def _task_count(text):
    """"2 Open" -> 2. Unreadable -> None, which is NOT the same as zero."""
    match = re.search(r"\d+", str(text or ""))
    return int(match.group()) if match else None


def task_questions(altdriver):
    """The question chips on the strip, in order: ``["Question_1", ...]``."""
    try:
        found = [e.name for e in (altdriver.get_all_elements() or [])
                 if e.name.startswith(TASK_QUESTION_PREFIX)]
    except Exception:                                # noqa: BLE001
        return []
    def number(name):
        digits = re.findall(r"\d+", name)
        return int(digits[-1]) if digits else 0
    return sorted(set(found), key=number)


def task_answers(altdriver):
    """The answer toggles of the question on screen, in the order SHOWN.

    Named ``Answer_Visual_<shown>_Data_<original>``: the visual slot is
    shuffled per question, so the Data index says nothing about which is
    correct — measured live, Data_0 was the wrong answer on question 2.
    """
    try:
        found = [e.name for e in (altdriver.get_all_elements() or [])
                 if e.name.startswith(TASK_ANSWER_PREFIX)]
    except Exception:                                # noqa: BLE001
        return []
    def shown(name):
        digits = re.findall(r"\d+", name)
        return int(digits[0]) if digits else 0
    return sorted(set(found), key=shown)


def task_answer_selected(altdriver, answer):
    """Is this answer chosen? Reads the Toggle, which is the real state.

    The `selectedAnswer` child exists on every answer whether chosen or not, so
    its presence proves nothing — and its active flag cannot be read.
    """
    try:
        obj = altdriver.find_object(By.NAME, answer)
        return bool(obj.get_component_property("UnityEngine.UI.Toggle", "isOn",
                                               "UnityEngine.UI"))
    except Exception:                                # noqa: BLE001
        return False


def task_answer_question(altdriver, settle=1.2):
    """Answer the question on screen. Returns ``(answered, note)``.

    Only multiple choice is automated. A task can also ask for TEXT or a
    RECORDING; those are reported, never silently passed over.
    """
    if find_any(altdriver, TASK_MULTIPLE_CHOICE) is None:
        return False, "not a multiple-choice question (text or recording?)"

    answers = task_answers(altdriver)
    if not answers:
        return False, "a multiple-choice question with no answers on screen"
    if any(task_answer_selected(altdriver, a) for a in answers):
        return True, ""                              # already answered

    for answer in answers:
        if not press_object(altdriver, answer, settle=settle):
            continue
        if task_answer_selected(altdriver, answer):
            return True, ""
    return False, f"none of {len(answers)} answers would select"


# The task API. The answer key is NOT in the game: the app never marks an option
# as correct, and no component exposes it (measured -- the driver cannot even
# enumerate fields). It comes from the backend, where a sub-task carries its
# options and a `correct_answer` naming the right one BY ID.
#
# The id is the link that makes this usable: `parameters[].id` is exactly the
# Data index in `Answer_Visual_<shown>_Data_<id>`, so "correct_answer: 1" means
# press the answer whose name ends `_Data_1`, wherever it happens to be shown.
# The environment the app under test talks to. `green` is where the task data
# lives for the accounts these tests use; override with VT_TASKS_API when
# pointing at another environment.
_VT_TASKS_API_DEFAULT = "https://green.vocatooki.com/data"
VT_TASKS_API = (__import__("os").getenv("VT_TASKS_API")
                or _VT_TASKS_API_DEFAULT)


# The login the APP itself uses. It answers with everything a task run needs to
# know about the player -- their id, their class, and which backend their data
# lives on -- so none of it has to be written into a Rally case, where it goes
# stale the moment the case is pointed at another account. (That mismatch once
# looked exactly like the app losing a student's answers.)
VT_PLAYER_LOGIN_URL = "https://login.vocatooki.com/access/login"
VT_PLAYER_EMAIL_DOMAIN = "@vocatooki.com"
_PLAYER_CACHE = {}


def vt_player(username, password):
    """``{"user_id", "class_id", "backend"}`` for a player, or ``{}``.

    The login wants the EMAIL form of the username: "vt233640" alone is refused,
    "vt233640@vocatooki.com" is accepted.
    """
    if not username or not password:
        return {}
    cached = _PLAYER_CACHE.get((username, password))
    if cached is not None:
        return cached

    email = username if "@" in str(username) else f"{username}{VT_PLAYER_EMAIL_DOMAIN}"
    try:
        # The payload the app itself sends: username AND email (both the email
        # form -- the bare "vt233640" is refused), the password, and the game.
        r = requests.post(VT_PLAYER_LOGIN_URL,
                          json={"username": email, "email": email,
                                "password": str(password), "game": VT_GAME},
                          headers={"Content-Type": "application/json",
                                   "Accept": "application/json"}, timeout=25)
        r.raise_for_status()
        data = r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not look up '{username}': {e}")
        _PLAYER_CACHE[(username, password)] = {}
        return {}

    who = {"user_id": data.get("id"), "class_id": data.get("class_id"),
           "backend": (data.get("backend") or "").rstrip("/")}
    if who["user_id"]:
        logging.info(f"[Tasks] '{username}' is player {who['user_id']} "
                     f"in class {who['class_id']} on {who['backend'] or 'the default backend'}")
    _PLAYER_CACHE[(username, password)] = who
    return who


def task_api_headers(token=None):
    """Bearer headers for the task API, logging in once if needed."""
    return get_auth_headers(token=token)


def class_tasks(class_id, token=None):
    """``[{"id", "name", ...}]`` — the tasks set for a class."""
    try:
        r = requests.get(f"{VT_TASKS_API}/get-class-tasks/{class_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not list the class's tasks: {e}")
        return []


def user_class_id(user_id, token=None):
    """The class this player's tasks belong to, or None.

    Saves the Rally case from carrying a class id that is only ever right for
    one account: `get-user-tasks` answers with `taskid_classid` ("651_2336"),
    so the class falls out of the player id on its own.
    """
    try:
        r = requests.get(f"{VT_TASKS_API}/get-user-tasks/{user_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        for entry in (r.json() or []):
            pair = str(entry.get("taskid_classid") or "")
            if "_" in pair:
                return int(pair.split("_", 1)[1])
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not work out the class for user {user_id}: {e}")
    return None


def task_answer_key(task_id, token=None):
    """``[{"index", "type", "question", "correct", "options"}]`` for a task.

    ``correct`` is the id to press (the `Data_` index), and ``options`` maps
    every id to its text, so a WRONG answer can be chosen deliberately too.
    """
    try:
        r = requests.get(f"{VT_TASKS_API}/get-task/{task_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        task = r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not read task {task_id}: {e}")
        return []

    key = []
    for index, sub in enumerate(task.get("sub_tasks") or [], start=1):
        data = sub.get("data") or {}
        options = {int(p.get("id")): p.get("freetext")
                   for p in (data.get("parameters") or [])
                   if p.get("id") is not None}
        key.append({
            "index": index,
            "type": sub.get("type") or "",
            "question": data.get("task_question") or "",
            "correct": data.get("correct_answer"),
            "options": options,
        })
    return key


def task_submitted_answers(user_id, task_id, token=None, attempt=0):
    """What the SERVER recorded for this user's attempt, or {}.

    The honest proof a run worked: `choosenAnswer` against `correctAnswer` per
    question, and the `result` the task scored -- read back from the backend
    rather than inferred from a tab count.
    """
    try:
        r = requests.get(
            f"{VT_TASKS_API}/get-task-answer/{user_id}/{task_id}/{attempt}",
            headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        return r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not read the submitted answers: {e}")
        return {}


def wait_for_task_recorded(user_id, task_id, timeout=90, poll=5):
    """Wait until the SERVER has stored this submission. Returns the record.

    Submitting is not instant: the app sits on the task while it uploads, and
    reading the answers straight afterwards comes back empty -- which reads
    exactly like a submit that never happened. Waiting for the record is also
    what makes it safe to go on to the NEXT task: the run only moves once the
    server agrees the last one landed.
    """
    end = time.time() + timeout
    while True:
        stored = task_submitted_answers(user_id, task_id)
        if stored.get("answer"):
            logging.info(f"[Tasks] the server recorded task {task_id} "
                         f"({len(stored['answer'])} answer(s), "
                         f"result={stored.get('result')})")
            return stored
        if time.time() >= end:
            logging.error(f"[Tasks] the server never recorded task {task_id} "
                          f"within {timeout}s")
            return stored
        time.sleep(poll)


def task_answer_by_data_id(altdriver, data_id, settle=1.2):
    """Press the answer whose name ends ``_Data_<data_id>``. Returns bool.

    The visual slot is shuffled per question, so the answer is chosen by its
    DATA id -- the one thing that means the same on every render.
    """
    wanted = f"_Data_{int(data_id)}"
    for name in task_answers(altdriver):
        if not name.endswith(wanted):
            continue
        # Already chosen (a re-opened task keeps its answers): pressing again
        # would toggle it back OFF and read as a failure.
        if task_answer_selected(altdriver, name):
            return True
        if press_object(altdriver, name, settle=settle):
            return task_answer_selected(altdriver, name)
        return False
    logging.error(f"[Tasks] no answer ending '{wanted}' on this question")
    return False


def _tasks_answer_key_for(title, class_id, user_id):
    """``(key, task_id)`` for the task with this title, or ``([], None)``."""
    if not class_id and user_id:
        class_id = user_class_id(user_id)
        if class_id:
            logging.info(f"[Tasks] class {class_id} discovered from user {user_id}")
    if not class_id:
        return [], None
    wanted = (title or "").strip().lower()
    for entry in class_tasks(class_id):
        if str(entry.get("name", "")).strip().lower() == wanted:
            return task_answer_key(entry.get("id")), entry.get("id")
    return [], None


def wait_for_task_checked(user_id, task_id, timeout=TASK_CHECKED_TIMEOUT, poll=3):
    """Wait until the server marks this task CHECKED. Returns the record.

    Recorded and checked are two different moments: the answers land first, and
    the app scores them a beat later. Waiting for the score means the next task
    starts from a settled account, and that the `result` read back is the real
    one rather than whatever was there mid-scoring.

    A ceiling, not a sleep -- and NOT a failure on its own if the status never
    arrives: the answers are already stored, so the run says so and goes on.
    """
    end = time.time() + timeout
    stored = {}
    while True:
        stored = task_submitted_answers(user_id, task_id)
        if stored.get("status") == TASK_STATUS_CHECKED:
            logging.info(f"[Tasks] task {task_id} is CHECKED "
                         f"(result={stored.get('result')})")
            return stored
        if time.time() >= end:
            logging.warning(f"[Tasks] task {task_id} was not marked checked within "
                            f"{timeout}s (status={stored.get('status')})")
            return stored
        time.sleep(poll)


def _tasks_settle_for_next(altdriver, timeout=TASK_NEXT_TIMEOUT):
    """Wait for the Tasks screen to come back and stop changing. Returns bool.

    Between two tasks the app has to put the finished one away -- the tab
    counts re-count and the card list rebuilds -- and a card pressed mid-rebuild
    is a press that lands on nothing. A ceiling rather than a sleep: as soon as
    the screen is there and settled, the run goes on.
    """
    end = time.time() + timeout
    while time.time() < end:
        if _current_scene(altdriver) == TASKS_SCENE:
            left = max(1.0, end - time.time())
            wait_for_scene_ready(altdriver, timeout=left, stable_for=1.0,
                                 label="tasks list")
            logging.info("[Tasks] the Tasks screen is settled; on to the next task")
            return True
        time.sleep(1.0)
    logging.info(f"[Tasks] still on {_current_scene(altdriver)} after {timeout}s; "
                 f"carrying on to the next task anyway")
    return False


def _tasks_solve_one(altdriver, trail, class_id=None, user_id=None,
                     wrong_answers=0, submit=True, timeout=90):
    """Open the first OPEN task, answer it, submit it. One task, never raises.

    Returns a record of that task alone; ``tasks_check`` stitches the records
    together. Split out so the run can go on to the NEXT task without the
    login, the tab counts and the final verdict being redone each time.
    """
    out = {"title": "", "task_id": None, "questions": 0, "answered": 0,
           "wrong": [], "unsupported": [], "submitted": False, "checked": False,
           "server": {}, "problems": [], "data_issues": [], "note": ""}

    try:
        card = altdriver.find_object(By.PATH, f"//{TASK_CARD_OPEN}[0]")
        out["title"] = _text_of(altdriver.find_object(
            By.PATH, f"//{TASK_CARD_OPEN}[0]//TaskText")) or ""
        _press(card)
    except Exception as e:                           # noqa: BLE001
        out["note"] = f"the open task card could not be opened: {e}"
        return out
    if not wait_for_scene(altdriver, TASK_SCENE, timeout=timeout):
        out["note"] = f"'{out['title']}' did not open into the task"
        return out
    trail.shot(altdriver, f"task-{_slugish(out['title'])}-opened", EVIDENCE_PROOF)

    questions = task_questions(altdriver)
    out["questions"] = len(questions)
    if not questions:
        out["note"] = f"'{out['title']}' shows no questions"
        return out
    logging.info(f"[Tasks] '{out['title']}': {len(questions)} question(s)")

    key, out["task_id"] = _tasks_answer_key_for(out["title"], class_id, user_id)
    if key:
        logging.info(f"[Tasks] answer key for '{out['title']}': {len(key)} question(s)")
    else:
        # Without the key the answers would be arbitrary, and the task is
        # SCORED -- a run must not post a bad score to a real teacher's task and
        # call it a pass. Said out loud, and nothing is sent.
        out["problems"].append(
            f"no answer key for '{out['title']}': without it the answers would "
            'be arbitrary on a task that is scored. Add "Class ID: <n>" to the '
            "Rally case.")
        submit = False

    # Which questions to get WRONG on purpose: the last ones, so a correct
    # answer is still exercised first.
    deliberately_wrong = set()
    if wrong_answers and key:
        deliberately_wrong = {e["index"] for e in key[-int(wrong_answers):]}

    for index, question in enumerate(questions, start=1):
        if not press_object(altdriver, question, settle=1.5):
            out["problems"].append(f"question {index} could not be opened")
            continue
        wait_for_scene_ready(altdriver, timeout=6, stable_for=0.8, label=question)

        entry = next((e for e in key if e["index"] == index), None)
        if entry is not None and entry.get("correct") is not None:
            correct = int(entry["correct"])
            if entry["options"] and correct not in entry["options"]:
                # The task's own data is wrong -- measured: 'a/an' Q5 and Q8 say
                # correct_answer 3 while the options are only 0 and 1. Leaving
                # the question blank would block the whole task, so an option is
                # chosen and the bad data is reported.
                fallback = sorted(entry["options"])[0]
                # Reported, but NOT a problem with the run: the task's content
                # is wrong, which the test should surface without failing for a
                # defect outside its own subject.
                out["data_issues"].append(
                    f"'{out['title']}' Q{index}: the task data says the correct "
                    f"answer is {correct}, which is not one of its options "
                    f"{sorted(entry['options'])} - answered "
                    f"{entry['options'][fallback]!r} instead")
                correct = fallback
            if index in deliberately_wrong:
                choice = next((i for i in entry["options"] if i != correct), correct)
                out["wrong"].append(
                    f"{out['title']} Q{index}: chose "
                    f"{entry['options'].get(choice)!r} instead of "
                    f"{entry['options'].get(correct)!r}")
            else:
                choice = correct
            if task_answer_by_data_id(altdriver, choice):
                out["answered"] += 1
                continue
            out["problems"].append(
                f"question {index}: could not press the answer Data_{choice}")
            continue

        answered, why = task_answer_question(altdriver)
        if answered:
            out["answered"] += 1
        else:
            # A task can also ask for TEXT or a RECORDING, and neither is
            # automated here. Never passed over quietly.
            out["unsupported"].append(f"{out['title']} Q{index}: {why}")
            logging.warning(f"[Tasks] question {index} not answered - {why}")

    trail.shot(altdriver, f"{_slugish(out['title'])}-answered-"
                          f"{out['answered']}-of-{out['questions']}", EVIDENCE_PROOF)

    if out["unsupported"]:
        out["note"] = (f"{len(out['unsupported'])} of {out['questions']} question(s) "
                       f"are not automatable, so '{out['title']}' was NOT submitted")
        return out                                   # never send a half-done task
    if out["answered"] != out["questions"]:
        # The app refuses a part-answered task and records NOTHING, leaving it
        # Open -- measured: submitting 18 of 20 stored 0 answers, and the run
        # then met the same task again. Better to stop and say which questions
        # were missed.
        out["problems"].append(
            f"'{out['title']}': only {out['answered']} of {out['questions']} "
            f"question(s) could be answered, so it was NOT submitted")
        out["note"] = out["problems"][-1]
        return out

    if not submit:
        out["note"] = (f"answered {out['answered']}/{out['questions']}; "
                       f"'{out['title']}' was not submitted")
        return out

    if not press_object(altdriver, TASK_SUBMIT, settle=2.0):
        out["problems"].append("Submit could not be pressed")
        return out

    # Submit only ASKS. It opens a YesNoPopup(Clone), and until Yes is pressed
    # nothing is sent -- measured live: a run sat on TaskScene with the tab
    # counts unmoved, having "submitted" a task that never left.
    if wait_for_any(altdriver, (TASK_CONFIRM_POPUP, TASK_CONFIRM_YES), timeout=10):
        trail.shot(altdriver, f"{_slugish(out['title'])}-submit-confirm", EVIDENCE_STEP)
        if not press_object(altdriver, TASK_CONFIRM_YES, settle=3.0):
            out["problems"].append(
                "the submit confirmation appeared but Yes could not be pressed")
            return out
        logging.info("[Tasks] confirmed the submit")
    else:
        logging.warning("[Tasks] no submit confirmation appeared")
    out["submitted"] = True

    # LEAVE the task before waiting for the server. The app shows its own
    # checked screen straight after the confirm, but the answers do not reach
    # the server until the task is exited -- measured: a run that sat on that
    # screen polling for 120s never saw the record appear, while the same task
    # submitted by code that navigated away first was stored within seconds.
    if not wait_for_scene(altdriver, TASKS_SCENE, timeout=20):
        return_to_start(altdriver)
        open_feature(altdriver, "tasks", timeout=timeout)

    # Only now is it worth asking the server. Waiting here is also what makes
    # going on to the NEXT task safe.
    if user_id and out["task_id"]:
        stored = wait_for_task_recorded(user_id, out["task_id"],
                                        timeout=TASK_RECORD_TIMEOUT)
        # Then wait for it to be CHECKED, so the score read back is the settled
        # one and the next task starts from a quiet account.
        checked = wait_for_task_checked(user_id, out["task_id"],
                                        timeout=TASK_CHECKED_TIMEOUT)
        if checked.get("answer"):
            stored = checked
        out["checked"] = stored.get("status") == TASK_STATUS_CHECKED
        answers = stored.get("answer") or []
        right = sum(1 for a in answers
                    if a.get("choosenAnswer") == a.get("correctAnswer"))
        out["server"] = {"result": stored.get("result"),
                         "status": stored.get("status"),
                         "answers": len(answers), "correct": right,
                         "incorrect": len(answers) - right}
        if not answers:
            # Cost a whole investigation once: the id in the Rally case belonged
            # to a DIFFERENT player, so the answers were looked for under
            # somebody else and the run read as data loss.
            out["problems"].append(
                f"the server has no answers for '{out['title']}' under user "
                f"{user_id}. The task WAS submitted, so check that the User ID "
                f"in the Rally case is this account's — an id belonging to "
                f"another player looks exactly like a submit that vanished.")
        elif len(answers) != out["questions"]:
            out["problems"].append(
                f"the server recorded {len(answers)} answer(s) for "
                f"{out['questions']} question(s) of '{out['title']}'")
        expected_wrong = len(out["wrong"]) + len(out["data_issues"])
        if key and (len(answers) - right) != expected_wrong:
            out["problems"].append(
                f"'{out['title']}': {len(answers) - right} answer(s) came back "
                f"wrong, but {expected_wrong} were expected to "
                f"({len(out['wrong'])} answered wrong on purpose, "
                f"{len(out['data_issues'])} unanswerable in the task data)")
    out["note"] = (f"'{out['title']}': answered {out['answered']}/{out['questions']}, "
                   f"submitted, {'checked' if out['checked'] else 'NOT yet checked'}, "
                   f"server result {out['server'].get('result')}")
    logging.info(f"[Tasks] {out['note']}")
    return out


def tasks_check(altdriver, username=None, password=None, tc_id="",
                submit=True, timeout=90, class_id=None, user_id=None,
                wrong_answers=0, max_tasks=None):
    """Solve the account's OPEN tasks and prove the server recorded them.

    Works through EVERY open task by default, going back to the Tasks screen
    between them; ``max_tasks`` caps how many. A task is answered from the
    backend ANSWER KEY, so it is answered CORRECTLY -- except for
    ``wrong_answers`` questions per task chosen on purpose, which exercise the
    wrong-answer path and show up in the score. Those are reported by name,
    because a run that quietly answered badly and one that deliberately
    answered badly must not look the same.

    A task is scored by the app and lands in CHECKED; only what a teacher must
    read waits in Sent. Never raises.
    """
    report = {"ok": False, "tasks": [], "solved": 0, "checked": 0, "title": "",
              "player": {}, "data_issues": [], "questions": 0,
              "answered": 0, "unsupported": [], "wrong": [], "counts_before": {},
              "counts_after": {}, "submitted": False, "server": {},
              "expected_incorrect": 0, "problems": [], "note": ""}

    reset_evidence_trail(tc_id)
    trail = evidence_trail(tc_id)

    # Who is this player? Asked of the login the app itself uses, so the id, the
    # class and the backend all come from the ACCOUNT rather than from numbers
    # typed into a Rally case -- where they go stale the moment the case is
    # pointed at somebody else, and a stale id looks exactly like the app losing
    # a student's answers. Anything passed in explicitly still wins.
    if username and password:
        who = vt_player(username, password)
        if who.get("user_id"):
            user_id = user_id or who["user_id"]
            class_id = class_id or who.get("class_id")
            report["player"] = who
            if who.get("backend"):
                globals()["VT_TASKS_API"] = f"{who['backend']}/data"
        elif not user_id:
            report["note"] = (f"could not look up '{username}' - without the "
                              f"player id the answers cannot be checked")
            return report

    if username and not fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not open_feature(altdriver, "tasks", username, password, timeout=timeout):
        report["note"] = "the Tasks screen did not open"
        return report

    report["counts_before"] = task_tab_counts(altdriver)
    trail.shot(altdriver, "tasks-BEFORE", EVIDENCE_KEY)
    open_before = _task_count(report["counts_before"].get("Open"))
    logging.info(f"[Tasks] tabs before: {report['counts_before']}")

    if find_any(altdriver, TASK_CARD_OPEN) is None:
        report["note"] = ("there is no OPEN task on this account to solve "
                          f"(tabs: {report['counts_before']})")
        return report

    limit = int(max_tasks) if max_tasks else 0        # 0 = every open task
    seen_titles = []
    while True:
        if limit and len(report["tasks"]) >= limit:
            break
        # Back on the Tasks screen, is there still something to answer?
        if _current_scene(altdriver) != TASKS_SCENE:
            return_to_start(altdriver)
            if not open_feature(altdriver, "tasks", timeout=timeout):
                report["problems"].append(
                    "could not get back to the Tasks screen for the next task")
                break
        if find_any(altdriver, TASK_CARD_OPEN) is None:
            break                                    # nothing open left

        one = _tasks_solve_one(altdriver, trail, class_id=class_id, user_id=user_id,
                               wrong_answers=wrong_answers, submit=submit,
                               timeout=timeout)
        report["tasks"].append(one)

        if one["submitted"]:
            # Let the app finish putting the task away before the next one is
            # opened: the tabs re-count and the card list rebuilds, and opening
            # a card mid-rebuild is how a press lands on nothing.
            _tasks_settle_for_next(altdriver, timeout=TASK_NEXT_TIMEOUT)

        # A task that could not be submitted would still be sitting in Open, so
        # trying again would open the SAME card forever.
        if not one["submitted"]:
            report["problems"].extend(one["problems"] or [])
            if one["note"]:
                report["problems"].append(one["note"])
            break
        if one["title"] and one["title"] in seen_titles:
            report["problems"].append(
                f"'{one['title']}' came round a second time - stopping rather "
                f"than solving the same task twice")
            break
        seen_titles.append(one["title"])

    # Stitch the per-task records into one picture.
    for one in report["tasks"]:
        report["questions"] += one["questions"]
        report["answered"] += one["answered"]
        report["wrong"].extend(one["wrong"])
        report["unsupported"].extend(one["unsupported"])
        report["problems"].extend(p for p in one["problems"]
                                  if p not in report["problems"])
        report["data_issues"].extend(one.get("data_issues") or [])
    report["solved"] = sum(1 for o in report["tasks"] if o["submitted"])
    report["checked"] = sum(1 for o in report["tasks"] if o.get("checked"))
    report["title"] = ", ".join(o["title"] for o in report["tasks"] if o["title"])
    report["submitted"] = bool(report["tasks"]) and all(
        o["submitted"] for o in report["tasks"])
    # What SHOULD come back wrong: the ones answered wrong on purpose, plus the
    # ones that cannot be answered correctly at all. A question whose
    # correct_answer is not among its options is guaranteed to score wrong
    # however it is answered -- counting only the deliberate ones failed a run
    # that had done everything right ('a/an' Q5 and Q8).
    report["expected_incorrect"] = len(report["wrong"]) + len(report["data_issues"])
    served = [o["server"] for o in report["tasks"] if o["server"]]
    if served:
        report["server"] = {
            "answers": sum(s.get("answers", 0) for s in served),
            "correct": sum(s.get("correct", 0) for s in served),
            "incorrect": sum(s.get("incorrect", 0) for s in served),
            "results": [s.get("result") for s in served],
        }

    if _current_scene(altdriver) != TASKS_SCENE:
        return_to_start(altdriver)
        open_feature(altdriver, "tasks", timeout=timeout)
    report["counts_after"] = task_tab_counts(altdriver)
    trail.shot(altdriver, "tasks-AFTER", EVIDENCE_KEY)
    open_after = _task_count(report["counts_after"].get("Open"))
    logging.info(f"[Tasks] tabs after: {report['counts_after']}")

    if report["solved"]:
        if None in (open_before, open_after):
            report["problems"].append(
                f"the tab counts could not be read ({report['counts_before']} -> "
                f"{report['counts_after']})")
        elif open_after >= open_before:
            # A drop, not a drop of exactly one per task: submitting one task
            # was measured moving TWO out of Open (3 -> 1, Checked 0 -> 2),
            # because the app settles whatever else it had already scored.
            report["problems"].append(
                f"Open went {open_before} -> {open_after}: submitting a task "
                f"should take it out of Open")

    report["ok"] = (bool(report["solved"]) and report["submitted"]
                    and not report["problems"]
                    and report["answered"] == report["questions"])
    report["note"] = report["note"] or (
        f"Solved {report['solved']} task(s), {report['checked']} checked "
        f"({report['title'] or 'none'}): "
        f"answered {report['answered']} of {report['questions']} question(s), "
        f"{report['expected_incorrect']} expected wrong "
        f"({len(report['wrong'])} on purpose, "
        f"{len(report['data_issues'])} unanswerable in the task data). "
        f"Open {open_before} -> {open_after}, "
        f"Checked {report['counts_before'].get('Checked')} -> "
        f"{report['counts_after'].get('Checked')}. "
        f"Server: {report['server'] or 'not read'}."
        + (f" CONTENT ISSUES in the task data (not an automation fault): "
           f"{report['data_issues']}." if report["data_issues"] else "")
        + (f" Problems: {report['problems']}." if report["problems"] else ""))
    logging.info(f"[Tasks] {report['note']}")
    return report


def _slugish(text, limit=24):
    """A short, filename-safe version of a title."""
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text or "")).strip("-")[:limit] or "task"


# --- Treasure Island: missions, islands, and the buildings on them ---------
#
# Surveyed live 2026-08-17. The whole feature is reachable BY OBJECT, which is
# what makes it automatable at all (see the no-coordinate-clicks rule).

TREASURE_ISLAND_SCENE = "TreasureIsland"
TI_INTRO_SKIP = "Skip"                    # the first-entry intro's pager
TI_MISSIONS_BUTTON = "TaskSummary"        # the clipboard, top left
TI_LEVEL_TEXT = "LevelText"               # "Level 1"
TI_PERCENT_TEXT = "PercentText"           # "0%"
TI_ROW = "CategorySummaryRow(Clone)"      # one per required skill
TI_ROW_PLAY = "PlayButton"                # gone once the skill is complete
TI_PANEL_PLAY = "PlayButton"              # the SAME name on a building's panel
TI_MISSIONS_EXIT = "ExitButton"
TI_ISLAND_PREFIX = "Category_"            # Category_3-Context, ...
TI_LOCK_HOLDER = "Lock-Place_Holder"
TI_LOCK_FOG = "GO-TI-Lock_Fog"
TI_BUILDING_PREFIX = "GO-TI-"

# The mission row names a SKILL; the island object names a CATEGORY, and they
# are not always the same word — the "Sentences" row is `Category_3-Context`.
# Anything not listed here matches the island whose name ends with the skill.
TI_ISLAND_ALIASES = {"sentences": "context"}

# There is no solver for Speaking anywhere in this framework. The rule the user
# set: skip it, and SAY SO in the result — never silently ignore it.
TI_NO_AUTOMATION = ("speaking",)

# A mission slider is 0.0 .. 1.0; this is what counts as finished.
TI_COMPLETE = 0.999

# How long the building's activity panel is given to finish fading in before
# its Play is pressed, and how many times that press is repeated when the
# activity does not start. Both measured live (2026-08-17).
TI_PANEL_SETTLE_SECONDS = 3.0
TI_PLAY_ATTEMPTS = 3


def _wait_leaves_scene(altdriver, scene, timeout=15, poll=0.5):
    """Wait until the app is no longer in ``scene``. Returns bool.

    Used as PROOF that a press landed: on Treasure Island nothing else
    distinguishes a Play that started an activity from one the panel swallowed.
    """
    end = time.time() + timeout
    while time.time() < end:
        if _current_scene(altdriver) != scene:
            return True
        time.sleep(poll)
    return False


def _ti_short(building):
    """`GO-TI-Break_Out Variant(Clone)` -> `Break_Out`, for a readable filename."""
    return (str(building).replace(TI_BUILDING_PREFIX, "")
            .replace(" Variant(Clone)", "").strip() or "building")


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


def ti_skip_intro(altdriver):
    """Press the intro's Skip when it is showing. True if it was pressed."""
    if find_any(altdriver, TI_INTRO_SKIP) is None:
        return False
    return press_object(altdriver, TI_INTRO_SKIP, settle=2.0)


def ti_open_missions(altdriver, timeout=30):
    """Open the mission list from the clipboard. True once it is readable."""
    ti_skip_intro(altdriver)
    if find_any(altdriver, TI_LEVEL_TEXT) is not None:
        return True                              # already open
    press_object(altdriver, TI_MISSIONS_BUTTON, settle=2.5)
    return wait_for_any(altdriver, (TI_LEVEL_TEXT,), timeout=timeout)


def ti_level(altdriver):
    """``("Level 1", "0%")`` from the open mission list."""
    level = find_any(altdriver, TI_LEVEL_TEXT)
    percent = find_any(altdriver, TI_PERCENT_TEXT)
    return (_text_of(level) if level else "",
            _text_of(percent) if percent else "")


def _ti_percent(text):
    """``"75%"`` -> ``75.0``. Unreadable -> ``0.0``."""
    try:
        return float(str(text).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def ti_missions(altdriver):
    """The mission rows: ``[{"index", "skill", "progress", "automatable"}]``.

    Rows are walked by INDEXED PATH rather than by scanning loose objects, so a
    skill always keeps its own progress bar even though every row uses the same
    object names.
    """
    rows = []
    try:
        found = altdriver.find_objects(By.NAME, TI_ROW) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read the mission rows: {e}")
        return rows

    for i in range(len(found)):
        skill, progress = "", None
        try:
            skill = _text_of(altdriver.find_object(
                By.PATH, f"//{TI_ROW}[{i}]//CategoryText")) or ""
        except Exception:                            # noqa: BLE001
            pass
        try:
            slider = altdriver.find_object(
                By.PATH, f"//{TI_ROW}[{i}]//Progress//Slider")
            progress = float(slider.get_component_property(
                "UnityEngine.UI.Slider", "value", "UnityEngine.UI"))
        except Exception:                            # noqa: BLE001
            pass

        # A FINISHED skill swaps its row to the completion layer, and the
        # slider stops answering — reading that as "progress unknown" would
        # send the run off to replay a skill it had already completed.
        # A FINISHED skill's row loses its Play button, its Progress and its
        # slider outright — measured live, they stop resolving. That absence is
        # the completion signal: `completedIcon` is no use because it exists on
        # every row finished or not, and its active flag cannot be read (the
        # property raises on these objects).
        has_play = True
        try:
            altdriver.find_object(By.PATH, f"//{TI_ROW}[{i}]//{TI_ROW_PLAY}")
        except Exception:                            # noqa: BLE001
            has_play = False
        done = progress is None and not has_play
        if done:
            progress = 1.0

        rows.append({
            "index": i,
            "skill": skill,
            "progress": progress,
            "done": done,
            "automatable": skill.strip().lower() not in TI_NO_AUTOMATION,
        })
    return rows


def ti_press_row_play(altdriver, index, settle=4.0):
    """Press one mission row's Play. Rows are addressed by INDEXED PATH.

    Not ``press_object``: every row's button is called `PlayButton`, so a press
    by name would play whichever row the app hands back first.
    """
    try:
        button = altdriver.find_object(By.PATH, f"//{TI_ROW}[{index}]//PlayButton")
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] row {index} has no Play button: {e}")
        return False
    if not _press(button):
        return False
    logging.info(f"[TI] pressed Play on row {index}")
    time.sleep(settle)
    return True


def _ti_elements(altdriver):
    """``(elements, by_id)`` for one walk of the scene tree, INACTIVE included.

    ``get_all_elements()`` defaults to ``enabled=True``, and that breaks the
    walk from a building up to its island: one inactive node in the chain and
    the walk simply stops. That is how a live run reported "Category_2-Reading
    has no buildings to play" about an island covered in them.
    """
    try:
        elements = altdriver.get_all_elements(enabled=False) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read the scene: {e}")
        return [], {}
    return elements, {e.id: e for e in elements}


def ti_island_for_skill(altdriver, skill):
    """The island object for a mission row's skill, or "".

    Play does NOT change scene — it zooms the camera — and every island's
    buildings stay findable whichever one is in front. So the island a skill
    belongs to has to be resolved by NAME here; there is no "what is on screen"
    to ask.
    """
    wanted = TI_ISLAND_ALIASES.get(skill.strip().lower(), skill.strip().lower())
    elements, _by_id = _ti_elements(altdriver)
    for element in elements:
        if not element.name.startswith(TI_ISLAND_PREFIX):
            continue
        # "Category_3-Context" -> "context"
        if element.name.split("-", 1)[-1].strip().lower() == wanted:
            return element.name
    return ""


def ti_island_locked(altdriver, island):
    """Is this island still fogged over?

    The lock is PER ISLAND (`Category_N-X/Lock-Place_Holder/GO-TI-Lock_Fog`), so
    a bare search for the fog object answers about whichever island happens to
    be locked rather than about this one.

    Measured live: the fog object EXISTS only under a locked island (Writing had
    one, the four open islands had none), so its presence is the answer and no
    active flag has to be read — which matters, because reading one off these
    objects raises.
    """
    try:
        return bool(altdriver.find_objects(By.PATH, f"//{island}//{TI_LOCK_FOG}"))
    except Exception:                                # noqa: BLE001
        return False


def ti_buildings(altdriver, island):
    """The activity buildings on one island, by object name.

    Found by PATH, under the island itself. Walking up from a building instead
    cannot work: an object's ``transformParentId`` is a TRANSFORM id while its
    ``id`` is a GameObject id, so the two never match and every island came
    back empty.

    The buildings are NAMED FOR THEIR ACTIVITY, which is the whole reason this
    is automatable: `GO-TI-Puzzles Variant(Clone)` opens the puzzles activity,
    for which a solver already exists.
    """
    try:
        found = altdriver.find_objects(By.PATH, f"//{island}//Cntrl_Resize/*") or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read {island}'s buildings: {e}")
        return []
    names = {obj.name for obj in found
             if obj.name.startswith(TI_BUILDING_PREFIX)
             and "Variant(Clone)" in obj.name}       # not locks, tubes or bars
    if not names:
        logging.error(f"[TI] no buildings found under '{island}'")
    return sorted(names)


def ti_play_building(altdriver, building, timeout=90, tc_id="", trail=None):
    """Open one building and play what it starts. Never raises.

    Tapping a building opens an in-scene panel (an `ActivityCard` and a single
    `PlayButton`); that Play loads the real ACTIVITY SCENE, so the framework's
    own solvers finish the job. Returns ``{"building", "activity", "played",
    "note"}``.
    """
    out = {"building": building, "activity": "", "played": False, "note": ""}

    if not press_object(altdriver, building, settle=3.0):
        out["note"] = f"the building '{building}' could not be pressed"
        return out
    if not wait_for_any(altdriver, ("PlayButton",), timeout=15):
        out["note"] = f"'{building}' opened no activity panel"
        if trail:
            trail.shot(altdriver, f"{_ti_short(building)}-no-panel", EVIDENCE_KEY)
        return out
    if trail:
        # WHICH building was chosen, and the card it offered.
        trail.shot(altdriver, f"{_ti_short(building)}-panel")

    # The panel fades in, and a Play pressed into that animation is SWALLOWED —
    # the panel just stays open. Measured live: the very press that did nothing
    # mid-animation started the activity once the panel had settled. So the
    # press is proven by the scene leaving Treasure Island, and repeated when
    # it is not, instead of being assumed to have landed.
    time.sleep(TI_PANEL_SETTLE_SECONDS)
    started = False
    for attempt in range(1, TI_PLAY_ATTEMPTS + 1):
        press_object(altdriver, TI_PANEL_PLAY, settle=2.0)
        if _wait_leaves_scene(altdriver, TREASURE_ISLAND_SCENE, timeout=15):
            wait_for_scene_ready(altdriver, label="activity")
            started = True
            break
        logging.warning(f"[TI] Play did not start '{building}' "
                        f"(attempt {attempt}/{TI_PLAY_ATTEMPTS}) — the panel is still up")
        time.sleep(2)
    if not started:
        out["note"] = (f"'{building}' opened its panel but Play never started the "
                       f"activity after {TI_PLAY_ATTEMPTS} presses")
        if trail:
            trail.shot(altdriver, f"{_ti_short(building)}-play-stuck", EVIDENCE_KEY)
        else:
            capture_evidence(altdriver, f"ti-{building}-play-stuck", tc_id=tc_id)
        return out

    # Ask WHICH activity, not for a CHANGE of activity. The scene leaving
    # Treasure Island above already proved one started, and a run plays the
    # same building twice all the time (a skill usually needs more than one go)
    # — demanding a different name then spins through every retry wait, seven
    # minutes of "scene still UNSCRAMBLE_QUIZ", and gives up on a run that was
    # working perfectly.
    activity = _get_current_activity_with_retry(altdriver, max_attempts=6,
                                                waits=(2, 3, 5, 8, 12))
    if not activity:
        out["note"] = f"'{building}' did not start an activity"
        return out
    out["activity"] = activity
    logging.info(f"[TI] {building} started '{activity}'")

    if trail:
        trail.shot(altdriver, f"{activity}-opened")

    out["played"] = _solve_open_activity(altdriver, activity, label=f"TI {building}")
    # The board as the solver left it — finished or not, this is the frame that
    # shows whether the activity was really played.
    if trail:
        trail.shot(altdriver,
                   f"{activity}-{'finished' if out['played'] else 'UNFINISHED'}",
                   EVIDENCE_PROOF if out["played"] else EVIDENCE_KEY)
    if not out["played"]:
        out["note"] = f"the '{activity}' solver did not finish it"
        if not trail:
            capture_evidence(altdriver, f"ti-{activity}-unfinished", tc_id=tc_id)

    # Back to the island whatever happened, so the next building is reachable.
    for _ in range(4):
        if _current_scene(altdriver) == TREASURE_ISLAND_SCENE:
            break
        try:
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:                            # noqa: BLE001
            when_finish_activity(altdriver)
        wait_for_scene(altdriver, TREASURE_ISLAND_SCENE, timeout=20)
    if _current_scene(altdriver) != TREASURE_ISLAND_SCENE:
        out["note"] = (out["note"] + "; " if out["note"] else "") + \
            f"stuck on {_current_scene(altdriver)} after the activity"
    return out


def treasure_island_check(altdriver, username=None, password=None, tc_id="",
                          max_plays=12, timeout=90):
    """Play Treasure Island's missions and watch its LEVEL. Never raises.

    Each required skill is played until its progress reads 100%, then the next;
    when the automatable ones are done the Treasure Island level must go up.
    SPEAKING is skipped — no solver exists for it — and the report says so
    rather than passing over it quietly.

    Returns ``{"ok", "level_before", "level_after", "skills", "skipped",
    "plays", "problems", "note"}``.
    """
    report = {"ok": False, "level_before": "", "level_after": "", "skills": {},
              "skipped": [], "plays": [], "problems": [], "note": ""}

    if username and not fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not open_feature(altdriver, "treasure island", username, password, timeout=timeout):
        report["note"] = "Treasure Island did not open"
        return report

    ti_skip_intro(altdriver)
    if not ti_open_missions(altdriver, timeout=timeout):
        report["note"] = "the mission list did not open from the clipboard"
        return report

    # ONE budget for the whole case, shared with any helper that calls
    # capture_evidence() on its own.
    reset_evidence_trail(tc_id)
    trail = evidence_trail(tc_id)
    report["level_before"], percent_before = ti_level(altdriver)
    missions = ti_missions(altdriver)
    if not missions:
        report["note"] = "the mission list has no rows"
        return report
    logging.info(f"[TI] {report['level_before']} ({percent_before}): "
                 f"{[(m['skill'], m['progress']) for m in missions]}")
    trail.shot(altdriver, "missions-BEFORE", EVIDENCE_KEY)

    for mission in missions:
        skill = mission["skill"]
        report["skills"][skill] = {"before": mission["progress"], "after": mission["progress"]}
        if not mission["automatable"]:
            # Said out loud, in the result, exactly as the user asked.
            report["skipped"].append(skill)
            logging.warning(f"[TI] '{skill}' has NO automation in this framework — skipped")
            continue

    plays = 0
    for mission in [m for m in missions if m["automatable"]]:
        skill, index = mission["skill"], mission["index"]
        island = ti_island_for_skill(altdriver, skill)
        if not island:
            report["problems"].append(f"{skill}: no island object matches this skill")
            continue
        if ti_island_locked(altdriver, island):
            report["problems"].append(f"{skill}: its island ({island}) is still locked")
            continue

        while plays < max_plays:
            # Read the row from an OPEN mission list. Playing an activity closes
            # it, and rows read against a closed list come back empty — which
            # reads as "progress unknown" and sends the run round again.
            if not ti_open_missions(altdriver, timeout=timeout):
                report["problems"].append(f"{skill}: the mission list would not open")
                break
            current = next((m for m in ti_missions(altdriver) if m["index"] == index), None)
            progress = (current or {}).get("progress")
            report["skills"][skill]["after"] = progress
            # A finished skill has no Play button at all — its row swaps to the
            # completion layer — so "done" has to be believed before the run
            # tries to press one that is not there.
            if (current or {}).get("done") or (progress is not None
                                               and progress >= TI_COMPLETE):
                logging.info(f"[TI] '{skill}' is complete")
                report["skills"][skill]["after"] = 1.0
                break

            if not ti_press_row_play(altdriver, index):
                report["problems"].append(f"{skill}: its Play button could not be pressed")
                break
            # The island Play zoomed to, with its buildings.
            trail.shot(altdriver, f"{skill}-island")

            buildings = ti_buildings(altdriver, island)
            if not buildings:
                report["problems"].append(f"{skill}: {island} has no buildings to play")
                break
            # Any building on the island will do — the user's rule.
            building = random.choice(buildings)
            outcome = ti_play_building(altdriver, building, timeout=timeout,
                                       tc_id=tc_id, trail=trail)
            plays += 1
            report["plays"].append(
                f"{skill}: {outcome['building']} -> {outcome['activity'] or '?'}"
                f"{'' if outcome['played'] else ' (NOT finished: ' + outcome['note'] + ')'}")
            if not outcome["played"]:
                report["problems"].append(
                    f"{skill}: {outcome['building']} did not complete — {outcome['note']}")
                break

            # The TASK SUMMARY after every activity — the user asked for this
            # one by name. It is the proof that the activity moved the skill,
            # and the only frame that shows the mission list mid-run.
            ti_open_missions(altdriver, timeout=timeout)
            after = next((m for m in ti_missions(altdriver) if m["index"] == index), None)
            moved = (after or {}).get("progress")
            trail.shot(altdriver, f"missions-after-{skill}-{outcome['activity'] or 'play'}",
                       EVIDENCE_PROOF)
            report["skills"][skill]["after"] = moved
            # Say what the activity was WORTH. Without this a skill that needs
            # several plays looks identical to one that is not advancing at all.
            logging.info(f"[TI] '{skill}' {progress} -> {moved} after "
                         f"{outcome['activity'] or outcome['building']}")
            if moved is not None and progress is not None and moved <= progress:
                report["problems"].append(
                    f"{skill}: finishing {outcome['activity']} left its progress at "
                    f"{moved} — an activity must raise the skill's progress")
                break

    # The point of the case: the LEVEL moves once the required skills are done.
    ti_open_missions(altdriver, timeout=timeout)
    report["level_after"], percent_after = ti_level(altdriver)
    trail.shot(altdriver, "missions-FINAL", EVIDENCE_KEY)
    report["screenshots"] = trail.names
    logging.info(f"[TI] level {report['level_before']!r} -> {report['level_after']!r} "
                 f"({percent_before} -> {percent_after})")

    automatable = [s for s in report["skills"] if s not in report["skipped"]]
    done = [s for s in automatable
            if (report["skills"][s].get("after") or 0) >= TI_COMPLETE]
    report["completed"] = done
    report["percent_before"] = _ti_percent(percent_before)
    report["percent_after"] = _ti_percent(percent_after)
    report["level_rose"] = bool(report["level_after"]
                                and report["level_after"] != report["level_before"])

    # PASS = every skill this framework CAN play reads 100%, and the overall did
    # not go backwards.
    #
    # Deliberately NOT "the level went up". Measured live: the overall is the
    # mean of all four skills, Speaking included, so with no solver for Speaking
    # the ceiling is exactly 75% and LevelText never moves. Asserting the level
    # would fail every run for a reason no run can fix. `level_rose` is reported
    # so the day Speaking becomes automatable it can be asserted.
    #
    # ">= before" rather than "> before" on purpose: a re-run starts with the
    # skills already complete, plays nothing, and must still pass.
    report["ok"] = (bool(automatable) and len(done) == len(automatable)
                    and not report["problems"]
                    and report["percent_after"] >= report["percent_before"])

    # What was NOT automated is said in the note ALWAYS — on a pass as much as
    # on a failure. A green result that never mentions Speaking reads as though
    # every required skill was exercised, and it was not: there is no solver for
    # it in this framework. The user asked for this to be in the result.
    notes = []
    if report["skipped"]:
        notes.append(
            f"NOT AUTOMATED — no solver exists in this framework for: "
            f"{', '.join(report['skipped'])}. "
            f"{'That skill was' if len(report['skipped']) == 1 else 'Those skills were'} "
            f"skipped and NOT verified by this run.")
    notes.append(f"Completed: {', '.join(done) if done else 'no skill'}. "
                 f"Level {report['level_before'] or '?'} -> {report['level_after'] or '?'} "
                 f"({percent_before} -> {percent_after}).")
    if report["skipped"] and not report["level_rose"]:
        # Say WHY the level held, or the reader is left to assume a bug.
        notes.append(
            f"The Treasure Island level did NOT change: the overall percentage is the "
            f"mean of ALL required skills, so it cannot reach 100% while "
            f"{', '.join(report['skipped'])} has no automation "
            f"({percent_after} is the ceiling for this run).")
    if report["plays"]:
        notes.append(f"Played: {'; '.join(report['plays'])}.")
    if report["problems"]:
        notes.append(f"Problems: {report['problems']}.")
    # A note set earlier (the run never got started) is the whole story.
    report["note"] = report["note"] or " ".join(notes)
    logging.info(f"[TI] {report['note']}")
    return report


def _infer_scene_from_title(title):
    """The activity scene a printed thumb title stands for, or ""."""
    from runner.test_generator import RallyTestGenerator      # local: avoids a cycle
    hay = (title or "").strip().lower()
    best = ""
    for keyword, scene in RallyTestGenerator.ACTIVITY_SCENES.items():
        if keyword in hay and len(keyword) > len(best or ""):
            best, best_scene = keyword, scene
    return best_scene if best else ""


def app_health(altdriver):
    """``('ok', '')`` | ``('error', popup)`` | ``('dead', why)``.

    "No crash happened" in a guest run means two things: the driver still
    answers, and the app is not sitting on an error/connection popup.
    """
    try:
        altdriver.get_current_scene()
    except Exception as e:                       # noqa: BLE001
        return "dead", str(e)[:120]
    for name in GUEST_ERROR_POPUPS:
        if find_any(altdriver, name) is not None:
            return "error", name
    return "ok", ""


def guest_open_level(altdriver, level, timeout=90):
    """From wherever we are, open ``level`` and reach its activity list.

    Returns ``(ok, note)``. Uses the icon's own name (icons carry their level
    number) and the shared level-intro walk, so a first visit that goes through
    the word list / vending machine is handled the same as a revisit.
    """
    # Reach the map the same way everything else does: _guest_back_to_map picks
    # the route for where we actually are ('Back' from the activity list,
    # 'GO-Map' from the hub) and does not report success until the level icons
    # are there AND the map has settled enough to accept a press.
    if not _map_ready(altdriver, timeout=5) and not _guest_back_to_map(altdriver):
        return False, f"could not reach the map to open level {level}"

    icon, icon_name, kind = _level_icon_by_number(altdriver, level)
    if icon is None:
        return False, f"level {level} has no icon on the guest's map"

    # PRESS AGAIN before failing. A press that arrives while the map is still
    # settling is swallowed silently, and one press followed by a long wait
    # spends the whole timeout on a click that never landed.
    for attempt in range(1, 4):
        logging.info(f"[Guest] opening level {level} ({kind}) via '{icon_name}'"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        press_object(altdriver, icon_name, settle=2.0)
        if open_level_to_activities(altdriver, timeout=timeout):
            return True, ""
        logging.warning(f"[Guest] level {level} did not reach its activity list "
                        f"(on {_current_scene(altdriver)}) — pressing again")
        if not _guest_back_to_map(altdriver):
            break
        icon, icon_name, kind = _level_icon_by_number(altdriver, level)
        if icon is None:
            break

    return False, (f"level {level} did not reach the activity list after 3 attempts "
                   f"(stuck on {_current_scene(altdriver)})")


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
        now = _current_scene(altdriver)
        if now and now != scene and now in solvers:
            logging.info(f"[Guest] '{scene}' settled into '{now}'")
            scene, solver = now, solvers[now]
    if solver is None:
        logging.warning(f"[Guest] no solver mapped for scene '{scene}' ({label})")
        return False

    dismiss_replay_popup(altdriver)
    # The instructions parrot blocks the whole screen until it is clicked, and
    # every press the solver makes would land on the blocker, not the board.
    dismiss_screen_blocker(altdriver)
    try:
        solver(altdriver)
    except Exception as e:                       # noqa: BLE001
        logging.error(f"[Guest] the {scene} solver raised: {str(e)[:140]}")
        return False
    return wait_for_finish_feedback(altdriver, timeout=40)


def guest_walk_levels(altdriver, levels=(1, 2, 3), complete_one=True, timeout=90):
    """Open each level in ``levels``, prove every activity starts, finish one.

    For each level: open it, then press every activity thumb in turn and wait
    for a real activity scene to load, checking after each that the app is
    healthy. One activity overall is played to completion with the proven
    solver. Returns a report and never raises, so the calling test can assert
    on the whole picture:

        {"ok": bool, "levels": {1: {...}}, "opened": [...],
         "completed": str, "problems": [...]}
    """
    report = {"ok": False, "levels": {}, "opened": [], "completed": "",
              "problems": []}

    for level in levels:
        entry = {"activities": [], "opened": [], "problems": []}
        report["levels"][level] = entry

        ok, note = guest_open_level(altdriver, level, timeout=timeout)
        if not ok:
            entry["problems"].append(note)
            report["problems"].append(f"level {level}: {note}")
            continue

        listed = list_level_activities(altdriver)
        entry["activities"] = [a["title"] or "(unlabelled)" for a in listed]
        logging.info(f"[Guest] level {level} offers {entry['activities']}")

        for idx in range(len(listed)):
            # Re-read the thumbs: coming back from an activity rebuilds the scene,
            # so the AltObjects captured earlier are stale. The THUMBS decide
            # whether the level has to be re-opened — an activity can hand back
            # to a list that does not report ACTIVITY_SELECTION_SCENE, and
            # re-entering the level in that case is pure round trip.
            if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is None:
                ok, note = guest_open_level(altdriver, level, timeout=timeout)
                if not ok:
                    entry["problems"].append(f"could not re-open level {level}: {note}")
                    break
            now = list_level_activities(altdriver)
            if idx >= len(now):
                break
            thumb = now[idx]["thumb"]
            title = now[idx]["title"] or f"thumb {idx + 1}"

            # THREE presses before an activity counts as "did not open". A press
            # that lands while the list is still rebuilding is swallowed, and
            # that is not the same as an activity that cannot start.
            scene = ""
            for attempt in range(1, 4):
                if attempt > 1:
                    if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is None:
                        ok, _note = guest_open_level(altdriver, level, timeout=timeout)
                        if not ok:
                            break
                    again = list_level_activities(altdriver)
                    if idx >= len(again):
                        break
                    thumb = again[idx]["thumb"]
                    logging.info(f"[Guest] '{title}' did not open — pressing again "
                                 f"(attempt {attempt}/3)")
                try:
                    thumb.click()
                except Exception as e:           # noqa: BLE001
                    if attempt == 3:
                        entry["problems"].append(f"{title}: thumb press failed ({e})")
                    continue

                deadline = time.time() + 40
                while time.time() < deadline:
                    current = _current_scene(altdriver)
                    if current and current not in _GUEST_NON_ACTIVITY_SCENES:
                        scene = current
                        break
                    time.sleep(0.5)
                if scene:
                    break

            state, detail = app_health(altdriver)
            if state != "ok":
                problem = f"{title}: the app went {state} ({detail})"
                entry["problems"].append(problem)
                report["problems"].append(f"level {level} {problem}")
                return report                    # a crash ends the run, honestly

            if not scene:
                # Three presses spent and it never opened — photograph it.
                shot = capture_failure_screenshot(altdriver, f"L{level}_{title}_no_open")
                entry["problems"].append(
                    f"{title}: did not open after 3 attempts (still on "
                    f"{_current_scene(altdriver)})"
                    + (f" [screenshot: {shot}]" if shot else ""))
                report["problems"].append(f"level {level} {title}: did not open")
                continue

            entry["opened"].append(f"{title} -> {scene}")
            report["opened"].append(f"L{level} {title} -> {scene}")
            logging.info(f"[Guest] level {level}: '{title}' opened as {scene}")

            # Let the activity finish building, then close the parrot's
            # instruction bubble — it sits over the board, so anything checked
            # underneath it is checked through a popup.
            time.sleep(GUEST_ACTIVITY_SETTLE_SECONDS)
            dismiss_help_popup(altdriver)

            # Now prove the activity actually DREW itself. The scene changing
            # only says the app navigated there.
            ui_ok, ui_known, ui_note = validate_activity_ui(altdriver, scene)
            if ui_ok:
                logging.info(f"[Guest] level {level}: '{title}' UI ok — {ui_note}")
            elif ui_known:
                shot = capture_failure_screenshot(altdriver, f"L{level}_{title}_no_ui")
                problem = (f"{title}: opened as {scene} but its UI never appeared "
                           f"({ui_note})" + (f" [screenshot: {shot}]" if shot else ""))
                entry["problems"].append(problem)
                report["problems"].append(f"level {level} {problem}")
            else:
                # No markers established for this activity — say so plainly
                # rather than failing the run on our own missing knowledge.
                logging.warning(f"[Guest] level {level}: '{title}' ({scene}) has no UI "
                                f"markers to check — {ui_note}")

            # Back to the activity list for the next thumb — the list, NOT the
            # map: walking out to the map costs a level re-entry per activity.
            if not back_to_activity_list(altdriver):
                return_to_map(altdriver)         # last resort, re-opens the level

        # Finish exactly one activity for the run, from this level's activity
        # list. solve_activity_in_level opens the right thumb by its printed
        # title and verifies the game registered the completion — this is the
        # path proven green live, so it is used rather than driving the solver
        # directly on an already-open activity.
        if complete_one and not report["completed"] and entry["opened"]:
            # Pick an activity this framework can actually finish: an activity
            # whose scene has no solver mapped can never be completed, and some
            # open on an intro scene ("WordsMatchingOpenningScene") that is not
            # in the map at all.
            solvers = get_activity_solver_map()
            candidates = []
            for line in entry["opened"]:
                a_title, _, a_scene = line.partition(" -> ")
                if a_scene in solvers:
                    candidates.append((a_title, a_scene))
            if not candidates:
                entry["problems"].append(
                    "no activity in this level has a solver mapped "
                    f"({[l for l in entry['opened']]})")
            for title, scene in candidates:
                if _current_scene(altdriver) != ACTIVITY_SELECTION_SCENE:
                    guest_open_level(altdriver, level, timeout=timeout)
                logging.info(f"[Guest] completing '{title}' ({scene}) in level {level}")
                try:
                    hint = title if not title.startswith(("(unlabelled)", "thumb ")) else None
                    # solve_activity_in_level already retries 3x internally, for
                    # every flow — don't wrap it in another loop or a run would
                    # spend nine attempts on one activity.
                    outcome = solve_activity_in_level(altdriver, scene, title_hint=hint)
                except Exception as e:           # noqa: BLE001
                    entry["problems"].append(f"{title}: solver raised ({str(e)[:100]})")
                    continue
                if activity_completed(outcome):
                    report["completed"] = (f"level {level}: {title} ({scene}) "
                                           f"{outcome.get('done')}/{outcome.get('total')}")
                    logging.info(f"[Guest] completed {report['completed']}")
                    break
                entry["problems"].append(
                    f"{title}: not completed after 3 attempts — "
                    f"found={outcome.get('found')} "
                    f"progress={outcome.get('done')}/{outcome.get('total')} "
                    f"feedback={outcome.get('feedback')}")

    every_level_opened = all(
        report["levels"].get(lv, {}).get("opened")
        and not report["levels"].get(lv, {}).get("problems")
        for lv in levels)
    report["ok"] = bool(every_level_opened and (report["completed"] or not complete_one))
    return report


# --- Guest: the first exam, and the levels a guest may not enter -----------
# A guest's accessible band is levels 1-5, the 5th being the first exam, and
# every higher level still has an icon on the map — the restriction is a STATE,
# not a missing icon, so it has to be proven behaviourally.

# What the app puts up when a guest presses something they have not paid for.
GUEST_LOCK_MARKERS = ("BuyButton", "ChoosePackage", "ChoosePlan", "LoginPopUp",
                      "Blocker", "BlockScreen", "BlockScreenWithoutClick")

# How long the map is given to settle before an exam icon is pressed.
GUEST_EXAM_SETTLE_SECONDS = 6.0
# How long to stand still after ARRIVING on the map, before pressing anything on
# it. The icons appear before the map has finished arranging itself, and a press
# that lands in that window is swallowed silently — which is why an icon press
# could look like it did nothing at all.
MAP_SETTLE_SECONDS = 5.0

# Text-ish objects, for reading a popup whose object names are not known.
_TEXT_SCAN_PATHS = ("//*[contains(@name,'Text')]", "//*[contains(@name,'TMP')]",
                    "//*[contains(@name,'Label')]", "//*[contains(@name,'Message')]")


def visible_texts(altdriver, limit=40):
    """Every non-empty string on screen right now, in hierarchy order.

    Reads a popup's WORDING without needing its object name: the app's popups
    are not all named consistently, and asserting on a name we guessed would
    prove nothing about what the user was actually shown.
    """
    seen, out = set(), []
    for path in _TEXT_SCAN_PATHS:
        try:
            objects = altdriver.find_objects(By.PATH, path)
        except Exception:                            # noqa: BLE001
            continue
        for obj in (objects or [])[:limit]:
            try:
                text = (obj.get_text() or "").strip()
            except Exception:                        # noqa: BLE001 - not a text object
                continue
            if text and text not in seen:
                seen.add(text)
                out.append(text)
        if len(out) >= limit:
            break
    return out


# The app's own label for a popup's message ("You've completed all free levels.
# Please subscribe to open more levels.").
POPUP_MESSAGE_OBJECT = "MessageText"


# The gate the app puts up once a guest finishes the free content: an "Image"
# panel whose message lives on a "Text - RTLTMP" object, in the component
# property ``originalText`` (get_text() returns the SHAPED/typed-out string,
# which is why reading the label gave a fragment), closed with "OKButton".
GUEST_GATE_PANEL = "Image"
GUEST_GATE_TEXT = "Text - RTLTMP"
GUEST_GATE_OK = "OKButton"
GUEST_GATE_TEXT_PROPERTY = "originalText"
# Closing the gate hands over to a second notice ("Web Purchase Unavailable"),
# whose own button is called "Button". It has to be cleared as well: it covers
# the map, so the locked-level press underneath would land on the popup.
GUEST_GATE_FOLLOWUP_OK = "Button"
# These panels animate in, so a press that arrives with the panel is swallowed.
POPUP_CLICK_DELAY = 1.0


# Where the app keeps a popup's untyped message (confirmed live, and by the
# user): RTLTMPro's text component, whose "originalText" is the WHOLE string —
# the rendered label only holds however much has been typed out so far.
RTL_TEXT_COMPONENTS = (("RTLTMPro.RTLTextMeshPro", "RTLTMPro"),
                       ("RTLTMPro.RTLTextMeshPro3D", "RTLTMPro"))


def component_property(obj, prop):
    """``prop`` from the component on ``obj`` that carries it, or "".

    The known RTLTMPro components are tried first; only if neither answers is
    the object asked what components it has, so a renamed or swapped text class
    still resolves instead of failing silently.
    """
    for name, assembly in RTL_TEXT_COMPONENTS:
        try:
            value = obj.get_component_property(name, prop, assembly)
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    try:
        components = obj.get_all_components() or []
    except Exception:                                # noqa: BLE001
        return ""
    for component in components:
        name = (component.get("componentName") or component.get("name") or "")
        assembly = (component.get("assemblyName") or component.get("assembly") or "")
        if not name:
            continue
        try:
            value = obj.get_component_property(name, prop, assembly)
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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
    return name or capture_failure_screenshot(altdriver, label)


def guest_subscribe_gate(altdriver, expect=(), settle=None, timeout=30, tc_id=""):
    """Wait for the post-exam subscribe gate, READ it, and close it.

    Returns ``{"shown", "text", "closed", "note"}`` and never raises, so the
    test can assert on the wording with the whole picture in the message.

    The text is read from ``originalText`` rather than the rendered label: the
    label types itself out, so reading it mid-animation returns a fragment —
    ``originalText`` is the whole string from the moment the panel exists.
    """
    result = {"shown": False, "text": "", "closed": False, "note": "",
              "followup": "", "followup_shown": False, "followup_closed": False,
              "shots": []}
    time.sleep(MAP_SETTLE_SECONDS if settle is None else settle)

    if not wait_for_any(altdriver, (GUEST_GATE_OK, GUEST_GATE_PANEL), timeout=timeout):
        result["note"] = (f"no subscribe gate appeared within {timeout}s "
                          f"(looked for '{GUEST_GATE_OK}' / '{GUEST_GATE_PANEL}')")
        return result
    result["shown"] = True

    # More than one object can be called "Text - RTLTMP"; take the one whose
    # text actually reads like the gate, and fall back to everything found so a
    # failure message shows what WAS on screen.
    wanted = [w.lower() for w in expect if w]
    candidates = []
    try:
        for obj in altdriver.find_objects(By.NAME, GUEST_GATE_TEXT) or []:
            text = component_property(obj, GUEST_GATE_TEXT_PROPERTY)
            if not text:
                try:
                    text = (obj.get_text() or "").strip()
                except Exception:                    # noqa: BLE001
                    text = ""
            if text:
                candidates.append(text)
    except Exception as e:                           # noqa: BLE001
        result["note"] = f"could not read the gate's text: {e}"

    best = next((c for c in candidates
                 if wanted and all(w in c.lower() for w in wanted)), "")
    result["text"] = best or " ".join(candidates)
    logging.info(f"[Guest] the subscribe gate says: {result['text']!r}")

    # Photograph the gate BEFORE closing it — it is gone a second later.
    shot = capture_evidence(altdriver, "guest-gate-subscribe", tc_id=tc_id)
    if shot:
        result["shots"].append(shot)

    time.sleep(POPUP_CLICK_DELAY)                    # let the panel settle first
    result["closed"] = bool(press_object(altdriver, GUEST_GATE_OK, timeout=6, settle=1.5))
    if not result["closed"]:
        result["note"] = (result["note"] + "; " if result["note"] else "") + \
                         f"'{GUEST_GATE_OK}' did not close the gate"
        return result

    # The gate hands over to a "Web Purchase Unavailable" notice. Clear it too,
    # or the next press lands on the popup instead of the map underneath.
    if wait_for_any(altdriver, GUEST_GATE_FOLLOWUP_OK, timeout=8):
        result["followup_shown"] = True
        followup = ""
        try:
            for obj in altdriver.find_objects(By.NAME, GUEST_GATE_TEXT) or []:
                text = component_property(obj, GUEST_GATE_TEXT_PROPERTY)
                if text and len(text) > len(followup):
                    followup = text
        except Exception:                            # noqa: BLE001
            pass
        if followup:
            logging.info(f"[Guest] follow-up notice: {followup!r}")
        result["followup"] = followup
        shot = capture_evidence(altdriver, "guest-gate-purchase-notice", tc_id=tc_id)
        if shot:
            result["shots"].append(shot)
        time.sleep(POPUP_CLICK_DELAY)
        result["followup_closed"] = bool(
            press_object(altdriver, GUEST_GATE_FOLLOWUP_OK, timeout=6, settle=1.5))
        if not result["followup_closed"]:
            result["note"] = (result["note"] + "; " if result["note"] else "") + \
                             f"the follow-up notice would not close via " \
                             f"'{GUEST_GATE_FOLLOWUP_OK}'"

    # The map with nothing in front of it: this is the frame that shows which
    # levels are actually locked, which is the point of the whole check.
    _guest_back_to_map(altdriver)
    shot = capture_evidence(altdriver, "guest-map-after-gates", tc_id=tc_id)
    if shot:
        result["shots"].append(shot)
        logging.info(f"[Guest] map frame saved: {shot}")
    return result


def guest_clear_data_notice(tc_id=""):
    """Tell whoever is watching that the app must be reset before the next case.

    A guest run deliberately does NOT log out at the end: the registration has
    to be cleared from the device, and only a data clear plus an app restart
    does that. Logging out instead would leave the guest registered and the
    next case would resume it rather than registering its own.
    """
    banner = "=" * 72
    for line in (banner,
                 f"[Guest] {tc_id + ': ' if tc_id else ''}RUN FINISHED — the app was "
                 f"left signed in as this guest, ON PURPOSE.",
                 "[Guest] CLEAR THE APP DATA AND RESTART THE APP before the next "
                 "guest test case,",
                 "[Guest] or it will resume this guest instead of registering a new one.",
                 banner):
        logging.warning(line)
        print(line)


def popup_text(altdriver, settle=1.5, limit=40):
    """The wording a popup is showing, as one string. Never raises.

    Reads ``MessageText`` — the label the app puts its message in — and waits
    for it to STOP GROWING before believing it: these panels animate in and the
    text types itself out, so a read taken too early returns a fragment (which
    is exactly what a screenshot of the same moment shows). Falls back to
    scanning the visible text objects when that label is not on screen.
    """
    time.sleep(settle)
    obj = find_any(altdriver, POPUP_MESSAGE_OBJECT)
    if obj is not None:
        previous = ""
        for _ in range(10):
            try:
                current = (obj.get_text() or "").strip()
            except Exception:                        # noqa: BLE001
                break
            if current and current == previous:
                return current
            previous = current
            time.sleep(0.3)
        if previous:
            return previous
    return " ".join(visible_texts(altdriver, limit=limit))


def _map_ready(altdriver, timeout=30):
    """Is the map loaded AND usable — i.e. are its level ICONS there?

    The scene name flips to MapScene before the icons spawn, so "the scene is
    the map" is not enough: a level lookup made in that window finds nothing
    and reports the level as missing from the map. Waiting on the icons is what
    the callers actually need, since every one of them is about to press one.
    """
    end = time.time() + timeout
    while True:
        if _current_scene(altdriver) == MAP_SCENE and _find_level_icons(altdriver):
            # The icons exist, but the map is still arranging itself for a
            # moment longer. Every caller here is about to press one, so the
            # settle belongs in this one place rather than at each press.
            time.sleep(MAP_SETTLE_SECONDS)
            return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


def _guest_back_to_map(altdriver, timeout=60):
    """Get to the map from wherever the guest is. No login, no logout.

    The route depends on WHERE the guest is. From the activity list the map is
    one 'Back' press away and there is no 'GO-Map' there at all — asking for it
    first cost ~70s per call (12s hunting the button, then 60s waiting for a
    scene change that was never coming) before the fallback pressed 'Back'
    anyway. 'GO-Map' is the hub's control, so it is used from the hub.
    """
    scene = _current_scene(altdriver)
    if scene == MAP_SCENE and _map_ready(altdriver, timeout=15):
        return True

    if scene == ACTIVITY_SELECTION_SCENE:
        for name in ("Back", "BackButton", "prev"):
            if press_object(altdriver, name, timeout=4, settle=1.0):
                if _map_ready(altdriver, timeout=timeout):
                    return True
                break
    elif press_object(altdriver, "GO-Map", timeout=6, settle=10.0):
        if _map_ready(altdriver, timeout=timeout):
            return True

    return_to_map(altdriver)
    return _map_ready(altdriver, timeout=20)


def guest_first_exam_level(altdriver):
    """The lowest-numbered exam node on the map — the guest's FIRST exam.

    Which level carries the first exam is not fixed (it moves with the language
    and level the guest picked), so it is read off the map rather than assumed.
    Icons are named for the level they open, so the number comes from the name.
    Returns 0 when no exam node is on the map.
    """
    best = 0
    for obj in _find_level_icons(altdriver) or []:
        m = re.match(r"TestLevelIcon(?:\s*Variant)?\(Clone\)\s*(\d+)",
                     getattr(obj, "name", "") or "")
        if m:
            number = int(m.group(1))
            if best == 0 or number < best:
                best = number
    if best:
        logging.info(f"[Guest] the first exam on this map is level {best}")
    else:
        logging.error("[Guest] no exam node found on the guest's map")
    return best


def guest_take_exam(altdriver, level=None, timeout=90):
    """Open the guest's exam at ``level`` and solve every page.

    An exam sits on the map like any other level but leads to the 'Tests' scene
    instead of an activity list, so it needs its own opener; from there
    ``open_exam`` and ``solve_exam_pages`` are shared with the account exam flow
    (both are login-free, so a guest can use them unchanged).

    Returns the solve_exam_pages report plus ``ok``/``note``; never raises.
    """
    if not _guest_back_to_map(altdriver):
        return {"ok": False, "note": "could not reach the map for the exam"}

    if not level:
        level = guest_first_exam_level(altdriver)
        if not level:
            return {"ok": False, "note": "no exam node on the guest's map"}

    icon, icon_name, kind = _level_icon_by_number(altdriver, level)
    if icon is None:
        return {"ok": False, "note": f"level {level} is not on the guest's map"}
    if kind and kind != "exam":
        return {"ok": False,
                "note": f"level {level} is a '{kind}' node, not an exam — the "
                        f"guest's first exam is the one to point this at"}
    # PRESS AGAIN before failing: the exam icon can swallow a press that lands
    # while the map is still settling, and giving up on one press means a human
    # has to click it — which is exactly what happened on 2026-08-13.
    opened = False
    for attempt in range(1, 4):
        logging.info(f"[Guest] opening the exam at level {level} ('{icon_name}')"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        # Let the map finish settling before pressing. The icon answers a find
        # straight away but swallows a press that arrives while the map is
        # still arranging itself — the same trap as the trial entry.
        time.sleep(GUEST_EXAM_SETTLE_SECONDS)
        press_object(altdriver, icon_name, settle=2.0)
        if open_exam(altdriver):
            opened = True
            break
        logging.warning(f"[Guest] the exam did not open from '{icon_name}' "
                        f"(on {_current_scene(altdriver)}) — pressing again")
        if not _guest_back_to_map(altdriver):
            break
        icon, icon_name, _kind = _level_icon_by_number(altdriver, level)
        if icon is None:
            break

    if not opened:
        return {"ok": False,
                "note": f"the exam did not open after 3 attempts "
                        f"(scene {_current_scene(altdriver)})"}

    report = solve_exam_pages(altdriver, label=f"guest exam L{level}",
                              dismiss_help=True)
    report["ok"] = bool(report.get("total")
                        and report.get("parts") == report.get("total")
                        and report.get("submitted")
                        and not report.get("problems"))
    report.setdefault("note", "")
    if not report["ok"]:
        report["note"] = (f"answered {report.get('parts')}/{report.get('total')} pages, "
                          f"submitted={report.get('submitted')}, "
                          f"problems={report.get('problems')}")
    return report


def guest_level_locked(altdriver, level=None, timeout=25):
    """Press ``level`` and prove a guest cannot get in.

    Locked levels keep their icon (a guest sees the whole map), so "the icon is
    missing" is not the check. What is: after pressing it the app must NOT leave
    the map into that level's content. A paywall/sign-up prompt appearing is
    positive evidence and is reported as such.

    Returns ``{"locked": bool, "evidence": str, "note": str}``; never raises.
    """
    if not _guest_back_to_map(altdriver):
        return {"locked": False, "evidence": "",
                "note": "could not reach the map to test the lock"}

    if not level:
        # The band ends at the first exam, so the level after it is the first
        # one a guest must not be able to enter.
        first_exam = guest_first_exam_level(altdriver)
        if not first_exam:
            return {"locked": False, "evidence": "",
                    "note": "no exam node on the map to measure the band from"}
        level = first_exam + 1

    icon, icon_name, _kind = _level_icon_by_number(altdriver, level)
    if icon is None:
        return {"locked": False, "evidence": "",
                "note": f"level {level} has no icon on the map to press"}

    logging.info(f"[Guest] checking level {level} is locked ('{icon_name}')")
    # This press follows the exam being submitted and the app returning to the
    # map, which is the least settled the map ever is — the score/collect
    # animation is still unwinding. A press that lands in that window is
    # swallowed, and a swallowed press looks exactly like a locked level: the
    # app stays on the map, so the check would PASS without ever testing it.
    time.sleep(MAP_SETTLE_SECONDS)
    press_object(altdriver, icon_name, settle=2.0)

    deadline = time.time() + timeout
    while time.time() < deadline:
        scene = _current_scene(altdriver)
        if scene and scene != MAP_SCENE:
            return {"locked": False, "evidence": scene,
                    "note": f"level {level} opened into '{scene}' — a guest got in"}
        for marker in GUEST_LOCK_MARKERS:
            if find_any(altdriver, marker) is not None:
                shown = popup_text(altdriver)
                logging.info(f"[Guest] level {level} is gated by '{marker}'")
                logging.info(f"[Guest] the gate says: {shown!r}")
                return {"locked": True, "evidence": marker, "text": shown,
                        "note": f"level {level} put up '{marker}' instead of opening"}
        if find_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER) is not None:
            return {"locked": False, "evidence": ACTIVITY_SELECTION_SCENE_MARKER,
                    "text": "",
                    "note": f"level {level} reached its activity list — a guest got in"}
        time.sleep(1)

    # No known marker, but the app never left the map. The subscribe prompt is
    # itself the proof, so read whatever is on screen and report it: the wording
    # is what the test asserts, and it is logged even when nothing matched so a
    # renamed popup can be seen instead of guessed at.
    shown = popup_text(altdriver)
    logging.info(f"[Guest] level {level} stayed on the map; screen says: {shown!r}")
    return {"locked": True, "evidence": "stayed on the map", "text": shown,
            "note": f"level {level} did not open within {timeout}s"}


def ensure_on_map(altdriver, username=None, password=None, max_rounds=4):
    """Get to the level map from WHEREVER the app currently is.

    A generated test can start anywhere: on the map, on the start screen, deep
    inside an activity, on a feedback popup, or logged out. Rather than assume,
    this escalates one step at a time:

      1. level icons visible          -> done
      2. login screen                 -> log in (needs credentials)
      3. start screen (GO-Map)        -> press it
      4. anywhere else                -> press back/close one screen at a time
                                         (``return_to_map``)
      5. still stuck                  -> keep backing out to the START screen
                                         (``return_to_start``), then GO-Map
      6. still stuck, creds available -> log out and back in

    Returns True when the map is showing. Never raises.
    """
    for rnd in range(max_rounds):
        if _find_level_icons(altdriver):
            return True

        if _login_screen_visible(altdriver):
            if not username:
                logging.error("[Map Navigation] On the login screen and no credentials given.")
                return False
            logging.info("[Map Navigation] On the login screen — logging in")
            login(altdriver, username, password)
            time.sleep(2)
            continue

        if _current_scene(altdriver) == START_SCENE or find_element(altdriver, "GO-Map") is not None:
            logging.info("[Map Navigation] On the start screen — clicking GO-Map")
            click_by_name(altdriver, "GO-Map")
            time.sleep(12)              # the map scene takes a while to load
            continue

        # Somewhere inside a level/activity/exam: walk out like a user.
        logging.info(f"[Map Navigation] Not on the map (round {rnd + 1}) — backing out")
        if return_to_map(altdriver):
            return True

        # Keep going back: the start screen is always reachable that way, and
        # GO-Map from there is a known-good route to the map.
        if return_to_start(altdriver):
            logging.info("[Map Navigation] At the start screen — clicking GO-Map")
            click_by_name(altdriver, "GO-Map")
            time.sleep(12)
            continue

        # Last resort: a clean session beats a stuck screen.
        if username:
            logging.warning("[Map Navigation] Still stuck — logging out and back in")
            try:
                call_method(altdriver, "AltTesterUtils", "Logout")
                time.sleep(3)
            except Exception as e:
                logging.warning(f"[Map Navigation] Logout failed: {e}")
            global _LAST_LOGIN_USER
            _LAST_LOGIN_USER = None      # force a real login next time
            login(altdriver, username, password)
            time.sleep(2)

    ok = bool(_find_level_icons(altdriver))
    if not ok:
        try:
            scene = altdriver.get_current_scene()
        except Exception:
            scene = "unknown"
        logging.error(f"[Map Navigation] Could not reach the map (scene: {scene}).")
    return ok


def enter_level_number(altdriver, level_num, retries=3, username=None, password=None):
    """Open the map level labelled ``level_num``, from wherever the app is.

    Navigation is self-recovering: ``ensure_on_map`` first walks the app back to
    the map (backing out of an activity, or logging in again if the session
    dropped), then the icon is picked BY NAME — icons are named after the level
    they open, so no counting. The 0-based index is kept as a fallback for
    builds whose icons aren't named that way (label N is index N-1).
    """
    logging.info(f"[Map Navigation] Entering level number {level_num}")
    try:
        if not ensure_on_map(altdriver, username=username, password=password,
                             max_rounds=max(retries, 2)):
            return False

        obj, name, kind = _level_icon_by_number(altdriver, level_num)
        if obj is not None:
            obj.click()
            time.sleep(4)
            logging.info(f"[Map Navigation] Entered level {level_num} "
                         f"({kind} level, icon '{name}').")
            return True

        level_objs = _find_level_icons(altdriver)
        index = level_num - 1          # label 44 -> icon index 43
        if index < 0 or index >= len(level_objs):
            logging.error(f"[Map Navigation] Level {level_num} out of range ({len(level_objs)} icons).")
            return False
        level_objs[index].click()
        time.sleep(4)
        logging.info(f"[Map Navigation] Entered level {level_num} (icon index {index}).")
        return True
    except Exception as e:
        logging.error(f"[Map Navigation] Exception clicking level {level_num}: {e}")
        return False


def open_level_to_activities(altdriver, timeout=90):
    """From a just-clicked level, reach ActivitySelectionScene.

    Same route as handle_level_flow — an already-opened level goes straight to
    the activity selection, a level opened for the FIRST time shows the intro
    (nextButton) and then the vending machine (Toggle) — but driven as a loop
    instead of one shot per step. That matters for a not-yet-opened level: the
    intro can be more than one page, and both the vending scene and the
    selection screen take several seconds to load, so a single "click next,
    look once" pass gets stuck on whatever is still loading.

    Never raises (click_by_name swallows misses); returns True once the
    activity selection screen is showing.
    """
    deadline = time.time() + timeout
    last_scene = object()          # sentinel: log the first scene we see
    while time.time() < deadline:
        try:
            scene = altdriver.get_current_scene()
        except Exception as e:     # scene swap in progress
            logging.debug(f"[Level Flow] get_current_scene failed: {e}")
            scene = None

        if scene == 'ActivitySelectionScene':
            return True
        if scene != last_scene:
            logging.info(f"[Level Flow] on '{scene}' — opening the level")
            last_scene = scene

        if scene == 'VendingMachineScene':
            # First visit to a level: pick a prize to get past the machine.
            click_by_name(altdriver, "Toggle")
            time.sleep(12)
            continue

        # Level intro: keep pressing next for as long as one is on screen.
        if find_element(altdriver, "nextButton") is not None:
            click_by_name(altdriver, "nextButton")
            time.sleep(3)
            continue

        time.sleep(2)              # still loading — look again

    try:
        now = altdriver.get_current_scene()
    except Exception:
        now = "unknown"
    logging.error(f"[Level Flow] ActivitySelectionScene not reached in {timeout}s (now: {now})")
    return False


_LAST_LOGIN_USER = None


def ensure_logged_in(altdriver, username, password):
    """Login only when needed.

    Several generated test cases often run in one pytest session with the same
    user; logging out/in between them wastes ~40s each. Skip the login when
    this session already logged that user in and we are not on the login
    screen. A different user (or a logged-out app) gets the full login flow.
    """
    global _LAST_LOGIN_USER
    if _LAST_LOGIN_USER == username and not _login_screen_visible(altdriver):
        logging.info(f"[Login] already logged in as {username} — skipping login")
        return
    login(altdriver, username, password)
    # A brand-new user is asked which avatar they are before anything else, and
    # answering opens the avatar builder. Only ever on a FIRST entry: an
    # account that has answered already just carries on. Checked here as well
    # as in fresh_login, because this is the other way a run signs in — and it
    # costs nothing on the path above, which does not log in at all.
    handle_gender_select(altdriver)
    _LAST_LOGIN_USER = username


# Buttons a real user presses to leave a screen, most specific first: the
# activity/feedback exit ("prev"), close/X popups, "Exit" (how Settings and the
# location popup are closed — matched EXACTLY so it can never hit the start
# screen's ExitButton_1, which quits the app), generic back, then the home
# screen's GO-Map. Whichever exists on the current screen gets clicked.
_BACK_BUTTON_NAMES = ("prev", "X", "x", "CloseButton", "close", "Close", "Exit",
                      "BackButton", "backButton", "Back", "HomeButton", "GO-Map",
                      # Last resort: the word list has no back/close at all —
                      # "next" is how you leave it (same button that carries the
                      # level intro forward). Tried only when nothing else fits,
                      # so it can't skip a step on a screen that has a real back.
                      "nextButton")


def return_to_map(altdriver, max_steps=8):
    """Clean state between chained test cases: go back to the level map.

    Navigates the way a user would — pressing back / close (X) / home buttons
    one screen at a time — until the map's level icons are visible. No direct
    scene loading. Never raises; the next test's enter_level_number can still
    self-recover.
    """
    for step in range(max_steps):
        if _find_level_icons(altdriver):
            logging.info("[Map Navigation] Back on the map.")
            return True
        clicked = None
        for name in _BACK_BUTTON_NAMES:
            try:
                obj = altdriver.find_object(By.NAME, name)
            except Exception:
                continue
            try:
                obj.click()
                clicked = name
                break
            except Exception:
                continue
        if clicked:
            logging.info(f"[Map Navigation] step {step + 1}: clicked '{clicked}'")
        else:
            logging.warning(f"[Map Navigation] step {step + 1}: no back/close/home button found")
        time.sleep(4)
    if _find_level_icons(altdriver):
        logging.info("[Map Navigation] Back on the map.")
        return True
    logging.warning("[Map Navigation] Map not reached; continuing anyway.")
    return False


def read_activity_progress(altdriver):
    """(done, total) from the activity's ProgressText, or (0, 0) if unreadable."""
    try:
        a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(a), int(b)
    except Exception:
        return 0, 0


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


# The full-screen catcher that comes up with the INSTRUCTIONS PARROT when an
# activity opens. Its name says what it does: it blocks the screen until it is
# clicked. (The user named this object, 2026-08-17.)
SCREEN_BLOCKER = "BlockScreenWithoutClick"


def dismiss_screen_blocker(altdriver, tries=3, settle=1.0):
    """Click the instructions parrot away if it is up. Returns bool.

    An activity opens with the parrot reading out its instructions, over a
    full-screen `BlockScreenWithoutClick`. Until that is clicked away every
    press the solver makes lands on the blocker instead of the board, so the
    activity scores nothing and it looks like a solver that cannot play.

    Any click dismisses it, and the blocker is ITSELF a full-screen object — so
    clicking the object does it without tapping a coordinate (see
    [[no-coordinate-based-clicks]]).
    """
    dismissed = False
    for _ in range(tries):
        blocker = find_any(altdriver, SCREEN_BLOCKER)
        if blocker is None:
            break
        if not _press(blocker):
            break
        dismissed = True
        logging.info(f"[Activity] clicked '{SCREEN_BLOCKER}' away (the parrot's bubble)")
        time.sleep(settle)
    return dismissed


def dismiss_replay_popup(altdriver):
    """Close the 'last attempt' notice that blocks a replayed activity.

    Re-entering an already-completed activity shows a popup ("this is your
    last chance to improve your score") over the board; the solver then plays
    against a blocked screen and scores 0. Present = active container found;
    close via its Yes / X button. Inactive popups are invisible to find_object,
    so this is a no-op on a fresh activity.
    """
    for container in ("PlaceHolder", "LastAttempetPopUp"):
        try:
            altdriver.find_object(By.NAME, container)
        except Exception:
            continue
        for btn in ("Yes", "X", "x", "CloseButton", "close", "Close"):
            try:
                altdriver.find_object(By.NAME, btn).click()
                time.sleep(1)
                logging.info(f"[Activity] dismissed replay popup ({container} -> '{btn}')")
                return True
            except Exception:
                continue
        logging.warning(f"[Activity] replay popup '{container}' found but no button worked")
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
    dismiss_replay_popup(altdriver)          # replayed activities are blocked by it
    dismiss_screen_blocker(altdriver)        # so is the instructions parrot
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
    result["screenshot"] = capture_failure_screenshot(
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
            prev_scene = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
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
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:
            when_finish_activity(altdriver)
        if not wait_for_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER, timeout=8):
            back_to_activity_list(altdriver)

    thumbs = altdriver.find_objects(By.NAME, "ActivityThumb")
    total = len(thumbs)
    logging.info(f"[Activity] {total} activities in this level; hunting {target_scene}")

    for i in range(total):
        thumbs = altdriver.find_objects(By.NAME, "ActivityThumb")
        if i >= len(thumbs):
            break
        try:
            prev_scene = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
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
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception as e:
            logging.warning(f"[Activity] LoadPreviousScene failed: {e}")
            when_finish_activity(altdriver)
        # Wait for the thumbs instead of a flat sleep — the list is usually
        # back well inside a second, and when it is not, pressing the exit
        # ourselves beats sleeping and hoping.
        if not wait_for_any(altdriver, ACTIVITY_SELECTION_SCENE_MARKER, timeout=8):
            back_to_activity_list(altdriver)

    logging.error(f"[Activity] {target_scene} not found among {total} thumbs")
    return result


def solve_lesson_levels(altdriver, class_id, lesson_num):
    difficulties = [("easy", 0), ("medium", 1), ("hard", 2)]

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            logging.warning(f"[solve_lesson_levels] Skipped {level_name} level — no level found or failed to enter.")
            continue

        try:
            solve_level(altdriver, diff)

            back_button = altdriver.wait_for_object(By.NAME, 'Back')
            back_button.click()
            time.sleep(6)
        except Exception as e:
            logging.error(f"[solve_lesson_levels] Error solving {level_name} level: {e}")


def solve_level(altdriver, difficulty):
    """
    Executes opened level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (int or str): 0, 1, 2 or "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Starting level solving for difficulty: {difficulty}")

    # Normalize difficulty
    if isinstance(difficulty, str):
        difficulty = {"easy": 0, "medium": 1, "hard": 2}.get(difficulty.lower(), -1)

    if difficulty not in [0, 1, 2]:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        raise ValueError(f"Unknown difficulty: {difficulty}")

    repetitions = {0: 3, 1: 2, 2: 1}[difficulty]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)


def solve_event_levels(altdriver):
    """
    Solves all levels by clicking each LessonLevelIcon Variant(Clone) for each lesson and difficulty.
    Each lesson has 3 levels: easy, medium, hard.

    Args:
        altdriver (AltDriver): AltTester driver instance
    """
    # Loop through lessons 1 to 8
    for lesson_num in range(1, 9):  # Lessons 1 to 8
        logging.info(f"[solve_event_levels] Solving levels for lesson {lesson_num}")

        # Loop through each difficulty: easy, medium, hard
        for difficulty_num in range(1, 4):  # Difficulty 1 - easy, 2 - medium, 3 - hard
            level_index = (lesson_num - 1) * 3 + difficulty_num  # Calculate index for the level
            difficulty = ["easy", "medium", "hard"][difficulty_num - 1]  # Map difficulty_num to difficulty name

            logging.info(
                f"[solve_event_levels] Solving {difficulty} level for lesson {lesson_num} (Level Index: {level_index})")

            try:
                # Click on the respective LessonLevelIcon Variant(Clone) based on the level index
                level_icon = altdriver.wait_for_object(By.NAME, f"LessonLevelIcon Variant(Clone) {level_index}")
                level_icon.click()
                logging.info(f"[solve_event_levels] Clicked on level {level_index}")

                # Solve the level by calling solve_level with the corresponding difficulty
                solve_level(altdriver, difficulty)

                # After solving the level, click 'Back' to go back
                back_button = altdriver.wait_for_object(By.NAME, 'Back')
                back_button.click()
                time.sleep(6)  # Wait for a few seconds before moving to the next level

            except Exception as e:
                logging.error(f"[solve_event_levels] Error solving level {level_index} for lesson {lesson_num}: {e}")
                continue  # Continue to the next level if one fails

def solve_specific_event_level(altdriver, level_index):
    """
    Solves a specific level based on the provided level index.
    This function will click the corresponding level icon and solve it.

    Args:
        altdriver (AltDriver): AltTester driver instance
        level_index (int): The index of the level to solve (1 to 24).
    """
    logging.info(f"[solve_specific_level] Solving specific level {level_index}...")

    try:
        # Click on the specific LessonLevelIcon Variant(Clone) based on the level index
        level_icon = altdriver.wait_for_object(By.NAME, f"LessonLevelIcon Variant(Clone) {level_index}")
        level_icon.click()
        logging.info(f"[solve_specific_level] Clicked on level {level_index}")

        # Determine the difficulty based on the level index:
        # 1 → easy, 2 → medium, 3 → hard, 4 → easy, 5 → medium, 6 → hard, etc.
        difficulty = ["easy", "medium", "hard"][(level_index - 1) % 3]
        solve_level(altdriver, difficulty)

        # After solving the level, click 'Back' to go back
        back_button = altdriver.wait_for_object(By.NAME, 'Back')
        back_button.click()
        time.sleep(6)  # Wait for a few seconds before moving to the next level

    except Exception as e:
        logging.error(f"[solve_specific_level] Error solving level {level_index}: {e}")
        return False  # Return False in case of an error solving the level

    return True  # Return True when level is solved successfully


def solve_level(altdriver, difficulty):
    """
    Executes the level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (str): "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Solving level with difficulty: {difficulty}")

    # Normalize difficulty to a numeric value
    difficulty_map = {"easy": 0, "medium": 1, "hard": 2}
    difficulty_value = difficulty_map.get(difficulty.lower(), -1)

    if difficulty_value == -1:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        return

    # Number of repetitions based on difficulty
    repetitions = {0: 3, 1: 2, 2: 1}[difficulty_value]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    # Loop through the repetitions and handle each level flow
    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")

    logging.info(f"[solve_level] Finished solving level with difficulty {difficulty}")
    time.sleep(4)  # Wait before continuing to the next level





# How long to let an exam page finish appearing before reading its type.
EXAM_APPEAR_SETTLE_SECONDS = 3.0
# The results screen that proves a submit was ACCEPTED. Its "Collect" button is
# what the run presses to bank the score, so its presence is the observable
# difference between "submitted" and "the app ignored the submit because
# something was still unanswered".
EXAM_RESULT_MARKERS = ("Collect", "CollectButton", "ResultPanel", "ScorePanel")


def detect_exam_type_settled(altdriver, tries=6, pause=0.5):
    """The page's type, once the page has STOPPED changing into it.

    A page is built in pieces, and the first widget to exist decides the answer
    — that is how a page was solved with ``exam_swap_letters`` in the very
    second the exam icon was pressed. Two agreeing reads mean the page is
    really that type, not merely part-way to being it.
    """
    previous = ""
    for _ in range(tries):
        current = detect_exam_type(altdriver)
        if current and current == previous:
            return current
        previous = current
        time.sleep(pause)
    return previous


def detect_exam_type(altdriver):
    """Detect active exam type based on UI elements.

    Called per PAGE, not per exam: the pages of one exam are usually different
    types, and a given type can appear on any page.
    """
    # Rows of scrambled letters; drag one onto another to swap them.
    if altdriver.find_objects(By.NAME, "SwapLetterText(Clone)"):
        return "swap_letters"
    # Sentences with blanks; drag each word from the bank into its blank.
    if altdriver.find_objects(By.NAME, "WordInShuffledContext(Clone)"):
        return "shuffled_context"
    if altdriver.find_objects(By.NAME, "SpellingInputField"):
        return "spelling"
    if altdriver.find_objects(By.NAME, "LetterTestPanel(Clone)"):
        return "audio_letter"
    if altdriver.find_objects(By.NAME, "LetterWordText Variant(Clone)"):
        return "letter_to_word"
    if altdriver.find_objects(By.NAME, "MatchShapeImage(Clone)"):
        return "word_to_image"
    if altdriver.find_objects(By.NAME, "WordAudioShape(Clone)"):
        return "audio"
    if altdriver.find_objects(By.NAME, "WordMeaningShape(Clone)"):
        return "meaning"
    if altdriver.find_objects(By.NAME, "FillWord(Clone)"):
        return "spelling"
    if altdriver.find_objects(By.NAME, "Context"):
        return "context"
    if altdriver.find_objects(By.NAME, "QuestionTemplate(Clone)"):
        return "image_4_voices"
    if altdriver.find_objects(By.NAME, "ImageAudioShape(Clone)"):
        return "audio_to_image"

    return "unknown"


def open_exam(altdriver, timeout=60):
    """From a just-clicked exam level on the map, wait until the exam is showing.

    Same idea as ``open_level_to_activities`` but for an exam node: press
    through whatever intro the level shows and return once the exam pages are
    up (``TestNumText`` is the "1/3" counter). Never raises.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_element(altdriver, "TestNumText") is not None:
            # The counter shows before the page's widgets are built. Solving
            # immediately reads the type off a half-built page and runs the
            # WRONG solver (seen live: 'swap_letters' picked in the same second
            # the exam icon was pressed), so let the page appear properly.
            time.sleep(EXAM_APPEAR_SETTLE_SECONDS)
            return True
        if find_element(altdriver, "nextButton") is not None:
            click_by_name(altdriver, "nextButton")
            time.sleep(3)
            continue
        time.sleep(2)
    try:
        now = altdriver.get_current_scene()
    except Exception:
        now = "unknown"
    logging.error(f"[Exam] exam pages not reached in {timeout}s (scene: {now})")
    return False


def solve_exam_pages(altdriver, label="", dismiss_help=False):
    """Solve the 3 pages of an exam that is ALREADY open, and submit it.

    Split out of ``solve_exam`` so a test can navigate to the exam its own way
    (e.g. a Rally case that names a map level) and still reuse the proven
    per-page detection and solvers.

    ``dismiss_help`` closes the parrot's instruction bubble once per page. It is
    OFF by default and switched on only by the guest flow: a logged-in user does
    not get that popup, and pressing 'HelpButton' where no bubble is showing
    would OPEN one right over the controls the solver needs.

    Returns ``{"parts": int, "problems": [str], "submitted": bool}`` and never
    raises: a caller that fails on ``problems`` leaves the app on the screen
    that broke, so the failure screenshot shows it.
    """
    from Activities import activitiesDemo as A  # local import breaks circulars

    def next_test():
        click_by_name(altdriver, "Next_Test")
        time.sleep(1)

    def page_number():
        """The page the exam is showing ('2/3' -> 2), or None."""
        try:
            return int((get_text_by_name(altdriver, "TestNumText") or "").split("/", 1)[0])
        except Exception:
            return None

    def submit_and_confirm(current, solver, attempts=3):
        """Submit the exam, and PROVE it was accepted.

        The app accepts a submit only when every question is answered: press it
        with anything still open and it simply stays on the page — the results
        screen never comes. So a submit with no results screen does NOT mean the
        button was missed, it means something is still unanswered. Solve what is
        left and submit again, rather than clicking Collect at a screen that is
        not there and reporting the exam as submitted.
        """
        for attempt in range(1, attempts + 1):
            click_by_name(altdriver, "SubmitButton")
            click_by_name(altdriver, "YesButton")
            time.sleep(1.5)
            if wait_for_any(altdriver, EXAM_RESULT_MARKERS, timeout=20):
                if attempt > 1:
                    logging.info(f"[Exam] submitted on attempt {attempt}")
                return True
            logging.warning(f"[Exam] the submit was not accepted "
                            f"(attempt {attempt}/{attempts}) — the exam still has "
                            f"unanswered questions; solving them and re-submitting")
            if not solver:
                break
            try:
                solver(altdriver)
            except Exception as e:                   # noqa: BLE001
                logging.error(f"[Exam] re-solve before re-submit failed: {e}")
                break
        return False

    def advance_from(current, solver, attempts=3):
        """Leave page ``current``, making sure it is FULLY answered first.

        The app will not advance a page with anything left unanswered, so a
        page that does not change is not a missed button press — it is a solver
        that thought it was done and was not (one tile left in the bank is
        enough). Running the solver again picks up what it missed; only when
        that stops helping is it a real failure.
        """
        for attempt in range(1, attempts + 1):
            next_test()
            time.sleep(1.5)
            if page_number() != current:
                return True
            logging.warning(f"[Exam] page {current} did not advance "
                            f"(attempt {attempt}/{attempts}) — it is not fully "
                            f"answered; running the solver again")
            if not solver:
                break
            try:
                solver(altdriver)
            except Exception as e:                   # noqa: BLE001
                logging.error(f"[Exam] re-solve of page {current} failed: {e}")
                break
        return page_number() != current

    exam_solvers = {
        "spelling": A.exam_spelling,
        "audio_letter": A.exams_3rd_audio_to_letter_matrix,
        "letter_to_word": A.exams_3rd_letter_to_word_image_match,
        "word_to_image": A.exams_word_to_image,
        "audio": A.exams_audio_to_meaning,
        "meaning":A.exams_word_to_meaning,
        "spelling":A.exam_spelling,
        'context':A.exam_multiple_choice,
        "image_4_voices":A.exams_image_for_voices,
        "audio_to_image":A.exams_image_to_audio,
        "swap_letters": A.exam_swap_letters,
        "shuffled_context": A.exam_shuffled_context,

    }

    problems = []          # parts that failed or couldn't be solved
    parts_seen = 0
    submitted = False

    # Start from the first page. The exam can be entered part-way through (a
    # previous attempt, or a human clicking ahead), and the loop only moves
    # forward — without rewinding, earlier pages would be submitted unanswered.
    for _ in range(6):
        try:
            page = (get_text_by_name(altdriver, "TestNumText") or "").strip()
            index = int(page.split("/", 1)[0])
        except Exception:
            break
        if index <= 1:
            break
        logging.info(f"[Exam] starting on page {page} — going back")
        click_by_name(altdriver, "Prev_Test")
        time.sleep(2)

    # The page count is whatever TestNumText says ("1/2", "1/3", ...) — exams
    # are not always 3 pages, and a page type can appear on any of them, so the
    # loop follows the counter instead of assuming a fixed list of labels.
    total_pages = 0
    seen = set()
    while True:
        try:
            label = (get_text_by_name(altdriver, "TestNumText") or "").strip()
            current, total_pages = (int(p) for p in label.split("/", 1))
        except Exception as e:      # exam not on screen, or an odd counter
            logging.error(f"[Exam] could not read the page counter: {e}")
            break
        if label in seen:           # Next_Test did not advance — don't loop forever
            logging.error(f"[Exam] still on page {label} after Next_Test; stopping")
            problems.append(f"page {label}: did not advance")
            break
        seen.add(label)
        parts_seen += 1

        logging.info(f"[Exam] Solving page {label}")
        # GUEST runs only: a guest's exam page opens behind the parrot's
        # instruction bubble. Close it FIRST — it types itself out, so waiting
        # for it wastes seconds a page, and it sits over the controls the solver
        # is about to use. Exactly ONE press per page: 'HelpButton' toggles the
        # bubble, so a second press would bring it back.
        if dismiss_help:
            dismiss_help_popup(altdriver)
        # Read the type only once the page has settled INTO that type.
        exam_type = detect_exam_type_settled(altdriver)
        solver = exam_solvers.get(exam_type)

        if solver:
            try:
                solver(altdriver)
                logging.info(f"[Exam] Solved page {label} using {solver.__name__}")
            except Exception as e:
                logging.error(f"[Exam] Failed on page {label} ({exam_type}): {e}")
                problems.append(f"page {label} ({exam_type}): {e}")
        else:
            logging.warning(f"[Exam] Unknown exam type on page {label}, skipping.")
            problems.append(f"page {label}: unknown exam type '{exam_type}'")

        if current < total_pages:
            if not advance_from(current, solver):
                logging.error(f"[Exam] page {label} stayed unanswered; stopping")
                shot = capture_failure_screenshot(altdriver, f"exam_page_{current}")
                problems.append(f"page {label}: could not be completed "
                                f"(the app would not advance past it)"
                                + (f" [screenshot: {shot}]" if shot else ""))
                break
        else:
            if submit_and_confirm(current, solver):
                click_by_name(altdriver, "Collect")
                time.sleep(5)
                click_by_name(altdriver, "BackButton")
                time.sleep(2)
                submitted = True
            else:
                shot = capture_failure_screenshot(altdriver, f"exam_submit_{current}")
                logging.error(f"[Exam] the exam would not submit from page {label}")
                problems.append(f"page {label}: the exam would not submit — "
                                f"questions are still unanswered"
                                + (f" [screenshot: {shot}]" if shot else ""))
            break

    # Pages that were never opened are a failure, not a silent pass: entering an
    # exam part-way through (Prev_Test does not go back) would otherwise submit
    # with the earlier pages unanswered and still report no problems.
    if total_pages and parts_seen < total_pages:
        problems.append(f"only {parts_seen}/{total_pages} pages were answered — "
                        f"the exam was entered part-way through")

    logging.info(f"[Exam] Finished {parts_seen}/{total_pages or '?'} page(s)"
                 + (f" for {label}" if label else "")
                 + (f"; problems: {problems}" if problems else ""))
    return {"parts": parts_seen, "total": total_pages,
            "problems": problems, "submitted": submitted}


def solve_exam(altdriver, class_id, lesson_num):
    """Navigate to a lesson's exam through the class map and solve it.

    Unchanged behaviour for the runner's lesson flows: raises on failure so the
    run records a FAILED row with the stuck-screen screenshot, and appends a
    PASSED row on success so the exam shows up in the report.
    """
    from datetime import datetime as _dt
    _start = _dt.now()

    enter_to_level(altdriver, class_id, lesson_num, type="exam")
    time.sleep(4)
    result = solve_exam_pages(altdriver, label=f"lesson {lesson_num}")

    dur = f"{int((_dt.now() - _start).total_seconds())}s"
    if result["parts"] == 0:
        raise RuntimeError(
            f"Exam lesson {lesson_num} never opened — no exam parts were found "
            f"(navigation/level issue).")
    if result["problems"]:
        raise RuntimeError(f"Exam lesson {lesson_num} failed: "
                           + " | ".join(result["problems"]))
    activity_report.append({
        "activity": f"Exam · lesson {lesson_num}",
        "status": "PASSED",
        "error": "",
        "duration": dur,
        "platform": getattr(altdriver, "platform", "Unknown"),
    })


def solve_lesson(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels(altdriver, class_id, lesson_num)
        time.sleep(2)
        solve_exam(altdriver, class_id, lesson_num)
        time.sleep(2)
    except Exception as e:
        print(f"[ERROR] Failed to solve lesson {lesson_num}: {e}")

def solve_level_express(altdriver, difficulty):
    """
    Executes opened level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (int or str): 0, 1, 2 or "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Starting level solving for difficulty: {difficulty}")

    # Normalize difficulty
    if isinstance(difficulty, str):
        difficulty = {"easy": 0, "medium": 1, "hard": 2}.get(difficulty.lower(), -1)

    if difficulty not in [0, 1, 2]:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        raise ValueError(f"Unknown difficulty: {difficulty}")

    repetitions = {0: 1, 1: 1, 2: 1}[difficulty]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)
def solve_level_express_hard(altdriver, difficulty):
    """
    Executes opened level flow(s) based on difficulty level:
    - Easy → 3 activities
    - Medium → 2 activities
    - Hard → 1 activity

    Args:
        altdriver (AltDriver): AltTester driver instance
        difficulty (int or str): 0, 1, 2 or "easy", "medium", "hard"
    """
    logging.info(f"[solve_level] Starting level solving for difficulty: {difficulty}")

    # Normalize difficulty
    if isinstance(difficulty, str):
        difficulty = {"hard": 2}.get(difficulty.lower(), -1)

    if difficulty not in [2]:
        logging.error(f"[solve_level] Invalid difficulty level: {difficulty}")
        raise ValueError(f"Unknown difficulty: {difficulty}")

    repetitions = {2: 1}[difficulty]
    logging.info(f"[solve_level] Will run {repetitions} open-level flow(s)")

    for i in range(repetitions):
        logging.info(f"[solve_level] Executing flow {i + 1}/{repetitions}")
        try:
            handle_level_flow(altdriver)
        except Exception as e:
            logging.warning(f"[solve_level] Flow {i + 1} failed: {e}")

    logging.info(f"[solve_level] Finished solving level for difficulty {difficulty}")
    time.sleep(4)

def solve_lesson_express(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels_express(altdriver, class_id, lesson_num)
        time.sleep(5)
        solve_exam(altdriver, class_id, lesson_num)
        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] Failed to solve lesson {lesson_num}: {e}")

def solve_lesson_express_hard(altdriver, class_id, lesson_num):
    """Solve full lesson including all levels and the exam."""
    try:
        print(f"[INFO] Solving lesson {lesson_num} for class {class_id}")
        solve_lesson_levels_express_hard(altdriver, class_id, lesson_num)
        time.sleep(5)
        solve_exam(altdriver, class_id, lesson_num)
        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] Failed to solve lesson {lesson_num}: {e}")


def solve_lessons_express_hard(altdriver, class_id, num_lessons, start_lesson=0):
    """
    Solve a range of lessons (hard express flow).

    Args:
        altdriver: AltTester driver instance.
        class_id: Class ID to solve lessons for.
        num_lessons (int): How many lessons to run.
        start_lesson (int): First lesson number to start from (default 0).

    Example:
        # Run lessons 0..6 (7 lessons)
        solve_lessons_express_hard(altdriver, class_id, num_lessons=7)
    """
    end_lesson = start_lesson + num_lessons
    print(f"[INFO] Solving {num_lessons} lesson(s): {start_lesson}..{end_lesson - 1} for class {class_id}")
    for lesson_num in range(start_lesson, end_lesson):
        # solve_lesson_express_hard already guards each lesson with try/except,
        # so a failure in one lesson won't stop the rest of the run.
        solve_lesson_express_hard(altdriver, class_id, lesson_num)

def solve_lesson_levels_express(altdriver, class_id, lesson_num):
    difficulties = [("easy", 0), ("medium", 1), ("hard", 2)]

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            logging.warning(f"[solve_lesson_levels] Skipped {level_name} level — no level found or failed to enter.")
            continue

        try:
            time.sleep(2)
            solve_level_express(altdriver, diff)
            back_button = altdriver.wait_for_object(By.NAME, 'Back')
            back_button.click()
            time.sleep(6)
        except Exception as e:
            logging.error(f"[solve_lesson_levels] Error solving {level_name} level: {e}")

def solve_lesson_levels_express_hard(altdriver, class_id, lesson_num):
    difficulties = [("hard", 2)]

    for level_name, diff in difficulties:
        logging.info(f"[solve_lesson_levels] Solving {level_name} level...")

        if not enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty=level_name):
            logging.warning(f"[solve_lesson_levels] Skipped {level_name} level — no level found or failed to enter.")
            continue

        try:
            time.sleep(2)
            solve_level_express_hard(altdriver, diff)
            back_button = altdriver.wait_for_object(By.NAME, 'Back')
            back_button.click()
            time.sleep(6)

        except Exception as e:
            logging.error(f"[solve_lesson_levels] Error solving {level_name} level: {e}")

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

def run_all_exams(altdriver, class_id):
    """
    Runs solve_exam for all lessons (0–18) in sequence.
    """
    for lesson_number in range(10, 40):  # lessons 0 to 18 inclusive
        try:
            logging.info(f"[Exam Runner] Starting exam for lesson {lesson_number}")
            solve_exam(altdriver, class_id, lesson_number)
            logging.info(f"[Exam Runner] Completed exam for lesson {lesson_number}")
            time.sleep(3)  # short pause between lessons
        except Exception as e:
            logging.error(f"[Exam Runner] Error at lesson {lesson_number}: {e}")
            continue

import os
import logging
import requests
from datetime import datetime

def _load_project_env():
    """Populate env vars from a local, gitignored .env (or rally/email env) if
    they aren't already set. Mirrors run_panel's minimal loader so direct pytest
    runs pick up credentials too. Never overrides values already in the env."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in (".env", "rally.env", "automation_email.env"):
        try:
            with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            continue


_load_project_env()

VT_LOGIN_URL = os.getenv("VT_LOGIN_URL", "https://login.vocatooki.com/access/auth")
VT_GAME = os.getenv("VT_GAME", "vt")

# Credentials are read from the environment (see .env.template). Never hard-code
# secrets here — this file is tracked in git.
VT_USERNAME = os.getenv("VT_USERNAME")
VT_PASSWORD = os.getenv("VT_PASSWORD")


_TOKEN_CACHE = {
    "access_token": None
}


def format_exam_timestamp(ms_value):
    if not ms_value:
        return None
    try:
        return datetime.fromtimestamp(ms_value / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ms_value


def extract_user_id_from_userid_examid(userid_examid: str) -> str:
    if "_" not in userid_examid:
        raise ValueError(f"Invalid userid_examid format: {userid_examid}")
    return userid_examid.split("_", 1)[0]


def login_and_get_vt_token(username=None, password=None, force_refresh=False):
    """
    Logs in to Voca Tooki auth service and returns a bearer token.
    Caches token in memory for reuse during the same test run.
    """
    if _TOKEN_CACHE["access_token"] and not force_refresh:
        return _TOKEN_CACHE["access_token"]

    username = username or VT_USERNAME
    password = password or VT_PASSWORD

    if not username or not password:
        raise ValueError("Missing VT credentials. Set VT_USERNAME and VT_PASSWORD.")

    payload = {
        "username": username,
        "password": password,
        "game": VT_GAME
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    logging.info("[login_and_get_vt_token] Requesting auth token")

    response = requests.post(VT_LOGIN_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    # support a few common token keys
    token = (
            data.get("jwtToken")
            or data.get("token")
            or data.get("access_token")
            or data.get("jwt")
            or data.get("id_token")
    )

    if not token:
        raise ValueError(f"Token not found in login response. Response keys: {list(data.keys())}")

    _TOKEN_CACHE["access_token"] = token
    return token


def get_auth_headers(token=None, username=None, password=None, force_refresh=False):
    """
    Returns Authorization headers.
    If token is not supplied, fetches it automatically via login.
    """
    bearer = token or login_and_get_vt_token(
        username=username,
        password=password,
        force_refresh=force_refresh
    )

    if not bearer.startswith("Bearer "):
        bearer = f"Bearer {bearer}"

    return {
        "Authorization": bearer,
        "Accept": "application/json"
    }


def get_user_exam_by_userid_examid(userid_examid, class_id=2336, token=None, username=None, password=None):
    """
    Calls:
    GET {VT_DATA_API}/get-user-exams/{user_id}/{class_id}

    Returns only the matching record for userid_examid.
    """
    user_id = extract_user_id_from_userid_examid(userid_examid)
    url = f"{VT_DATA_API}/get-user-exams/{user_id}/{class_id}"

    headers = get_auth_headers(token=token, username=username, password=password)

    logging.info(
        f"[get_user_exam_by_userid_examid] Fetching exam for userid_examid={userid_examid}, class_id={class_id}"
    )

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if isinstance(data.get("data"), list):
                records = data["data"]
            elif isinstance(data.get("exams"), list):
                records = data["exams"]
            else:
                records = [data]
        else:
            logging.warning("[get_user_exam_by_userid_examid] Unexpected response type")
            return None

        for record in records:
            if record.get("userid_examid") == userid_examid:
                return {
                    "userid_examid": record.get("userid_examid"),
                    "delivered_date": record.get("delivered_date"),
                    "delivered_date_readable": format_exam_timestamp(record.get("delivered_date")),
                    "class_id": record.get("class_id"),
                    "lesson_id": record.get("lesson_id"),
                    "name": record.get("name"),
                    "grade": record.get("grade")
                }

        logging.warning(f"[get_user_exam_by_userid_examid] No record found for {userid_examid}")
        return None

    except requests.exceptions.HTTPError as e:
        logging.error(f"[get_user_exam_by_userid_examid] HTTP error: {e}")
        try:
            logging.error(f"[get_user_exam_by_userid_examid] Response text: {response.text}")
        except Exception:
            pass

        # optional retry once with fresh token on 401
        if getattr(response, "status_code", None) == 401 and token is None:
            logging.info("[get_user_exam_by_userid_examid] Token may be expired, retrying with fresh token")
            try:
                fresh_headers = get_auth_headers(
                    username=username,
                    password=password,
                    force_refresh=True
                )
                retry_response = requests.get(url, headers=fresh_headers, timeout=30)
                retry_response.raise_for_status()
                retry_data = retry_response.json()

                if isinstance(retry_data, list):
                    retry_records = retry_data
                elif isinstance(retry_data, dict):
                    if isinstance(retry_data.get("data"), list):
                        retry_records = retry_data["data"]
                    elif isinstance(retry_data.get("exams"), list):
                        retry_records = retry_data["exams"]
                    else:
                        retry_records = [retry_data]
                else:
                    return None

                for record in retry_records:
                    if record.get("userid_examid") == userid_examid:
                        return {
                            "userid_examid": record.get("userid_examid"),
                            "delivered_date": record.get("delivered_date"),
                            "delivered_date_readable": format_exam_timestamp(record.get("delivered_date")),
                            "class_id": record.get("class_id"),
                            "lesson_id": record.get("lesson_id"),
                            "name": record.get("name")
                        }
            except Exception as retry_err:
                logging.error(f"[get_user_exam_by_userid_examid] Retry failed: {retry_err}")

    except requests.exceptions.RequestException as e:
        logging.error(f"[get_user_exam_by_userid_examid] Request error: {e}")
    except ValueError as e:
        logging.error(f"[get_user_exam_by_userid_examid] JSON parse/token error: {e}")

    return None

# example : exam = get_user_exam_by_userid_examid("49295_3", class_id=2336)

# ---------------------------------------------------------------------------
# The placement PRETEST
#
# When the account's CLASS is configured for a pretest in the CRM, GO-Map lands
# on PretestScene instead of the map (see PRETEST_SCENE above). The scene is a
# ship's cabin with seven glowing objects, one per skill:
#
#   listening1/2/3   Reading   speaking1   writing1/2
#
# Tapping one opens an ordinary activity (LISTEN_FIND, RADAR, UNSCRAMBLE_QUIZ,
# TaskScene, ...), which is why the pretest needs no solver of its own -- but a
# whole placement test does not have to be sat to get past it. After FIVE node
# entries the scene offers a Skip, which is what a case wanting the map behind
# the gate actually needs.
#
# Two traps, both found live on 2026-08-30:
#   * A node that has already been played WILL NOT REOPEN. Tapping it does
#     nothing, so the five entries have to walk across the nodes rather than
#     hammering one, and "it did not open" is how a played node is recognised --
#     nothing in the hierarchy marks it.
#   * The scene takes POSITIONAL taps, not object clicks: `AltObject.click()` on
#     a node or on SkipButton is swallowed. The confirm popup that follows is
#     ordinary UI, and its YesButton does take an object click.
# ---------------------------------------------------------------------------
PRETEST_NODES = ("listening1", "listening2", "listening3", "Reading",
                 "speaking1", "writing1", "writing2")
PRETEST_ENTRIES_FOR_SKIP = 5


def _pretest_object(altdriver, name):
    """A pretest object by name whether or not it is active, or None."""
    try:
        for obj in altdriver.get_all_elements(enabled=False):
            if obj.name == name:
                return obj
    except Exception:
        pass
    return None


def pretest_skip_ready(altdriver):
    """True once the pretest is offering its Skip."""
    button = _pretest_object(altdriver, "SkipButton")
    return bool(button and button.enabled)


def _pretest_wait_scene(altdriver, wanted, timeout, equal=True):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            scene = altdriver.get_current_scene()
        except Exception:
            scene = None
        if scene and ((scene == wanted) if equal else (scene != wanted)):
            return scene
        time.sleep(0.6)
    return None


def pretest_skip(altdriver, entries=PRETEST_ENTRIES_FOR_SKIP, open_timeout=18,
                 timeout=60):
    """Get past the placement pretest onto the map. Returns True on the map.

    Enters and leaves glowing nodes until the Skip appears, then takes it. The
    nodes are NOT solved -- the point is to reach the map, and a case that needs
    the pretest itself played should drive the activities instead.
    """
    scene = _current_scene(altdriver)
    if scene != PRETEST_SCENE:
        logging.info(f"[Pretest] not on the pretest (scene: {scene}) — nothing to skip")
        return scene == MAP_SCENE

    used = 0
    for node in PRETEST_NODES:
        if pretest_skip_ready(altdriver):
            break
        if used >= entries:
            break
        target = _pretest_object(altdriver, node)
        if target is None:
            continue
        altdriver.tap((float(target.x), float(target.y)))
        opened = _pretest_wait_scene(altdriver, PRETEST_SCENE, open_timeout, equal=False)
        if opened is None:
            # Already played: a finished node simply does not respond, and
            # nothing in the hierarchy says so.
            logging.info(f"[Pretest] '{node}' did not open — already played")
            continue
        when_finish_activity(altdriver)
        back = _pretest_wait_scene(altdriver, PRETEST_SCENE, timeout)
        used += 1
        logging.info(f"[Pretest] entered '{node}' ({opened}) and left again "
                     f"[{used}/{entries}]{'' if back else ' — did NOT return'}")

    if not pretest_skip_ready(altdriver):
        logging.error(f"[Pretest] the Skip never appeared after {used} node "
                      f"entries; the map is still behind the pretest")
        return False

    button = _pretest_object(altdriver, "SkipButton")
    altdriver.tap((float(button.x), float(button.y)))   # object clicks are swallowed here

    # The confirm popup is ordinary UI and DOES take an object click.
    deadline = time.time() + 15
    while time.time() < deadline:
        yes = find_element(altdriver, "YesButton")
        if yes is not None:
            try:
                yes.click()
                logging.info("[Pretest] confirmed the skip")
            except Exception as e:
                logging.warning(f"[Pretest] could not press YesButton: {e}")
            break
        time.sleep(0.5)
    else:
        logging.warning("[Pretest] no confirmation popup appeared after Skip")

    if _pretest_wait_scene(altdriver, MAP_SCENE, timeout):
        logging.info("[Pretest] skipped — the map is open")
        return True
    logging.error(f"[Pretest] skip did not reach the map "
                  f"(scene: {_current_scene(altdriver)})")
    return False
