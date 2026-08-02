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


def solve_activity_in_level(altdriver, target_scene, title_hint=None):
    """Open ``target_scene``'s activity in the current level, solve AND VERIFY it.

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
        time.sleep(5)

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
        # Not the one — back out to the activity selection and try the next.
        logging.info(f"[Activity] thumb {i} opened '{scene}', not {target_scene}; going back")
        try:
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception as e:
            logging.warning(f"[Activity] LoadPreviousScene failed: {e}")
            when_finish_activity(altdriver)
        time.sleep(5)

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





def detect_exam_type(altdriver):
    """Detect active exam type based on UI elements.

    Called per PAGE, not per exam: the pages of one exam are usually different
    types, and a given type can appear on any page.
    """
    # Rows of scrambled letters; drag one onto another to swap them.
    if altdriver.find_objects(By.NAME, "SwapLetterText(Clone)"):
        return "swap_letters"
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


def solve_exam_pages(altdriver, label=""):
    """Solve the 3 pages of an exam that is ALREADY open, and submit it.

    Split out of ``solve_exam`` so a test can navigate to the exam its own way
    (e.g. a Rally case that names a map level) and still reuse the proven
    per-page detection and solvers.

    Returns ``{"parts": int, "problems": [str], "submitted": bool}`` and never
    raises: a caller that fails on ``problems`` leaves the app on the screen
    that broke, so the failure screenshot shows it.
    """
    from Activities import activitiesDemo as A  # local import breaks circulars

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
        "audio_to_image":A.exams_image_to_audio,
        "swap_letters": A.exam_swap_letters,

    }

    problems = []          # parts that failed or couldn't be solved
    parts_seen = 0
    submitted = False

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
        exam_type = detect_exam_type(altdriver)
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
            next_test()
            time.sleep(2)
        else:
            click_by_name(altdriver, "SubmitButton")
            click_by_name(altdriver, "YesButton")
            time.sleep(1)
            click_by_name(altdriver, "Collect")
            time.sleep(5)
            click_by_name(altdriver, "BackButton")
            time.sleep(2)
            submitted = True
            break

    logging.info(f"[Exam] Finished {parts_seen}/{total_pages or '?'} page(s)"
                 + (f" for {label}" if label else "")
                 + (f"; problems: {problems}" if problems else ""))
    return {"parts": parts_seen, "problems": problems, "submitted": submitted}


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