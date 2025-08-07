import alttester
import inflect
import unicodedata
from alttester import By
import time
import re
from langdetect import detect
from Utilities.utilsdemo import *

def search(altdriver):
    """Automates the Search activity by matching and tapping letters."""
    progress = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progress.split('/')[1])

    for _ in range(number_of_words):
        time.sleep(2)
        full_text = altdriver.find_object(By.NAME, "WordPanel")\
            .get_component_property("WordPanel", "Word.ToLower", "Assembly-CSharp")
        current_text = altdriver.find_object(By.NAME, "RTLTMPWordPanel")\
            .get_component_property("TMProWordPanel", "Text", "Assembly-CSharp")

        differences = [char2 for char1, char2 in zip(current_text, full_text) if char1 == "_" and char2 != "_"]

        letters = altdriver.find_objects(By.NAME, "SearchObj(Clone)")
        covers = altdriver.find_objects(By.NAME, "CoverObj")
        letter_obj_pairs = [(l.get_component_property("com.kideo.learn.english.SearchObj", "letter", "Assembly-CSharp"), o)
                            for l, o in zip(letters, covers)]

        for letter in differences:
            for idx, (ltr, obj) in enumerate(letter_obj_pairs):
                if ltr == letter:
                    obj.tap(count=1, interval=1.5, wait=True)
                    letter_obj_pairs.pop(idx)
                    break

    print("[INFO] Search activity complete")


def find_matching_pairs(items):
    return [(i, j) for i in range(len(items)) for j in range(i+1, len(items)) if items[i] == items[j]]

def memory(altdriver):
    """Matches word-image pairs in the Memory activity."""
    time.sleep(17)

    text_cards = altdriver.find_objects(By.NAME, "ImageCardPrefab(Clone)")
    image_cards = altdriver.find_objects(By.NAME, "TextCardPrefab(Clone)")
    cards = image_cards + text_cards

    card_contents = [card.get_component_property("CardHandler1", "word.word", "Assembly-CSharp") for card in cards]
    pairs = find_matching_pairs(card_contents)

    for i, j in pairs:
        cards[i].click()
        time.sleep(0.5)
        cards[j].click()
        time.sleep(0.5)

    print("[INFO] Memory activity complete")


def fill_in(altdriver):
    """Solves Sentence Completion Quiz by selecting the correct index with detailed logs, including context text."""
    print("[INFO] Starting FillIn activity...")

    progress_text = altdriver.find_object(By.NAME, "ProgressText").get_text()
    print(f"[DEBUG] Progress text: {progress_text}")

    num_words = int(progress_text.split('/')[1])
    print(f"[INFO] Total number of words to complete: {num_words}")

    for i in range(num_words):
        print()
        print(f"[INFO] Solving word {i + 1} of {num_words}")
        time.sleep(1.6)

        try:
            context = altdriver.find_object(By.NAME, 'RTLTMPWordPanel')
            context_text = context.get_component_property('TMProWordPanel', 'Text', 'Assembly-CSharp')
            print(f"[CONTEXT] {context_text}")
        except Exception as e:
            print(f"[WARN] Could not fetch context text: {e}")

        try:
            answer_idx = altdriver.find_object(By.NAME, "Canvas").get_component_property(
                "SentenceCompletionQuiz", "answerIndex", "Assembly-CSharp"
            )
            print(f"[DEBUG] Correct answer index: {answer_idx}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch answer index: {e}")
            continue

        buttons = altdriver.find_objects(By.NAME, "Button")
        clicked = False
        for btn in buttons:
            index = btn.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if index == answer_idx:
                btn.click()
                print(f"[INFO] Clicked on correct button with index {index}")
                clicked = True
                break

        if not clicked:
            print("[WARN] No matching button was found for the correct answer index")

    print("[INFO] FillIn activity complete")

def normalize_text(text):
    """
    Normalize text for Arabic, Hebrew, and other languages.
    - Unicode normalization (NFKC)
    - Arabic presentation forms → base letters
    - Remove diacritics (Arabic, Hebrew)
    - Remove zero-width and directional marks
    """
    # Step 1: NFKC (safe for all languages)
    text = unicodedata.normalize("NFKC", text.strip())

    # Step 2: Normalize Arabic presentation forms
    text = ''.join(base_arabic_mapping.get(c, c) for c in text)

    # Step 3: Remove diacritics (Arabic harakat + Hebrew niqqud)
    text = ''.join(c for c in text if not unicodedata.category(c).startswith('M'))

    # Step 4: Remove invisible formatting (e.g. RTL/LTR marks, ZWNJ)
    text = re.sub(r'[\u200B-\u200F\u202A-\u202E]', '', text)

    return text
def is_rtl(text):
    """Returns True if text contains Arabic or Hebrew characters (i.e. RTL)."""
    return any('\u0590' <= c <= '\u06FF' for c in text)

