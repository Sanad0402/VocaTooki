import alttester
import inflect
import unicodedata
from alttester import By
import time
import re
from langdetect import detect
from Utilities.utilsdemo import *
from Utilities.utilsdemo import click_by_name
import math
import time
from alttester import By

from Utilities.utils_audio import say, init_audio  # or wherever you placed it


def search(altdriver):
    """Automates the Search activity by matching and tapping letters."""
    progress = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progress.split('/')[1])

    for _ in range(number_of_words):

        # Wait for screen to settle
        time.sleep(1)

        full_text = altdriver.find_object(By.NAME, "WordPanel") \
            .get_component_property("WordPanel", "Word.ToLower", "Assembly-CSharp")

        current_text = altdriver.find_object(By.NAME, "RTLTMPWordPanel") \
            .get_component_property("TMProWordPanel", "Text", "Assembly-CSharp")

        # Hebrew/Arabic: the RTL panel reports its Text in visual (reversed)
        # order while WordPanel.Word is logical order, so reverse current_text
        # to align the underscores with full_text before diffing.
        if is_rtl(full_text):
            current_text = current_text[::-1]

        differences = [char2 for char1, char2 in zip(current_text, full_text)
                       if char1 == "_" and char2 != "_"]

        for letter in differences:

            # Re-scan before each click → sequential clicking
            letters = altdriver.find_objects(By.NAME, "SearchObj(Clone)")
            covers = altdriver.find_objects(By.NAME, "CoverObj")

            letter_obj_pairs = [
                (l.get_component_property("com.kideo.learn.english.SearchObj", "letter", "Assembly-CSharp").lower(), o)
                for l, o in zip(letters, covers)
            ]

            for ltr, obj in letter_obj_pairs:
                if ltr == letter:
                    obj.tap(count=1, interval=0.5, wait=True)

                    # Wait for Unity to update between letters
                    time.sleep(0.7)
                    break

        # ✅ Wait 5 seconds before going to the next word
        time.sleep(5)

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
        "Sea": "LeafPref_Sea(Clone)", "FairyTales": "LeafPref(Clone)", "Dinosaurs": "LeafPref_Dinosaurs(Clone)",
        "Space": "LeafPref_Moon(Clone)", "Candy": "LeafPref_Candy(Clone)", "Farm": "LeafPref(Clone)",
        "Desert": "LeafPref_Desert(Clone)", "Pole": "LeafPref_Pole(Clone)","Islam":"LeafPref_Islam(Clone)","China":"LeafPref_Rome(Clone)"
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
        words= altdriver.find_objects(By.NAME, 'KL_WordMeaningObject(Clone)')

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
    """Automates matching audio meanings to word labels via swipe interaction."""
    time.sleep(1)

    # --- Find audio shapes ---
    audio_shapes = altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')
    if not audio_shapes:
        audio_shapes = altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)')
    if not audio_shapes:
        audio_shapes = altdriver.find_objects(By.NAME, 'WordAudioShape_RTL(Clone)')
    if not audio_shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")

    # --- Click each shape once to activate audio ---
    for shape in audio_shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    # --- Find word objects ---
    words = altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
    if not words:
        words = altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)')
    if not words:
        words = altdriver.find_objects(By.NAME, 'WordAudioObject_RTL(Clone)')
    if not words:
        raise Exception("[ERROR] No word objects found.")

    # --- Collect data ---
    word_data = []
    for w in words:
        try:
            word_text = w.get_component_property(
                'com.kideo.learn.english.WordAudioObject', 'word', 'Assembly-CSharp'
            )
            word_pos = w.get_screen_position()
            word_data.append((word_text, w, word_pos))
        except Exception as e:
            print(f"[WARN] Failed to read word: {e}")

    shape_data = []
    for s in audio_shapes:
        try:
            shape_text = s.get_component_property(
                'com.kideo.learn.english.WordAudioShape', 'word', 'Assembly-CSharp'
            )
            x, y = s.get_screen_position()
            shape_data.append((shape_text, s, (x, y - 100)))  # small offset upwards
        except Exception as e:
            print(f"[WARN] Failed to read shape: {e}")

    # --- Swipe matches ---
    matched = 0
    for word_text, word_obj, word_pos in word_data:
        for shape_text, _, shape_pos in shape_data:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                time.sleep(0.5)
                word_obj.click()
                matched += 1
                break

    print(f"[INFO] exams_audio_to_meaning completed ({matched}/{len(word_data)} matched).")

def exam_spelling(altdriver):
    """Completes the spelling activity by clicking missing letters."""
    # ✅ Corrected missing_words fallback logic
    missing_words = altdriver.find_objects(By.NAME, "FillWord(Clone)")
    if not missing_words:
        missing_words = altdriver.find_objects(By.NAME, 'KL_FillWord(Clone)')
    if not missing_words:  # second fallback
        missing_words = altdriver.find_objects(By.NAME, "VTFillWord_RTL(Clone)")

    missing_letters_list = []

    for obj in missing_words:
        raw_letters = obj.get_component_property(
            "com.kideo.learn.english.FillMissingWord",
            "missingLetters",
            "Assembly-CSharp"
        )
        try:
            # ✅ Safer parsing (no risky eval)
            if isinstance(raw_letters, str):
                import ast
                letters = ast.literal_eval(raw_letters)
            elif isinstance(raw_letters, list):
                letters = raw_letters
            else:
                raise ValueError()
            missing_letters_list.append([l.lower() for l in letters])
        except Exception:
            raise ValueError(f"Invalid format: {raw_letters}")

    toggles = altdriver.find_objects(By.NAME, "FillWordToggle")
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }

    for i, letters in enumerate(missing_letters_list):
        if i < len(toggles):
            toggles[i].click()
            time.sleep(0.4)  # ✅ small delay for UI update
            for letter in letters:
                if letter in letters_map:
                    letters_map[letter].click()
                    time.sleep(0.2)
                else:
                    print(f"[WARN] Letter '{letter}' not found in map.")

    print("[INFO] exam_spelling completed")

def exam_multiple_choice(altdriver):
    """Clicks toggle by index across all questions using pre-collected toggle lists."""

    # --- Find all question templates ---
    questions = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')
    if not questions:
        questions = altdriver.find_objects(By.NAME, 'QuestionTemplate_RTL(Clone)')
    if not questions:
        questions = altdriver.find_objects(By.NAME, 'KL_QuestionTemplate(Clone)')
    if not questions:
        raise Exception("[ERROR] No question templates found in the scene.")

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
    time.sleep(1)
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    print(f"[INFO] Total sentences: {num_words}")

    for i in range(num_words):
        time.sleep(2)

        # --- Get the correct sentence (handle both normal and KL variants) ---
        sentence = None
        for name in ["ContextEchoOrderQuiz(Clone)", "KL_ContextEchoOrderQuiz(Clone)"]:
            objs = altdriver.find_objects(By.NAME, name)
            if objs:
                sentence = objs[0].get_component_property(
                    "com.kideo.learn.english.ContextBuilderQuiz",
                    "correctAnswer_",
                    "Assembly-CSharp"
                )
                break

        if not sentence:
            print(f"[WARN] No sentence found for question {i+1}")
            continue

        print(f"[INFO] Sentence to solve: {sentence}")
        words_in_order = [normalize_text(w) for w in sentence.split()]

        # --- Find clickable word objects ---
        text_objects = altdriver.find_objects(By.NAME, "Text")
        clickable_words = [(normalize_text(t.get_text()), t.get_parent()) for t in text_objects]
        word_map = {}
        for word, parent in clickable_words:
            word_map.setdefault(word, []).append(parent)

        # --- Click words in order ---
        click_counts = {}
        for word in words_in_order:
            click_counts[word] = click_counts.get(word, 0)
            if word in word_map and click_counts[word] < len(word_map[word]):
                word_map[word][click_counts[word]].click()
                click_counts[word] += 1
                print(f"[INFO] Clicked: {word}")
                time.sleep(0.7)
            else:
                print(f"[WARN] Could not find word: {word}")

        # --- Check and move to next ---
        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)
        if i < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1)

    print("\n[INFO] EchoOrder activity complete ✅")
