
from Utilities.utils import *

@pytest.mark.sanity
def test_01_san_nav_tasks(altdriver):
    login(altdriver, "vt01274560001", "7819")
    time.sleep(7)


    tasks_button = altdriver.wait_for_object(By.NAME, "TaskManagerButton")
    assert tasks_button is not None
    tasks_button.click()
    time.sleep(2)

    # Validate that the tasks scene opened
    expected_scene = "TaskManager"
    actual_scene = altdriver.get_current_scene()
    assert expected_scene == actual_scene
    expected_text_on_the_scene = 'There are no tasks available at the moment.'
    actual_text_on_the_scene = altdriver.find_object(By.NAME, "Text - RTLTMP").get_text()
    assert expected_text_on_the_scene == actual_text_on_the_scene, "Text doesn't match, scene not opened"
    time.sleep(1)

    # Click on the "x" on the no tasks available pop-up
    x_button = altdriver.find_object(By.NAME, "Button")
    x_button.click()
    time.sleep(0.5)

    # Click on the back button
    back_button = altdriver.find_object(By.NAME, "prev")
    back_button.click()
    time.sleep(1)

    # Validate that after clicking the back button the start scene appears
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f

@pytest.mark.sanity
def test_02_san_nav_competitions(altdriver):
    competition_button = altdriver.wait_for_object(By.NAME, "TournamentsButton")
    assert competition_button is not None
    competition_button.click()
    time.sleep(2)

    # Verify that the scene loaded (by verifying the scene, and taking and text from the scene)
    expected_scene = 'TournamentSelectionScene'
    actual_scene = altdriver.get_current_scene()
    assert expected_scene == actual_scene
    expected_text_on_the_scene = 'Yearly Competition'
    actual_text_on_the_scene = altdriver.find_object(By.NAME, "Text").get_text()
    assert expected_text_on_the_scene == actual_text_on_the_scene, "Text doesn't match, scene not opened"
    time.sleep(1)

    # Navigate through the scene
    scenes = ["BigRace", "HardWorker", "Tournaments"]
    for scene in scenes:
        scene_button = altdriver.find_object(By.NAME, scene)
        scene_button.click()
        time.sleep(2)

    back_button = altdriver.find_object(By.NAME, "BackButton")
    back_button.click()
    time.sleep(1)

    # Validate that after clicking the back button the start scene appears
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f

@pytest.mark.skip
def test_03_san_nav_wordlist(altdriver):
    word_list_button = altdriver.wait_for_object(By.PATH, "/StartSceneController/ButtonsPanel/CenterButtons/WordListButton", enabled=False)
    assert word_list_button is not None
    word_list_button.click()
    time.sleep(2)
    # Validate that the scene opened
    expected_scene = 'WordListScene'
    actual_scene = altdriver.get_current_scene()
    assert expected_scene == actual_scene ,'WordListScene'
    time.sleep(1)

    drop_down_title = altdriver.find_object(By.NAME, "Label")
    actual_drop_down_title_text = drop_down_title.get_component_property("RTLTMPro.RTLTextMeshPro", "m_text", "RTLTMPro")
    expected_drop_down_title_text = "Review 1"
    assert actual_drop_down_title_text == expected_drop_down_title_text

    user_state = get_user_state(user_id=39829, avatar_version=1, awards_version=1, lessons_version=12, add_is_complete=False)
    lesson_titles = extract_lesson_titles(user_state)

    lesson_title = altdriver.wait_for_object(By.NAME, "DropDown", enabled=False)
    lesson_title.click()
    time.sleep(2)

    lessons = altdriver.find_objects(By.NAME, "Item Label")
    lessons_list = [lesson.get_text() for lesson in lessons]

    print(f"Extracted lessons: {lessons_list}")

    # Verify that the lessons from the response and the app are the same
    assert lessons_list == lesson_titles, f"Lessons list mismatch: {lessons_list} != {lesson_titles}"

    exit_button = altdriver.wait_for_object(By.NAME, "nextButton")
    exit_button.click()
    time.sleep(1)
    #validate that the start scene opened :
    actual_final_scene = altdriver.get_current_scene()
    expected_final_scene= "StartScene"
    assert actual_final_scene == expected_final_scene,"in startscene"