# Arabic presentation form mapping (used only if character found)
base_arabic_mapping = {
    'ﺍ': 'ا', 'ﺎ': 'ا',
    'ﺏ': 'ب', 'ﺐ': 'ب', 'ﺑ': 'ب', 'ﺒ': 'ب',
    'ﺕ': 'ت', 'ﺖ': 'ت', 'ﺗ': 'ت', 'ﺘ': 'ت',
    'ﺙ': 'ث', 'ﺚ': 'ث', 'ﺛ': 'ث', 'ﺜ': 'ث',
    'ﺝ': 'ج', 'ﺞ': 'ج', 'ﺟ': 'ج', 'ﺠ': 'ج',
    'ﺡ': 'ح', 'ﺢ': 'ح', 'ﺣ': 'ح', 'ﺤ': 'ح',
    'ﺥ': 'خ', 'ﺦ': 'خ', 'ﺧ': 'خ', 'ﺨ': 'خ',
    'ﺩ': 'د', 'ﺪ': 'د',
    'ﺫ': 'ذ', 'ﺬ': 'ذ',
    'ﺭ': 'ر', 'ﺮ': 'ر',
    'ﺯ': 'ز', 'ﺰ': 'ز',
    'ﺱ': 'س', 'ﺲ': 'س', 'ﺳ': 'س', 'ﺴ': 'س',
    'ﺵ': 'ش', 'ﺶ': 'ش', 'ﺷ': 'ش', 'ﺸ': 'ش',
    'ﺹ': 'ص', 'ﺺ': 'ص', 'ﺻ': 'ص', 'ﺼ': 'ص',
    'ﺽ': 'ض', 'ﺾ': 'ض', 'ﺿ': 'ض', 'ﻀ': 'ض',
    'ﻁ': 'ط', 'ﻂ': 'ط', 'ﻃ': 'ط', 'ﻄ': 'ط',
    'ﻅ': 'ظ', 'ﻆ': 'ظ', 'ﻇ': 'ظ', 'ﻈ': 'ظ',
    'ﻉ': 'ع', 'ﻊ': 'ع', 'ﻋ': 'ع', 'ﻌ': 'ع',
    'ﻍ': 'غ', 'ﻎ': 'غ', 'ﻏ': 'غ', 'ﻐ': 'غ',
    'ﻑ': 'ف', 'ﻒ': 'ف', 'ﻓ': 'ف', 'ﻔ': 'ف',
    'ﻕ': 'ق', 'ﻖ': 'ق', 'ﻗ': 'ق', 'ﻘ': 'ق',
    'ﻙ': 'ك', 'ﻚ': 'ك', 'ﻛ': 'ك', 'ﻜ': 'ك',
    'ﻝ': 'ل', 'ﻞ': 'ل', 'ﻟ': 'ل', 'ﻠ': 'ل',
    'ﻡ': 'م', 'ﻢ': 'م', 'ﻣ': 'م', 'ﻤ': 'م',
    'ﻥ': 'ن', 'ﻦ': 'ن', 'ﻧ': 'ن', 'ﻨ': 'ن',
    'ﻩ': 'ه', 'ﻪ': 'ه', 'ﻫ': 'ه', 'ﻬ': 'ه',
    'ﻭ': 'و', 'ﻮ': 'و',
    'ﻱ': 'ي', 'ﻲ': 'ي', 'ﻳ': 'ي', 'ﻴ': 'ي',
}

def bubbels(altdriver):
    """Solves the Missing Bubble activity by identifying and clicking missing letters with detailed logs."""
    print("[INFO] Starting Bubbels activity...")

    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    print(f"[INFO] Total words to solve: {num_words}")

    for i in range(num_words):
        print(f"[INFO] Solving word {i + 1} of {num_words}")
        time.sleep(4.5)

        full_word = altdriver.find_object(By.NAME, "BubblesGameManager").get_component_property(
            "com.kideo.learn.english.BubblesGameManager", "newWord", "Assembly-CSharp"
        )
        print(f"[CONTEXT] Full target word: {full_word}")

        partial_word = altdriver.find_object(By.NAME, "text").get_text()
        print(f"[DEBUG] Partial word shown to user: {partial_word}")

        bg_name = altdriver.find_object(By.NAME, "bubbles_activity").get_component_property(
            "com.kideo.learn.english.BubblesActivityManagerScript", "currentBackground_.name", "Assembly-CSharp"
        )

        bubble_path = f"Bubble_{bg_name}" if bg_name in ['FairyTales(Clone)', 'Moon(Clone)', 'Candy(Clone)'] else "Bubble(Clone)"
        text_path = "Text_1"

        missing_letters = [c2 for c1, c2 in zip(partial_word, full_word) if c1 == "_" and c2 != "_"]
        print(f"[DEBUG] Missing letters to find: {missing_letters}")

        while missing_letters:
            try:
                bubbles = list(zip(
                    altdriver.find_objects(By.NAME, text_path),
                    altdriver.find_objects(By.NAME, bubble_path)
                ))
                for letter in missing_letters[:]:
                    for label, obj in bubbles:
                        label_text = normalize_text(label.get_text())
                        target_letter = normalize_text(letter)

                        if label_text == target_letter:
                            obj.click()
                            print(f"[INFO] Clicked bubble: {letter}")
                            missing_letters.remove(letter)
                            break
            except alttester.exceptions.NotFoundException:
                print("[WARN] Bubble objects not found, retrying...")
                time.sleep(0.5)
            time.sleep(0.5)

        print(f"[INFO] Word {i + 1} ('{full_word}') completed")

    print("[INFO] Bubbels activity complete")


