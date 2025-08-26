# Utility: Google TTS + Pygame Playback
import logging

import time
import traceback

from alttester import By, AltKeyCode, AltDriver
import pytest
import requests
from google.cloud import texttospeech
from pygame import mixer
from datetime import datetime


FAILED_ACTIVITIES = set()
activity_report = []


# Utility: Google TTS + Pygame Playback


def say(word, lang="en"):
    """Speak a word using Google TTS and play it via Pygame."""
    synthesis_input = texttospeech.SynthesisInput(text=word)
    voice = texttospeech.VoiceSelectionParams(language_code=lang, ssml_gender=2)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

    with open("output2.wav", "wb") as out:
        out.write(response.audio_content)

    mixer.music.unload()
    time.sleep(1)
    mixer.music.load("output2.wav")
    mixer.music.play()


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

    return game_object.call_component_method(
        assembly=assembly,
        component_name=component_name,
        method_name=method_name,
        parameters=parameters,
        type_of_parameters=parameter_types
    )


# Login Utility
def login(altdriver, username=None, password=None):
    call_method(altdriver, "AltTesterUtils", "Logout")
    time.sleep(3)
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

def _get_current_activity_with_retry(altdriver, prev_scene=None, max_attempts=6, waits=(1, 2, 3, 5, 5, 5)):
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

    time.sleep(1)
    activity.click()
    time.sleep(2)  # small settle time before polling

    # --- get new scene with retries ---
    scene = _get_current_activity_with_retry(altdriver, prev_scene=prev_scene, max_attempts=6, waits=(5,8,15,25,30,45))
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
        'CROSSWORD2': A.crosswords2
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
    url = f"https://vtbe2025.vocatooki.com/data/get-class-map/{class_id}/{map_id}"
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
        f"[Map Navigation] Attempting to enter level: class_id={class_id}, lesson={lesson_number}, type={type}, difficulty={difficulty}")

    level_num = get_level(class_id, lesson_number, type, difficulty)
    if level_num < 0:
        logging.error(f"[Map Navigation] Invalid level number: {level_num}. Cannot proceed.")
        return False

    try:
        level_objs = altdriver.find_objects(By.PATH,
                                            "/MapCanvas/MapSection/Scroll View/Viewport/Content/Map Backgrounds/Levels/level_icons/*")

        if level_num >= len(level_objs):
            logging.error(f"[Map Navigation] Level index {level_num} out of range ({len(level_objs)} icons).")
            return False

        level_objs[level_num].click()
        time.sleep(4)
        logging.info(f"[Map Navigation] Entered level index {level_num} successfully.")
        return True

    except Exception as e:
        logging.error(f"[Map Navigation] Exception while clicking level: {e}")
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
        'context':A.exam_multiple_choice
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
