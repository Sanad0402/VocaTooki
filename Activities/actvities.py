import alttester
import inflect
from alttester import By

from Utilities.utils import *
import time


def search(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfWords = int(progressArr[1])

    for _ in range(numberOfWords):
        # Clear the 'a' list at the beginning of each iteration
        a = []
        time.sleep(2)

        full_text_obj = altdriver.find_object(By.NAME, "WordPanel")
        fullText = full_text_obj.get_component_property("WordPanel", "Word.ToLower", "Assembly-CSharp")
        current_text_obj= altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        currentText = current_text_obj.get_component_property("TMProWordPanel", "Text", "Assembly-CSharp")

        # Find the differences
        differences = [char2 for char1, char2 in zip(currentText, fullText) if char1 == "_" and char2 != "_"]

        # Find objects and their letters
        objects_letters = altdriver.find_objects(By.NAME, "SearchObj(Clone)")
        objects = altdriver.find_objects(By.NAME, "CoverObj")

        # Create a list of (letter, object) pairs
        for obj, obj_letter in zip(objects, objects_letters):
            letter = obj_letter.get_component_property("com.kideo.learn.english.SearchObj", "letter", "Assembly-CSharp")
            a.append((letter, obj))

        # Click objects based on differences
        for letter in differences:
            for idx, (a_letter, a_obj) in enumerate(a):
                if a_letter == letter:
                    print(f"Clicking and holding on object with letter: {letter}")
                    time.sleep(0.5)  # Ensure the object is ready
                    a_obj.tap(count=1, interval=1.5, wait=True)
                    a.pop(idx)  # Remove the clicked object
                    break

        # Clear lists for the next iteration
        a.clear()
        differences.clear()
    print('search activity done')

def find_matching_pairs(cardscont):
    matching_pairs = []
    for i in range(len(cardscont)):
        for j in range(i + 1, len(cardscont)):
            if cardscont[i] == cardscont[j]:
                matching_pairs.append((i, j))
    return matching_pairs


def memory(altdriver):
    # Pause for 15 seconds before starting the test
    time.sleep(17)

    # Find text and image cards
    textcards = altdriver.find_objects(By.NAME, "ImageCardPrefab(Clone)")
    imagecards = altdriver.find_objects(By.NAME, "TextCardPrefab(Clone)")
    cards = imagecards + textcards

    # Extract card contents
    cardscont = [
        card.get_component_property("CardHandler1", "word.word", "Assembly-CSharp")
        for card in cards
    ]

    print(cardscont)

    # Find matching pairs
    matching_pairs = find_matching_pairs(cardscont)

    # Click on matching cards
    for pair in matching_pairs:
        card1_index, card2_index = pair
        card1 = cards[card1_index]
        card2 = cards[card2_index]

        # Click on the first card
        card1.click()
        time.sleep(0.5)
        # Add an assertion or wait for card selection to complete

        # Click on the second card
        card2.click()
        # Add an assertion or wait for card selection to complete
    print('memory activity done')


def bubbels(altdriver):
    try:
        # Check if alttester is properly imported
        assert 'alttester' in globals(), "alttester module is not imported."

        # Get progress text and parse it
        progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
        progressArr = progresstext.split('/')
        numberOfwords = int(progressArr[1])

        for i in range(numberOfwords):
            time.sleep(4.5)
            full_word_object = altdriver.find_object(By.NAME, "BubblesGameManager")
            missing_word_object = altdriver.find_object(By.NAME, "text")
            full_word_text = full_word_object.get_component_property("com.kideo.learn.english.BubblesGameManager",
                                                                     "newWord", "Assembly-CSharp")
            missing_word_text = missing_word_object.get_text()

            # Get current background
            bubbles_activity_obj = altdriver.find_object(By.NAME, "bubbles_activity")
            current_bubbles_background = bubbles_activity_obj.get_component_property(
                "com.kideo.learn.english.BubblesActivityManagerScript",
                "currentBackground_.name",
                "Assembly-CSharp"
            )

            # Determine paths based on the current background
            if current_bubbles_background == 'FairyTales(Clone)':
                letter_text_path = "Text_1"
                bubble_path = "Bubble_FairyTales(Clone)"
            elif current_bubbles_background == 'Moon(Clone)':
                letter_text_path = "Text_1"
                bubble_path = "Bubble_Moon(Clone)"
            elif current_bubbles_background == 'Candy(Clone)':
                letter_text_path = "Text_1"
                bubble_path = "Bubble_Candy(Clone)"
            else:
                letter_text_path = "Text_1"
                bubble_path = "Bubble(Clone)"

            # Find the differences between the words
            differences = [char2 for char1, char2 in zip(missing_word_text, full_word_text) if
                           char1 == "_" and char2 != "_"]

            # Loop through the differences and click on corresponding objects
            while differences:
                try:
                    # Refresh objects after each click
                    letters_text_objects = altdriver.find_objects(By.NAME, letter_text_path)
                    letters_objects = altdriver.find_objects(By.NAME, bubble_path)

                    # Map letters to objects
                    letter_object_map = {letter_text.get_text(): obj for letter_text, obj in
                                         zip(letters_text_objects, letters_objects)}

                    for letter in differences:
                        if letter in letter_object_map:
                            letter_object_map[letter].click()  # Click the bubble corresponding to the letter
                            print(f"Clicked on letter: {letter}")
                            differences.remove(letter)  # Remove the clicked letter from the list
                            break  # Break to refresh objects after the click
                        else:
                            print(f"Letter '{letter}' not found in the current bubbles.")
                            time.sleep(0.1)  # Wait briefly before retrying

                except alttester.exceptions.NotFoundException as e:
                    print(f"Error: {e}. Retrying object lookup.")
                    time.sleep(0.5)  # Wait a moment before retrying

                # Add a small delay before the next iteration
                time.sleep(0.5)

            # After completing this word's actions, proceed to the next iteration
            print(f"Iteration {i + 1} completed.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print('bubbels activity done')


def fillIn(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(1.6)

        correct_word_object = altdriver.find_object(By.NAME, "Canvas")
        correct_word_index = correct_word_object.get_component_property("SentenceCompletionQuiz", "answerIndex",
                                                                        "Assembly-CSharp")
        answers = altdriver.find_objects(By.NAME, "Button")
        for answer in answers:
            a = answer.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if a == correct_word_index:
                answer.click()

    print('FillIN activity done')

def spiders(altdriver):
    time.sleep(2)
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(1.6)

        correct_context_object = altdriver.find_object(By.NAME, "Canvas")
        answer_Index = correct_context_object.get_component_property("SentenceTranslationQuiz", "answerIndex",
                                                                     "Assembly-CSharp")
        answers = []
        answers = altdriver.find_objects(By.NAME, "Button")
        for answer in answers:
            a = answer.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if a == answer_Index:
                answer.click()

    print('spiders activity done')


def megaphone(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    # Determine iterations based on numberOfwords
    if numberOfwords == 4:
        iterations = 4  # Easy
    elif 5 <= numberOfwords <= 6:
        iterations = 2  # Medium
    elif numberOfwords > 6:
        iterations = 3  # Hard

    for i in range(iterations):
        time.sleep(4)

        # Get current megaphone background
        megaphone_activity_obj = altdriver.find_object(By.NAME, "ListenFind_activity")
        current_megaphone_background = megaphone_activity_obj.get_component_property(
            "com.kideo.learn.english.ListenFindActivityManagement",
            "sessionData_.CurrentGeographyName",
            "Assembly-CSharp")

        # Determine paths for paper and leaf objects based on the current background
        if current_megaphone_background == 'Sea':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Sea(Clone)")
        elif current_megaphone_background == 'FairyTales':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Farm(Clone)")
        elif current_megaphone_background == 'Dinosaurs':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Dinosaurs(Clone)")
        elif current_megaphone_background == 'Space':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Moon(Clone)")
        elif current_megaphone_background == 'Candy':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Candy(Clone)")
        elif current_megaphone_background == 'Farm':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Farm(Clone)")
        elif current_megaphone_background == 'Desert':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Desert(Clone)")
        elif current_megaphone_background == 'Pole':
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref_Pole(Clone)")
        else:
            # Default behavior - original code
            words_with_paper_objects = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
            words_with_leaf_objects = altdriver.find_objects(By.NAME, "LeafPref(Clone)")

        # Combine the paper and leaf objects into one list
        combined_objects = words_with_paper_objects + words_with_leaf_objects

        # Initialize an empty list to store word and object pairs
        words_with_objects = []

        # Iterate through the combined list and retrieve word text
        for word_obj in combined_objects:
            word_text = word_obj.get_component_property("com.kideo.learn.english.ListenFindObject", "word.word",
                                                        "Assembly-CSharp")
            words_with_objects.append((word_text, word_obj))

        # Initialize a set to keep track of clicked words
        clicked_words = set()

        # Assuming Words_in_sequence_objects is already defined and usedWords are fetched
        Words_in_sequence_objects = altdriver.find_object(By.NAME, "ListenFindGameManager")
        words_in_sequence_list = Words_in_sequence_objects.get_component_property(
            "com.kideo.learn.english.ListenFindGameManager", "usedWords", "Assembly-CSharp")

        # Iterate through the words_in_sequence_list in the specified order
        for target_word in words_in_sequence_list:
            for word_text, word_obj in words_with_objects:
                # Check if the current word matches the target word in the sequence and has not been clicked before
                if word_text == target_word and word_text not in clicked_words:
                    # Click the word object
                    word_obj.click()  # Assuming tap() is the method to click the object
                    time.sleep(1)
                    # Add the word to the set of clicked words
                    clicked_words.add(word_text)
                    break  # Break the inner loop and move to the next target word

    print('megaphone activity done')

def exams_word_to_meaning(altdriver):
    # Find word objects

    time.sleep(1)
    words_to_drag = altdriver.find_objects(By.NAME, 'WordMeaningObject(Clone)')
    if len(words_to_drag)==0:
        raise Exception("This is not word to meaning exam")

    # Initialize another list for words
    a_list = []  # ['word(text), word(object), word(position)]
    for word in words_to_drag:
        a_list.append((word.get_text(), word, word.get_screen_position()))

    # Initialize another list for shapes
    b_list = []  # ['shape(text), shape(object), shape(position)]
    shapes = altdriver.find_objects(By.NAME, 'WordMeaningShape(Clone)')
    for shape in shapes:
        shape_text = shape.get_component_property('com.kideo.learn.english.WordMeaningShape', 'word', 'Assembly-CSharp')
        position = shape.get_screen_position()
        adjusted_position = (position[0], position[1] - 100)  # Adjust position
        b_list.append((shape_text, shape, adjusted_position))

    # Match words and shapes by their text and perform the swipe and click
    for word_text, word, word_pos in a_list:
        for shape_text, shape, shape_pos in b_list:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word.click()
                break

    print('exams_word_to_meaning  done')


def exams_word_to_image(altdriver):
    # Find word objects
    time.sleep(1)
    words_to_drag = altdriver.find_objects(By.NAME, 'MatchWordText(Clone)')

    if len(words_to_drag)==0:
        raise Exception("This is not word to image exam")
    # Initialize another list for worsd
    a_list = []  # ['word(text), word(object), word(position)]
    for word in words_to_drag:
        a_list.append((word.get_text(), word, word.get_screen_position()))

    # Initialize another list for shapes
    b_list = []  # ['shape(text), shape(object), shape(position)]
    shapes = altdriver.find_objects(By.NAME, 'MatchShapeImage(Clone)')
    for shape in shapes:
        word = shape.get_component_property('com.kideo.learn.english.MatchTestShape', 'word', 'Assembly-CSharp')
        position = shape.get_screen_position()
        adjusted_position = (position[0], position[1] - 100)  # Adjust position
        b_list.append((word, shape, adjusted_position))

    # Match words and shapes by their text and perform the swipe and cick
    for word_text, word, word_pos in a_list:
        for shape_text, shape, shape_pos in b_list:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word.click()
                break

    print('exams_word_to_image done')


def exams_word_to_image_3rd(altdriver):
    # Find word objects
    time.sleep(1)
    words_to_drag = altdriver.find_objects(By.NAME, 'LetterWordText Variant(Clone)')

    if len(words_to_drag) == 0:
        raise Exception("This is not a word-to-image exam")

    # Initialize a list for words
    a_list = []  # ['word(text), word(object), word(position)]
    for word in words_to_drag:
        word_text = word.get_component_property('com.kideo.learn.english.MatchTestWord', 'word',
                                                'Assembly-CSharp').lower()
        a_list.append((word_text, word, word.get_screen_position()))

    # Initialize a list for shapes
    b_list = []  # ['shape(text), shape(object), shape(positions)]
    shapes = altdriver.find_objects(By.NAME, 'LetterShapeImage Variant(Clone)')

    shape_positions = {}  # Dictionary to track shape positions
    for shape in shapes:
        shape_text = shape.get_component_property('com.kideo.learn.english.MatchTestShape', 'word',
                                                  'Assembly-CSharp').lower()
        position = shape.get_screen_position()

        # Store available positions for each shape
        if shape_text not in shape_positions:
            shape_positions[shape_text] = []

        shape_positions[shape_text].append(position)  # Add new position for this shape

    filled_positions = []  # Track used placeholders

    # Match words and shapes by text (exact match or "starts with")
    for word_text, word, word_pos in a_list:
        for shape_text, positions in shape_positions.items():
            if word_text == shape_text or word_text.startswith(shape_text):  # Match condition

                for shape_pos in positions:  # Try each available position
                    if shape_pos not in filled_positions:  # Check if already used
                        altdriver.swipe(word_pos, shape_pos, 2.3)  # Move word
                        filled_positions.append(shape_pos)  # Mark placeholder as used
                        word.click()  # Click to confirm placement
                        break  # Stop searching for positions once placed

                break  # Stop searching for shapes once matched

def exams_letter_matrix_3rd(altdriver):
    time.sleep(1)
    letter_ques_obj = altdriver.find_objects(By.NAME, 'Text')
    letter_ques =letter_ques_obj[0].get_text().lower()
    letter_selection_objs = altdriver.find_objects(By.NAME, 'LetterGridSelectionObject(Clone)')
    for letter in letter_selection_objs:
         a= letter.get_component_property('com.kideo.learn.english.LetterGridSelectionEntry','word','Assembly-CSharp')
         if a == letter_ques :
            letter.click()


def exams_audio_to_meaning(altdriver):
    time.sleep(1)
    #Click on the microphone
    megaphone_objs = altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')
    if len(megaphone_objs)==0:
        raise Exception("This is not audio to meaning exam")
    for megaphone_obj in megaphone_objs:
        megaphone_obj.click()
        time.sleep(1)

    # Find word objects
    words_to_drag = altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
    # Initialize another list for worsd
    a_list = []  # ['word(text), word(object), word(position)]
    for word in words_to_drag:
        a_list.append((word.get_text(), word, word.get_screen_position()))

    # Initialize another list for shapes
    b_list = []  # ['shape(text), shape(object), shape(position)']
    shapes = altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')

    for shape in shapes:
        word = shape.get_component_property('com.kideo.learn.english.WordAudioShape', 'word', 'Assembly-CSharp')
        position = shape.get_screen_position()
        adjusted_position = (position[0], position[1] - 100)  # Adjust position
        b_list.append((word, shape, adjusted_position))

    # Match words and shapes by their text and perform the swipe and cick
    for word_text, word, word_pos in a_list:
        for shape_text, shape, shape_pos in b_list:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word.click()
                break

    print('exams_audio_to_meaning done')

def exam_spelling(altdriver):
    # Retrieve all "FillWord(Clone)" objects, which contain the words with missing letters.
    missing_word_objects = altdriver.find_objects(By.NAME, "FillWord(Clone)")

    # Extract the missing letters from each "FillWord(Clone)" object, ensuring all letters are lowercase.
    missing_letters_list = []
    for word_obj in missing_word_objects:
        # Get the property and parse it if needed
        raw_missing_letters = word_obj.get_component_property(
            'com.kideo.learn.english.FillMissingWord',
            'missingLetters',
            'Assembly-CSharp'
        )
        if isinstance(raw_missing_letters, str):
            # If it is a string representation of a list, convert it to a list.
            try:
                missing_letters = eval(raw_missing_letters)
                if isinstance(missing_letters, list):
                    missing_letters_list.append([letter.lower() for letter in missing_letters])
                else:
                    raise ValueError("Unexpected format for missing letters")
            except (SyntaxError, ValueError):
                raise ValueError(f"Failed to parse missingLetters: {raw_missing_letters}")
        elif isinstance(raw_missing_letters, list):
            # Already a list
            missing_letters_list.append([letter.lower() for letter in raw_missing_letters])
        else:
            raise ValueError(f"Unsupported format for missingLetters: {raw_missing_letters}")

    # Retrieve all the fill word toggle buttons.
    fill_word_toggles = altdriver.find_objects(By.NAME, "FillWordToggle")

    # Retrieve all the letter objects that can be clicked to fill in the missing letters.
    letters_to_click = altdriver.find_objects(By.NAME, 'FillLetter')
    letters_map = {
        letter_obj.get_component_property(
            'TMPro.TextMeshProUGUI',
            'm_text',
            'Unity.TextMeshPro'
        ).lower(): letter_obj
        for letter_obj in letters_to_click
    }

    # Iterate over each set of missing letters.
    for i, missing_letters in enumerate(missing_letters_list):
        # Ensure the toggle button exists for the current word.
        if i < len(fill_word_toggles):
            # Click the toggle button to activate the current word.
            fill_word_toggles[i].click()

            # Click each missing letter in the current set.
            for letter in missing_letters:
                # Find and click the letter object corresponding to the missing letter.
                if letter in letters_map:
                    letters_map[letter].click()
                    time.sleep(0.2)

    print('exam_spelling done')

def exam_swap_letters(altdriver):
    # Retrieve all swap word objects
    swap_words_obj = altdriver.find_objects(By.NAME, 'SwapWord(Clone)')
    words = []
    for swap_word_obj in swap_words_obj:
        raw_correct_words = swap_word_obj.get_component_property(
            'com.kideo.learn.english.SwapTestWord',
            'word',
            'Assembly-CSharp'
        )
        words.append(raw_correct_words)

    # Retrieve all swap letter objects
    letters_obj = altdriver.find_objects(By.NAME, 'SwapLetterText(Clone)')
    letters = []
    positions = []
    for letter_obj in letters_obj:
        raw_current_letters = letter_obj.get_component_property(
            'com.kideo.learn.english.SwapTestLetter',
            'letter',
            'Assembly-CSharp'
        )
        current_position = letter_obj.get_screen_position()  # Get the screen position of the letter
        letters.append(raw_current_letters)
        positions.append(current_position)

    # Split letters into chunks based on word lengths
    letter_chunks = []
    position_chunks = []
    start = 0
    for word in words:
        end = start + len(word)
        letter_chunks.append(letters[start:end])
        position_chunks.append(positions[start:end])
        start = end

    # Process each word row by row
    for word, current_letters, current_positions in zip(words, letter_chunks, position_chunks):
        print(f"Processing word: {word}")
        print(f"Current letters: {current_letters}, Target: {list(word)}")

        # Swap letters to match the target word
        for i in range(len(word)):
            if current_letters[i] != word[i]:
                # Find the index of the correct letter
                target_index = current_letters.index(word[i])

                # Get the positions for swipe
                start_position = current_positions[i]
                end_position = current_positions[target_index]

                # Perform swipe in the UI
                print(f"Swiping from {start_position} to {end_position} to place {word[i]} correctly.")
                altdriver.swipe(start_position, end_position, duration=0.5)

                # Update the current letters to reflect the swap
                current_letters[i], current_letters[target_index] = (
                    current_letters[target_index],
                    current_letters[i],
                )
                current_positions[i], current_positions[target_index] = (
                    current_positions[target_index],
                    current_positions[i],
                )

        print(f"Completed word: {current_letters}")


def exam_multiple_choice(altdriver):
    import inflect
    p = inflect.engine()
    words_to_click = []
    words = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')

    # Retrieve words and append to the list
    for word in words:
        word_text = word.get_component_property('ContextWithMissingWordQuestion', 'word', 'Assembly-CSharp')
        words_to_click.append(word_text.lower())  # Convert to lowercase immediately

    # Initialize a new list to store the processed results
    processed_words = []

    # Process each item in words_to_click
    for item in words_to_click:
        # If the item contains a space, split it into its components
        if ' ' in item:
            parts = item.split(' ')
            processed_words.extend([part.lower() for part in parts])  # Lowercase the split parts
        processed_words.append(item.lower())  # Add the lowercase original item

    # Generate plural and capitalized variations (all in lowercase)
    plural_words = [p.plural(word) for word in processed_words]  # Pluralize and keep lowercase
    labels = altdriver.find_objects(By.NAME, 'Label')

    for label in labels:
        label_text = label.get_text().lower()  # Compare labels in lowercase
        if label_text in processed_words or label_text in plural_words:
            label.get_parent().click()
            time.sleep(0.2)

    print('exam_multiple_choice')

def Ispy(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(5)

        objs_with_text = altdriver.find_objects(By.NAME, 'GridElementWithText(Clone)')
        objs_with_image = altdriver.find_objects(By.NAME, 'GridElementWithImage(Clone)')
        answers = objs_with_text + objs_with_image
        flag = False
        for answer in answers:
            if flag:
                continue
            is_correct_answer = answer.get_component_property('ClickHandeler', 'onClick.Method.Name', 'Assembly-CSharp')
            time.sleep(0.1)
            if is_correct_answer == 'OnCorrectClick':
                answer.click()
                flag = True
                time.sleep(2)

    print('iSPY activity done')

def HangWords(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    for i in range(numberOfwords):
        while True:
            time.sleep(5)
            # מציאת כל האובייקטים שהם חלק מהרשימה
            clothes = [obj for obj in altdriver.get_all_elements() if
                       obj.name.startswith("c") and "(Clone)" in obj.name]

            # רשימת האובייקטים עם is_right_answer == True
            correct_clothes = [cloth for cloth in clothes if
                               cloth.get_component_property('ClothesData', 'isCorrect', 'Assembly-CSharp') == True]

            # אם יש אובייקטים נכונים, נלחץ עליהם
            if correct_clothes:
                for cloth in correct_clothes:
                    cloth.click()
                    time.sleep(2)  # מחכים קצת בין קליקים

            # אם לא נשארו אובייקטים נכונים, אפשר לצאת מהלולאה ולהמשיך למילה הבאה
            if not correct_clothes:
                break

    print('HangWords activity done')

def Moving(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):

        answer = altdriver.find_object(By.NAME, 'Canvas')
        answer_index = answer.get_component_property('WordsMatchingQuiz', 'answerIndex', 'Assembly-CSharp')
        options = altdriver.find_objects(By.NAME, 'Button')
        flag = False
        for option in options:
            if flag:
                continue
            index = option.get_component_property('ChoiceClick', 'index', 'Assembly-CSharp')
            if index == answer_index:
                option.click()
                flag = True
                time.sleep(2)

    print('Moving activity done')

def Radar(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(7)
        # Fetch all radar objects and the target word
        radar_objects = altdriver.find_objects(By.NAME, 'radarObj')
        answer_obj = altdriver.find_object(By.NAME, 'Radar_activity')
        target_word = answer_obj.get_component_property('com.kideo.learn.english.RadarActivityManagement',
                                                        'radarGameManager.targetWord', 'Assembly-CSharp')

        # List to hold the radar text values
        radar_objects_texts = []
        for radar_object in radar_objects:
            radar_text = radar_object.get_component_property('com.kideo.learn.english.RadarObjectController', 'word',
                                                             'Assembly-CSharp')
            radar_objects_texts.append(radar_text)

        # Iterate through radar objects and click on those that match the target word
        for index, radar_text in enumerate(radar_objects_texts):
            if radar_text == target_word:
                # Perform the first click
                radar_objects[index].click()
                # Wait for a short duration before the second click
                time.sleep(0.5)  # Adjust this delay as needed (0.5 seconds here)
                # Perform the second click
                radar_objects[index].click()
                continue

    print('Radar activity done')

def Bee(altdriver):
    print('1')
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    print('2')

    for i in range(numberOfwords):
        time.sleep(3)
        # Get current background inside the loop
        bee_activity_obj = altdriver.find_object(By.NAME, "BeeCareful_activity")
        current_bee_background = bee_activity_obj.get_component_property(
            "com.kideo.learn.english.BeeCarefulActivityManagement",
            "sessionData_.CurrentGeographyName",
            "Assembly-CSharp"
        )

        # Set the object name based on the background
        if current_bee_background == "Sea":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Sea(Clone)")
        elif current_bee_background == "FairyTales":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_FairyTales(Clone)")
        elif current_bee_background == "Dinosaurs":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Farm(Clone)")
        elif current_bee_background == "Space":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Farm(Clone)")
        elif current_bee_background == "Candy":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Candy(Clone)")
        elif current_bee_background == "Farm":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Farm(Clone)")
        elif current_bee_background == "Desert":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Desert(Clone)")
        elif current_bee_background == "Pole":
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB_Farm(Clone)")
        else:
            objects = altdriver.find_objects(By.NAME, "DraggableObjectB(Clone)")

        word_to_drag = altdriver.find_object(By.NAME, 'WordPanel')
        word_to_drag_text = word_to_drag.get_component_property("WordPanel",'<wordObj_>k__BackingField.word','Assembly-CSharp')

        # Function to find the correct object based on the word
        def find_object_by_word(objects, word_to_drag_text):
            for obj in objects:
                try:
                    word = obj.get_component_property('com.kideo.learn.english.BeeCarefulObject', 'word',
                                                      'Assembly-CSharp')
                    if word == word_to_drag_text:
                        return obj  # Return the object if the word matches
                except alttester.exceptions.NotFoundException:
                    print(f"Failed to retrieve property from object: {obj}")
                    continue
            return None  # Return None if no matching object is found

        # Find the correct object
        matching_object = find_object_by_word(objects, word_to_drag_text)

        if matching_object:
            print("Found the matching object:", matching_object)

            # Get the hive object where the word needs to be dragged
            hive_object = altdriver.find_object(By.NAME, 'Vector Smart Object_3')
            start_position = matching_object.get_screen_position()  # Returns a tuple (x, y)

            # Get screen positions (now treated as tuples)
            end_position = hive_object.get_component_property("UnityEngine.Transform", "position",
                                                              "UnityEngine.CoreModule")

            # Update the position of the matching object directly
            matching_object.set_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule",
                                                   end_position)
            matching_object.click()

            # Click the draggable object at the new position
            matching_object.click()
            time.sleep(3)

            # Optionally, verify that the object reached the hive successfully
            print("Click action completed.")
        else:
            print("No matching object found.")

    print('Bee activity done')

def Frogger(altdriver):
    # Get the number of words to process
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    for i in range(numberOfwords):
        time.sleep(3)

        # Get the full sentence to complete
        full_sentence_obj = altdriver.find_object(By.NAME, 'FroggerGameManager')
        full_sentence_text = full_sentence_obj.get_component_property(
            'com.kideo.learn.english.Frogger.FroggerGameManager',
            'selectedSentence', 'Assembly-CSharp'
        )

        print(f"Full sentence to complete: {full_sentence_text}")

        # Split the sentence into words
        split_sentence = full_sentence_text.split(' ')

        # Retrieve text and parent objects
        words_to_click = [(word.get_text(), word.get_parent()) for word in altdriver.find_objects(By.NAME, "Text")]

        # Create a list to handle duplicates and ensure order
        used_indices = []

        for word in split_sentence:
            found = False
            for index, (text, parent) in enumerate(words_to_click):
                if text == word and index not in used_indices:
                    parent.click()
                    used_indices.append(index)
                    time.sleep(1)  # Wait 1 second between clicks
                    print(f"Clicked on: {word}")
                    found = True
                    break
            if not found:
                print(f"Word not found or already used: {word}")

        # Click the "Check" button to validate the sentence
        green_v = altdriver.find_object(By.NAME, "CheckSentenceButton")
        green_v.click()
        print("Validation button clicked.")
        time.sleep(2)

        # Move the Frogger element to the final line if required
        frogger = altdriver.find_object(By.NAME, "Frogger")
        final_position = altdriver.find_object(By.NAME, "FinalLine").get_component_property(
            "UnityEngine.Transform", "position", "UnityEngine.CoreModule"
        )

        # Set the position of the frogger to the final line
        frogger.set_component_property(
            "UnityEngine.Transform", "position", "UnityEngine.CoreModule", final_position
        )
        print("Frogger moved to the final line.")
        time.sleep(1)

        # Simulate additional interactions (if needed)
        up_button = altdriver.find_object(By.NAME, "UpButton")
        up_button.click()
        print("Up button clicked.")
        time.sleep(5)

    print('Frogger activity done')

def GapGuru(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    for i in range(numberOfwords):
        time.sleep(2.5)

        # Find the correct answer
        correct_answer_object = altdriver.find_object(By.NAME, "ContextGapGuruQuiz(Clone)")
        correct_answer = correct_answer_object.get_component_property(
            "com.kideo.learn.english.ContextFillMissingWordQuiz", "missingWord_", "Assembly-CSharp"
        )

        # Find all answer options
        answers = altdriver.find_objects(By.NAME, "QuizWordToggle(Clone)")
        for answer in answers:
            a = answer.get_component_property("com.kideo.learn.english.QuizWordToggle", "text.text", "Assembly-CSharp")

            # Click the correct answer
            if a == correct_answer:
                answer.click()
                time.sleep(1)

                # Click the check button
                check_button = altdriver.find_object(By.NAME, "QuizCheckButton")
                check_button.click()
                time.sleep(1)

                # Click the next button if it's not the last iteration
                if i != numberOfwords - 1:
                    next_button = altdriver.find_object(By.NAME, 'QuizNextButton')
                    next_button.click()

                # Continue to the next iteration after processing the current word
                break  # Exit the inner loop since the correct answer is found

        # Continue to the next word in the sentence
        continue

    print('gapguru activity done')

def TypeItRight(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    for i in range(numberOfwords):
        time.sleep(2.5)

        # Find the correct answer
        correct_answer_object = altdriver.find_object(By.NAME, "ContextTypingItQuiz(Clone)")
        correct_answer = correct_answer_object.get_component_property(
            "com.kideo.learn.english.ContextAudioTypingQuiz", "currentWord_.word", "Assembly-CSharp"
        )

        # Type the correct answer in the text area
        text_area = altdriver.find_object(By.NAME, "InputField")
        text_area.set_text(correct_answer)

        # Click the check button
        check_button = altdriver.find_object(By.NAME, "CheckButton")
        check_button.click()
        time.sleep(1)

        # Skip clicking NextButton in the last iteration
        if i < numberOfwords - 1:
            # Click the next button if it's not the last iteration
            next_button = altdriver.find_object(By.NAME, 'NextButton')
            next_button.click()

    print('type it activity done')

def EchoOrder(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    for i in range(numberOfwords):
        time.sleep(2.5)

        # Get the full sentence from the game manager
        full_sentence_obj = altdriver.find_object(By.NAME, 'ContextEchoOrderQuiz(Clone)')
        full_sentence_text = full_sentence_obj.get_component_property(
            'com.kideo.learn.english.ContextBuilderQuiz',
            'correctAnswer_', 'Assembly-CSharp')

        # Print the full sentence to complete
        print(f"Full sentence to complete: {full_sentence_text}")

        # Split the sentence into words
        split_sentence = full_sentence_text.split(' ')
        words = altdriver.find_objects(By.NAME, "Text")

        # Retrieve text and parent objects
        words_to_click = [(word.get_text(), word.get_parent()) for word in words]

        # Create a list of word occurrences (index position based) for precise clicks
        word_to_object_map = {}
        for word, parent in words_to_click:
            if word not in word_to_object_map:
                word_to_object_map[word] = []
            word_to_object_map[word].append(parent)

        # Dictionary to keep track of how many times each word was clicked
        clicked_count = {}

        # Click words in the order of the split sentence
        for word in split_sentence:
            # Initialize clicked count if not present
            if word not in clicked_count:
                clicked_count[word] = 0

            # Click the next occurrence of the word
            if word in word_to_object_map and clicked_count[word] < len(word_to_object_map[word]):
                word_parent = word_to_object_map[word][clicked_count[word]]
                word_parent.click()  # Click on the parent of the text
                time.sleep(1)  # Wait 1 second between clicks
                print(f"Clicked on: {word}")

                # Increment the count for this word
                clicked_count[word] += 1

        # After clicking all relevant words for this question, click the CheckButton
        check_button = altdriver.find_object(By.NAME, "QuizCheckButton")
        check_button.click()
        time.sleep(1)

        # Only click the NextButton if it's not the last iteration
        if i < numberOfwords - 1:
            next_button = altdriver.find_object(By.NAME, 'QuizNextButton')
            next_button.click()
            time.sleep(1)

    print('echo order activity done')

def TranslationWiz(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    # Loop for each word, waiting for 2.5 seconds and then proceeding to check the sentence
    for i in range(numberOfwords):
        time.sleep(2.5)

        # Get the full sentence from the game manager
        full_sentence_obj = altdriver.find_object(By.NAME, 'ContextTranslationWizQuiz(Clone)')
        full_sentence_text = full_sentence_obj.get_component_property(
            'com.kideo.learn.english.ContextBuilderQuiz',
            'correctAnswer_', 'Assembly-CSharp')

        # Print the full sentence to complete
        print(f"Full sentence to complete: {full_sentence_text}")

        # Split the sentence into words
        split_sentence = full_sentence_text.split(' ')
        words = altdriver.find_objects(By.NAME, "Text")

        # Retrieve text and parent objects
        words_to_click = [(word.get_text(), word.get_parent()) for word in words]

        # Create a list of word occurrences (index position based) for precise clicks
        word_to_object_map = {}
        for word, parent in words_to_click:
            if word not in word_to_object_map:
                word_to_object_map[word] = []
            word_to_object_map[word].append(parent)

        # Dictionary to keep track of how many times each word was clicked
        clicked_count = {}

        # Click words in the order of the split sentence
        for word in split_sentence:
            # Initialize clicked count if not present
            if word not in clicked_count:
                clicked_count[word] = 0

            # Click the next occurrence of the word
            if word in word_to_object_map and clicked_count[word] < len(word_to_object_map[word]):
                word_parent = word_to_object_map[word][clicked_count[word]]
                word_parent.click()  # Click on the parent of the text
                time.sleep(1)  # Wait 1 second between clicks
                print(f"Clicked on: {word}")

                # Increment the count for this word
                clicked_count[word] += 1

        # After clicking all relevant words for this question, click CheckButton
        check_button = altdriver.find_object(By.NAME, "QuizCheckButton")
        check_button.click()
        time.sleep(1)

        # Only click the NextButton if it's not the last iteration
        if i < numberOfwords - 1:
            next_button = altdriver.find_object(By.NAME, 'QuizNextButton')
            next_button.click()
            time.sleep(1)

    print('translation wiz activity done')

def LexiMatch(altdriver):
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])
    for i in range(numberOfwords):
        time.sleep(1.6)

        question_object = altdriver.find_object(By.NAME, "Canvas")
        correct_answer_index = question_object.get_component_property('UnscrambleQuiz', 'answerIndex',
                                                                      'Assembly-CSharp')
        answers = altdriver.find_objects(By.NAME, "Button")
        for answer in answers:
            a = answer.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if a == correct_answer_index:
                answer.click()

    print('lexi match activity done')

def Delivery_truck(altdriver):
    """
    Handles the Delivery Truck activity. Dynamically detects the box containing words
    and ensures all words are spoken one by one.

    Args:
        altdriver: The AltTester driver instance for interacting with the game.
    """
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])

    previous_word = None  # Variable to track the last spoken word

    for i in range(numberOfwords):
        retries = 0  # Retry counter for polling
        max_retries = 20  # Max retries before proceeding to the next iteration

        while True:
            try:
                time.sleep(3)
                # Dynamically locate the first 'Text - RTLTMP' object under 'Parcel(Clone)'
                box_obj = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
                box_text = box_obj.get_component_property('TMProWordPanel', 'TMPTextControl.OriginalText',
                                                          'Assembly-CSharp')

                # Ensure the text in the box has completely changed
                if box_text != previous_word:
                    print(f"New word in the box: {box_text}")

                    # Say the new word
                    try:
                        say(box_text)
                        previous_word = box_text  # Update the previous word to the full current box text
                    except Exception as e:
                        print(f"An error occurred while trying to say the word '{box_text}': {e}")

                    break  # Exit the loop and proceed to the next iteration
                else:
                    print("Waiting for the text to change...")

            except Exception as e:
                print(f"Error retrieving text: {e}")

            # Increment retry counter and wait before checking again
            retries += 1
            if retries >= max_retries:
                print("Max retries reached, proceeding to the next word...")
                break

            time.sleep(0.5)  # Wait before polling again


def Moles(altdriver):
    """
    Automates the 'Moles' activity by saying each word displayed by the mole.
    """
    # Add a delay before starting
    time.sleep(2)

    while True:
        try:
            # Wait for the mole to appear and fetch the updated text
            mole_object = altdriver.wait_for_object(By.NAME, "RTLTMPWordPanel")
            word_text = mole_object.get_component_property(
                'TMProWordPanel', 'Word.word', 'Assembly-CSharp'
            )

            if not word_text.strip():
                print("Word text is empty or invalid. Retrying...")
                continue

            # Say the word and log it
            print(f"Saying the word: {word_text}")
            say(word_text)  # Replace with your voice recognition function

        except Exception as e:
            # Handle any unexpected errors gracefully
            print(f"An error occurred: {e}")
            break

    print("Activity completed!")


def Cards(altdriver):
    while True:
        # Fetch all card word objects
        words = altdriver.find_objects(By.NAME, "RTLTMPWordPanel")

        for word in words:
            # Get the text from the word panel
            box_text = word.get_component_property('TMProWordPanel', 'Word.word', 'Assembly-CSharp')

            # Say the word
            print(f"Saying the word: {box_text}")
            say(box_text)  # Replace with your voice recognition function

            # Small delay to ensure synchronization
            time.sleep(2)

        # Check for successful final feedback
        try:
            # Replace "SuccessFeedback" with the actual name or identifier of the success feedback element
            exit_button = altdriver.find_object(By.NAME, "ExitButton")
            print("Final feedback detected. All words successfully said!")
            time.sleep(0.5)
            exit_button.click()

            break  # Exit the loop once feedback is detected
        except:
            # If no feedback yet, continue to the next iteration
            print("Waiting for final feedback...")
            time.sleep(0.5)

    print("Activity completed!")


def magic_trace(altdriver):
    # Get the progress text and extract the total number of words
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    progressArr = progresstext.split('/')
    numberOfwords = int(progressArr[1])  # Total number of words

    for word_index in range(numberOfwords):
        time.sleep(6)  # Pause before processing each word

        # Refresh the objects for the first and second numbers
        first_num_obj = altdriver.find_objects(By.NAME, "FirstNumber")
        second_num_obj = altdriver.find_objects(By.NAME, "SecondNumber")

        # Perform the swipe actions for the current word
        for i in range(len(first_num_obj)):
            altdriver.swipe(
                first_num_obj[i].get_screen_position(),
                second_num_obj[i].get_screen_position(),
                duration=0.8
            )
            time.sleep(0.5)

        # Optional: Add a log or debug message to track progress
        print(f"Completed word {word_index + 1}/{numberOfwords}")


def Signs(altdriver):
    # Create a list to store tuples of (monkey, bn_local_root)
    monkey_tuples = []

    # Find all Bn-Local_Root objects (returns a list)
    bn_local_roots = altdriver.find_objects(By.NAME, 'Bn-Local_Root')

    # Add GO-Monkey and its corresponding Bn-Local_Root[0] (if applicable)
    go_monkey = altdriver.find_object(By.NAME, 'GO-Monkey')
    if bn_local_roots:
        monkey_tuples.append((go_monkey, bn_local_roots[0]))

    # Add GO-Monkey_1 to GO-Monkey_8 and their corresponding Bn-Local_Root by index
    for i in range(1, 9):  # Iterate from 1 to 8
        monkey_name = f"GO-Monkey_{i}"
        monkey = altdriver.find_object(By.NAME, monkey_name)

        # Use the same index `i` for Bn-Local_Root (accounting for 0-based indexing)
        bn_local_root = bn_local_roots[i] if i < len(bn_local_roots) else None

        if bn_local_root:
            monkey_tuples.append((monkey, bn_local_root))

    # Iterate through the tuples and check each monkey for the correct property
    for monkey, bn_local_root in monkey_tuples:
        # Get the 'correct' property for the current monkey
        monkey_correct = monkey.get_component_property(
            'SortingMonkeyController', 'correct', 'Assembly-CSharp'
        )

        # Check if the monkey has the correct property set to True
        if monkey_correct == True:  # Now comparing directly to the boolean value
            # Click the corresponding Bn-Local_Root object
            bn_local_root.click()
            time.sleep(1)
            bn_local_root.click()

def Search_3rd(altdriver):
    activity_obj = altdriver.find_object(By.NAME, 'LettersSearch_activity')
    activity_play_mode = int(activity_obj.get_component_property(
        'com.kideo.learn.english.LettersSearchActivityManagement',
        'sessionData_.LettersActivityPlayMode',
        'Assembly-CSharp'
    ))

    letter_obj = altdriver.find_objects(By.NAME, 'WordPanel')
    letter_text = letter_obj[0].get_component_property('WordPanel', 'word_.letter', 'Assembly-CSharp').lower()

    rounds = 2 if activity_play_mode == 1 else 1

    for round_number in range(rounds):
        for index, letter in enumerate(letter_obj):
            if index == 0:
                continue  # Skip the first iteration
            text = letter.get_component_property('TMProWordPanel', 'Word.word', 'Assembly-CSharp').lower()
            print(f"Round {round_number + 1} - Letter Text: {text}")
            if text == letter_text or text.startswith(letter_text):
                letter.click()
                time.sleep(0.5)

        if round_number < rounds - 1:
            time.sleep(6)  # Sleep for 6 seconds between rounds


def bubbels_activity(altdriver):
    # Find activity object
    print("Searching for 'LettersBubbles_activity'...")
    activity_obj = altdriver.find_object(By.NAME, 'LettersBubbles_activity')
    activity_play_mode = int(activity_obj.get_component_property(
        'com.kideo.learn.english.LettersBubblesActivityManagement',
        'sessionData_.LettersActivityPlayMode',
        'Assembly-CSharp'
    ))
    print(f"Activity Play Mode: {activity_play_mode}")

    # Get the target letter
    print("Retrieving target letter...")
    letter_obj = altdriver.find_objects(By.NAME, 'WordPanel')
    if not letter_obj:
        print("Error: No WordPanel objects found.")
        return

    letter_text = letter_obj[0].get_component_property('WordPanel', 'word_.letter', 'Assembly-CSharp')

    if letter_text:
        letter_text = letter_text.lower().strip()
        print(f"Target letter to match: {letter_text}")
    else:
        print("Error: letter_text is None")
        return

    # Continuously scan bubbles until activity progress indicates completion
    while True:
        # Check if ExitButton exists
        try:
            print("Checking for ExitButton...")
            exit_button = altdriver.find_object(By.NAME, 'ExitButton')
            if exit_button:
                print("ExitButton found. Clicking and stopping execution.")
                exit_button.click()
                break  # Stop execution after clicking the ExitButton
        except alttester.exceptions.NotFoundException:
            print("ExitButton not found, continuing...")

        # Scan bubbles objects
        print("Scanning for bubbles...")
        time.sleep(5)
        bubbels_objs = altdriver.find_objects(By.NAME, 'LettersBubble(Clone)')

        if not bubbels_objs:
            print("No bubbles found, skipping iteration.")
            continue  # Skip to the next loop iteration

        for index, bubble in enumerate(bubbels_objs):
            print(f"\n🔍 Iteration {index}: Checking bubble...")

            # Skip first index
            if index == 0:
                print(f"Skipping bubble at index {index} (First item)")
                continue  # Skip the first index

            if not bubble:
                print(f"Skipping index {index}: Bubble object is None")
                continue

            try:
                # Initialize text as None
                text = None

                # Try to get 'alphabet.letter' first
                try:
                    text = bubble.get_component_property('com.kideo.learn.english.LettersBubble', 'alphabet.letter', 'Assembly-CSharp')
                    if text:
                        print(f"✅ Found 'alphabet.letter' for bubble at index {index}: {repr(text)}")
                except alttester.exceptions.NotFoundException:
                    print(f"⚠️ 'alphabet.letter' not found for bubble at index {index}, falling back to 'alphabet.word'...")

                # Fallback to 'alphabet.word' if 'alphabet.letter' is empty or None
                if not text:
                    try:
                        text = bubble.get_component_property('com.kideo.learn.english.LettersBubble', 'alphabet.word', 'Assembly-CSharp')
                        if text:
                            print(f"✅ Found 'alphabet.word' for bubble at index {index}: {repr(text)}")
                    except alttester.exceptions.NotFoundException:
                        print(f"⚠️ 'alphabet.word' not found for bubble at index {index}, skipping...")

                # If both are still None or empty, skip this bubble
                if not text or text.strip() == "":
                    print(f"⚠️ No valid text found for bubble at index {index}, skipping...")
                    continue

                text = text.lower().strip()
                print(f"✅ Final text for bubble at index {index}: {text}")

                # Click the bubble if the letter matches
                if text == letter_text or text.startswith(letter_text):
                    print(f"✅ Match found! Clicking bubble at index {index} 🚀")
                    bubble.click()
                else:
                    print(f"❌ No match for '{text}', skipping bubble at index {index}")

            except alttester.exceptions.NotFoundException:
                print(f"❌ Bubble at index {index} not found or destroyed, skipping.")
                continue  # Skip to the next bubble

        # Wait a short period before rescanning bubbles
        time.sleep(1)