def spiders(altdriver):
    """Solves the Sentence Translation Quiz by clicking the correct option."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        time.sleep(1.6)
        answer_idx = altdriver.find_object(By.NAME, "Canvas").get_component_property(
            "SentenceTranslationQuiz", "answerIndex", "Assembly-CSharp"
        )
        for btn in altdriver.find_objects(By.NAME, "Button"):
            if btn.get_component_property("ChoiceClick", "index", "Assembly-CSharp") == answer_idx:
                btn.click()
                break

    print("[INFO] Spiders activity complete")

def megaphone(altdriver):
    """Solves the Listen & Find activity using correct word sequence and background layout."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    iterations = 4 if num_words == 4 else 2 if num_words <= 6 else 3

    geo_name = altdriver.find_object(By.NAME, "ListenFind_activity").get_component_property(
        "com.kideo.learn.english.ListenFindActivityManagement", "sessionData_.CurrentGeographyName", "Assembly-CSharp"
    )

    leaf_map = {
        "Sea": "LeafPref_Sea(Clone)", "FairyTales": "LeafPref_Farm(Clone)", "Dinosaurs": "LeafPref_Dinosaurs(Clone)",
        "Space": "LeafPref_Moon(Clone)", "Candy": "LeafPref_Candy(Clone)", "Farm": "LeafPref_Farm(Clone)",
        "Desert": "LeafPref_Desert(Clone)", "Pole": "LeafPref_Pole(Clone)"
    }
    leaf_name = leaf_map.get(geo_name, "LeafPref(Clone)")

    for _ in range(iterations):
        time.sleep(4)
        papers = altdriver.find_objects(By.NAME, "PaperPref(Clone)")
        leaves = altdriver.find_objects(By.NAME, leaf_name)
        combined = papers + leaves

        word_objs = [(obj.get_component_property("com.kideo.learn.english.ListenFindObject", "word.word", "Assembly-CSharp"), obj)
                     for obj in combined]
        used_words = altdriver.find_object(By.NAME, "ListenFindGameManager").get_component_property(
            "com.kideo.learn.english.ListenFindGameManager", "usedWords", "Assembly-CSharp"
        )

        clicked = set()
        for word in used_words:
            for text, obj in word_objs:
                if word == text and word not in clicked:
                    obj.click()
                    clicked.add(word)
                    time.sleep(1)
                    break

    print("[INFO] Megaphone activity complete")

def exams_word_to_meaning(altdriver):
    """Matches words to their correct meaning shapes by swiping."""
    time.sleep(1)
    words = altdriver.find_objects(By.NAME, 'WordMeaningObject(Clone)')
    if not words:
        raise Exception("Not a word-to-meaning exam")

    shapes = altdriver.find_objects(By.NAME, 'WordMeaningShape(Clone)')

    word_data = [(w.get_text(), w, w.get_screen_position()) for w in words]
    shape_data = [(s.get_component_property('com.kideo.learn.english.WordMeaningShape', 'word', 'Assembly-CSharp'),
                   s, (s.get_screen_position()[0], s.get_screen_position()[1] - 100)) for s in shapes]

    for word_text, word_obj, word_pos in word_data:
        for shape_text, shape_obj, shape_pos in shape_data:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word_obj.click()
                break

    print("[INFO] exams_word_to_meaning completed")

def exams_word_to_image(altdriver):
    """Matches words to images by swiping and clicking."""
    time.sleep(1)
    words = altdriver.find_objects(By.NAME, 'MatchWordText(Clone)')
    if not words:
        raise Exception("Not a word-to-image exam")

    shapes = altdriver.find_objects(By.NAME, 'MatchShapeImage(Clone)')

    word_data = [(w.get_text(), w, w.get_screen_position()) for w in words]
    shape_data = [(s.get_component_property('com.kideo.learn.english.MatchTestShape', 'word', 'Assembly-CSharp'),
                   s, (s.get_screen_position()[0], s.get_screen_position()[1] - 100)) for s in shapes]

    for word_text, word_obj, word_pos in word_data:
        for shape_text, shape_obj, shape_pos in shape_data:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word_obj.click()
                break

    print("[INFO] exams_word_to_image completed")

def exams_3rd_letter_to_word_image_match(altdriver):
    """Generically matches words to images based on shared letters (e.g. 'G' -> 'giraffe')."""
    time.sleep(1)
    words = altdriver.find_objects(By.NAME, 'LetterWordText Variant(Clone)')
    shapes = altdriver.find_objects(By.NAME, 'LetterShapeImage Variant(Clone)')

    if not words or not shapes:
        raise Exception("Missing words or shapes for letter-to-word matching")

    # Get word data: (text, object, screen_position)
    word_data = [
        (w.get_component_property('com.kideo.learn.english.MatchTestWord', 'word', 'Assembly-CSharp'), w, w.get_screen_position())
        for w in words
    ]

    # Get shape data: (letter, object, adjusted_screen_position)
    shape_data = [
        (s.get_component_property('com.kideo.learn.english.MatchTestShape', 'word', 'Assembly-CSharp'),
         s, (s.get_screen_position()[0], s.get_screen_position()[1] - 100))
        for s in shapes
    ]

    used_words = set()

    for shape_letter, shape_obj, shape_pos in shape_data:
        matched = False
        for word_text, word_obj, word_pos in word_data:
            if word_text.lower() not in used_words and shape_letter.lower() in word_text.lower():
                print(f"[INFO] Matching letter '{shape_letter}' with word '{word_text}'")
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word_obj.click()
                used_words.add(word_text.lower())
                matched = True
                break
        if not matched:
            print(f"[WARNING] No matching word found for letter: {shape_letter}")

    print("[INFO] Letter-to-word image matching completed.")


