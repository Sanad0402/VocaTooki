import logging
from alttester import By, AltKeyCode, AltDriver
from alttester.exceptions import ComponentNotFoundException
import re
import requests
import io
import time


FAILED_ACTIVITIES = set()
activity_report = []
# Generic Method Invoker
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
        response = requests.post("http://vtbe.vocatooki.com/data/get-user-state", json=payload)
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
        'TETRIS':A.tetris
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
    url = f"https://vtbe.vocatooki.com/data/get-class-map/{class_id}/{map_id}"
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
        # --- Try standard map path first ---
        level_objs = altdriver.find_objects(By.PATH, "/MainMap(Clone)/Map Backgrounds/Levels/level_icons/*")

        # --- If no icons found, fallback to 5thMap path ---
        if not level_objs or len(level_objs) == 0:
            logging.warning("[Map Navigation] No levels found under MainMap(Clone). Trying 5thMap(Clone)...")
            level_objs = altdriver.find_objects(By.PATH, "/5thMap(Clone)/Map Backgrounds/Levels/level_icons/*")

        # --- Validate result ---
        if not level_objs or len(level_objs) == 0:
            logging.error("[Map Navigation] No level icons found in either MainMap or 5thMap.")
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
    }


def _find_level_icons(altdriver):
    """Level icons of whichever map is currently loaded.

    The anchored search works for every map prefab (MainMap, 5thMap, ...);
    the two explicit paths are kept as fallbacks.
    """
    for path in ("//Levels/level_icons/*",
                 "/MainMap(Clone)/Map Backgrounds/Levels/level_icons/*",
                 "/5thMap(Clone)/Map Backgrounds/Levels/level_icons/*"):
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
MAP_SCENE = "MapScene"

# Every feature reachable from the start screen, surveyed on the live app.
# button  - what to click on the start screen
# scene   - the scene it loads ("" when it opens a popup on the start screen)
# markers - objects that prove the feature is really open
# back    - how to leave it (None: no back control exists, needs ensure_on_map)
APP_FEATURES = {
    "map":            {"button": "GO-Map", "scene": MAP_SCENE,
                       "markers": ["BackButton"], "back": "BackButton"},
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

    btn = find_element(altdriver, spec["button"])
    if btn is None:
        logging.error(f"[Feature] '{spec['button']}' is not on the start screen")
        return False
    click_by_name(altdriver, spec["button"])

    deadline = time.time() + timeout
    while time.time() < deadline:
        if spec["scene"] and _current_scene(altdriver) == spec["scene"]:
            logging.info(f"[Feature] '{feature}' open (scene {spec['scene']})")
            return True
        for marker in spec["markers"]:
            if find_element(altdriver, marker) is not None:
                logging.info(f"[Feature] '{feature}' open (found {marker})")
                return True
        time.sleep(2)

    logging.error(f"[Feature] '{feature}' did not open "
                  f"(scene: {_current_scene(altdriver)})")
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


def wait_for_scene(altdriver, scene, timeout=40, poll=0.5):
    """Poll until the app is in ``scene``. Returns bool, never raises."""
    end = time.time() + timeout
    while True:
        if _current_scene(altdriver) == scene:
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


def dismiss_help_popup(altdriver, settle=0.4):
    """Close the parrot's instruction bubble. Returns True when it acted.

    Every exam page opens with one ("All you have to do is drag the ...") and it
    TYPES ITSELF OUT, so waiting for it to finish costs seconds on every page —
    the solver can start the moment it is gone. 'HelpButton' is the app's own
    control for that bubble; tapping an empty point is the fallback.

    Call this only where the popup is actually expected (entering a page): the
    button toggles the bubble, so pressing it on a clean screen would OPEN one.
    """
    obj = find_any(altdriver, "HelpButton")
    if obj is not None and _press(obj):
        logging.info("[Help] closed the instruction popup via 'HelpButton'")
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
    _LAST_LOGIN_USER = username
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
        logging.error(f"[Event] could not read the leaderboard: {e}")
        return rows

    # A row is a name and a score on the SAME line — pair them by y, not by
    # order, so a re-sorted board cannot pair a name with someone else's score.
    for y, name in sorted(names):
        nearest = min(scores, key=lambda s: abs(s[0] - y), default=None)
        if nearest is not None and abs(nearest[0] - y) < 25:
            rows.append((name, nearest[1]))
    for name, score in rows:
        logging.info(f"[Event] leaderboard: {name!r} = {score}")
    # Keep the board itself: it is the other half of the comparison, and it is
    # gone as soon as the run closes it.
    capture_evidence(altdriver, "event-leaderboard", tc_id=tc_id)
    return rows


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


def capture_evidence(altdriver, label, tc_id=""):
    """A screenshot kept on purpose, not as a failure artefact. Returns a name.

    Written into the run's own folder so it shows up with that run's frames in
    the panel, and never counted against the per-run budget: these frames are
    what a human looks at afterwards, so "we ran out of allowance" must not be
    the reason one is missing.
    """
    try:
        from runner import screenshots as _shots    # local: avoids a cycle
        path = _shots.evidence(altdriver, label, tc_id=tc_id)
        if path is not None:
            return path.name
    except Exception as e:                          # noqa: BLE001
        logging.debug(f"[Shot] run-folder evidence unavailable: {e}")
    return capture_failure_screenshot(altdriver, label)


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
    GET https://vtbe.vocatooki.com/data/get-user-exams/{user_id}/{class_id}

    Returns only the matching record for userid_examid.
    """
    user_id = extract_user_id_from_userid_examid(userid_examid)
    url = f"https://vtbe.vocatooki.com/data/get-user-exams/{user_id}/{class_id}"

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