@pytest.mark.sanity
def test_04_san_nav_settings(altdriver):
    # Click on settings button
    settings_button = altdriver.wait_for_object(By.NAME, "SettingsButton")
    settings_button.click()
    time.sleep(2)

    # Verify that the scene opened (by taking the text of US)
    languages_texts = altdriver.find_objects(By.NAME, "Text - RTLTMP")
    actual_text_on_the_settings_scene = languages_texts[1].get_text()
    expected_text_on_the_settings_scene = "US"
    assert expected_text_on_the_settings_scene == actual_text_on_the_settings_scene

    # Click on the x button on the settings pop up
    x_button = altdriver.wait_for_object(By.NAME, "exit")
    x_button.click()
    time.sleep(2)
    # Validate that after clicking the back button the start scene appears
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f

@pytest.mark.sanity
def test_05_san_nav_exit(altdriver):
    # Verify that the exit pop-up appears when clicked
    exit_button = altdriver.wait_for_object(By.NAME, "ExitButton_1")
    exit_button.click()
    time.sleep(2)

    title_on_exit_popup = altdriver.find_object(By.NAME, "Title")
    actual_title_exit_text_on_pop_up = title_on_exit_popup.get_text()
    expected_title_exit_text_on_pop_up = 'Exit'
    assert actual_title_exit_text_on_pop_up == expected_title_exit_text_on_pop_up, "The text doesn't match on the exit button pop-up"

    #validate "are you sure?" text
    text_on_exit_pop_up = altdriver.find_object(By.NAME, "Message")
    actual_text_on_pop_up = text_on_exit_pop_up.get_text()  # 'Are you sure?' text
    expected_text_on_pop_up = 'Are you sure?'
    assert actual_text_on_pop_up == expected_text_on_pop_up

    time.sleep(1)
    exit_button_on_popup = altdriver.wait_for_object(By.NAME, "Exit")
    exit_button_on_popup.click()
    time.sleep(2)

    # Validate that after clicking the back button the start scene appears
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f


@pytest.mark.skip
def test_san_nav_en_instructions(altdriver):
    # Click on settings button
    settings_button = altdriver.wait_for_object(By.NAME, "SettingsButton")
    settings_button.click()
    time.sleep(2)

    # Select US as instructions language
    eng_language = altdriver.find_object(By.PATH, "/Settings(Clone)/Panel/Positioner/Fitter/LanguageToggleGroup/en")
    eng_language.click()
    time.sleep(0.5)

    # Click on the x button on the settings pop-up and return to the start scene
    x_button = altdriver.wait_for_object(By.NAME, "exit")
    x_button.click()
    time.sleep(2)

    # Verify that all buttons text appears in English
    texts_on_exit_popup = altdriver.find_objects(By.NAME, "Text - RTLTMP")
    expected_texts = ['Competition', 'Login', 'Lessons', 'Settings']
    for i, expected_text in enumerate(expected_texts, start=2):
        actual_text = texts_on_exit_popup[i].get_text()
        assert actual_text == expected_text, f"Expected '{expected_text}', but got '{actual_text}'"

    # Click on the parrot and verify the instruction
    parrot_button = altdriver.wait_for_object(By.NAME, "HelpButton")
    parrot_button.click()
    time.sleep(5)

    expected_eng_instructions_text = 'Hi, my name is Voca, and this is my app Voca'
    actual_eng_instructions_text = altdriver.find_object(By.PATH, "/StandaloneHelpCenter/ParrotController/RightComicBubble/Text").get_text()
    assert expected_eng_instructions_text == actual_eng_instructions_text

@pytest.mark.skip
def test_san_nav_ar_instructions(altdriver):
    # Click on settings button
    settings_button = altdriver.wait_for_object(By.NAME, "SettingsButton")
    settings_button.click()
    time.sleep(2)

    # Select Arabic as instructions language
    ar_language = altdriver.find_object(By.PATH, "/Settings(Clone)/Panel/Positioner/Fitter/LanguageToggleGroup/ar")
    ar_language.click()
    time.sleep(0.5)

    # Click on the x button on the settings pop-up and return to the start scene
    x_button = altdriver.wait_for_object(By.NAME, "exit")
    x_button.click()
    time.sleep(2)

    # Get all objects with the name "Text - RTLTMP"
    text_objects = altdriver.find_objects(By.NAME, "Text - RTLTMP")

    # Loop over each object and get the text
    actual_ar_buttons_list = []
    for text_object in text_objects:
        arabic_text = text_object.get_component_property("RTLTMPro.RTLTextMeshPro", "originalText", "RTLTMPro")
        actual_ar_buttons_list.append(arabic_text)

    # Expected Arabic buttons list
    expected_ar_buttons_list = ['????', '??????', '?????????', '????? ??????', '??????', '?????????', '??????']

    # Print the actual list to verify
    for text in actual_ar_buttons_list:
        print(text)

