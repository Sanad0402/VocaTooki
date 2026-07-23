import logging
from alttester import By, AltKeyCode, AltDriver
from alttester.exceptions import ComponentNotFoundException
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
        'RINGS':A.rings
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

        activity_map[scene](altdriver)

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

        end_time = datetime.now()
        activity_report.append({
            "activity": scene,
            "status": "FAILED",
            "error": error_msg,
            "duration": str(end_time - start_time),
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


def enter_level_number(altdriver, level_num, retries=3):
    """Click the map level labelled ``level_num`` (as shown on the icon).

    For Rally cases whose description names the exact map level ("level 44"),
    so no lesson/difficulty resolution through the class map is needed.
    The number is the HUMAN-VISIBLE label: icons are numbered from 1 on screen
    while the icon list is 0-based, so label N is index N-1 (clicking index 44
    opened the level labelled 45).
    Right after login the app is on the home screen, not the map, so when no
    icons are visible this first navigates there via the GO-Map button.
    """
    logging.info(f"[Map Navigation] Entering level number {level_num} directly")
    try:
        level_objs = []
        for attempt in range(retries):
            level_objs = _find_level_icons(altdriver)
            if level_objs:
                break
            # Not on the map (e.g. fresh login lands on the home screen).
            logging.info("[Map Navigation] No level icons visible — clicking GO-Map")
            click_by_name(altdriver, "GO-Map")
            time.sleep(12)      # the map scene takes a while to load
        if not level_objs:
            logging.error("[Map Navigation] No level icons found (not on a map?).")
            return False
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


def open_level_to_activities(altdriver, timeout=30):
    """From a just-clicked level, reach ActivitySelectionScene.

    Tolerant version of the opening steps of handle_level_flow: an already
    opened level goes straight there; a fresh one passes the intro
    (nextButton) and the vending machine (Toggle). Returns True when the
    activity selection screen is showing.
    """
    time.sleep(2)
    scene = altdriver.get_current_scene()
    if scene != 'ActivitySelectionScene':
        click_by_name(altdriver, "nextButton")
        time.sleep(3)
        if altdriver.get_current_scene() == 'VendingMachineScene':
            click_by_name(altdriver, "Toggle")
            time.sleep(15)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if altdriver.get_current_scene() == 'ActivitySelectionScene':
            return True
        time.sleep(2)
    logging.error(f"[Level Flow] ActivitySelectionScene not reached (now: {altdriver.get_current_scene()})")
    return False


def solve_activity_in_level(altdriver, target_scene):
    """Find the activity thumb that opens ``target_scene``, solve it, exit.

    A level holds several ActivityThumbs and which one is which activity is
    only knowable by opening it: click a thumb, read GetCurrentActivity, and
    if it is not the target go back and try the next. When the target comes up
    its solver runs (same dispatch table as run_activity) and the finish popup
    is exited. Returns True if the target activity was found and solved.
    """
    solvers = get_activity_solver_map()
    if target_scene not in solvers:
        logging.error(f"[Activity] No solver mapped for '{target_scene}'")
        return False

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
            solvers[target_scene](altdriver)
            time.sleep(4)
            when_finish_activity(altdriver)
            time.sleep(2)
            return True
        # Not the one — back out to the activity selection and try the next.
        logging.info(f"[Activity] thumb {i} opened '{scene}', not {target_scene}; going back")
        try:
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception as e:
            logging.warning(f"[Activity] LoadPreviousScene failed: {e}")
            when_finish_activity(altdriver)
        time.sleep(5)

    logging.error(f"[Activity] {target_scene} not found among {total} thumbs")
    return False


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





def detect_exam_type(altdriver):
    """Detect active exam type based on UI elements."""
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


def solve_exam(altdriver, class_id, lesson_num):
    from Activities import activitiesDemo as A  # local import breaks circulars


    """
    Efficiently solves all 3 exam parts based on fast detection of type.
    """
    enter_to_level(altdriver, class_id, lesson_num, type="exam")
    time.sleep(4)

    def next_test():
        click_by_name(altdriver, "Next_Test")
        time.sleep(1)

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
        "audio_to_image":A.exams_image_to_audio

    }

    for part in ['1/3', '2/3', '3/3']:
        test_num = get_text_by_name(altdriver, "TestNumText")
        if test_num != part:
            continue

        logging.info(f"[Exam] Solving part {part}")
        exam_type = detect_exam_type(altdriver)
        solver = exam_solvers.get(exam_type)

        if solver:
            try:
                solver(altdriver)
                logging.info(f"[Exam] Solved part {part} using {solver.__name__}")
            except Exception as e:
                logging.error(f"[Exam] Failed on part {part} ({exam_type}): {e}")
        else:
            logging.warning(f"[Exam] Unknown exam type in part {part}, skipping.")

        if part != '3/3':
            next_test()
        else:
            click_by_name(altdriver, "SubmitButton")
            click_by_name(altdriver, "YesButton")
            time.sleep(1)
            click_by_name(altdriver, "Collect")
            time.sleep(5)
            click_by_name(altdriver, "BackButton")
            time.sleep(2)

    logging.info("[Exam] Finished all parts.")


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