def exams_3rd_audio_to_letter_matrix(altdriver):
    "Generically matches words to images based on shared letters (e.g. 'G' -> 'giraffe')."

    time.sleep(1)
    audio_obj = altdriver.find_object(By.NAME, 'LetterTestPanel(Clone)')
    audio_text = audio_obj.get_component_property(
        'com.kideo.learn.english.LetterTest', 'alphabet.letter', 'Assembly-CSharp'
    ).lower()

    letters_objs = altdriver.find_objects(By.NAME, 'WordPanel')

    for letter in letters_objs[1:10]:  # start from index 1
        letter_text = letter.get_component_property(
            'WordPanel', 'textControl.text', 'Assembly-CSharp'
        ).lower()

        if letter_text == audio_text:
            letter.click()
              # optional: stop after first match

    print("[INFO] Letter-to-word image matching completed.")


def exams_audio_to_meaning(altdriver):
    """Matches audio meanings to word labels via swipe interaction."""
    time.sleep(1)
    audio_shapes = altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')
    if not audio_shapes:
        raise Exception("Not an audio-to-meaning exam")

    for shape in audio_shapes:
        shape.click()
        time.sleep(1)

    words = altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
    word_data = [(w.get_component_property('com.kideo.learn.english.WordAudioObject', 'word', 'Assembly-CSharp'), w, w.get_screen_position()) for w in words]

    shape_data = [(s.get_component_property('com.kideo.learn.english.WordAudioShape', 'word', 'Assembly-CSharp'),
                   s, (s.get_screen_position()[0], s.get_screen_position()[1] - 100)) for s in audio_shapes]

    for word_text, word_obj, word_pos in word_data:
        for shape_text, shape_obj, shape_pos in shape_data:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                word_obj.click()
                break

    print("[INFO] exams_audio_to_meaning completed")

def exam_spelling(altdriver):
    """Completes the spelling activity by clicking missing letters."""
    missing_words = altdriver.find_objects(By.NAME, "FillWord(Clone)")
    if len(missing_words) == 0:
        missing_words = altdriver.find_objects(By.NAME, "VTFillWord_RTL(Clone)")

    missing_letters_list = []

    for obj in missing_words:
        raw_letters = obj.get_component_property("com.kideo.learn.english.FillMissingWord", "missingLetters", "Assembly-CSharp")
        try:
            if isinstance(raw_letters, str):
                letters = eval(raw_letters)
            elif isinstance(raw_letters, list):
                letters = raw_letters
            else:
                raise ValueError()
            missing_letters_list.append([l.lower() for l in letters])
        except:
            raise ValueError(f"Invalid format: {raw_letters}")

    toggles = altdriver.find_objects(By.NAME, "FillWordToggle")
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }

    for i, letters in enumerate(missing_letters_list):
        if i < len(toggles):
            toggles[i].click()
            for letter in letters:
                if letter in letters_map:
                    letters_map[letter].click()
                    time.sleep(0.2)

    print("[INFO] exam_spelling completed")

def exam_multiple_choice(altdriver):
    """Clicks toggle by index across all questions using pre-collected toggle lists."""

    questions = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')
    if len(questions) == 0 :
        questions = altdriver.find_objects(By.NAME, 'QuestionTemplate_RTL(Clone)')
    correct_indexes = []

    # Step 1: Get correct index for each question
    for q in questions:
        index = q.get_component_property("ContextWithMissingWordQuestion", "answerIndex", "Assembly-CSharp")
        correct_indexes.append(index)

    # Step 2: Get all toggles globally (lists)
    toggles0 = altdriver.find_objects(By.NAME, 'Toggle0')
    toggles1 = altdriver.find_objects(By.NAME, 'Toggle1')
    toggles2 = altdriver.find_objects(By.NAME, 'Toggle2')
    toggles3 = altdriver.find_objects(By.NAME, 'Toggle3')

    toggle_lists = [toggles0, toggles1, toggles2, toggles3]

    # Step 3: Click correct toggle per question
    for i, correct_index in enumerate(correct_indexes):
        try:
            target_toggle = toggle_lists[correct_index][i]
            target_toggle.click()
            print(f"[INFO] Question {i+1}: Clicked Toggle{correct_index}[{i}]")
        except Exception as e:
            print(f"[ERROR] Question {i+1}: Failed to click Toggle{correct_index}[{i}] - {e}")


