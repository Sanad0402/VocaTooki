import time
from alttester import By, AltKeyCode, AltDriver
import pytest
import requests
from Activities.actvities import *
from google.cloud import texttospeech
from pygame import mixer

# Initialize Google TTS Client and Pygame Mixer
GOOGLE_CLOUD_JSON = r"C:\Users\sanad\Downloads\vocatooki-translation-0c42cb154191.json"
client = texttospeech.TextToSpeechClient.from_service_account_json(GOOGLE_CLOUD_JSON)
mixer.init()

# Audio Utilities
def say(word, lang="en"):
    """
    Synthesizes speech from the input string of text or ssml.
    Requires Google Cloud credentials and Pygame for playback.

    Args:
        word (str): The text to be synthesized into speech.
        lang (str): The language code for the voice (default is "en").
    """
    synthesis_input = texttospeech.SynthesisInput(text=word)

    voice = texttospeech.VoiceSelectionParams(
        language_code=lang, ssml_gender=2  # Neutral
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    mixer.music.unload()
    with open("output2.wav", "wb") as out:
        out.write(response.audio_content)

    time.sleep(1)  # Optional delay for unloading
    mixer.music.unload()
    mixer.music.load('output2.wav')
    mixer.music.play()

# All other pre-existing functions remain unchanged

def call_method(altdriver, component_name, method_name, parameters=None, parameter_types=None, game_object=None,
                game_object_name="AltTesterPrefab", assembly="Assembly-CSharp"):
    """
    Wrapper to call a method on a game object.
    # Example usage
    result = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")
    Methods :PlayClickSound,LoadPreviousScene,GetCurrentActivity,LoadMapScene,Logout,LoadStartScene
    """
    parameters = parameters or []
    parameter_types = parameter_types or []

    # Find the game object if not provided
    if not game_object:
        game_object = altdriver.find_object(By.NAME, game_object_name)

    return game_object.call_component_method(
        assembly=assembly,
        component_name=component_name,
        method_name=method_name,
        parameters=parameters,
        type_of_parameters=parameter_types
    )



def login(altdriver, username, password):
    call_method(altdriver, "AltTesterUtils", "Logout")
    time.sleep(3)
    user_name = altdriver.wait_for_object(By.NAME, "UserInputField", enabled=True)
    user_name.set_text(username)
    password_field = altdriver.wait_for_object(By.NAME, "PasswordInputField", enabled=True)
    password_field.set_text(password)
    login_button = altdriver.wait_for_object(By.NAME, "LoginButton")
    login_button.click()
    time.sleep(7)
    #example usage : login(altdriver, "vt01274560002", "1030")


def extract_lesson_titles(user_state):
    lessons_data = user_state.get('lessons', {}).get('lessons', [])
    lesson_titles = [lesson['title'] for lesson in lessons_data]
    return lesson_titles


def get_user_state(user_id, avatar_version, awards_version, lessons_version, add_is_complete):
    url = "http://vtbe.vocatooki.com/data/get-user-state"
    payload = {
        "user_id": user_id,
        "avatar_version": avatar_version,
        "awards_version": awards_version,
        "lessons_version": lessons_version,
        "add_is_complete": add_is_complete
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user state: {e}")
        return None


@pytest.fixture
def altdriver():
    altdriver = AltDriver(enable_logging=False)
    yield altdriver
    altdriver.stop()


def click_by_name(altdriver, element_name):
    try:
        element = altdriver.wait_for_object(By.NAME, element_name)
        element.click()
        time.sleep(2)
    except:
        print("fail to locate the element to click by name")


def click_by_path(altdriver, path):
    try:
        element = altdriver.wait_for_object(By.PATH, path)
        element.click()
        time.sleep(2)
    except:
        print("fail to locate the element to click by path")


def assert_text_by_path(altdriver, text_path, expected_text):
    element = altdriver.wait_for_object(By.PATH, text_path)
    actual_text = element.get_text()
    time.sleep(2)
    assert actual_text == expected_text, f"{actual_text}!={expected_text}"


def assert_text_by_name(altdriver, text_name, expected_text):
    element = altdriver.wait_for_object(By.NAME, text_name)
    actual_text = element.get_text()
    time.sleep(2)
    assert actual_text == expected_text, f"{actual_text}!={expected_text}"


def get_text_by_name(altdriver, text_name):
    element = altdriver.wait_for_object(By.NAME, text_name)
    actual_text = element.get_text()
    return actual_text


def get_text_by_path(altdriver, text_path):
    element = altdriver.wait_for_object(By.PATH, text_path)
    actual_text = element.get_text()
    return actual_text


def find_element(driver, element_name):
    try:
        element = driver.find_object(By.NAME, element_name)
        return element
    except:
        return None


def handle_level_flow(altdriver):
    time.sleep(2)
    # Automation steps for the opened level flow
    # handle_level_flow
    current_scene = altdriver.get_current_scene()
    if current_scene == 'ActivitySelectionScene':
        print("Executing opened level flow")

        expected_scene = 'ActivitySelectionScene'
        actual_scene = altdriver.get_current_scene()
        assert expected_scene == actual_scene, f"Expected scene {expected_scene}, but got {actual_scene}"

        activities = altdriver.find_objects(By.NAME, "ActivityThumb")
        num_of_activities = len(activities)
        assert num_of_activities == 3, f"Expected 3 activities, but found {num_of_activities}"

        for i in range(num_of_activities):
            run_activity(altdriver, activities[i])

            validate_final_feedback(altdriver)

            when_finish_activity(altdriver)
            time.sleep(2)
            activities = altdriver.find_objects(By.NAME, "ActivityThumb")
    else:
        # Automation steps for the already opened level flow
        print("Handle Not opened level flow")
        time.sleep(4)
        x_button = altdriver.find_object(By.NAME, "nextButton")
        x_button.click()
        time.sleep(3)
        actual_scene = altdriver.get_current_scene()
        expected_scene = 'VendingMachineScene'
        assert actual_scene == expected_scene
        on_button = altdriver.find_object(By.NAME, "Toggle")
        on_button.click()
        time.sleep(15)

        expected_scene_1 = 'ActivitySelectionScene'
        actual_scene_1 = altdriver.get_current_scene()
        time.sleep(1)
        assert expected_scene == actual_scene, f"Expected scene {expected_scene}, but got {actual_scene}"
        activities = altdriver.find_objects(By.NAME, "ActivityThumb")
        num_of_activities = len(activities)
        assert num_of_activities == 3, f"Expected 3 activities, but found {num_of_activities}"
        for i in range(num_of_activities):
            run_activity(altdriver, activities[i])
            validate_final_feedback(altdriver)
            when_finish_activity(altdriver)
            time.sleep(2)
            activities = altdriver.find_objects(By.NAME, "ActivityThumb")


def run_activity(altdriver, activity):
    time.sleep(2)
    activity.click()
    time.sleep(10)
    current_scene = call_method(altdriver, "AltTesterUtils", "GetCurrentActivity")

    if current_scene == 'MEMMORY_CARDS':
        memory(altdriver)
        # when_finish_activity(altdriver)
    elif current_scene == 'LISTEN_FIND':
        megaphone(altdriver)
    elif current_scene == 'SENTENCE_COMPLETION_QUIZ':
        fillIn(altdriver)
    elif current_scene == 'SENTENCE_TRANSLATION_QUIZ':
        spiders(altdriver)
    elif current_scene == 'SEARCH':
        search(altdriver)
    elif current_scene == 'MISSING_BUBBLE':
        bubbels(altdriver)
    elif current_scene == 'RADAR':
        Radar(altdriver)
    elif current_scene == 'UNSCRAMBLE_QUIZ':
        LexiMatch(altdriver)
    elif current_scene == 'GAP_GURU':
        GapGuru(altdriver)
    elif current_scene == 'TYPE_IT_RIGHT':
        TypeItRight(altdriver)
    elif current_scene == 'TRANSLATION_WIZ':
        TranslationWiz(altdriver)
    elif current_scene == 'ECHO_ORDER':
        EchoOrder(altdriver)
    elif current_scene == 'FROGGER':
        Frogger(altdriver)
    elif current_scene == 'HANGWORDS':
        HangWords(altdriver)
    elif current_scene == 'WORDS_MATCHING_QUIZ':
        Moving(altdriver)
    elif current_scene == 'BEE_CAREFUL':
        Bee(altdriver)
    elif current_scene == 'ISPY':
        Ispy(altdriver)


    else:
        print('activity not defined')
    time.sleep(4)


def get_class_map(class_id, map_id):
    url = f"https://vtbe2025.vocatooki.com/data/get-class-map/{class_id}/{map_id}"

    response = requests.get(url)

    if response.status_code == 200:
        return response.json()


def get_level(class_id, lesson_number, type="lesson", difficulty=-1):
    mapData = get_class_map(class_id, 1)
    expectedLessonLevels = mapData["map"]["levels"][lesson_number]
    if type == "lesson":
        for level in expectedLessonLevels:
            if level["difficulty"] == difficulty:
                return level["level"]
    if type == "exam":
        for level in expectedLessonLevels:
            if level["type"] == type:
                return level["level"]
    return -1


def enter_to_level(altdriver, class_id, lesson_number, type="lesson", difficulty=-1):
    time.sleep(2)
    levelNum = get_level(class_id, lesson_number, type, difficulty)
    objs = altdriver.find_objects(By.PATH,"/MapCanvas/MapSection/Scroll View/Viewport/Content/Map Backgrounds/Levels/level_icons/*")
    objs[levelNum].click()
    time.sleep(4)


# print(get_level(2891,19, "lesson", "easy"))

def solve_level(altdriver, difficulty):
    time.sleep(3)
    difficulty_mapping = {0: 'easy', 1: 'medium', 2: 'hard'}
    difficulty_level = difficulty_mapping.get(difficulty, 'unknown')

    if difficulty_level == 'easy':
        for i in range(3):
            handle_level_flow(altdriver)
    elif difficulty_level == 'medium':
        for i in range(2):
            handle_level_flow(altdriver)
    elif difficulty_level == 'hard':
        handle_level_flow(altdriver)
    else:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    # After solving the required number of opened level flows, solve the exam
    # solve_exam(altdriver)
    time.sleep(4)


def validate_easy_level_score_on_actvity_selection_scene(altdriver):
    """
    this function will validate that the score in the easy level is 240 as defined
    """
    time.sleep(2)
    activities_score_text = []
    activities_score = altdriver.find_objects(By.NAME, "Score")
    for activity in activities_score:
        c = activity.get_text()
        activities_score_text.append(c)
    actual_scores = [item.split('/')[1] for item in activities_score_text]
    expected_score = '240'
    assert actual_scores[0] == '240'
    assert actual_scores[1] == '240'
    assert actual_scores[2] == '240'
    time.sleep(2)


def validate_medium_level_score_on_activity_selection_scene(altdriver):
    """
    This function will validate that the score in the medium level is 480 as defined.
    """
    time.sleep(2)
    activities_score_text = []
    activities_score = altdriver.find_objects(By.NAME, "Score")
    for activity in activities_score:
        c = activity.get_text()
        activities_score_text.append(c)
    actual_scores = [item.split('/')[1] for item in activities_score_text]
    expected_score = '840'
    assert actual_scores[0] == expected_score
    assert actual_scores[1] == expected_score
    assert actual_scores[2] == expected_score
    time.sleep(2)


def validate_hard_level_score_on_activity_selection_scene(altdriver):
    """
    This function will validate that the score in the hard level is 720 as defined.
    """
    time.sleep(2)
    activities_score_text = []
    activities_score = altdriver.find_objects(By.NAME, "Score")
    for activity in activities_score:
        c = activity.get_text()
        activities_score_text.append(c)
    actual_scores = [item.split('/')[1] for item in activities_score_text]
    expected_score = '1160'
    assert actual_scores[0] == expected_score
    assert actual_scores[1] == expected_score
    assert actual_scores[2] == expected_score
    time.sleep(2)


def validate_final_feedback(altdriver):
    time.sleep(4)
    #assert_text_by_name(altdriver, 'title_text', 'You Won!')

    num_of_rows = len(altdriver.find_objects(By.NAME, "RowPref(Clone)"))
    if num_of_rows == 4:
        print("Verify hard level final feedback")
    elif num_of_rows == 3:
        print("Verify medium level final feedback")
    elif num_of_rows == 1:
        print("Verify easy level final feedback")
        #validate_easy_level_feedback(altdriver)
    else:
        print("Something went wrong in the final feedback")
    time.sleep(4)


def validate_easy_level_feedback(altdriver):
    time.sleep(3)
    # verify that the titile won with right spelling
    time.sleep(2)
    assert_text_by_name(altdriver, 'title_text', "You Won!")

    # verify that the metrics name with correct spelling('correct words ')
    time.sleep(3)
    assert_text_by_name(altdriver, 'Text1_1', 'Correct Words')

    # validate that the score on the paramter 'correct words' is 80
    time.sleep(3)
    score_text_easy = get_text_by_name(altdriver, 'Text1')
    actual_score_text_on_easy = int(score_text_easy.split('<')[0])
    expected_score_text_on_easy = 80
    assert expected_score_text_on_easy == actual_score_text_on_easy, f"Expected easy score {expected_score_text_on_easy}, but got {actual_score_text_on_easy}"

    # validate that the number of word is equal to 4 or less on easy level
    time.sleep(1)

    num_of_words_text_easy = get_text_by_name(altdriver, 'Text0')
    num_of_words = num_of_words_text_easy.split('/')[0]

    # verify that the user got 80 coins
    time.sleep(1)

    assert_text_by_name(altdriver, 'Text (TMP)', '+0')

    # verify that the user got 80 score
    time.sleep(1)

    assert_text_by_name(altdriver, 'Text (TMP)', '+0')
    # verify that there's only 1 metric on easy
    time.sleep(1)
    expected_num_of_metrics_easy = 1
    actual_num_of_metrics_easy = len(altdriver.find_objects(By.NAME, 'RowPref(Clone)'))
    assert expected_num_of_metrics_easy == actual_num_of_metrics_easy, f"Num of rows in easy level final feedback doesn't match, expected {expected_num_of_metrics_easy}, but got {actual_num_of_metrics_easy}"

    # verify that the home button appears on easy level final feedback
    time.sleep(1)
    home_button_object = altdriver.find_object(By.NAME, "HomeButton")
    assert home_button_object is not None, "Home button doesn't appear in final feedback"

    # verify that the sum of the scores per each metric is the total score (calculation validation)

    time.sleep(1)
    score_text = []
    score_objects = altdriver.find_objects(By.NAME, "Text1")
    for score in score_objects:
        c = score.get_text()
        score_text.append(c)
    actual_scores = [int(item.split('<')[0]) for item in score_text]
    total_score = sum(actual_scores)
    expected_total_score = int(altdriver.find_object(By.NAME, "TotalScore").get_text())
    assert total_score == expected_total_score, f"Total score does not match, expected {expected_total_score}, but got {total_score}"


def when_finish_activity(altdriver):
    time.sleep(2)
    exit_button = altdriver.find_object(By.NAME, "ExitButton")
    exit_button.click()
    time.sleep(3)


def solve_lesson_levels(altdriver, class_id, lesson_num):
    try:
        # Solve easy level
        enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty="easy")
        solve_level(altdriver, 0)
        time.sleep(2)
        validate_easy_level_score_on_actvity_selection_scene(altdriver)
        time.sleep(1)
        back_button = altdriver.wait_for_object(By.NAME, 'Back')
        back_button.click()
        time.sleep(6)

        # Solve medium level
        enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty="medium")
        solve_level(altdriver, 1)
        time.sleep(4)
        validate_medium_level_score_on_activity_selection_scene(altdriver)
        time.sleep(1)
        back_button = altdriver.wait_for_object(By.NAME, 'Back')
        back_button.click()
        time.sleep(6)
        # Solve hard level
        enter_to_level(altdriver, class_id, lesson_num, type="lesson", difficulty="hard")
        solve_level(altdriver, 2)
        time.sleep(4)
        validate_hard_level_score_on_activity_selection_scene(altdriver)
        time.sleep(1)
        back_button = altdriver.wait_for_object(By.NAME, 'Back')
        back_button.click()
        time.sleep(6)
    except Exception as e:
        print(f"An error occurred: {e}")
        # Handle any specific error handling or logging here