def translation_wiz(altdriver):
    """Completes the Translation Wiz quiz by selecting words in correct translated order."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(num_words):
        time.sleep(2.5)
        try:
            sentence = altdriver.find_object(By.NAME, 'ContextTranslationWizQuiz(Clone)')\
                .get_component_property('com.kideo.learn.english.ContextBuilderQuiz', 'correctAnswer_', 'Assembly-CSharp')
        except:
            sentence = altdriver.find_object(By.NAME, 'KL_ContextTranslationWizQuiz(Clone)')\
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
    """Solves the GapGuru quiz by choosing the correct missing word."""
    time.sleep(1)

    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    print(f"[INFO] Total questions: {num_words}")

    for i in range(num_words):
        print(f"\n[STEP] Solving question {i+1}/{num_words}")

        # --- Find quiz object (support both versions) ---
        quiz_obj = None
        for name in ["ContextGapGuruQuiz(Clone)", "KL_ContextGapGuruQuiz(Clone)"]:
            objs = altdriver.find_objects(By.NAME, name)
            if objs:
                quiz_obj = objs[0]
                break
        if not quiz_obj:
            raise Exception("No quiz object found")

        # --- Get current context and correct word ---
        context = quiz_obj.get_component_property(
            "com.kideo.learn.english.ContextFillMissingWordQuiz",
            "currentContext_.context", "Assembly-CSharp"
        )
        correct_word = quiz_obj.get_component_property(
            "com.kideo.learn.english.ContextFillMissingWordQuiz",
            "missingWord_", "Assembly-CSharp"
        )
        print(f"[INFO] Sentence: {context}")
        print(f"[INFO] Correct word: {correct_word}")

        # --- Choose the correct option ---
        options = altdriver.find_objects(By.NAME, "QuizWordToggle(Clone)")
        for opt in options:
            word = opt.get_component_property(
                "com.kideo.learn.english.QuizWordToggle",
                "text.text", "Assembly-CSharp"
            )
            if normalize_text(word) == normalize_text(correct_word):
                opt.click()
                time.sleep(1.5)
                print(f"[INFO] Clicked: {word}")
                break

        # --- Confirm & go next ---
        click_by_name(altdriver, "QuizCheckButton")
        time.sleep(1)
        if i < num_words - 1:
            click_by_name(altdriver, "QuizNextButton")
            time.sleep(1.8)

    print("\n[INFO] GapGuru completed ✅")
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


def _safe_exists(altdriver, name: str) -> bool:
    try:
        altdriver.find_object(By.NAME, name)
        return True
    except Exception:
        return False


def _wait_until_exists(altdriver, name: str, timeout: float = 10.0, poll: float = 0.2) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _safe_exists(altdriver, name):
            return True
        time.sleep(poll)
    return False

def Cards(altdriver, lang="en-US", max_rounds=8):
    """Speaks all words from cards and exits when done."""
    init_audio()

    print("[INFO] Cards activity started")

    for _ in range(max_rounds):
        word_objs = altdriver.find_objects(By.NAME, "RTLTMPWordPanel")

        for word in word_objs:
            word_text = word.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
            word_text = str(word_text).strip()
            if not word_text:
                continue

            print(f"[INFO] Speaking card word: {word_text}")
            say(word_text, lang=lang, wait=True)
            time.sleep(0.35)  # small settle time for recognition pipeline

        # Try exit
        try:
            altdriver.find_object(By.NAME, "ExitButton").click()
            print("[INFO] Cards activity complete")
            return
        except:
            print("[INFO] Waiting for final feedback...")
            time.sleep(0.5)

    raise RuntimeError("[FAIL] Cards did not complete / ExitButton never appeared.")

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
    """Traces letters by swiping from FirstNumber to SecondNumber."""
    total = 8

    for i in range(total):
        time.sleep(6)

        # Find all FirstNumber and SecondNumber objects
        first_numbers = altdriver.find_objects(By.NAME, "FirstNumber")
        second_numbers = altdriver.find_objects(By.NAME, "SecondNumber")

        num_paths = len(first_numbers)
        print(f"[INFO] Found {num_paths} paths")

        # Find all Curve objects (may be less than num_paths)
        curves = altdriver.find_objects(By.NAME, "Curve")
        print(f"[INFO] Found {len(curves)} curves")

        curve_index = 0  # Track which curve we're using

        # Process each path (FirstNumber[i] to SecondNumber[i])
        for path_idx in range(num_paths):
            print(f"[INFO] Tracing from FirstNumber[{path_idx}] to SecondNumber[{path_idx}]")

            first_pos = first_numbers[path_idx].get_screen_position()
            second_pos = second_numbers[path_idx].get_screen_position()

            # Check if there's a curve available for this path
            # We need to determine if this path has a curve or is just a straight line
            # For now, let's check if a curve exists
            if curve_index < len(curves):
                # Try to use the curve
                curve = curves[curve_index]

                try:
                    # Get bezier points from the curve
                    bezier_points = curve.get_component_property(
                        'IndieStudio.EnglishTracingBook.Game.Curve',
                        'bezierPoints',
                        'Assembly-CSharp'
                    )

                    if bezier_points and len(bezier_points) > 0:
                        print(f"[INFO] Path {path_idx} has curve with {len(bezier_points)} bezier points")

                        # Get the curve's screen position and world position for conversion
                        curve_screen_x, curve_screen_y = curve.get_screen_position()
                        curve_world_x = curve.worldX
                        curve_world_y = curve.worldY

                        # Calculate screen positions for bezier points
                        screen_points = []
                        for point in bezier_points:
                            offset_x = point['x'] - curve_world_x
                            offset_y = point['y'] - curve_world_y
                            scale = 200
                            screen_x = curve_screen_x + (offset_x * scale)
                            screen_y = curve_screen_y + (offset_y * scale)
                            screen_points.append((screen_x, screen_y))

                        # Swipe point by point through the curve
                        for j in range(len(screen_points) - 1):
                            altdriver.swipe(screen_points[j], screen_points[j + 1], duration=0.05)

                        curve_index += 1  # Move to next curve
                    else:
                        # No bezier points, do straight line
                        print(f"[INFO] Path {path_idx} is a straight line (no bezier points)")
                        altdriver.swipe(first_pos, second_pos, duration=1)

                except Exception as e:
                    print(f"[INFO] Path {path_idx} is a straight line (no curve): {e}")
                    altdriver.swipe(first_pos, second_pos, duration=1)
            else:
                # No more curves available, do straight line
                print(f"[INFO] Path {path_idx} is a straight line (no curve available)")
                altdriver.swipe(first_pos, second_pos, duration=1)

            # Click at the end position (SecondNumber position) to lift finger
            altdriver.click(second_pos)

            print(f"[INFO] Completed path {path_idx}, finger lifted")

            # Wait 3 seconds before next path
            time.sleep(5)

        print(f"[INFO] Traced letter {i + 1}/{total}")

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
        time.sleep(3)
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
    time.sleep(3)
    total = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    for _ in range(total):
        time.sleep(2)
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
                time.sleep(1)
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

    # ✅ Step 1: Build the letters map once
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }
    print(f"[DEBUG] Available letters : {list(letters_map.keys())}")

    # ✅ Step 2: Iterate through each word
    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Get current target word
        current_word_obj = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        current_word_text = current_word_obj.get_component_property(
            'TMProWordPanel', 'Word.word', 'Assembly-CSharp'
        ).lower()
        print(f"[DEBUG] Target word: {current_word_text}")

        # Step 3: Use cached letters_map
        for letter in current_word_text:
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")

        # Wait for next round to load

#def crosswords2(altdriver): KLLLLL
    """Solve all crossword items based on ProgressText (click letters in reverse order)."""
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progresstext.split('/')[1])
    print(f"[INFO] Total words to solve: {number_of_words}")

    # ✅ Step 1: Build the letters map once
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }
    print(f"[DEBUG] Available letters: {list(letters_map.keys())}")

    # ✅ Step 2: Iterate through each word
    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Get current target word
        current_word_obj = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        current_word_text = current_word_obj.get_component_property(
            "TMProWordPanel", "Word.word", "Assembly-CSharp"
        ).lower()
        print(f"[DEBUG] Target word: {current_word_text}")

        # ✅ Step 3: Click letters in reverse order
        for letter in reversed(current_word_text):
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")

        # Wait before next word loads
        time.sleep(1)

    print("[INFO] Crosswords2 activity complete ✅")


from collections import Counter


def _as_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes"}


def _button_interactable(next_btn):
    try:
        return _as_bool(next_btn.get_component_property(
            "UnityEngine.UI.Button", "interactable", "UnityEngine.UI"
        ))
    except Exception:
        return getattr(next_btn, "enabled", False)


def solve_puzzles(altdriver):
    time.sleep(10)
    print("[INFO] Puzzle solver started...")
    altdriver.wait_for_object(By.NAME, "ProgressText", timeout=15)
    progress = altdriver.find_object(By.NAME, "ProgressText")
    manager = altdriver.find_object(By.NAME, "PuzzlesManager")

    total = int(progress.get_text().split("/")[1])
    print(f"[INFO] Total sentences: {total}")

    # ===== Timer Extension for Hard =====
    if total > 6:
        try:
            timer = altdriver.find_object(By.NAME, "LenearTimer")
            timer.set_component_property(
                "com.kideo.learn.english.LenearTimerScript",
                "timeLeft",
                "Assembly-CSharp",
                1700
            )
            print("[INFO] Timer extended to 1700 for hard level.")
        except Exception as e:
            print(f"[WARNING] Failed to set timer: {e}")

    # ===== Difficulty Ranges =====
    if total == 4:  # EASY
        group_ranges = [(42, 55), (28, 41), (14, 27), (0, 13)]
    elif total == 6:  # NORMAL
        group_ranges = [(70, 83), (56, 69), (42, 55),
                        (28, 41), (14, 27), (0, 13)]
    elif total > 6:  # HARD
        group_ranges = [
            (147, 167), (119, 139), (91, 111), (63, 83),
            (35, 55), (7, 27), (140, 160), (112, 132),
            (84, 104), (56, 76), (28, 48), (0, 20)
        ]
    else:
        group_ranges = [(0, 9999)]

    def read_pieces(target_words, start_idx, end_idx):
        freq = Counter(target_words)
        pieces = []
        for e in reversed(altdriver.get_all_elements()):
            if not e.name.isdigit():
                continue
            num = int(e.name)
            if num < start_idx or num > end_idx or not e.enabled:
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if freq.get(word, 0) > 0:
                pieces.append({"obj": e, "text": word})
                freq[word] -= 1
            if sum(freq.values()) == 0:
                break
        pieces.sort(key=lambda p: (-p["obj"].y, p["obj"].x))
        return pieces

    for i in range(total):
        print(f"\n--- Sentence {i+1}/{total} ---")
        time.sleep(0.5)

        target = manager.get_component_property(
            "com.kideo.learn.english.PuzzlesManager",
            "currentSentence_",
            "Assembly-CSharp"
        ).split()
        print("[TARGET]", " ".join(target))

        start_idx, end_idx = group_ranges[i] if i < len(group_ranges) else (0, 9999)

        while True:
            pieces = read_pieces(target, start_idx, end_idx)
            current = [p["text"] for p in pieces]
            print("[CURRENT]", " ".join(current))

            if current == target:
                print(f"[OK] Sentence solved.")
                break

            visited = set()

            for idx, want in enumerate(target):
                if idx >= len(pieces):
                    continue

                have = pieces[idx]["text"]
                if have == want:
                    visited.add(idx)
                    continue

                cand_idx = None
                for j in range(idx + 1, len(pieces)):
                    if pieces[j]["text"] != want:
                        continue
                    if j in visited:
                        continue
                    if j < len(target) and pieces[j]["text"] == target[j]:
                        continue
                    cand_idx = j
                    break

                if cand_idx is None:
                    continue

                visited.add(idx)
                print(f" [SWAP] '{have}' ↔ '{want}' (idx={idx}, j={cand_idx})")
                a_obj, b_obj = pieces[idx]["obj"], pieces[cand_idx]["obj"]

                try:
                    a_obj.click()
                    time.sleep(0.2)
                    b_obj.click()
                    time.sleep(1)
                except Exception:
                    print(" [WARNING] Swap click failed.")
                    continue

                pieces = read_pieces(target, start_idx, end_idx)
                current = [p["text"] for p in pieces]
                print("[AFTER SWAP]", " ".join(current))

                if idx < len(current) and current[idx] == want:
                    print(f" [VALID] '{want}' now correctly placed.")
                else:
                    print(f" [REVERT] '{want}' not correct — reverting.")
                    try:
                        a_obj.click()
                        time.sleep(1)
                        b_obj.click()
                        time.sleep(1)
                    except Exception:
                        print(" [WARNING] Revert failed.")

                    pieces = read_pieces(target, start_idx, end_idx)
                    current = [p["text"] for p in pieces]
                    print("[AFTER REVERT]", " ".join(current))

            time.sleep(0.5)

        print("[NEXT] Clicking next button...")
        try:
            time.sleep(1.5)
            next_btn = altdriver.find_object(By.NAME, "nextButton")
            next_btn.click()
        except Exception:
            print("[WARNING] Failed to click Next.")

        print("[WAIT] Waiting 5s for next sentence to load...")
        time.sleep(6.5)

    print("\n[SUCCESS] All puzzles processed!")
# Example of how to run the script:
# from altdriver import AltDriver
# alt_driver = AltDriver()
# solve_puzzles(alt_driver)


# ----------------------------------------------------------------
# Helper: swipe in an arc path for curved strokes
# ----------------------------------------------------------------
def swipe_arc(altdriver, start, end, center=None, steps=14, clockwise=True, duration=0.25):
    """Helper to trace an arc path when a stroke is curved."""
    if center is None:
        # default center roughly above midpoint
        center = ((start[0] + end[0]) // 2,
                  (start[1] + end[1]) // 2 - 120)

    def angle(p):
        return math.degrees(math.atan2(p[1] - center[1], p[0] - center[0]))

    start_angle = angle(start)
    end_angle   = angle(end)

    # Normalise rotation direction
    if clockwise and end_angle > start_angle:
        end_angle -= 360
    if not clockwise and end_angle < start_angle:
        end_angle += 360

    points = []
    for i in range(steps + 1):
        t = i / steps
        ang = math.radians(start_angle + (end_angle - start_angle) * t)
        x = center[0] + math.cos(ang) * abs(start[0] - center[0])
        y = center[1] + math.sin(ang) * abs(start[1] - center[1])
        points.append((x, y))

    for i in range(len(points) - 1):
        altdriver.swipe(points[i], points[i + 1], duration=duration)
        time.sleep(0.05)


# ----------------------------------------------------------------
# Inner routine: traces **one single letter** currently on screen
# ----------------------------------------------------------------
def trace_letter(altdriver, use_arc_for_index=None, arc_center=None):
    """
    Traces all strokes for the current letter already visible on screen.
    After each stroke it taps the SecondNumber to confirm/fill.
    """

    first_numbers = altdriver.find_objects(By.NAME, "FirstNumber")
    second_numbers = altdriver.find_objects(By.NAME, "SecondNumber")

    print(f"[INFO] Found {len(first_numbers)} FirstNumber and {len(second_numbers)} SecondNumber")

    total = min(len(first_numbers), len(second_numbers))

    for i in range(total):
        start_obj = first_numbers[i]
        end_obj   = second_numbers[i]

        start = start_obj.get_screen_position()
        end   = end_obj.get_screen_position()

        print(f"  Stroke {i+1}: {start_obj.name}[{i}] -> {end_obj.name}[{i}]")

        if use_arc_for_index is not None and i in use_arc_for_index:
            print("    Using arc swipe for this stroke.")
            swipe_arc(altdriver, start, end, center=arc_center, steps=16)
        else:
            print("    Using straight swipe.")
            altdriver.swipe(start, end, duration=1.0)

        time.sleep(0.3)

        print("    Clicking on second number to fill.")
        altdriver.tap(end)
        time.sleep(0.3)

    print("✅ Letter tracing finished.")


# ----------------------------------------------------------------
# Outer routine: handles the **whole Magic Trace activity**
#   e.g. 4 × 'N' (capital) then 4 × 'n' (small)
# ----------------------------------------------------------------
def magic_trace(altdriver):
    print("[INFO] Starting Magic Trace activity…")

    # read total rounds from ProgressText
    progress_obj = altdriver.find_object(By.NAME, "ProgressText")
    total_rounds = int(progress_obj.get_text().split("/")[1]) if progress_obj else 1
    print(f"[INFO] Total rounds to do: {total_rounds}")

    previous_letter = None

    for round_idx in range(total_rounds):
        # wait for next letter to appear
        time.sleep(8)

        # read which letter is now displayed (if available)
        try:
            current_letter = altdriver.find_object(By.NAME, "CurrentLetter").get_text()
        except:
            current_letter = "?"
        print(f"\n=== Round {round_idx+1}/{total_rounds}: Letter '{current_letter}' ===")

        # pause 5 s if we changed from capital to small or to a new letter
        if previous_letter and current_letter != previous_letter:
            print("[INFO] Detected letter change → waiting 5 sec for transition")
            time.sleep(10)
        previous_letter = current_letter

        # trace the strokes of this letter
        trace_letter(altdriver)

        print(f"[INFO] Finished round {round_idx+1}/{total_rounds}")
        time.sleep(1.0)   # short pause before next round

    print("\n✅ Magic Trace activity complete.")

def exams_image_to_audio(altdriver):

    """Automates matching audio meanings to word labels via swipe interaction."""
    time.sleep(1)

    # --- Find audio shapes ---
    audio_shapes = altdriver.find_objects(By.NAME, 'ImageAudioShape(Clone)')
    if not audio_shapes:
        audio_shapes = altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)')
    if not audio_shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")

    # --- Click each shape once to activate audio ---
    for shape in audio_shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    # --- Find word objects ---
    words = altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
    if not words:
        words = altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)')
    if not words:
        raise Exception("[ERROR] No word objects found.")

    # --- Collect data ---
    word_data = []
    for w in words:
        try:
            word_text = w.get_component_property(
                'com.kideo.learn.english.WordAudioObject', 'word', 'Assembly-CSharp'
            )
            word_pos = w.get_screen_position()
            word_data.append((word_text, w, word_pos))
        except Exception as e:
            print(f"[WARN] Failed to read word: {e}")

    shape_data = []
    for s in audio_shapes:
        try:
            shape_text = s.get_component_property(
                'com.kideo.learn.english.WordAudioShape', 'word', 'Assembly-CSharp'
            )
            x, y = s.get_screen_position()
            shape_data.append((shape_text, s, (x, y - 100)))  # small offset upwards
        except Exception as e:
            print(f"[WARN] Failed to read shape: {e}")

    # --- Swipe matches ---
    matched = 0
    for word_text, word_obj, word_pos in word_data:
        for shape_text, _, shape_pos in shape_data:
            if word_text == shape_text:
                altdriver.swipe(word_pos, shape_pos, 2.3)
                time.sleep(0.5)
                word_obj.click()
                matched += 1
                break

    print(f"[INFO] exams_audio_to_meaning completed ({matched}/{len(word_data)} matched).")


def exams_image_for_voices(altdriver):
    """Automates toggle click per question based on answerIndex and question index."""
    time.sleep(1)
    questions = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')

    for i, question in enumerate(questions):
        try:
            answer_index = int(question.get_component_property(
                'ImageWithAudioChoicesQuestion', 'answerIndex', 'Assembly-CSharp'))

            toggle_name = f'Toggle{answer_index}'
            toggles = altdriver.find_objects(By.NAME, toggle_name)

            if i < len(toggles):
                toggles[i].click()
                print(f"[INFO] Question {i}: Clicked {toggle_name}[{i}]")
            else:
                print(f"[WARN] {toggle_name}[{i}] not found. Skipping.")

            time.sleep(0.5)

        except Exception as e:
            print(f"[ERROR] Question {i}: {e}")

import re
import time

def rings(altdriver):
    """Solves RINGS: drag each structure onto the ring of letters it spells.

    The board is a hex grid of letters; each target word snakes through it as a
    connected ring. The right-hand panel holds one pre-shaped cover per word
    (CoverHolder-<word>), scrollable, with several off screen at any time.

    Three things had to be right, all learned the hard way against the build:

    1. Engaging the drag. A cover only lifts after a long press followed by
       GRADUAL nudges; one large jump does nothing and a plain vertical drag is
       swallowed by the panel's scroll view.
    2. Steering. Once lifted, the cover travels ~2x the finger delta, so it is
       steered closed-loop off its measured position with the gain re-estimated
       live. Dead reckoning overshoots straight off the screen.
    3. Cells are exclusive. Every word owns its own hexes, so a ring already
       under a placed structure must not be reused. That is re-measured from
       live state each round -- a remembered list goes stale when the round
       regenerates and ends up blocking the entire fresh grid.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    ADJ = 75.0            # px between neighbouring hexes
    TOL = 16.0            # px; close enough for the cover to snap
    NUDGES = (10, 25, 45, 70)
    SETTLE = 4.0          # the score animation lags - reading earlier lies
    REGEN_WAIT = 5.0      # past halfway the round spawns fresh structures
    VIS_LO, VIS_HI = 120, 500     # holder y-range that is actually reachable
    PANEL_X = 980         # right of this is the inventory, not the board

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def read_grid():
        """[(x, y, letter)] for every letter hex on the board."""
        out = []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name != "Letter":
                continue
            try:
                p = e.get_screen_position()
                t = (e.get_text() or "").strip().lower()
            except Exception:
                continue
            if t:
                out.append((p[0], p[1], t))
        return out

    def occupied():
        """Cells under an already-placed structure, measured from live state."""
        pts = []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            if p[0] <= PANEL_X and 0 < p[1] < 600:
                pts.append((p[0], p[1]))
        return pts

    def path_finder(cells, blocked_pts=()):
        blocked = set()
        for i, c in enumerate(cells):
            for q in blocked_pts:
                if ((c[0]-q[0])**2 + (c[1]-q[1])**2) ** 0.5 < 30:
                    blocked.add(i)
                    break

        nbr = {i: [] for i in range(len(cells))}
        for i, a in enumerate(cells):
            for j, b in enumerate(cells):
                if i != j and ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5 <= ADJ:
                    nbr[i].append(j)

        def find(word):
            w = "".join(word.split()).lower()

            def dfs(idx, pos, used):
                if pos == len(w):
                    return list(used)
                for k in nbr[idx]:
                    if k in used or k in blocked or cells[k][2] != w[pos]:
                        continue
                    used.append(k)
                    r = dfs(k, pos+1, used)
                    if r:
                        return r
                    used.pop()
                return None

            for i, c in enumerate(cells):
                if i in blocked or c[2] != w[0]:
                    continue
                r = dfs(i, 1, [i])
                if r:
                    return r
            return None

        return find

    def holders():
        """word -> screen position of its cover, e.g. CoverHolder-tasty.

        The holder name IS the word: a card reading "all the ___" still only
        places the blank, so the name must not be expanded to the phrase.
        """
        out = {}
        for e in altdriver.get_all_elements(enabled=False):
            if e.name.startswith("CoverHolder-"):
                try:
                    out[e.name.split("-", 1)[1].lower()] = e.get_screen_position()
                except Exception:
                    pass
        return out

    def cover_near(pt):
        best, bd = None, 1e9
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            dd = ((p[0]-pt[0])**2 + (p[1]-pt[1])**2) ** 0.5
            if dd < bd:
                best, bd = e, dd
        return best, bd

    def pos_of(cid):
        for e in altdriver.get_all_elements(enabled=True):
            if e.id == cid:
                try:
                    return e.get_screen_position()
                except Exception:
                    return None
        return None

    def scroll_inventory(dy=-150):
        """A vertical drag inside the panel scrolls it to reach hidden covers.

        Always the same direction: alternating merely oscillates between two
        positions and never cycles the list.
        """
        x, y0 = 1057, 430
        altdriver.move_mouse((x, y0), duration=0.15)
        finger = altdriver.begin_touch((x, y0))
        try:
            time.sleep(0.2)
            for i in range(1, 13):
                pt = (x, y0 + dy*i/12.0)
                altdriver.move_touch(finger, pt)
                altdriver.move_mouse(pt, duration=0.01)
                time.sleep(0.03)
            time.sleep(0.3)
        finally:
            altdriver.end_touch(finger)
        time.sleep(1.2)

    def place(holder_pos, target):
        cov, dist = cover_near(holder_pos)
        if cov is None or dist > 120:
            print(f"[warn] no cover at holder ({dist:.0f}px away)")
            return False
        cid = cov.id
        start = cov.get_screen_position()
        altdriver.move_mouse(start, duration=0.25)
        time.sleep(0.35)
        finger = [start[0], start[1]]
        touch = altdriver.begin_touch(tuple(finger))
        try:
            time.sleep(0.6)                       # long press to grab
            for n in NUDGES:                      # gradual nudges to engage
                finger[0] = start[0] - n
                altdriver.move_touch(touch, tuple(finger))
                altdriver.move_mouse(tuple(finger), duration=0.01)
                time.sleep(0.12)
            here = pos_of(cid)
            if here and abs(here[0]-start[0]) < 8 and abs(here[1]-start[1]) < 8:
                print("[warn] drag never engaged")
                return False

            gain = 2.0                            # cover moves ~2x the finger
            prev_f, prev_c = list(finger), here
            for _ in range(28):
                c = pos_of(cid)
                if not c:
                    break
                ex, ey = target[0]-c[0], target[1]-c[1]
                if (ex*ex + ey*ey) ** 0.5 <= TOL:
                    break
                if prev_c:
                    dfx, dcx = finger[0]-prev_f[0], c[0]-prev_c[0]
                    if abs(dfx) > 3 and abs(dcx) > 3:
                        g = abs(dcx/dfx)
                        if 0.3 < g < 6:
                            gain = 0.5*gain + 0.5*g
                prev_f, prev_c = list(finger), c
                finger[0] += (ex/gain) * 0.55
                finger[1] += (ey/gain) * 0.55
                altdriver.move_touch(touch, tuple(finger))
                altdriver.move_mouse(tuple(finger), duration=0.01)
                time.sleep(0.16)
            time.sleep(0.4)
        finally:
            altdriver.end_touch(touch)
        return True

    done, total = progress()
    print(f"[info] starting rings at {done}/{total}")
    failed, idle = {}, 0

    for _ in range(60):
        done, total = progress()
        if total and done >= total:
            print(f"[info] all {total} structures placed.")
            break

        cells = read_grid()
        busy = occupied()
        find = path_finder(cells, busy)
        hs = holders()

        cand = None
        for w, p in sorted(hs.items(), key=lambda kv: -kv[1][1]):
            if failed.get(w, 0) >= 2:
                continue
            if VIS_LO < p[1] < VIS_HI and find(w):
                cand = (w, p)
                break

        if not cand:
            idle += 1
            if idle > 24:
                print("[warn] nothing placeable — stopping.")
                break
            if idle % 3 == 0:
                scroll_inventory(-150)
            else:
                # the round generates fresh structures as it goes
                failed.clear()
                time.sleep(REGEN_WAIT)
            continue
        idle = 0

        word, holder_pos = cand
        ring = [cells[i] for i in find(word)]
        tx = sum(p[0] for p in ring) / len(ring)
        ty = sum(p[1] for p in ring) / len(ring)
        print(f"[act] {word}: ring of {len(ring)} cells at ({tx:.0f},{ty:.0f}), "
              f"{len(busy)} cells already covered")

        before = done
        if place(holder_pos, (tx, ty)):
            time.sleep(SETTLE)
            now, total = progress()
            if now > before:
                failed.pop(word, None)
                print(f"[info] progress {now}/{total}")
                if total and now >= total / 2.0:
                    time.sleep(REGEN_WAIT)     # new structures are spawning
            else:
                failed[word] = failed.get(word, 0) + 1
        else:
            failed[word] = failed.get(word, 0) + 1

    done, total = progress()
    print(f"[done] rings finished at {done}/{total}")