@pytest.mark.skip
def test_06_san_nav_ui(altdriver):
    # Verify that all buttons text appears
    texts_on_exit_popup = altdriver.find_objects(By.NAME, "Text - RTLTMP")
    expected_texts = ['Exit','Tasks','Competition','Logout', 'Lessons','Settings','Daily Games']
    for i in texts_on_exit_popup:
        actual_text = texts_on_exit_popup[i].get_text()
        print(actual_text)
        assert actual_text == expected_text, f"Expected '{expected_text}', but got '{actual_text}'"
    time.sleep(4)
    altdriver.get_current_scene()

@pytest.mark.sanity
def test_07_san_nav_dailygames(altdriver):
    #validate button apperance
    daily_games_button = altdriver.find_object(By.NAME,"DailyGamesButton")

    assert daily_games_button is not None

    #validate button text
    daily_games_button_text = altdriver.find_object(By.PATH,"/StartSceneController/ButtonsPanel/CenterButtons/DailyGamesButton/Text")
    actual_daily_games_button_text = daily_games_button_text.get_text()
    expected_daily_games_button_text = "Daily Games"
    assert actual_daily_games_button_text == expected_daily_games_button_text

    #validate daily games scene (by taking the scene and taking an text from the scene)
    daily_games_button.click()
    time.sleep(3)
    actual_daily_games_scene = altdriver.get_current_scene()
    expected_daily_games_scene = "DailyGamesSelection"
    assert actual_daily_games_scene == expected_daily_games_scene
    daily_games_title = altdriver.find_object(By.PATH,"/VTDailyActivitiesCanvas/SelectionPanel/Border/Fitter/Title/Text - RTLTMP")
    actual_daily_games_title = daily_games_title.get_text()
    expected_daily_games_title = "Daily Games"
    assert actual_daily_games_title == expected_daily_games_title
    # Validate that after clicking the back button the start scene appears
    back_button = altdriver.find_object(By.NAME, "prev")
    back_button.click()
    time.sleep(2)
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f
@pytest.mark.skip
def test_san_08_nav_dialouge(altdriver):
    #validate dialouge button apperance
    dialouge_button = altdriver.find_object(By.NAME,"DialogueButton")
    assert dialouge_button is not None

    #validate dialouge button text
    dialouge_button_text = altdriver.find_object(By.PATH,"/StartSceneController/ButtonsPanel/CenterButtons/DialogueButton/Text - RTLTMP")
    actual_dialouge_button_text = dialouge_button_text.get_text()
    expected_dialouge_button_text = "Dialogue"
    assert actual_dialouge_button_text == expected_dialouge_button_text

    #validate dialouge scene (by taking the scene and taking an text from the scene)
    dialouge_button.click()
    time.sleep(3)
    actual_dialouge_scene = altdriver.get_current_scene()
    expected_dialouge_scene = "DialogueSelectionScene"
    assert actual_dialouge_scene == expected_dialouge_scene
    dialouge_title = altdriver.find_object(By.PATH,"/Canvas/Horizontal Scroll Snap/Content/DialogueSelectionPage(Clone)/DialogueSelectionButton(Clone)/Title")
    actual_dialouge_title = dialouge_title.get_text()
    expected_dialouge_title = "At the Airport II"
    assert actual_dialouge_title == expected_dialouge_title
    # Validate that after clicking the back button the start scene appears
    back_button = altdriver.find_object(By.NAME, "BackButton")
    back_button.click()
    time.sleep(2)
    expected_scene_f = 'StartScene'
    actual_scene_f = altdriver.get_current_scene()
    assert actual_scene_f == expected_scene_f