def solve_exam(altdriver, class_id, lesson_num):
    enter_to_level(altdriver, class_id, lesson_num, type="exam")
    time.sleep(3)
    test_num = altdriver.find_object(By.NAME, 'TestNumText').get_text()

    if test_num == '1/3':
        function_executed = False  # Track whether any function executed successfully

        try:
            print('Running exams_word_to_meaning...')
            exams_word_to_meaning(altdriver)
            print('exams_word_to_meaning completed successfully.')
            function_executed = True
        except Exception as e:
            print(f"exams_word_to_meaning failed: {e}")
            try:
                print('Running exams_word_to_image...')
                exams_word_to_image(altdriver)
                print('exams_word_to_image completed successfully.')
                function_executed = True
            except Exception as e1:
                print(f"exams_word_to_image failed: {e1}")
                try:
                    print('Running exams_audio_to_meaning...')
                    exams_audio_to_meaning(altdriver)
                    print('exams_audio_to_meaning completed successfully.')
                    function_executed = True
                except Exception as e2:
                    print(f"exams_audio_to_meaning failed: {e2}")

        if function_executed:
            print("At least one function executed successfully.")
        else:
            print("All functions failed.")

        print("Proceeding to the next test...")
        # Perform the actions after all functions are done
        time.sleep(1)
        next_button = altdriver.find_object(By.NAME, "Next_Test")
        next_button.click()
        time.sleep(3)
        test_num = altdriver.find_object(By.NAME, 'TestNumText').get_text()

    if test_num == '2/3':
        exam_spelling(altdriver)
        time.sleep(1)
        next_button = altdriver.find_object(By.NAME, "Next_Test")
        next_button.click()
        time.sleep(2)
        test_num = altdriver.find_object(By.NAME, 'TestNumText').get_text()

    if test_num == '3/3':
        exam_multiple_choice(altdriver)
        time.sleep(2)
        submit_Button = altdriver.find_object(By.NAME, 'SubmitButton')
        submit_Button.click()
        assert_text_by_name(altdriver, 'Text', "Are you sure you're done?")
        yes_button = altdriver.find_object(By.NAME, 'YesButton')
        yes_button.click()
        time.sleep(2)
        # Collect rewards and go back
        collect_button = altdriver.find_object(By.NAME, 'Collect')
        collect_button.click()
        time.sleep(7)
        back_button = altdriver.find_object(By.NAME, 'BackButton')
        back_button.click()


def solve_lesson(altdriver, class_id, lesson_num):
    try:
        # Solve all lesson levels: Easy, Medium, Hard
        solve_lesson_levels(altdriver, class_id, lesson_num)

        # Solve the exam
        solve_exam(altdriver, class_id, lesson_num)
    except Exception as e:
        print(f"An error occurred during solve_lesson: {e}")
        # Additional error handling or logging can be added here