def echo_order(altdriver):
    """Completes the Echo Order quiz by selecting words in the correct order."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        time.sleep(2.5)

        sentence = altdriver.find_object(By.NAME, 'ContextEchoOrderQuiz(Clone)')\
            .get_component_property('com.kideo.learn.english.ContextBuilderQuiz', 'correctAnswer_', 'Assembly-CSharp')
        print('Current Sentence to solve:', sentence)

        words_in_order = [normalize_text(w) for w in sentence.split(' ')]

        text_objects = altdriver.find_objects(By.NAME, "Text")
        clickable_words = [(normalize_text(t.get_text()), t.get_parent()) for t in text_objects]

        word_map = {}
        for word, parent in clickable_words:
            word_map.setdefault(word, []).append(parent)

        click_counts = {}

        for word in words_in_order:
            click_counts[word] = click_counts.get(word, 0)
            if word in word_map and click_counts[word] < len(word_map[word]):
                word_map[word][click_counts[word]].click()
                print(f"[INFO] Clicked word: {word}")
                click_counts[word] += 1
                time.sleep(1)
            else:
                print(f"[WARN] Could not find word to click: {word}")

        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)

        if _ < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1)

    print("[INFO] EchoOrder activity complete")
def translation_wiz(altdriver):
    """Completes the Translation Wiz quiz by selecting words in correct translated order."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        time.sleep(2.5)
        sentence = altdriver.find_object(By.NAME, 'ContextTranslationWizQuiz(Clone)')\
            .get_component_property('com.kideo.learn.english.ContextBuilderQuiz', 'correctAnswer_', 'Assembly-CSharp')
        words_in_order = sentence.split(' ')

        text_objects = altdriver.find_objects(By.NAME, "Text")
        clickable_words = [(t.get_text(), t.get_parent()) for t in text_objects]

        word_map = {}
        for word, parent in clickable_words:
            word_map.setdefault(word, []).append(parent)

        click_counts = {}

        for word in words_in_order:
            click_counts[word] = click_counts.get(word, 0)
            if word in word_map and click_counts[word] < len(word_map[word]):
                word_map[word][click_counts[word]].click()
                click_counts[word] += 1
                time.sleep(1)

        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)

        if _ < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1)

    print("[INFO] TranslationWiz activity complete")


def frogger(altdriver):
    """Solves Frogger activity with RTL-aware word clicking order."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        time.sleep(3)

        sentence = altdriver.find_object(By.NAME, 'FroggerGameManager')\
            .get_component_property('com.kideo.learn.english.Frogger.FroggerGameManager', 'selectedSentence', 'Assembly-CSharp')
        print('Current sentence to solve:', sentence)

        words = [normalize_text(w) for w in sentence.split(' ')]
        if is_rtl(sentence):
            words = words[::-1]  # reverse only for Hebrew/Arabic

        word_objs = [(normalize_text(t.get_text()), t.get_parent()) for t in altdriver.find_objects(By.NAME, "Text")]

        used = []
        for word in words:
            for idx, (text, obj) in enumerate(word_objs):
                if text == word and idx not in used:
                    obj.click()
                    used.append(idx)
                    time.sleep(1.8)
                    break


        click_by_name(altdriver, "CheckSentenceButton")
        time.sleep(2)

        # Move frog to final line
        frog = altdriver.find_object(By.NAME, "Frogger")
        final_line = altdriver.find_object(By.NAME, "FinalLine")\
            .get_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule")
        frog.set_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule", final_line)

        click_by_name(altdriver, "UpButton")
        time.sleep(5)

    print("[INFO] Frogger activity complete")
def gap_guru(altdriver):
    """Solves the GapGuru quiz by selecting and confirming the correct word choice."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for i in range(num_words):
        current_sentence = altdriver.find_object(By.NAME, 'ContextGapGuruQuiz(Clone)')
        current_sentence_text = current_sentence.get_component_property(
            'com.kideo.learn.english.ContextFillMissingWordQuiz',
            'currentContext_.context', 'Assembly-CSharp')
        print('Current Sentence : ', current_sentence_text)

        time.sleep(2.5)

        correct_word = altdriver.find_object(By.NAME, "ContextGapGuruQuiz(Clone)")\
            .get_component_property("com.kideo.learn.english.ContextFillMissingWordQuiz", "missingWord_", "Assembly-CSharp")

        normalized_correct = normalize_text(correct_word)

        options = altdriver.find_objects(By.NAME, "QuizWordToggle(Clone)")
        for opt in options:
            word = opt.get_component_property("com.kideo.learn.english.QuizWordToggle", "text.text", "Assembly-CSharp")
            normalized_option = normalize_text(word)


            if normalized_option == normalized_correct:
                opt.click()
                print(f"[INFO] Clicked correct option: {word}")
                break
        else:
            print(f"[WARN] Correct word '{correct_word}' not found among options.")

        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)

        if i < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1)

    print("[INFO] GapGuru activity complete")