def pipes(altdriver):
    """Solves PIPES by dragging along each correct pipe path.

    The build exposes its own answer key: `PipesStructureHandler`
    .correctPathsAutomationInfo on Pipes_Hard_Panel gives, per sentence, the
    ordered `pipesNames` plus `pipesPositions` -- the segment endpoints in WORLD
    units ("x1,y1,x2,y2").

    Those world coordinates matter. Dragging between pipe *centres* cuts
    diagonally across empty space and the game ignores it; dragging through each
    segment's real start/end keeps the finger inside the pipe. World->screen is
    fitted live from the pipes on screen, so this is resolution independent.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    SH_C = "com.kideo.learn.english.Pipes.PipesStructureHandler"
    ASM = "Assembly-CSharp"
    STEPS = 15             # interpolation points per segment
    STEP_PAUSE = 0.02      # sec between move_touch calls

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def answer_key():
        """[{sentence, pipesNames, pipesPositions}, ...] straight from the game."""
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Pipes_Hard_Panel":
                continue
            try:
                v = e.get_component_property(SH_C, "correctPathsAutomationInfo", ASM)
                if v:
                    return v
            except Exception:
                pass
        return []

    def screen_pos(name):
        try:
            p = altdriver.find_object(By.NAME, name).get_screen_position()
            return (p[0], p[1])
        except Exception:
            return None

    def _fit(pairs):
        """Least-squares slope/intercept for a list of (world, screen) pairs."""
        n = len(pairs)
        mw = sum(p[0] for p in pairs) / n
        ms = sum(p[1] for p in pairs) / n
        num = sum((p[0] - mw) * (p[1] - ms) for p in pairs)
        den = sum((p[0] - mw) ** 2 for p in pairs) or 1e-9
        a = num / den
        return a, ms - a * mw

    def world_to_screen(key):
        """Fit the transform from the pipes currently on screen."""
        xs, ys = [], []
        for path in key:
            for name, seg in zip(path.get("pipesNames") or [],
                                 path.get("pipesPositions") or []):
                sp = screen_pos(name)
                if not sp:
                    continue
                try:
                    x1, y1, x2, y2 = [float(v) for v in seg.split(",")]
                except Exception:
                    continue
                xs.append(((x1 + x2) / 2.0, sp[0]))
                ys.append(((y1 + y2) / 2.0, sp[1]))
        if len(xs) < 2:
            return None
        ax, bx = _fit(xs)
        ay, by = _fit(ys)
        return lambda wx, wy: (ax * wx + bx, ay * wy + by)

    def drag(path, w2s):
        """Press at the path start, follow every segment, release."""
        way = []
        for seg in path.get("pipesPositions") or []:
            try:
                x1, y1, x2, y2 = [float(v) for v in seg.split(",")]
            except Exception:
                continue
            way.append(w2s(x1, y1))
            way.append(w2s(x2, y2))
        if len(way) < 2:
            return False
        finger = altdriver.begin_touch(way[0])
        try:
            time.sleep(0.25)
            for a, b in zip(way, way[1:]):
                for i in range(1, STEPS + 1):
                    altdriver.move_touch(finger, (a[0] + (b[0] - a[0]) * i / STEPS,
                                                  a[1] + (b[1] - a[1]) * i / STEPS))
                    time.sleep(STEP_PAUSE)
            time.sleep(0.25)
        finally:
            altdriver.end_touch(finger)
        return True

    done, total = progress()
    print("[info] starting pipes at %d/%d" % (done, total))
    stuck = 0

    for _ in range(60):
        done, total = progress()
        if total and done >= total:
            print("[info] all %d sentences solved." % total)
            break

        key = answer_key()
        if not key:
            stuck += 1
            if stuck > 8:
                print("[warn] no correct paths exposed — stopping.")
                break
            time.sleep(1.5)
            continue

        w2s = world_to_screen(key)
        if w2s is None:
            time.sleep(1.0)
            continue

        before = done
        for path in key:
            print("[act] %s" % (path.get("sentence") or "")[:60])
            try:
                drag(path, w2s)
            except Exception as e:
                print("[warn] drag failed: %s" % e)
            time.sleep(2.0)
            now, total = progress()
            if now != before:
                print("[info] progress %d/%d" % (now, total))
                before = now
                break          # the board reshuffles after a solve — re-read

        if before == done:
            stuck += 1
            if stuck > 8:
                print("[warn] no progress — stopping.")
                break
        else:
            stuck = 0

    done, total = progress()
    print("[done] pipes finished at %d/%d" % (done, total))


def brickout(altdriver):
    """Solves BRICKOUT: catch ONLY the required words, let the decoys pass.

    Unlike the other activities (which tap objects directly) this is a live
    arcade game. A ball breaks word-bricks and the words fall toward the paddle.
    Catching a word that is NOT in the target list costs a heart, so the paddle
    must intercept the needed words and actively stay clear of the rest.

    Movement uses short `press_key(duration=...)` bursts sized to the distance.
    A held key (`key_down`/`key_up`) was tried and is worse here: any slow poll
    overshoots and slams the paddle into the wall, whereas a burst self-limits.

    NOTE: the app must have OS focus while this runs — Unity pauses play mode
    when the window is in the background and the ball simply freezes.
    """
    from alttester import AltKeyCode

    ASM = "Assembly-CSharp"
    PADDLE_SPEED = 950.0   # px/sec, measured against the live build
    MAX_BURST = 0.22       # sec; keep bursts short so we re-read often
    DEADZONE = 35          # px; don't jitter when roughly aligned
    FALL_EPS = 4           # px; y must drop at least this much to count as falling
    SAFE_GAP = 260         # px of clearance to keep from a falling decoy
    BOARD_MIN, BOARD_MAX = 120, 1450   # px; playable range of the paddle

    def targets():
        """Words still listed as needed (collected ones leave the panel list)."""
        out = set()
        for e in altdriver.get_all_elements(enabled=True):
            if e.name == "WordPanel(Clone)":
                try:
                    w = e.get_component_property("WordPanel", "Word.word", ASM)
                    if w:
                        out.add(str(w).strip().lower())
                except Exception:
                    pass
        return out

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def paddle_x():
        try:
            return altdriver.find_object(By.NAME, "Paddle").get_screen_position()[0]
        except Exception:
            return None

    def move_to(px, tx):
        delta = tx - px
        if abs(delta) <= DEADZONE:
            return
        key = AltKeyCode.RightArrow if delta > 0 else AltKeyCode.LeftArrow
        try:
            altdriver.press_key(key, duration=min(abs(delta) / PADDLE_SPEED, MAX_BURST))
        except Exception:
            pass

    need = targets()
    done, total = progress()
    print("[info] start %d/%d | need(%d): %s" % (done, total, len(need), sorted(need)))

    last_done = done
    stalled = 0
    prev_word_y = {}       # object id -> last y, to tell falling from parked

    for _ in range(3000):
        done, total = progress()
        if total and done >= total:
            print("[info] all %d words collected." % total)
            break

        if done != last_done:
            need = targets()
            print("[info] progress %d/%d | remaining %d" % (done, total, len(need)))
            last_done, stalled = done, 0
        else:
            stalled += 1
            if stalled > 1500:
                print("[warn] stalled — stopping.")
                break

        px = paddle_x()
        if px is None:
            time.sleep(0.15)
            continue

        # --- find falling words -------------------------------------------
        # A word counts as falling only if its y is DECREASING. A fixed y
        # threshold does not work: the layout shifts between builds/resolutions
        # and the parked grid can sit below it, which made the paddle chase
        # static bricks (usually on the left) and abandon the ball.
        falling = []
        seen_y = {}
        try:
            for e in altdriver.get_all_elements(enabled=True):
                if e.name != "BrickWord":
                    continue
                try:
                    pos = e.get_screen_position()
                except Exception:
                    continue
                oid = getattr(e, "id", None)
                seen_y[oid] = pos[1]
                was = prev_word_y.get(oid)
                if was is None or pos[1] >= was - FALL_EPS:
                    continue                  # parked in the grid (or new)
                txt = ""
                try:
                    txt = (e.get_text() or "").strip().lower()
                except Exception:
                    pass
                if txt:
                    falling.append((pos[1], pos[0], txt))
        except Exception:
            pass
        prev_word_y = seen_y

        # Where is the ball? None while it respawns after a lost heart.
        ball_x = None
        try:
            ball_x = altdriver.find_object(By.NAME, "Ball").get_screen_position()[0]
        except Exception:
            pass

        if falling:
            falling.sort()                    # lowest y == closest to the paddle
            y, x, word = falling[0]
            if word in need:
                move_to(px, x)                # CATCH it
            elif abs(x - px) < SAFE_GAP:
                # Decoy heading for us. Never dodge while the ball is missing:
                # that is how the paddle used to get stranded at a wall after a
                # lost heart and then drop every remaining one.
                if ball_x is not None:
                    # Step just clear of the decoy rather than running to the
                    # wall, and prefer the side that keeps us nearer the ball.
                    step = SAFE_GAP + 40
                    spots = [max(BOARD_MIN, min(BOARD_MAX, px - step)),
                             max(BOARD_MIN, min(BOARD_MAX, px + step))]
                    safe = [s for s in spots if abs(s - x) >= SAFE_GAP]
                    if safe:
                        move_to(px, min(safe, key=lambda s: abs(s - ball_x)))
            continue

        # nothing falling -> keep the ball alive so more bricks get broken
        if ball_x is not None:
            move_to(px, ball_x)
        else:
            time.sleep(0.1)

    done, total = progress()
    print("[done] finished at %d/%d" % (done, total))



def turtle_island(altdriver):
    def detect_rtl():
        """Solve direction comes from the WORD'S SCRIPT, not from an object name.

        RTLTMPWordPanel is the TMP panel that *supports* RTL; it exists in both
        VocaTooki and Kideo Land regardless of language, so its mere presence is
        not evidence the word is Hebrew/Arabic.
        """
        try:
            panel = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        except Exception:
            return False
        for comp, prop in (("TMProWordPanel", "Word.word"), ("TMProWordPanel", "Text")):
            try:
                text = panel.get_component_property(comp, prop, "Assembly-CSharp")
                if text and str(text).strip():
                    return is_rtl(str(text))
            except Exception:
                continue
        try:
            return is_rtl(panel.get_text() or "")
        except Exception:
            return False

    def parse_true_order(true_raw):
        """
        supports:
          - "3"
          - "[1, 2]"
          - "System.Int32[] { 1, 2 }"
          - any string containing integers
        returns:
          - int if single
          - list[int] if multiple
          - None if missing
        """
        if true_raw is None:
            return None
        s = str(true_raw).strip()
        if s == "" or s.lower() == "null":
            return None

        nums = [int(n) for n in re.findall(r"-?\d+", s)]
        if not nums:
            return None
        return nums if len(nums) > 1 else nums[0]

    def as_allowed_set(true_order):
        if true_order is None:
            return set()
        if isinstance(true_order, (list, tuple, set)):
            return set(int(x) for x in true_order)
        try:
            return {int(true_order)}
        except:
            return set()

    def dist_to_allowed(pos, allowed):
        if not allowed:
            return 999999
        return min(abs(pos - a) for a in allowed)

    print("[info] starting turtle island activity...")

    # get total words
    progress_obj = altdriver.find_object(By.NAME, "ProgressText")
    total = int(progress_obj.get_text().split('/')[1])
    print(f"[info] total words to solve: {total}")

    # main word loop
    for word_i in range(total):
        print(f"\n====== solving word {word_i + 1}/{total} ======")
        time.sleep(2)

        # Re-read per word: the lesson's language decides the solve direction.
        is_rtl_word = detect_rtl()
        print(f"[info] direction: {'RTL (Hebrew/Arabic)' if is_rtl_word else 'LTR (English)'}")

        # remove false-letter turtles
        all_objs = altdriver.get_all_elements()
        turtles = [t for t in all_objs if t.name.startswith("turtle_") and t.name.replace("turtle_", "").isdigit()]

        for t in turtles:
            try:
                true_raw = t.get_component_property(
                    "com.kideo.learn.english.TurtleScript",
                    "turtleLetter.trueOrders", "Assembly-CSharp"
                )
                if true_raw is None or str(true_raw).strip().lower() == "null":
                    print(f"[action] removing {t.name} (false letter)")
                    t.tap()
                    time.sleep(2)
            except:
                pass

        # swap loop
        MAX_SWAPS = 80  # a bit higher for harder/double-letter cases

        for _ in range(MAX_SWAPS):
            # refresh turtles
            all_objs = altdriver.get_all_elements()
            turtles = [t for t in all_objs if t.name.startswith("turtle_") and t.name.replace("turtle_", "").isdigit()]
            if not turtles:
                break

            # build info list with visual positions
            info_list = []
            for t in turtles:
                # true orders -> allowed set
                try:
                    true_raw = t.get_component_property(
                        "com.kideo.learn.english.TurtleScript",
                        "turtleLetter.trueOrders", "Assembly-CSharp"
                    )
                    true_order = parse_true_order(true_raw)
                except:
                    true_order = None

                allowed = as_allowed_set(true_order)

                # current x -> visual index
                try:
                    pos = t.get_screen_position()
                    x = pos["x"] if isinstance(pos, dict) else getattr(pos, "x", pos[0])
                except:
                    x = 999999

                info_list.append({
                    "obj": t,
                    "name": t.name,
                    "allowed": allowed,
                    "x": x,
                })

            # sort by x => visual index
            info_list.sort(key=lambda c: c["x"])

            # RTL (Hebrew/Arabic): reverse visual indices (position 0 is rightmost)
            if is_rtl_word:
                for i, info in enumerate(info_list):
                    info["visual"] = len(info_list) - 1 - i
                    info["correct"] = (info["visual"] in info["allowed"]) if info["allowed"] else False
            else:
                # LTR (English): normal left-to-right indexing
                for i, info in enumerate(info_list):
                    info["visual"] = i
                    info["correct"] = (i in info["allowed"]) if info["allowed"] else False

            # if all turtles with known allowed sets are correct -> done
            wrongs = [i for i in info_list if i["allowed"] and not i["correct"]]
            if not wrongs:
                print("[info] all turtles in correct order.")
                break

            # pick first wrong turtle
            wrong = wrongs[0]

            # choose best swap candidate:
            # 1) maximize correctness delta for the two swapped turtles
            # 2) if no improvement, minimize wrong distance to allowed after swap
            best = None
            best_delta = -999999

            a_vis = wrong["visual"]
            a_allowed = wrong["allowed"]
            a_correct_before = a_vis in a_allowed

            for cand in info_list:
                if cand["name"] == wrong["name"]:
                    continue

                b_vis = cand["visual"]
                b_allowed = cand["allowed"]

                b_correct_before = (b_vis in b_allowed) if b_allowed else False

                a_correct_after = (b_vis in a_allowed)
                b_correct_after = (a_vis in b_allowed) if b_allowed else b_correct_before

                delta = (int(a_correct_after) + int(b_correct_after)) - (int(a_correct_before) + int(b_correct_before))

                if delta > best_delta:
                    best_delta = delta
                    best = cand

            # if we found no candidate (shouldn't happen), break
            if best is None:
                print("[warn] no swap candidate found.")
                break

            # if swap doesn't improve correctness, do a "closest" swap to escape duplicates deadlocks
            if best_delta <= 0:
                best = min(
                    (c for c in info_list if c["name"] != wrong["name"]),
                    key=lambda c: dist_to_allowed(c["visual"], wrong["allowed"])
                )
                print("[warn] no improving swap found, using fallback swap (duplicate letters case).")

            print(
                f"[swap] {wrong['name']} (pos={wrong['visual']}, allowed={sorted(list(wrong['allowed']))}) "
                f"↔ {best['name']} (pos={best['visual']}, allowed={sorted(list(best['allowed'])) if best['allowed'] else []})"
            )

            # perform swap
            try:
                start = wrong["obj"].get_screen_position()
                end = best["obj"].get_screen_position()
                altdriver.swipe(start, end, 0.7)
                time.sleep(1.5)
            except Exception as e:
                print(f"[error] swap failed: {e}")
                time.sleep(1.5)

        print("[info] word completed.\n")

    print("\n✔✔✔ turtle island completed ✔✔✔")

def wordle(altdriver):
    # 1️⃣ Read target word from Gameplay Manager
    gm = altdriver.find_object(By.NAME, "Gameplay Manager")
    word = gm.get_component_property(
        "KaelmixStudioGameAssets.TemplateWordGuess.GameplayManager",
        "word",
        "Assembly-CSharp"
    ).upper()

    print(f"[INFO] Target word: {word}")

    # 2️⃣ Type each character by finding Key(<letter>)
    for index, letter in enumerate(word):
        key_name = f"Key ({letter})"   # 🟢 Construct object name dynamically

        print(f"[INFO] Clicking letter {index+1}/{len(word)}: {letter} -> {key_name}")

        key_obj = altdriver.find_object(By.NAME, key_name)
        key_obj.tap()  # 👈 Click the key

        time.sleep(0.2)  # ⏱️ Small delay for realism

    # 3️⃣ Press ENTER
    enter_btn = altdriver.find_object(By.NAME, "Enter")
    enter_btn.tap()
    print("[INFO] Submitted the word successfully!")




def word_connect(altdriver, words=("HIT", "GET", "EIGHTY", "THEY", "EIGHT"),card_name="WordsConnectCard_4 Variant(Clone)",sleep_after_word=0.25):

    print("[INFO] word_connect: Fetching cards...")
    cards = altdriver.find_objects(By.NAME, card_name)
    print(f"[INFO] Found {len(cards)} cards")

    # Build: letter -> [card objects]
    cards_by_letter = {}
    for idx, card in enumerate(cards):
        # IMPORTANT: no ".//*" here ('.' breaks PATH parsing); use "//Letter"
        letter_obj = card.find_object_from_object(By.PATH, "//Letter")  #
        letter = letter_obj.get_text().strip().upper()
        print(f"[INFO] Card[{idx}] = {letter}")
        cards_by_letter.setdefault(letter, []).append(card)

    print(f"[INFO] Available letters: {sorted(cards_by_letter.keys())}")

    # Swipe each target word
    for raw_word in words:
        word = raw_word.strip().upper()
        if not word:
            continue

        # For safety, allow repeated letters in a word by "consuming" card instances
        pool = {k: v[:] for k, v in cards_by_letter.items()}

        positions = []
        for ch in word:
            if ch not in pool or not pool[ch]:
                raise Exception(f"[ERROR] Missing letter '{ch}' on cards. Word='{word}'")

            card = pool[ch].pop(0)
            positions.append(card.get_screen_position())

        duration = max(4, 1.7 * len(positions))
        print(f"[INFO] Swiping '{word}' with {len(positions)} points, duration={duration}")

        altdriver.multipoint_swipe(positions, duration=duration, wait=True)  #
        time.sleep(sleep_after_word)


def crosswords(altdriver):

    # Get activity and matrix size
    activity = altdriver.find_object(By.NAME, 'CrosswordActivity')
    number_of_columns = activity.get_component_property(
        'com.kideo.learn.english.CrosswordActivityManager',
        'numberOfColumns',
        'Assembly-CSharp'
    )
    number_of_rows = activity.get_component_property(
        'com.kideo.learn.english.CrosswordActivityManager',
        'numberOfRows',
        'Assembly-CSharp'
    )

    # Use the actual row/column values from properties
    matrix_size = number_of_columns  # Assuming square matrix, or use max(number_of_columns, number_of_rows)

    print(f"Matrix size: {number_of_rows}x{number_of_columns}")

    # Initialize empty matrix and letter panel mapping
    matrix = [['empty' for _ in range(number_of_columns)] for _ in range(number_of_rows)]
    letter_panels = {}
    letter_objects = {}  # Store actual AltDriver objects for swiping

    # Get all letter panels
    texts = altdriver.find_objects(By.NAME, 'Text - RTLTMP')

    for text in texts:
        parent = text.get_parent()
        parent_name = parent.name
        letter = text.get_text()

        # Only process LetterPanel objects with valid letters
        if 'LetterPanel' in parent_name and letter.strip():
            # Parse position from parent name
            position = None
            if parent_name == 'LetterPanel':
                position = 0
            else:
                match = re.match(r'LetterPanel \((\d+)\)(?:_(\d+))?', parent_name)
                if match:
                    base_num = int(match.group(1))
                    offset = int(match.group(2)) if match.group(2) else 0
                    position = base_num + offset

            # Place letter in matrix and save panel info
            if position is not None:
                row = position // number_of_columns
                col = position % number_of_columns
                if row < number_of_rows and col < number_of_columns:
                    matrix[row][col] = letter
                    letter_panels[position] = {
                        'letter': letter,
                        'panel_name': parent_name,
                        'row': row,
                        'col': col,
                        'position': position,
                        'object': parent
                    }
                    letter_objects[(row, col)] = parent

    # Print the matrix
    print("\nCrossword Matrix:")
    print("-" * (number_of_columns * 8))
    for row in matrix:
        print(" ".join(f"{cell:>6}" for cell in row))
    print("-" * (number_of_columns * 8))

    # Get words to find
    words_to_find_panel = altdriver.find_object(By.NAME, 'WordsToFindPanel')
    words_to_find_list = words_to_find_panel.get_component_property(
        'com.kideo.learn.english.CrossWordToFindManager',
        'cleanedWordsList_',
        'Assembly-CSharp'
    )

    print(f"\nWords to find: {words_to_find_list}")

    # Define all 8 directions
    directions = {
        'horizontal': (0, 1),
        'vertical': (1, 0),
        'diagonal-down-right': (1, 1),
        'diagonal-down-left': (1, -1),
        'horizontal-reverse': (0, -1),
        'vertical-reverse': (-1, 0),
        'diagonal-up-right': (-1, 1),
        'diagonal-up-left': (-1, -1)
    }

    found_words = []

    # Find and solve each word
    for word in words_to_find_list:
        word_lower = word.lower()
        word_len = len(word)
        word_found = False

        # Search in all positions
        for row in range(number_of_rows):
            if word_found:
                break
            for col in range(number_of_columns):
                if word_found:
                    break

                # Try all directions
                for dir_name, (dr, dc) in directions.items():
                    # Check if word fits in the matrix
                    end_row = row + dr * (word_len - 1)
                    end_col = col + dc * (word_len - 1)

                    if end_row < 0 or end_row >= number_of_rows or end_col < 0 or end_col >= number_of_columns:
                        continue

                    # Check each letter
                    match = True
                    for i, letter in enumerate(word_lower):
                        curr_row = row + dr * i
                        curr_col = col + dc * i
                        cell_value = matrix[curr_row][curr_col]

                        if cell_value == 'empty' or cell_value.lower() != letter:
                            match = False
                            break

                    # If word found, swipe it
                    if match:
                        print(f"Found '{word}' at ({row},{col}) going {dir_name}")

                        start_obj = letter_objects.get((row, col))
                        end_obj = letter_objects.get((end_row, end_col))

                        if start_obj and end_obj:
                            try:
                                altdriver.swipe(
                                    start=start_obj.get_screen_position(),
                                    end=end_obj.get_screen_position(),
                                    duration=0.5
                                )
                                print(f"✓ Swiped '{word}' successfully")

                                found_words.append({
                                    'word': word,
                                    'start': (row, col),
                                    'end': (end_row, end_col),
                                    'direction': dir_name
                                })

                                # Sleep 2 seconds after finding a word
                                time.sleep(2)

                            except Exception as e:
                                print(f"✗ Error swiping '{word}': {e}")

                        word_found = True
                        break

    print(f"\n✓ Solved {len(found_words)} out of {len(words_to_find_list)} words")

    return {
        'matrix': matrix,
        'letter_panels': letter_panels,
        'matrix_size': (number_of_rows, number_of_columns),
        'words_to_find': words_to_find_list,
        'found_words': found_words
    }