def bee(altdriver):
    """Solves Bee Careful by dragging the correct word to the hive."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    bg_name = altdriver.find_object(By.NAME, "BeeCareful_activity").get_component_property(
        "com.kideo.learn.english.BeeCarefulActivityManagement",
        "sessionData_.CurrentGeographyName",
        "Assembly-CSharp"
    )

    background_map = {
        "Sea": "DraggableObjectB_Sea(Clone)", "FairyTales": "DraggableObjectB_FairyTales(Clone)",
        "Dinosaurs": "DraggableObjectB_Farm(Clone)", "Space": "DraggableObjectB_Farm(Clone)",
        "Candy": "DraggableObjectB_Candy(Clone)", "Farm": "DraggableObjectB_Farm(Clone)",
        "Desert": "DraggableObjectB_Desert(Clone)", "Pole": "DraggableObjectB_Farm(Clone)"
    }
    obj_name = background_map.get(bg_name, "DraggableObjectB(Clone)")

    for _ in range(num_words):
        time.sleep(3)
        objects = altdriver.find_objects(By.NAME, obj_name)
        target_word = altdriver.find_object(By.NAME, 'WordPanel')\
            .get_component_property("WordPanel", "<wordObj_>k__BackingField.word", "Assembly-CSharp")

        match = next((o for o in objects if o.get_component_property(
            "com.kideo.learn.english.BeeCarefulObject", "word", "Assembly-CSharp") == target_word), None)

        if match:
            hive = altdriver.find_object(By.NAME, "Vector Smart Object_3")
            pos = hive.get_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule")
            match.set_component_property("UnityEngine.Transform", "localScale", "UnityEngine.CoreModule",
                                     {"x": 0.3, "y": 0.3, "z": 0.3})

            match.set_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule", pos)
            match.click()
            time.sleep(3)

    print("[INFO] Bee activity complete")
'''
s = altdriver.find_objects(By.NAME,'DraggableObjectB(Clone)')
s.set_component_property("UnityEngine.Transform", "localScale", "UnityEngine.CoreModule", {"x": 1, "y": 2, "z": 1})

'''

def radar(altdriver):
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


def type_it_right(altdriver):
    """Types the correct word into the input, reversing only Arabic."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for i in range(num_words):
        time.sleep(2.5)

        raw_answer = altdriver.find_object(By.NAME, "ContextTypingItQuiz(Clone)") \
            .get_component_property("com.kideo.learn.english.ContextAudioTypingQuiz", "currentWord_.word",
                                    "Assembly-CSharp")

        normalized = normalize_text(raw_answer)

        # Reverse ONLY Arabic
        final_to_type = normalized[::-1] if is_rtl(normalized) else normalized

        input_field = altdriver.find_object(By.NAME, "InputField")
        input_field.set_text(final_to_type)
        print(f"[DEBUG] Typed: '{final_to_type}' (original: '{raw_answer}')")

        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)

        if i < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1)

    print("[INFO] TypeItRight activity complete")
def hang_words(altdriver):
    """Clicks all correct clothing items for each word."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        while True:
            current_sentence = altdriver.find_object(By.NAME, 'Canvas')
            current_sentence_text = current_sentence.get_component_property('HangWordsActivityManagement','gameManager.sentance','Assembly-CSharp')
            print('Current Sentence : ',current_sentence_text)
            time.sleep(5)
            clothes = [o for o in altdriver.get_all_elements() if o.name.startswith("c") and "(Clone)" in o.name]
            correct = [c for c in clothes if c.get_component_property("ClothesData", "isCorrect", "Assembly-CSharp") is True]

            if not correct:
                break

            for c in correct:
                c.click()
                time.sleep(2)

    print("[INFO] HangWords activity complete")

def Cards(altdriver):
    """Speaks all words from cards and exits when done."""
    while True:
        word_objs = altdriver.find_objects(By.NAME, "RTLTMPWordPanel")
        for word in word_objs:
            word_text = word.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
            print(f"[INFO] Speaking card word: {word_text}")
            say(word_text)
            time.sleep(2)

        try:
            exit_button = altdriver.find_object(By.NAME, "ExitButton")
            exit_button.click()
            break
        except:
            print("[INFO] Waiting for final feedback...")
            time.sleep(0.5)

    print("[INFO] Cards activity complete")

def Delivery_truck(altdriver):
    """Speaks out loud each new word in the delivery truck boxes."""
    total_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    previous = None

    for _ in range(total_words):
        retries = 0
        while retries < 20:
            try:
                box = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
                word = box.get_component_property("TMProWordPanel", "TMPTextControl.OriginalText", "Assembly-CSharp")

                if word != previous:
                    say(word)
                    previous = word
                    break
                else:
                    print("[INFO] Waiting for next word to load...")
            except Exception as e:
                print(f"[WARN] Failed to retrieve text: {e}")

            retries += 1
            time.sleep(0.5)

    print("[INFO] Delivery_truck activity complete")


def moles(altdriver):
    """Speaks each word as it appears from the mole."""
    time.sleep(2)

    while True:
        try:
            mole = altdriver.wait_for_object(By.NAME, "RTLTMPWordPanel")
            word = mole.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
            if word.strip():
                say(word)
            else:
                print("[INFO] Empty word detected. Waiting...")
        except Exception as e:
            print(f"[INFO] Mole game ended: {e}")
            break

    print("[INFO] Moles activity complete")


def magic_trace(altdriver):
    """Connects tracing dots between FirstNumber and SecondNumber objects."""
    total = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for i in range(total):
        time.sleep(6)
        first = altdriver.find_objects(By.NAME, "FirstNumber")
        second = altdriver.find_objects(By.NAME, "SecondNumber")

        for a, b in zip(first, second):
            altdriver.swipe(a.get_screen_position(), b.get_screen_position(), duration=0.8)
            time.sleep(0.5)

        print(f"[INFO] Traced word {i + 1}/{total}")

    print("[INFO] magic_trace activity complete")


def signs(altdriver):
    """Performs the Signs activity – finds and clicks all monkeys with the matching letter."""
    print("[INFO] Starting Signs activity...")

    try:
        # Step 1: Get the current letter from the WordPanel
        current_letter_obj = altdriver.find_object(By.NAME, 'WordPanel')
        current_letter_raw = current_letter_obj.get_component_property(
            'WordPanel',
            '<wordObj_>k__BackingField.levelData.letter',
            'Assembly-CSharp'
        )

        if not current_letter_raw:
            print("[ERROR] Current letter is None or empty. Exiting activity.")
            return

        target_letter = current_letter_raw.lower()
        print(f"[INFO] Target letter: '{target_letter}'")

    except Exception as e:
        print(f"[ERROR] Failed to get current letter: {e}")
        return

    try:
        # Step 2: Get monkeys and clickable roots
        monkeys = [altdriver.find_object(By.NAME, "GO-Monkey" if i == 0 else f"GO-Monkey_{i}") for i in range(9)]
        roots = altdriver.find_objects(By.NAME, "Bn-Local_Root")
    except Exception as e:
        print(f"[ERROR] Failed to find monkeys or roots: {e}")
        return

    found_any = False

    # Step 3: Iterate and click all matching monkeys
    for i, monkey in enumerate(monkeys):
        try:
            monkey_letter_raw = monkey.get_component_property(
                "SortingMonkeyController",
                "alphabet.word",
                "Assembly-CSharp"
            )

            if not monkey_letter_raw:
                print(f"[WARN] Monkey {i}: No letter found.")
                continue

            monkey_letter = monkey_letter_raw.lower()

            if monkey_letter == target_letter or target_letter in monkey_letter:
                print(f"[INFO] Found match on monkey {i}: '{monkey_letter}' – clicking.")
                roots[i].click()
                time.sleep(1)
                roots[i].click()
                found_any = True

        except Exception as e:
            print(f"[ERROR] Failed to process monkey {i}: {e}")

    if not found_any:
        print("[WARN] No matching monkeys found.")

    print("[INFO] Signs activity complete ✅")

def search_3rd(altdriver):
    time.sleep(10)
    """Performs the letter search activity (3rd grade version) – clicks words that match, start with, or contain the target letter."""

    try:
        # Step 1: Get the activity mode (to know if it's 1 round or 2 rounds)
        mode = int(altdriver.find_object(By.NAME, "LettersSearch_activity")\
            .get_component_property("com.kideo.learn.english.LettersSearchActivityManagement",
                                    "sessionData_.LettersActivityPlayMode", "Assembly-CSharp"))
    except Exception as e:
        print(f"[ERROR] Failed to get play mode: {e}")
        return

    # Step 2: Get the target letter from the first WordPanel
    try:
        target_wordpanel = altdriver.find_objects(By.NAME, "WordPanel")[0]
        target_letter_raw = target_wordpanel.get_component_property("WordPanel", "Word.letter", "Assembly-CSharp")

        if not target_letter_raw:
            print("[ERROR] Target letter is None or empty! Exiting activity.")
            return

        target = target_letter_raw.lower()
        print(f"[INFO] Target letter: '{target}'")
    except Exception as e:
        print(f"[ERROR] Failed to get target letter: {e}")
        return

    # Step 3: Determine number of rounds
    rounds = 2 if mode == 1 else 1

    # Step 4: Play each round
    for round_num in range(rounds):
        print(f"[INFO] Starting round {round_num + 1} of {rounds}...")

        try:
            word_panels = altdriver.find_objects(By.NAME, "WordPanel")
        except Exception as e:
            print(f"[ERROR] Failed to find WordPanels: {e}")
            continue

        for i, word_panel in enumerate(word_panels):
            if i == 0:
                continue  # Skip the first WordPanel (it's the target letter display)

            try:
                text_raw = word_panel.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
                if not text_raw:
                    print(f"[WARN] Word {i}: 'Word.word' is None or empty, skipping...")
                    continue

                text = text_raw.lower()

                if text == target or text.startswith(target) or target in text:
                    word_panel.click()
                    print(f"[INFO] Clicked word {i}: '{text}'")
                    time.sleep(0.5)

            except Exception as e:
                print(f"[ERROR] Could not process word {i}: {e}")

        # Wait between rounds if needed
        if round_num < rounds - 1:
            print("[INFO] Waiting for next round...")
            time.sleep(6)

    print("[INFO] Search_3rd activity complete ✅")

def bubbels_activity_3rd(altdriver, max_rounds=10):
    """
    Solves the LettersBubbles activity by clicking correct letter bubbles,
    without relying on the Exit button to break the loop.
    """
    logging.info("[Bubbles] Starting LettersBubbles activity")
    time.sleep(2)

    # Get the mode if needed (unused in logic currently)
    activity = altdriver.find_object(By.NAME, "LettersBubbles_activity")
    mode = int(activity.get_component_property(
        "com.kideo.learn.english.LettersBubblesActivityManagement",
        "sessionData_.LettersActivityPlayMode", "Assembly-CSharp"))

    # Get the target letter
    target = altdriver.find_objects(By.NAME, "WordPanel")[0]\
        .get_component_property("WordPanel", "Word.letter", "Assembly-CSharp").lower().strip()

    rounds = 0
    while rounds < max_rounds:
        bubbles = altdriver.find_objects(By.NAME, "LettersBubble(Clone)")
        found_match = False

        for bubble in bubbles:
            text = None
            try:
                text = bubble.get_component_property("com.kideo.learn.english.LettersBubble", "alphabet.letter", "Assembly-CSharp")
            except:
                pass
            if not text:
                try:
                    text = bubble.get_component_property("com.kideo.learn.english.LettersBubble", "alphabet.word", "Assembly-CSharp")
                except:
                    continue

            if text:
                text = text.lower().strip()
                if text == target or text.startswith(target):
                    try:
                        bubble.click()
                        found_match = True
                        logging.debug(f"[Bubbles] Clicked on bubble with text: {text}")
                    except:
                        logging.warning(f"[Bubbles] Failed to click bubble with text: {text}")

        if not found_match:
            logging.info("[Bubbles] No more matching bubbles found. Assuming activity is done.")
            break

        time.sleep(3)
        rounds += 1

    logging.info("[Bubbles] Activity complete, attempting to exit")
def moving(altdriver):
    """Solves the Words Matching Quiz by clicking the correct option."""
    total = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(total):
        answer_index = altdriver.find_object(By.NAME, "Canvas")\
            .get_component_property("WordsMatchingQuiz", "answerIndex", "Assembly-CSharp")
        options = altdriver.find_objects(By.NAME, "Button")

        for option in options:
            idx = option.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if idx == answer_index:
                option.click()
                time.sleep(2)
                break

    print("[INFO] Moving activity complete")


def lexi_match(altdriver):
    """Solves the Unscramble Quiz by clicking the correct answer."""
    total = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(total):
        time.sleep(1.6)
        current_word = altdriver.find_object(By.NAME, 'Canvas')
        current_word_text = current_word.get_component_property('UnscrambleQuiz', 'questionWord.Text','Assembly-CSharp')
        print('Current word : ',current_word_text)


        correct_idx = altdriver.find_object(By.NAME, "Canvas")\
            .get_component_property("UnscrambleQuiz", "answerIndex", "Assembly-CSharp")
        buttons = altdriver.find_objects(By.NAME, "Button")

        for btn in buttons:
            idx = btn.get_component_property("ChoiceClick", "index", "Assembly-CSharp")
            if idx == correct_idx:
                btn.click()
                break

    print("[INFO] LexiMatch activity complete")

def ispy(altdriver):
    """
    Solves the Ispy activity by detecting and clicking correct objects.
    Supports fallback for white and brown text/image variants.
    """
    print("[INFO] Starting Ispy activity...")

    def find_first_available_objects(name_variants):
        """Tries each object name until one returns results."""
        for name in name_variants:
            objs = altdriver.find_objects(By.NAME, name)
            if objs:
                print(f"[DEBUG] Found {len(objs)} objects with name: {name}")
                return objs
            else:
                print(f"[DEBUG] No objects found for: {name}")
        return []

    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    numberOfwords = int(progresstext.split('/')[1])
    print(f"[INFO] Total items to find: {numberOfwords}")

    for i in range(numberOfwords):
        print(f"[INFO] Solving item {i + 1} of {numberOfwords}")
        time.sleep(5)

        text_variants = [
            'GridElementWithText(Clone)',
            'GridElementWithText white(Clone)',
            'GridElementWithText brown(Clone)',
        ]
        image_variants = [
            'GridElementWithImage(Clone)',
            'GridElementWithImage white(Clone)',
            'GridElementWithImage brown(Clone)',
        ]

        objs_with_text = find_first_available_objects(text_variants)
        objs_with_image = find_first_available_objects(image_variants)

        answers = objs_with_text + objs_with_image
        current_word = altdriver.find_object(By.NAME, 'Canvas')
        current_word_text = current_word.get_component_property('ISpyLevelGenerator', 'currentQuestion.word.word','Assembly-CSharp')
        print(f"[DEBUG] Total answer objects found: {len(answers)}")

        print('Current word : ',current_word_text)

        flag = False
        for answer in answers:
            if flag:
                continue
            try:
                is_correct_answer = answer.get_component_property(
                    'ClickHandeler', 'onClick.Method.Name', 'Assembly-CSharp'
                )
                if is_correct_answer == 'OnCorrectClick':
                    answer.click()
                    print("[INFO] Correct answer clicked")
                    flag = True
                    time.sleep(2)
            except Exception as e:
                print(f"[WARN] Error processing answer: {e}")

    print("[INFO] Ispy activity complete")

def crosswords2(altdriver):
    """Solve all crossword items based on ProgressText."""
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progresstext.split('/')[1])
    print(f"[INFO] Total words to solve: {number_of_words}")

    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Step 1: Get current target word
        current_word_obj = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        current_word_text = current_word_obj.get_component_property(
            'TMProWordPanel', 'Word.word', 'Assembly-CSharp'
        ).lower()
        print(f"[DEBUG] Target word: {current_word_text}")

        # Step 2: Get clickable letters on screen
        letters_map = {
            letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
            for letter in altdriver.find_objects(By.NAME, 'FillLetter')
        }
        print(f"[DEBUG] Available letters: {list(letters_map.keys())}")

        # Step 3: Click each letter in the word
        for letter in current_word_text:
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")

        # Wait for next round to load
        time.sleep(1.5)

    print("[INFO] Crosswords2 activity complete.")


