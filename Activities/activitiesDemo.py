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

def _read_matchables(objects, component=None, lift=0):
    """``[(text, object, position)]`` for one side of a matching exam.

    ``component`` reads the word off a component property; without it the
    printed label is used. ``lift`` raises the target point, which is how these
    exams have always aimed at a shape's drop area.
    """
    out = []
    for obj in objects or []:
        try:
            text = (obj.get_component_property(component, 'word', 'Assembly-CSharp')
                    if component else obj.get_text())
            x, y = obj.get_screen_position()
            out.append(((text or "").strip(), obj, (x, y - lift)))
        except Exception:                            # noqa: BLE001 - skip unreadable
            continue
    return out


def solve_match_exam(altdriver, read_board, label, attempts=3, match=None,
                     tolerance=(60, 80), duration=2.3):
    """Drag each word onto the shape that wants it, and PROVE each one landed.

    Shared by every match-and-swipe exam page. ``read_board()`` returns
    ``(words, shapes)`` READ FRESH FROM THE APP each time — a screen position
    captured before a swipe describes where the word WAS, so a second pass that
    reuses it would drag from empty space.

    Why the verification matters: the app refuses to advance or submit a page
    that is not fully answered. A solver that swipes once and prints "completed"
    therefore does not fail — it strands the whole exam later, on a page nobody
    can leave. One unplaced word ("black", seen live) is enough.

    Returns the list of words it could not place (empty means all placed).
    """
    same = match or (lambda w, s: (w or "").strip().lower() == (s or "").strip().lower())
    tol_x, tol_y = tolerance

    def placed(word_pos, shape_pos):
        return (abs(word_pos[0] - shape_pos[0]) < tol_x
                and abs(word_pos[1] - shape_pos[1]) < tol_y)

    def outstanding(words, shapes):
        """Words that are not sitting on the shape that wants them."""
        left, used = [], set()
        for text, obj, pos in words:
            index = next((i for i, (s_text, _o, _p) in enumerate(shapes)
                          if i not in used and same(text, s_text)), None)
            if index is None:
                continue                             # no shape wants this word
            used.add(index)
            if not placed(pos, shapes[index][2]):
                left.append((text, obj, pos, shapes[index][2]))
        return left

    left = []
    for attempt in range(1, max(1, attempts) + 1):
        words, shapes = read_board()
        if not words:
            raise Exception(f"Not a {label} exam")
        pending = outstanding(words, shapes)
        if not pending:
            break
        for text, obj, word_pos, target in pending:
            altdriver.swipe(word_pos, target, duration)
            time.sleep(0.4)
            try:
                obj.click()
            except Exception:                        # noqa: BLE001
                pass
        time.sleep(0.8)
        words, shapes = read_board()                 # which of them actually landed?
        left = [t for t, _o, _p, _g in outstanding(words, shapes)]
        if not left:
            break
        print(f"[WARN] {label}: {left} not placed (attempt {attempt})")

    if left:
        print(f"[WARN] {label} finished with {left} unplaced")
    else:
        print(f"[INFO] {label} completed")
    return left


def exams_word_to_meaning(altdriver, attempts=3):
    """Match words to their meaning shapes by swiping, verifying each one."""
    time.sleep(1)

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordMeaningObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordMeaningObject(Clone)'))
        shapes = altdriver.find_objects(By.NAME, 'WordMeaningShape(Clone)')
        return (_read_matchables(words),
                _read_matchables(shapes, 'com.kideo.learn.english.WordMeaningShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_word_to_meaning", attempts=attempts)


def exams_word_to_image(altdriver, attempts=3):
    """Match words to images by swiping, verifying each one."""
    time.sleep(1)

    def read_board():
        words = altdriver.find_objects(By.NAME, 'MatchWordText(Clone)')
        shapes = altdriver.find_objects(By.NAME, 'MatchShapeImage(Clone)')
        return (_read_matchables(words),
                _read_matchables(shapes, 'com.kideo.learn.english.MatchTestShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_word_to_image", attempts=attempts)


def exams_3rd_letter_to_word_image_match(altdriver, attempts=3):
    """Match a letter shape to a word that contains it ('G' -> 'giraffe')."""
    time.sleep(1)

    def read_board():
        words = altdriver.find_objects(By.NAME, 'LetterWordText Variant(Clone)')
        shapes = altdriver.find_objects(By.NAME, 'LetterShapeImage Variant(Clone)')
        if not words or not shapes:
            raise Exception("Missing words or shapes for letter-to-word matching")
        return (_read_matchables(words, 'com.kideo.learn.english.MatchTestWord'),
                _read_matchables(shapes, 'com.kideo.learn.english.MatchTestShape', lift=100))

    # The pairing rule is CONTAINMENT here, not equality: the shape carries a
    # letter and the word is the one spelled with it.
    solve_match_exam(altdriver, read_board, "letter-to-word image matching",
                     attempts=attempts,
                     match=lambda w, s: bool(s) and (s or "").strip().lower()
                     in (w or "").strip().lower())


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


def exams_audio_to_meaning(altdriver, attempts=3):
    """Match audio meanings to word labels by swiping, verifying each one."""
    time.sleep(1)

    def audio_shapes():
        return (altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'WordAudioShape_RTL(Clone)'))

    shapes = audio_shapes()
    if not shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")
    # Each shape has to be played once before it can be matched.
    for shape in shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'WordAudioObject_RTL(Clone)'))
        if not words:
            raise Exception("[ERROR] No word objects found.")
        return (_read_matchables(words, 'com.kideo.learn.english.WordAudioObject'),
                _read_matchables(audio_shapes(),
                                 'com.kideo.learn.english.WordAudioShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_audio_to_meaning", attempts=attempts)


def _spelling_bare_letter(text):
    """The base letter, with any combining marks removed.

    `missingLetters` carries the word's diacritics (Hebrew 'mem + hiriq' is two
    code points), but the on-screen keyboard offers only bare letters, so looking
    a pointed letter up straight misses every time. Worse than missing: the game
    fills the first empty slot whatever key is pressed, so the few letters that DO
    match land in the leading slots and the word reads back reversed.

    Pressing the bare letter is what the game expects -- IsWordCompleted() accepts
    a slot matching either wordLetters[i] or RemoveDiacritics(word)[i]. Used only
    as a FALLBACK after an exact match fails, so a keyboard that really does offer
    accented tiles keeps working, and English (no combining marks) is untouched.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


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
                tile = letters_map.get(letter)
                if tile is None:
                    bare = _spelling_bare_letter(letter).lower()
                    tile = letters_map.get(bare)
                if tile is not None:
                    tile.click()
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


def _signs_entry(altdriver, max_rounds=12, round_timeout=25):
    """Letters Sorting ("signs"): solve whichever round is currently open.

    By default this is a SOLVER ONLY — it does not navigate. It works out which
    round it has been dropped into and plays it; getting into the activity (and
    back out again) is the caller's job, so it composes with
    solve_activity_in_level, the lesson range runs and anything else that drives
    the map.

    Pass ``play_all_modes=True`` to play the whole activity in one call: after
    an entry is finished it goes back ONE screen to the activity selection,
    re-enters this same activity and plays the next mode, up to three entries.
    That is opt-in precisely because the callers above do their own navigation.

    The activity has three modes, and they do NOT follow each other in place:
    the activity has to be left and re-entered to get the next one. So this
    plays the board(s) of the current entry and returns.

        listen & find                signs show letters, either case counts
        find capital / find small    one entry, split into TWO boards — the
                                     second appears in place, so it is played
                                     without re-entering
        find images                  signs show pictures; the correct ones are
                                     the letter's own words, matched BY ID
                                     ("kite" belongs to "I" by sound, which no
                                     spelling rule would catch)

    Nothing is read once: every board re-reads its target and its nine signs,
    and the loop follows the activity's progress counter ("0/5") rather than any
    fixed count. A sign takes TWO clicks — the first turns it round, the second
    selects it — and each sign is addressed by its own path
    (//GO-Monkey_i//Bn-Local_Root) so one can never be mistaken for another.
    """
    def target():
        """(letter, word_ids) for the current board.

        The letter drives the letter rounds. ``word_ids`` drives the images
        round, where the signs show PICTURES: the letter's data lists the ids of
        the words that belong to it, so the right signs are matched by id rather
        than by spelling — "kite" belongs to "I" by sound, and no string rule
        would ever catch that.
        """
        try:
            wp = altdriver.find_object(By.NAME, "WordPanel")
            word = wp.get_component_property("WordPanel", "Word", "Assembly-CSharp") or {}
            level = word.get("levelData") or {}
            letter = (level.get("letter") or "").strip().lower()
            ids = [int(i) for i in (level.get("words") or [])]
            return letter, ids
        except Exception as e:
            print(f"[ERROR] could not read the target: {e}")
            return "", []

    def signs_on_board():
        """[(name, shown, word_id)] for the nine signs, read fresh.

        ``shown`` is the letter in the letter rounds and the word in the images
        round; ``word_id`` identifies the word behind the picture.
        """
        out = []
        for i in range(9):
            name = "GO-Monkey" if i == 0 else f"GO-Monkey_{i}"
            try:
                monkey = altdriver.find_object(By.NAME, name)
                alphabet = monkey.get_component_property(
                    "SortingMonkeyController", "alphabet", "Assembly-CSharp") or {}
            except Exception:
                continue
            # A LETTER sign carries `letter`; a PICTURE sign carries a word and
            # no letter. `word` is not reliable for letter signs — it comes back
            # empty in some rounds — so the letter field decides which it is.
            letter = str(alphabet.get("letter") or "").strip()
            shown = letter or str(alphabet.get("word") or "").strip()
            try:
                obj_id = int(alphabet.get("id"))
            except (TypeError, ValueError):
                obj_id = None
            out.append((name, shown, obj_id, bool(letter)))
        return out

    def diagnose(board, word_ids):
        """Name the round we are in, from what is actually on the board.

        The four round objects (ListenFindRound / FindLowerCase /
        FindUpperCase / FindImages) all report enabled=True at once, so they
        cannot be asked. What distinguishes them is the board:

        * signs showing WORDS whose ids belong to the letter -> find images
        * signs showing LETTERS with an AudioButton on screen  -> listen & find
        * signs showing LETTERS with no audio                  -> the find
          capital / find small round (which half it is cannot be told apart
          from the data — and does not matter, because each half only shows the
          case it asks for, so matching on the letter is right either way)
        """
        if any(not is_letter for _n, _w, _i, is_letter in board):
            return "find images (matching by word id)"
        try:
            has_audio = bool(altdriver.find_objects(By.NAME, "AudioButton"))
        except Exception:
            has_audio = False
        if has_audio:
            return "listen & find (either case counts)"
        return "find capital / find small letters"

    def click_sign(name):
        """Turn the sign, then select it."""
        path = f"//{name}//Bn-Local_Root"
        try:
            altdriver.find_object(By.PATH, path).click()   # turns it round
        except Exception as e:
            print(f"[WARN] {name}: first click failed: {e}")
            return False
        time.sleep(1.2)
        try:
            altdriver.find_object(By.PATH, path).click()   # selects it
        except Exception as e:
            print(f"[WARN] {name}: second click failed: {e}")
            return False
        time.sleep(0.8)
        return True

    def activity_open():
        """Is the Letters Sorting board still on screen?

        This used to compare the scene name against "LettersSorting", which is
        the VOCA TOOKI scene. Kideo Land runs the very same activity inside
        `KideoLandOldActivityScene`, so the check failed on the first pass and
        the solver returned "0 boards played" without ever reading a board --
        every object it needs was present and correct.

        Asking whether the board itself is there works for both apps and for any
        future scene name. `WordPanel` is the target panel this solver already
        depends on in `target()`, so if it is gone the activity is gone.
        """
        try:
            return bool(altdriver.find_objects(By.NAME, "WordPanel"))
        except Exception:
            return True      # unreadable -> assume open; the timeout still bounds the wait

    def wait_for_round(timeout=30):
        """Wait for a round to be ready.

        Returns (letter, done, total), or None when this entry has no more
        rounds. Two different things end a round:

        * The find-upper/lower mode is split in half — when the first half is
          done a SECOND board appears in the same entry, so a completed
          progress bar is not necessarily the end.
        * The modes themselves (listen & find -> upper/lower -> images) do NOT
          follow each other in place: the activity has to be left and re-entered
          from the activity selection screen to get the next one. So once a
          board is finished and no new one appears, this returns and the caller
          re-enters for the next mode.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not activity_open():
                return None                         # activity closed
            letter, word_ids = target()
            done, total = read_activity_progress(altdriver)
            if letter and total and done < total:
                # The counter and the target appear BEFORE the signs finish
                # populating — a board read too early looks like nine blank
                # signs and nothing to click.
                if any(shown for _n, shown, _o, _l in signs_on_board()):
                    return letter, word_ids, done, total
            time.sleep(1.5)
        return None

    print("[INFO] Signs activity: starting")
    rounds_played = 0

    for rnd in range(1, max_rounds + 1):
        # Generous wait for the FIRST board (the activity is still loading),
        # short afterwards: a second board only appears for the split
        # upper/lower mode, otherwise this entry is done.
        ready = wait_for_round(timeout=30 if rnd == 1 else 10)
        if ready is None:
            break
        letter, word_ids, done, total = ready

        board = signs_on_board()
        print(f"[INFO] round {rnd}: {diagnose(board, word_ids)}")
        # A LETTER sign is correct when it shows the target letter; a PICTURE
        # sign when its word is one of the letter's words. The two are kept
        # apart deliberately: word ids and letter ids overlap (the word "red"
        # and the letter "I" are both id 10), so matching on id alone would
        # click the wrong sign in the images round.
        matches = [n for n, shown, oid, is_letter in board
                   if (shown.lower() == letter if is_letter
                       else (oid is not None and oid in word_ids))]
        print(f"[INFO] round {rnd}: target '{letter}' ({done}/{total}) — "
              f"signs {[shown for _n, shown, _o, _l in board]} -> clicking {len(matches)}")
        if not matches:
            print("[WARN] no sign carries the target letter; stopping")
            break

        for name in matches:
            click_sign(name)

        # Wait for this round to be counted complete.
        deadline = time.time() + round_timeout
        while time.time() < deadline:
            done, total = read_activity_progress(altdriver)
            if total and done >= total:
                break
            time.sleep(1.5)
        rounds_played += 1
        print(f"[INFO] round {rnd} finished at {done}/{total}")

    print(f"[INFO] Signs entry complete — {rounds_played} board(s) played")
    return rounds_played


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

# --- CROSSWORD2 board reading -------------------------------------------------
# Crossword words INTERSECT: a cell can already be filled by an earlier word.
# The game fills the first cell whose text component is inactive --
#
#   for (; currentPos < TextLengthExcludingDiacritics(word); currentPos++)
#       if (!wordCards[word][currentPos].GetComponentInChildren<RTLTextMeshPro>()
#               .isActiveAndEnabled) break;
#
# -- so it skips crossing cells itself, but it still counts EVERY keypress and
# stops accepting input at `collectedKeyboardString.Length >= word.Length`.
# Pressing one key per letter therefore overflows on any word that crosses a
# solved one, and the surplus press is written into the next cell as a wrong
# letter. Confirmed live on Hebrew 'kniya' (two yods, one already on the board
# from a crossing word): 5 presses for 4 empty cells and the word scored wrong.
_CW_GENERATOR = "CrossWords.CrossWordsGenerator"
_CW_CELL_COMPONENT = "RTLTMPro.RTLTextMeshPro"
_CW_CELL_ASSEMBLY = "RTLTMPro"


def _cw_selected_word(altdriver):
    """The generator's own selected word, as (word, [(row, col), ...]).

    Read `lastSelectedWord` rather than `RTLTMPWordPanel`: the panel reports RTL
    words MIRRORED ('kniya' arrives reversed), which is what the old reverse-order
    pass existed to undo. `lastSelectedWord.word` is always in logical order.
    """
    for canvas in altdriver.find_objects(By.NAME, "Canvas"):
        try:
            sel = canvas.get_component_property(
                _CW_GENERATOR, "lastSelectedWord", "Assembly-CSharp", max_depth=2
            )
        except Exception:
            continue
        if isinstance(sel, dict) and sel.get("word"):
            points = [
                (int(p["x"]), int(p["y"]))
                for p in (sel.get("wordPointsInMatrix") or [])
                if isinstance(p, dict) and "x" in p and "y" in p
            ]
            return sel["word"], points
    return None, None


def _cw_cell_is_filled(cell):
    """The game's own test for a filled cell.

    NOT the cell's text: a cleared board keeps its old letters in `m_text` with
    the component disabled, so reading text reports empty cells as full and the
    solver then presses nothing at all.
    """
    try:
        return bool(cell.get_component_property(
            _CW_CELL_COMPONENT, "isActiveAndEnabled", _CW_CELL_ASSEMBLY))
    except Exception:
        return False  # unreadable -> treat as empty -> press it, as before


def _cw_grid_shape(cells):
    """(rows, cols) if `find_objects` returned the grid in row-major order, else None.

    The generator indexes cells as (row, col); `find_objects` returns them in
    instantiation order, which is that same row-major order -- verified live on a
    169-cell board. Which screen corner holds (0, 0) depends on text direction
    (col 0 sits on the right for Hebrew, the left for English), so only the ORDER
    is relied on, never the geometry. This proves the order really is a grid, and
    recovers its shape, before an index into it is trusted. Rows and columns are
    counted separately so a non-square board still works.
    """
    xs = sorted({c.x for c in cells})
    ys = sorted({c.y for c in cells})
    rows, cols = len(ys), len(xs)
    if rows * cols != len(cells):
        return None
    for x_axis in (xs, list(reversed(xs))):
        for y_axis in (ys, list(reversed(ys))):
            xi = {v: i for i, v in enumerate(x_axis)}
            yi = {v: i for i, v in enumerate(y_axis)}
            if all((i // cols, i % cols) == (yi[c.y], xi[c.x])
                   for i, c in enumerate(cells)):
                return rows, cols
    return None


def _cw_letters_to_press(altdriver, word, points):
    """Letters whose cells are still empty, in press order.

    Returns None when the board cannot be read confidently; the caller then
    presses every letter, which is exactly the old behaviour, so a board this
    cannot parse is never made worse.
    """
    if not word or not points or len(points) != len(word):
        return None

    cells = altdriver.find_objects(By.NAME, "Letter")
    if not cells:
        return None
    shape = _cw_grid_shape(cells)
    if shape is None:
        print("[WARN] crossword: cell order is not a grid, pressing every letter")
        return None
    _rows, cols = shape

    to_press = []
    for ch, (row, col) in zip(word, points):
        index = row * cols + col
        if not (0 <= index < len(cells)):
            return None
        if not _cw_cell_is_filled(cells[index]):
            to_press.append(ch)
    return to_press


def crosswords2(altdriver):
    """Solve all crossword items based on ProgressText."""
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progresstext.split('/')[1])
    print(f"[INFO] Total words to solve: {number_of_words}")

    # Build the letters map once - the keyboard holds one tile per letter.
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }
    print(f"[DEBUG] Available letters : {list(letters_map.keys())}")

    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Stop once the board is done. The loop is sized from ProgressText, but
        # the activity can finish on an earlier pass; without this the last pass
        # finds no selected word, falls back to the panel's MIRRORED text and
        # presses junk into a completed board.
        try:
            solved = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[0])
        except Exception:
            solved = None
        if solved is not None and solved >= number_of_words:
            print(f"[INFO] crossword: all {number_of_words} words solved, stopping")
            break

        word, points = _cw_selected_word(altdriver)
        if word:
            word = word.lower()
            to_press = _cw_letters_to_press(altdriver, word, points)
        else:
            # No generator state: fall back to the panel exactly as before.
            word = altdriver.find_object(By.NAME, "RTLTMPWordPanel").get_component_property(
                'TMProWordPanel', 'Word.word', 'Assembly-CSharp'
            ).lower()
            to_press = None
        print(f"[DEBUG] Target word: {word}")

        if to_press is None:
            to_press = list(word)
        elif len(to_press) != len(word):
            print(f"[INFO] crossword: {len(word) - len(to_press)} cell(s) already filled "
                  f"by crossing words, pressing {len(to_press)}/{len(word)} letters")

        for letter in to_press:
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")

        # Wait for next round to load


def crosswords2_kl(altdriver):
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


# How many rearrange passes one sentence gets before the solver moves on. A
# pass is a full sweep over the sentence, so a solvable board is done in one or
# two; this only ever stops a board that CANNOT be assembled from the pieces
# the solver can read.
MAX_PASSES_PER_SENTENCE = 12

# Pieces of one sentence row share a y; this is how far apart two pieces may
# sit and still count as the same row.
ROW_HEIGHT_TOLERANCE = 30


def _puzzle_progress(progress_object):
    """How many sentences the game says are done, or None if unreadable."""
    try:
        return int(progress_object.get_text().split("/")[0])
    except (AttributeError, IndexError, ValueError):
        return None


def solve_puzzles(altdriver):
    time.sleep(10)
    print("[INFO] Puzzle solver started...")
    altdriver.wait_for_object(By.NAME, "ProgressText", timeout=15)
    progress = altdriver.find_object(By.NAME, "ProgressText")
    manager = altdriver.find_object(By.NAME, "PuzzlesManager")

    # "3/6" — the second half is how many sentences this puzzle has.
    raw = progress.get_text()
    try:
        total = int(raw.split("/")[1])
    except (IndexError, ValueError) as e:
        raise AssertionError(
            f"PUZZLES: ProgressText read {raw!r}, which is not 'done/total' - "
            f"the sentence count is unknown, so the puzzle cannot be played.") from e
    print(f"[INFO] Total sentences: {total}")

    # Sentences that could not be assembled; reported together at the end.
    unsolved = []
    # Consecutive sentences in which no click moved a single piece.
    dead_boards = 0
    # First piece id of each run already claimed by a sentence. Two sentences of
    # one puzzle can read word for word the same, and without this the second
    # would be handed the first one's pieces and never move.
    used_windows = set()

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

    def piece_map():
        """``{piece id: word}`` for every readable piece on the board."""
        out = {}
        for e in altdriver.get_all_elements():
            if not e.name.isdigit() or not e.enabled:
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if word:
                out[int(e.name)] = word
        return out

    def find_window(target_words, used):
        """The run of pieces that IS this sentence, as ``(first id, last id)``.

        The board is one grid of slots (168 of them on a hard puzzle) and a
        sentence owns a CONTIGUOUS run of piece ids -- which is what the
        `group_ranges` table above was guessing at. Guessing it is the whole
        bug: when the guess drifts, the solver picks up same-word pieces
        belonging to a neighbouring sentence and swaps those instead, so the
        sentence it is trying to build never changes. Two sentences of a puzzle
        can read word for word the same, so `used` keeps the second one from
        being handed the first one's pieces.
        """
        pieces = piece_map()
        ids = sorted(pieces)
        want = Counter(target_words)
        size = len(target_words)
        for start in range(len(ids) - size + 1):
            run = ids[start:start + size]
            if run[-1] - run[0] != size - 1:         # must be consecutive slots
                continue
            if run[0] in used:
                continue
            if Counter(pieces[k] for k in run) == want:
                return run[0], run[-1]
        return None

    def read_rows(target_words):
        """The board's ROWS that hold this sentence, top row first.

        The index windows above are per-difficulty guesses. When one drifts,
        `read_pieces` happily returns pieces belonging to a DIFFERENT row --
        and clicking those does nothing at all, because they are not the row
        being played. Two sentences with the same words (the puzzle repeats
        them) make that certain rather than unlucky. Pieces of one row share a
        y, so grouping by y gives the real candidates to try instead.
        """
        by_row = {}
        for e in altdriver.get_all_elements():
            if not e.name.isdigit() or not e.enabled:
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if word:
                by_row.setdefault(round(float(e.y) / ROW_HEIGHT_TOLERANCE), []).append(
                    {"obj": e, "text": word})

        want = Counter(target_words)
        rows = []
        for key, row in sorted(by_row.items(), key=lambda kv: -kv[0]):
            if Counter(p["text"] for p in row) == want:
                row.sort(key=lambda p: (-p["obj"].y, p["obj"].x))
                rows.append(row)
        return rows

    for i in range(total):
        # The puzzle may already be part-done (a retry resumes a board that a
        # previous attempt got most of the way through), and it ENDS the moment
        # the count is full. Without this the loop kept playing phantom
        # sentences on a finished board and called that a failure.
        done_now = _puzzle_progress(progress)
        if done_now is not None and done_now >= total:
            print(f"[DONE] the puzzle is complete ({done_now}/{total}).")
            break

        print(f"\n--- Sentence {i+1}/{total} ---")
        time.sleep(0.5)

        target = manager.get_component_property(
            "com.kideo.learn.english.PuzzlesManager",
            "currentSentence_",
            "Assembly-CSharp"
        ).split()
        print("[TARGET]", " ".join(target))

        # Which pieces ARE this sentence: found on the board, not guessed from
        # a difficulty table. The guessed table stays as a fallback for a board
        # this cannot read.
        window = find_window(target, used_windows)
        if window is not None:
            used_windows.add(window[0])
            print(f"[PIECES] sentence {i+1} is pieces {window[0]}-{window[1]}")
        else:
            window = group_ranges[i] if i < len(group_ranges) else (0, 9999)
            print(f"[PIECES] no run of pieces spells this sentence - falling back "
                  f"to the guessed window {window[0]}-{window[1]}")

        # A sentence is rearranged in PASSES, and the pass count is bounded.
        # Nothing here guarantees the board can reach the target: the index
        # windows above are per-difficulty guesses, so a window that misses a
        # piece leaves `pieces` shorter than the sentence, every index falls
        # through `idx >= len(pieces)`, and no click is ever made. That is how
        # `while True` used to sit on the puzzle forever with the run hung.
        solved = False
        previous = None
        stalled = 0
        # Did ANY click move this board? A puzzle that has ended (or timed out)
        # keeps its pieces on screen and keeps reporting a currentSentence_,
        # but ignores every click -- see the dead-board check after the loop.
        first_seen = None
        moved = False
        # None = the guessed index window (what has always worked); 0, 1, ... =
        # the board's rows holding this sentence, tried in turn when the window
        # picks a row whose pieces do not respond to a click.
        row_choice = None

        def read_now():
            nonlocal window
            if row_choice is not None:
                rows = read_rows(target)
                return rows[row_choice] if row_choice < len(rows) else []
            found = read_pieces(target, *window)
            if len(found) < len(target) and window != (0, 9999):
                # The window missed pieces - read the WHOLE board rather than
                # spin on a view that can never match the sentence. It stays
                # widened for the rest of this sentence, so the re-reads after
                # each swap below see the same pieces this pass did.
                print(f" [WIDEN] window {window[0]}-{window[1]} found "
                      f"{len(found)}/{len(target)} pieces - reading every piece.")
                window = (0, 9999)
                found = read_pieces(target, *window)
            return found

        for _pass in range(1, MAX_PASSES_PER_SENTENCE + 1):
            pieces = read_now()
            current = [p["text"] for p in pieces]
            print("[CURRENT]", " ".join(current))

            if first_seen is None:
                first_seen = current
            elif current != first_seen:
                moved = True

            if current == target:
                print(f"[OK] Sentence solved.")
                solved = True
                break

            # Two passes that change nothing will not start working on a third:
            # the swap rule is deterministic, so the same board makes the same
            # moves. A row that does not move under a click is the WRONG row,
            # so switch to the next candidate rather than giving up on the
            # sentence -- that is what left "The uncle lives in Berlin." unbuilt
            # while its pieces sat one row away.
            if current == previous:
                stalled += 1
                if stalled >= 2:
                    row_choice = 0 if row_choice is None else row_choice + 1
                    if row_choice >= len(read_rows(target)):
                        print(f" [STALL] no row of the board responds - giving up "
                              f"on sentence {i + 1}.")
                        break
                    print(f" [ROW] that row does not move under a click - "
                          f"trying board row {row_choice} instead.")
                    # Reading a DIFFERENT row changes `current` without a single
                    # piece having moved, so the movement check restarts here.
                    # Otherwise switching rows looks like progress and the
                    # dead-board exit below never fires.
                    stalled, previous, first_seen = 0, None, None
                    continue
            else:
                stalled = 0
            previous = current

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
                # ASCII only: this solver has to survive a cp1252 console. A
                # '<->' here used to be a U+2194, and printing it killed the
                # run mid-sentence outside the panel (which sets UTF-8 itself).
                print(f" [SWAP] '{have}' <-> '{want}' (idx={idx}, j={cand_idx})")
                a_obj, b_obj = pieces[idx]["obj"], pieces[cand_idx]["obj"]

                try:
                    a_obj.click()
                    time.sleep(0.2)
                    b_obj.click()
                    time.sleep(1)
                except Exception:
                    print(" [WARNING] Swap click failed.")
                    continue

                pieces = read_now()
                current = [p["text"] for p in pieces]
                print("[AFTER SWAP]", " ".join(current))

                if idx < len(current) and current[idx] == want:
                    print(f" [VALID] '{want}' now correctly placed.")
                else:
                    print(f" [REVERT] '{want}' not correct - reverting.")
                    try:
                        a_obj.click()
                        time.sleep(1)
                        b_obj.click()
                        time.sleep(1)
                    except Exception:
                        print(" [WARNING] Revert failed.")

                    pieces = read_now()
                    current = [p["text"] for p in pieces]
                    print("[AFTER REVERT]", " ".join(current))

            time.sleep(0.5)

        if not solved:
            unsolved.append(i + 1)
            print(f"[WARN] Sentence {i+1}/{total} was not assembled - moving on.")

        # A puzzle that has ENDED -- finished, or its timer ran out -- leaves
        # the pieces on screen and keeps answering currentSentence_, but takes
        # no clicks at all. Grinding through the remaining sentences on a board
        # like that buys nothing, so stop as soon as it is recognisable: two
        # sentences running where not one click moved anything.
        if not solved and not moved:
            dead_boards += 1
            if dead_boards >= 2:
                raise AssertionError(
                    f"PUZZLES: the board stopped responding at sentence "
                    f"{i + 1}/{total} (ProgressText {progress.get_text()!r}). No "
                    f"click moved a piece across two sentences, so the puzzle is "
                    f"over or frozen -- there is nothing left to play.")
        else:
            dead_boards = 0

        print("[NEXT] Clicking next button...")
        try:
            time.sleep(1.5)
            next_btn = altdriver.find_object(By.NAME, "nextButton")
            next_btn.click()
        except Exception:
            print("[WARNING] Failed to click Next.")

        print("[WAIT] Waiting 5s for next sentence to load...")
        time.sleep(6.5)

    # Say what happened instead of reporting success for a board that was left
    # half-built. Raising hands it to the caller's 3-attempt retry (utilsdemo),
    # which re-reads the board — and a failure that is REPORTED can be chased,
    # where a hang could only be killed.
    if unsolved:
        raise AssertionError(
            f"PUZZLES: {len(unsolved)} of {total} sentence(s) could not be "
            f"assembled (sentence {unsolved}). The pieces the solver could read "
            f"never matched the target sentence.")

    print("\n[SUCCESS] All puzzles processed!")
# Example of how to run the script:
# from altdriver import AltDriver
# alt_driver = AltDriver()
# solve_puzzles(alt_driver)


def exams_image_to_audio(altdriver, attempts=3):
    """Match audio shapes to their word labels by swiping, verifying each one."""
    time.sleep(1)

    def audio_shapes():
        return (altdriver.find_objects(By.NAME, 'ImageAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)'))

    shapes = audio_shapes()
    if not shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")
    # Each shape has to be played once before it can be matched.
    for shape in shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)'))
        if not words:
            raise Exception("[ERROR] No word objects found.")
        return (_read_matchables(words, 'com.kideo.learn.english.WordAudioObject'),
                _read_matchables(audio_shapes(),
                                 'com.kideo.learn.english.WordAudioShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_image_to_audio", attempts=attempts)


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

def _bare_letters(text):
    """`text` with any combining marks removed; identity when there are none.

    Hebrew arrives pointed from both sides of the RINGS match and the points are
    NOT letters: a cover named `CoverHolder-<ayin><tsere><final-tsadi>` is three
    code points for a two-letter word, so the path finder hunts the vowel point
    across the board as though it were a letter and never completes a ring.
    Measured live on a Kideo Land board: 0 of 6 rings found before normalising
    both sides, 6 of 6 after.

    English has no combining marks, so this returns the text unchanged and the
    comparisons it feeds are bit-identical to before -- Voca Tooki is unaffected.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


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
    SETTLE = 4.0          # the score animation lags - reading earlier lies
    REGEN_WAIT = 5.0      # past halfway the round spawns fresh structures

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def geometry():
        """Derive the layout constants from the live scene, not fixed pixels.

        The window is not always the same size, and every one of these used to
        be a magic pixel value tuned for one resolution. When the window grew,
        the hex spacing (~101px) sailed past a hardcoded ADJ of 75, so the path
        finder saw every cell as isolated and nothing was ever placeable. These
        are now measured each run:

        * ADJ    -- from the median nearest-neighbour spacing of the board hexes
        * PANEL_X-- the gap between the board's right edge and the inventory
        * board bbox -- so a placed cover is recognised anywhere on the board
        * VIS band  -- the inventory's reachable y-range, taken from the scroll
                       arrows that bracket the panel
        * inv_x  -- where to press to scroll the inventory (over the panel, not
                    the board)
        """
        # Fallbacks, used only when a measurement fails outright (no Letter
        # hexes on screen, no scroll arrows). They were tuned on a 1600x900
        # window, so they are scaled to the window in use rather than left as
        # values that are simply wrong on any other size.
        try:
            sw, sh = altdriver.get_application_screensize()
        except Exception:
            sw, sh = 1600.0, 900.0
        fx, fy = float(sw) / 1600.0, float(sh) / 900.0
        g = {"ADJ": 75.0 * fx, "PANEL_X": 980.0 * fx, "inv_x": 1057.0 * fx,
             "SPACING": 101.0 * fx, "PITCH": 150.0 * fy,
             "bx0": -1e9, "bx1": 1e9, "by0": -1e9, "by1": 1e9,
             "VIS_LO": 120.0 * fy, "VIS_HI": 500.0 * fy}

        bx, by = [], []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name != "Letter":
                continue
            try:
                p = e.get_screen_position()
                if (e.get_text() or "").strip():
                    bx.append(p[0]); by.append(p[1])
            except Exception:
                pass
        if len(bx) >= 4:
            g["bx0"], g["bx1"] = min(bx), max(bx)
            g["by0"], g["by1"] = min(by), max(by)
            cells = list(zip(bx, by))
            nn = []
            for i, a in enumerate(cells):
                best = 1e9
                for j, b in enumerate(cells):
                    if i != j:
                        best = min(best, ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5)
                nn.append(best)
            nn.sort()
            g["ADJ"] = max(75.0 * fx, nn[len(nn)//2] * 1.35)
            g["SPACING"] = nn[len(nn)//2]        # raw hex spacing, for scaling

        hx = []
        cover_pts = []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name.startswith("CoverHolder-"):
                try:
                    pos = e.get_screen_position()
                except Exception:
                    continue
                hx.append(pos[0])
                cover_pts.append(pos)
        if hx:
            hx.sort()
            g["inv_x"] = hx[len(hx)//2]
            if g["bx1"] > -1e8:
                g["PANEL_X"] = (g["bx1"] + min(hx)) / 2.0

        # How far apart the inventory covers sit: scrolling by exactly one
        # pitch advances the list by exactly one cover, whatever the window
        # size. A fixed step scrolls a fraction of a cover on a large window
        # and several on a small one.
        cover_ys = sorted(p[1] for p in cover_pts)
        gaps = [b - a for a, b in zip(cover_ys, cover_ys[1:]) if b - a > 1]
        if gaps:
            g["PITCH"] = sorted(gaps)[len(gaps)//2]

        arrows = {}
        for e in altdriver.get_all_elements(enabled=True):
            if e.name in ("Up Arrow", "Down Arrow"):
                try:
                    arrows[e.name] = e.get_screen_position()
                except Exception:
                    pass
        if "Up Arrow" in arrows and "Down Arrow" in arrows:
            lo = min(arrows["Up Arrow"][1], arrows["Down Arrow"][1])
            hi = max(arrows["Up Arrow"][1], arrows["Down Arrow"][1])
            margin = (hi - lo) * 0.07
            g["VIS_LO"], g["VIS_HI"] = lo + margin, hi - margin

        return g

    geom = geometry()
    ADJ = geom["ADJ"]
    PANEL_X = geom["PANEL_X"]
    VIS_LO, VIS_HI = geom["VIS_LO"], geom["VIS_HI"]

    # The gesture constants below were tuned when the board's hex spacing was
    # ~101px. The window is not always that size (it has been seen at 2153x1093,
    # where the spacing is 135), and a nudge that is proportionally too small
    # never engages the drag — the "drag never engaged" failure. Scale them off
    # the live board instead of leaving them as pixels.
    SCALE = max(0.5, geom["SPACING"] / 101.0)
    NUDGES = tuple(int(round(n * SCALE)) for n in (10, 25, 45, 70))
    ENGAGE_EPS = 8.0 * SCALE          # "did it move?" threshold
    PITCH = geom["PITCH"]             # one inventory cover
    # "same cell" radius: a quarter of the hex spacing, so it means the same
    # thing on every board size (it was a flat 25px, which is a quarter of a
    # hex at spacing 101 but under a fifth at 135).
    SAME_CELL_R2 = (0.25 * geom["SPACING"]) ** 2
    print("[info] rings scale: spacing=%.0f x%.2f nudges=%s pitch=%.0f"
          % (geom["SPACING"], SCALE, NUDGES, PITCH))
    TOL = max(16.0, ADJ * 0.16)
    print("[info] rings geometry: ADJ=%.0f PANEL_X=%.0f VIS=[%.0f,%.0f] inv_x=%.0f"
          % (ADJ, PANEL_X, VIS_LO, VIS_HI, geom["inv_x"]))

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
            # a placed cover sits within the board's bounding box; the covers
            # still in the inventory are further right (x ~ inv_x) and excluded
            if (p[0] <= PANEL_X
                    and geom["by0"] - ADJ < p[1] < geom["by1"] + ADJ):
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

        exact_letters = [c[2] for c in cells]
        bare_letters = [_bare_letters(t) for t in exact_letters]

        def walk(letters, w):
            def dfs(idx, pos, used):
                if pos == len(w):
                    return list(used)
                for k in nbr[idx]:
                    if k in used or k in blocked or letters[k] != w[pos]:
                        continue
                    used.append(k)
                    r = dfs(k, pos+1, used)
                    if r:
                        return r
                    used.pop()
                return None

            for i in range(len(cells)):
                if i in blocked or letters[i] != w[0]:
                    continue
                r = dfs(i, 1, [i])
                if r:
                    return r
            return None

        def find(word):
            """Match on exact letters first; only then retry ignoring marks.

            Hebrew (and Arabic) arrive POINTED on both sides and the points are
            not letters, so an exact walk can never complete a ring -- measured
            live, 0 of 6. Stripping marks fixes that.

            But the app also targets pt, es, de and tr, where a marked character
            IS its own letter: Spanish 'ano' and 'anno-with-tilde' are different
            words, Turkish dotless i is not i, German umlauts are distinct. There
            the board carries the accented tile itself, so a stripped match could
            walk a wrong-but-similar path.

            Trying exact first means those languages resolve on pass one and never
            reach the fallback, while pointed scripts still get solved. The
            fallback is skipped entirely when stripping changes nothing.
            """
            w_exact = "".join(word.split()).lower()
            found = walk(exact_letters, w_exact)
            if found:
                return found

            w_bare = _bare_letters(w_exact)
            if w_bare == w_exact and bare_letters == exact_letters:
                return None  # nothing to strip; the retry would be identical
            return walk(bare_letters, w_bare)

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

    def scroll_inventory(dy=None):
        """A vertical drag inside the panel scrolls it to reach hidden covers.

        Always the same direction: alternating merely oscillates between two
        positions and never cycles the list.
        """
        dy = -PITCH if dy is None else dy   # one cover per scroll, whatever the size
        x = geom["inv_x"]                 # press over the panel, not the board
        y0 = (VIS_LO + VIS_HI) / 2.0
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

    def dragged_centroid(hpos, ring_size, busy):
        """Centroid of the cover being dragged, from its hex pieces on the board.

        A cover is a rigid group of hexes shaped like its ring; we only hold one
        of them. The pieces already placed (busy) and the ones still in the
        inventory are excluded, then the `ring_size` pieces nearest the held hex
        are the dragged cover. Aligning this centroid -- not the single held hex
        -- is what actually snaps the cover: the held hex can sit at the ring
        centre while the shape as a whole is a hex or two off, and then nothing
        registers.
        """
        pts = []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            if p[0] > PANEL_X:                       # still in the inventory
                continue
            if any((p[0]-q[0])**2 + (p[1]-q[1])**2 < SAME_CELL_R2 for q in busy):
                continue                             # an already-placed cover
            pts.append((p[0], p[1]))
        pts.sort(key=lambda p: (p[0]-hpos[0])**2 + (p[1]-hpos[1])**2)
        grp = pts[:ring_size]
        if not grp:
            return None
        return (sum(p[0] for p in grp) / len(grp),
                sum(p[1] for p in grp) / len(grp))

    def place(holder_pos, target, ring_size, busy):
        cov, dist = cover_near(holder_pos)
        if cov is None or dist > 2.0 * ADJ:      # scales with the hex size
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
            if here and abs(here[0]-start[0]) < ENGAGE_EPS and abs(here[1]-start[1]) < ENGAGE_EPS:
                print("[warn] drag never engaged")
                return False

            # Coarse: drive the held hex to the ring centre. This gets the whole
            # cover onto the board, roughly over the ring, and clear of the
            # inventory so its cluster can be measured cleanly.
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

            # Fine: align the cover's whole cluster to the ring centre. The held
            # hex is usually off-centre in the shape, so centring it leaves the
            # cluster a hex or two adrift; correct that here or it will not snap.
            for _ in range(16):
                h = pos_of(cid)
                if not h:
                    break
                cc = dragged_centroid(h, ring_size, busy)
                if not cc:
                    break
                ex, ey = target[0]-cc[0], target[1]-cc[1]
                if (ex*ex + ey*ey) ** 0.5 <= 6.0:
                    break
                finger[0] += ex / gain
                finger[1] += ey / gain
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
    placed = set()          # words done this batch; a placed holder can linger
    regen_done = False

    for _ in range(90):
        done, total = progress()
        if total and done >= total:
            print(f"[info] all {total} structures placed.")
            break

        # A hard round (>8 words) does not show all its structures at once: once
        # half are placed it wipes the panel and spawns a fresh batch, and the
        # board regenerates with them. Handle that transition like a fresh start
        # -- wait for the new structures to settle, forget the old fail counts,
        # then fall through and re-read the whole scene.
        if total > 8 and not regen_done and done >= total / 2.0:
            print("[info] halfway reset — waiting for the new structures to spawn")
            time.sleep(REGEN_WAIT)
            failed.clear()
            placed.clear()          # the fresh batch may reuse a word
            idle = 0
            regen_done = True
            continue

        cells = read_grid()
        busy = occupied()
        find = path_finder(cells, busy)
        hs = holders()

        cand = None
        for w, p in sorted(hs.items(), key=lambda kv: -kv[1][1]):
            if w in placed or failed.get(w, 0) >= 2:
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
                scroll_inventory()
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
        if place(holder_pos, (tx, ty), len(ring), busy):
            time.sleep(SETTLE)
            now, total = progress()
            if now > before:
                failed.pop(word, None)
                placed.add(word)        # its holder may linger; don't re-drag it
                print(f"[info] progress {now}/{total}")
            else:
                failed[word] = failed.get(word, 0) + 1
        else:
            failed[word] = failed.get(word, 0) + 1

    done, total = progress()
    print(f"[done] rings finished at {done}/{total}")


def parashoot(altdriver):
    """Solves PARASHOOT: complete each word by shooting the falling letter crates.

    A word shows with blank letters (e.g. "c_t_h"). Crates parachute down, each
    showing a letter on a rotating cube; some crates hold a bird/bomb/fruit
    instead of a letter. The cannon at the bottom pivots left/right and fires a
    laser straight along its barrel. Hitting a needed letter fills a blank;
    hitting a wrong letter -- or a hazard crate -- costs a life. Letting a crate
    fall past is free.

    What this activity needed, all found against the live build:

    1. The answer. `ParashootGameManager.staticChosenWord` is the full word while
       `chosenWord` is the masked version (same idea as the bubbles solver's
       newWord). The missing letters are the blanks: zip the two and take the
       full-word letter wherever the mask has "_". Recomputed after every hit,
       so doubled letters (two blanks needing the same letter) are handled
       naturally -- the letter stays in the set until every blank is filled.

    2. Trust only the VISIBLE letter. The crates are rotating cubes with several
       letter faces, so the letter a crate "has" changes; the only reliable
       reading is the front-face Text on screen right now. Crates are targeted
       by that Text, not by guessing a cube's letter.

    3. Aim by ANGLE, not position. The cannon does not translate -- it pivots
       (left/right buttons rotate its barrel ~+-56 degrees). To hit a crate the
       barrel is rotated to point at the crate, so far-left/right lanes are
       reachable even though the cannon body barely moves. The tilt range is
       measured live at start.

    4. Never fire unless the shot is safe. Only fire when the front-most crate
       along the beam is the target letter and no hazard or wrong-letter crate
       sits on the beam before it -- and only at crates actually on screen
       (screen height from the camera; crates spawn above the top).

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    ASM = "Assembly-CSharp"
    GM = "com.kideo.learn.english.ParashootGameManager"
    RT = "UnityEngine.RectTransform"
    CO = "UnityEngine.CoreModule"

    gm = altdriver.find_object(By.NAME, "ParashootGameManager")

    def prop(f):
        try:
            return gm.get_component_property(GM, f, ASM)
        except Exception:
            return None

    def txt(n):
        try:
            return altdriver.find_object(By.NAME, n).get_text()
        except Exception:
            return None

    def P(n):
        return altdriver.find_object(By.NAME, n).get_screen_position()

    def progress():
        t = txt("ProgressText") or "0/0"
        try:
            a, b = t.split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def lives():
        try:
            return int(txt("LifesNumber"))
        except Exception:
            return -1

    # ---- live geometry (resolution independent) ----
    GUN = P("Gun_1")                       # pivot
    zoneW = P("RightDetector")[0] - P("LeftDetector")[0]
    BOXR = zoneW * 0.42                    # crate half-size
    SCREEN_H = 824.0
    for cam in ("Main Camera", "Camera"):
        try:
            v = altdriver.find_object(By.NAME, cam).get_component_property(
                "UnityEngine.Camera", "pixelHeight", CO)
            if v:
                SCREEN_H = float(v)
                break
        except Exception:
            pass
    TOP = SCREEN_H * 0.96                  # fully-on-screen ceiling
    ANGLE_TOL = 2.5

    def missing():
        full = (prop("staticChosenWord") or "")
        mask = (prop("chosenWord") or "")
        return set(c2.lower() for c1, c2 in zip(mask, full)
                   if c1 == "_" and c2 != "_")

    def scene():
        """(letters[(letter,x,y)], hazards[(x,y)]) on screen, above the gun.

        Letters are the visible front-face Texts. Hazards are cubes with no
        letter face showing -- bird / bomb / fruit crates.
        """
        cubes, letters = [], []
        for e in altdriver.get_all_elements(enabled=True):
            try:
                nm = e.name
                if nm == "Cube (2) 1(Clone)":
                    p = e.get_screen_position()
                    if GUN[1] + BOXR*0.3 < p[1] < TOP:
                        cubes.append((p[0], p[1]))
                elif nm == "Text":
                    t = (e.get_text() or "").strip().lower()
                    if len(t) == 1 and t.isalpha():
                        p = e.get_screen_position()
                        if GUN[1] < p[1] < TOP:
                            letters.append((t, p[0], p[1]))
            except Exception:
                continue
        hazards = [(cx, cy) for (cx, cy) in cubes
                   if not any(abs(lx-cx) < BOXR and abs(ly-cy) < BOXR
                              for (_, lx, ly) in letters)]
        return letters, hazards

    def gun_tilt():
        try:
            e = altdriver.find_object(By.NAME, "Gun_1").get_component_property(
                RT, "localEulerAngles", CO)
            z = e["z"] if isinstance(e, dict) else 0.0
        except Exception:
            z = 0.0
        return z if z <= 180 else z - 360     # signed: + = left, - = right

    def desired_tilt(bx, by):
        return -math.degrees(math.atan2(bx - GUN[0], max(1.0, by - GUN[1])))

    def nudge(err):
        """One proportional rotation step toward the target angle.

        `err` is (desired - current) tilt in degrees; negative means the target
        is to the right (barrel must rotate right). The hold time scales with
        the error so a large gap closes quickly and the last degrees are eased
        in. One step per control-loop pass, so the aim keeps tracking a crate
        that is still swaying and falling rather than committing to a stale spot.
        """
        btn = "RightButton" if err < 0 else "LeftButton"
        # The barrel turns ~85 deg/s while held, so hold for most of the time
        # the gap needs (err/95) -- a big gap is closed in one long hold instead
        # of many short taps -- then ease in near the target, capped so a single
        # hold cannot overshoot wildly.
        dt = min(0.5, max(0.03, abs(err) / 95.0))
        fid = altdriver.begin_touch(P(btn))
        time.sleep(dt)
        altdriver.end_touch(fid)

    def path_clear(target, letters, hazards):
        """No hazard / wrong-letter crate lies on the aim ray before the target.

        The laser travels along the barrel toward the target, so a crate whose
        body overlaps that ray at any point closer than the target is hit first.
        The perpendicular threshold is a full crate half-width (plus a margin)
        because it is the crate's *edge*, not its centre, that has to clear the
        beam -- a wrong crate grazing the beam still costs a life.
        """
        Tx, Ty, Tl = target
        gx, gy = GUN
        ux, uy = Tx - gx, Ty - gy
        L = math.hypot(ux, uy) or 1.0
        ux, uy = ux/L, uy/L
        blockers = [(x, y, l) for (l, x, y) in letters] + \
                   [(x, y, None) for (x, y) in hazards]
        for (cx, cy, lab) in blockers:
            if abs(cx-Tx) < 1 and abs(cy-Ty) < 1:
                continue
            vx, vy = cx - gx, cy - gy
            along = vx*ux + vy*uy
            if along <= 0 or along >= L - BOXR*0.3:
                continue                      # behind gun or at/after target
            if abs(vx*uy - vy*ux) < BOXR*1.2 and lab != Tl:
                return False                  # crate overlaps the beam first
        return True

    def fire():
        altdriver.find_object(By.NAME, "FireButton").tap()

    # The cannon rotates freely with no hard stop -- holding a button long
    # enough spins the barrel all the way around, past horizontal and down.
    # That must never happen: it may only aim UP at the falling crates. Every
    # on-screen crate is above the gun, so its aim angle is always within the
    # up hemisphere; MAX_TILT keeps commanded angles there and off the
    # near-horizontal edge where a shot would rake sideways.
    MAX_TILT = 78.0
    print("[info] parashoot: screen_h=%.0f max_tilt=%.0f" % (SCREEN_H, MAX_TILT))

    def reachable(bx, by):
        return abs(desired_tilt(bx, by)) <= MAX_TILT

    def relocate(committed, ms, letters, hazards):
        """Keep tracking the committed crate if it is still a valid shot.

        Returns the crate's fresh position, or None to pick a new one. Staying
        on one crate stops the cannon from swinging between several correct
        letters -- focus on one, and only move to another once this one is shot
        or has fallen past.
        """
        if not committed or committed[0] not in ms:
            return None
        cl, cx, cy = committed
        same = [(l, x, y) for (l, x, y) in letters
                if l == cl and abs(x-cx) < BOXR*1.6 and abs(y-cy) < BOXR*2.2]
        if not same:
            return None                        # shot or fell past -> next crate
        l, x, y = min(same, key=lambda z: (z[1]-cx)**2 + (z[2]-cy)**2)
        if not reachable(x, y):
            return None
        return (l, x, y)

    def pick(ms, letters, hazards):
        """Highest crate whose beam is clear of any wrong / hazard crate.

        Prefer the crate FARTHEST from the cannon (highest on screen): it has the
        longest fall left, giving the most time to aim precisely and land the
        shot rather than rushing a crate about to pass the cannon.
        """
        cand = [(l, x, y) for (l, x, y) in letters
                if l in ms and reachable(x, y)
                and path_clear((x, y, l), letters, hazards)]
        if not cand:
            return None
        return max(cand, key=lambda z: z[2])   # farthest from cannon = highest y

    done, total = progress()
    print("[info] starting parashoot at %d/%d, lives=%d" % (done, total, lives()))
    stuck = 0
    committed = None

    while True:
        done, total = progress()
        if total and done >= total:
            print("[info] all %d words complete." % total)
            break
        if stuck > 600:
            print("[warn] no clean shot for a while — stopping.")
            break
        stuck += 1

        ms = missing()
        if not ms:
            committed = None
            continue
        letters, hazards = scene()
        cur_tilt = gun_tilt()

        def try_fire(tl, tx, ty):
            """Fire, log a real hit, and report whether the mask advanced."""
            before, m0 = done, prop("chosenWord")
            fire()
            time.sleep(0.12)                   # brief — then immediately re-scan
            now, total = progress()
            m1 = prop("chosenWord")
            if m1 != m0 or now != before:
                print("[act] hit '%s' mask %r->%r prog %d/%d lives=%d"
                      % (tl, m0, m1, now, total, lives()))
                return True
            return False

        # Opportunistic: fire any reachable, clear, missing-letter crate the
        # barrel is ALREADY pointing at -- a free shot needs no travel, so grab
        # it (even if it is not the far crate we are heading for) for speed.
        ready = [(l, x, y) for (l, x, y) in letters
                 if l in ms and reachable(x, y)
                 and abs(desired_tilt(x, y) - cur_tilt) <= ANGLE_TOL
                 and path_clear((x, y, l), letters, hazards)]
        if ready:
            tl, tx, ty = min(ready,
                             key=lambda z: abs(desired_tilt(z[1], z[2]) - cur_tilt))
            stuck = 0
            if try_fire(tl, tx, ty):
                committed = None
            continue

        # Otherwise travel toward the committed crate (kept across passes so the
        # cannon follows one crate instead of swinging between several); prefer
        # the farthest so there is time to aim.
        target = relocate(committed, ms, letters, hazards) or pick(ms, letters, hazards)
        if not target:
            committed = None
            continue
        committed = target
        stuck = 0
        tl, tx, ty = target

        # Closed-loop: one rotation step toward the crate's CURRENT position (it
        # is re-measured every pass, so the aim tracks the still-swaying crate).
        err = desired_tilt(tx, ty) - cur_tilt
        if abs(err) > ANGLE_TOL:
            nudge(err)
            continue
        if path_clear((tx, ty, tl), letters, hazards) and try_fire(tl, tx, ty):
            committed = None

    done, total = progress()
    print("[done] parashoot finished at %d/%d, lives=%d" % (done, total, lives()))


def _pipes_trace(altdriver, path, difficulty=""):
    """Trace one sentence along its pipes. Returns True if a stroke was made.

    Four things about this activity are not obvious, all found against the live
    build. They apply to every difficulty -- the world-segment touch drag this
    replaced scored 0 on hard and medium as well as easy:

    1. The stroke needs BOTH input systems. The pipes carry an EventTrigger
       listening for Drag/EndDrag; `move_touch` never reaches that handler
       (`beingHeld` stays False for every point on the path), while `move_mouse`
       alone just slides an unpressed pointer around. Holding a touch open sets
       `beingHeld` and the handler then follows the mouse, so `begin_touch`
       latches, `move_mouse` steers, `end_touch` releases. The press must land
       ON a pipe, so it is anchored to the first letter.

    2. `pipesPositions` is only a straight nominal segment (both endpoints share
       one y) while the pipes are drawn as S-curves, so following that line
       leaves the pipe. The real curve is spelled out by the letter tiles
       (`PipeTextPref(Clone)`) lying along it. They stop short of the end caps,
       so each run is extended along its own tangent -- ending early scores
       nothing -- by an amount scaled to the letter spacing, because the board
       is laid out at different sizes between rounds.

    3. The wheels joining consecutive pipes are named Junction, Junction_1,
       Junction_2 ... and the path only counts if the stroke passes through
       them, so each gap is crossed via the nearest wheel, and a pipe that feeds
       a wheel is followed all the way into it.

    4. Only the FIRST pipe gets a head extension. A later pipe is entered from
       the wheel it comes out of; extrapolating backwards from its first letter
       lands outside the pipe and drops the latch mid-stroke, which is what made
       medium trace two pipes and then stall on the third.
    """
    HEAD_GAPS, HEAD_MIN, HEAD_MAX = 4.0, 40.0, 140.0
    TAIL_GAPS, TAIL_MIN, TAIL_MAX = 8.0, 90.0, 300.0
    # On easy the final pipe runs much further past its last letter than on the
    # other boards, so the stroke stops short of the closing junction unless the
    # last tail is driven harder. Easy only -- medium and hard are correct as is.
    LAST_TAIL_GAPS, LAST_TAIL_MAX = 20.0, 700.0
    JUNCTION_RADIUS = 120.0
    STEP_PX, STEP_DUR = 10.0, 0.03
    easy = "easy" in (difficulty or "").lower()

    pipes_at, letters, junctions = {}, [], []
    for e in altdriver.get_all_elements(enabled=True):
        name = e.name
        try:
            if name.startswith("Pipe_") and name.split("_")[-1].isdigit():
                pipes_at[name] = e.get_screen_position()
            elif "PipeTextPref" in name:
                text = (e.get_text() or "").strip()
                if text:
                    p = e.get_screen_position()
                    letters.append((p[0], p[1], text))
            elif name.startswith("Junction"):
                junctions.append(e.get_screen_position())
        except Exception:
            continue

    by_pipe = {}
    for x, y, text in letters:
        best, best_d = None, float("inf")
        for name, centre in pipes_at.items():
            d2 = (centre[0] - x) ** 2 + (centre[1] - y) ** 2
            if d2 < best_d:
                best, best_d = name, d2
        by_pipe.setdefault(best, []).append((x, y, text))

    # order each pipe's tiles so they spell the sentence; that also confirms the
    # right tiles were picked, since decoy words sit on the other pipes
    want = re.sub(r"\s+", "", path.get("sentence") or "")
    runs, spelled = [], ""
    for name in path.get("pipesNames") or []:
        tiles = sorted(by_pipe.get(name) or [], key=lambda r: r[0])
        for candidate in (tiles, list(reversed(tiles))):
            if want[len(spelled):].startswith("".join(r[2] for r in candidate)):
                tiles = candidate
                break
        spelled += "".join(r[2] for r in tiles)
        runs.append([(r[0], r[1]) for r in tiles])

    if spelled != want or not runs or not runs[0]:
        print("[warn] letters do not spell the sentence yet — waiting")
        return False

    def beyond(end, prev, dist):
        dx, dy = end[0] - prev[0], end[1] - prev[1]
        mag = (dx * dx + dy * dy) ** 0.5 or 1.0
        return (end[0] + dx / mag * dist, end[1] + dy / mag * dist)

    def wheel_between(a, b):
        """The junction joining two points, if there is one."""
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        gap = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        near = [j for j in junctions
                if ((j[0] - mid[0]) ** 2 + (j[1] - mid[1]) ** 2) ** 0.5
                <= max(gap, JUNCTION_RADIUS)]
        if not near:
            return None
        return min(near, key=lambda q: (q[0] - mid[0]) ** 2 + (q[1] - mid[1]) ** 2)

    way = []
    for i, run in enumerate(runs):
        if len(run) < 2:
            way.extend(run)
            continue
        gap_px = (((run[-1][0] - run[0][0]) ** 2 +
                   (run[-1][1] - run[0][1]) ** 2) ** 0.5 / max(1, len(run) - 1))
        head_ext = max(HEAD_MIN, min(HEAD_MAX, gap_px * HEAD_GAPS))
        if easy and i == len(runs) - 1:
            tail_ext = max(TAIL_MIN, min(LAST_TAIL_MAX, gap_px * LAST_TAIL_GAPS))
        else:
            tail_ext = max(TAIL_MIN, min(TAIL_MAX, gap_px * TAIL_GAPS))

        if i == 0:
            # only the first pipe needs its own start cap covered
            way.append(beyond(run[0], run[1], head_ext))
        else:
            # Entry to any later pipe is the wheel it comes out of.
            # Extrapolating backwards from its first letter (as the first pipe
            # does) lands outside the pipe and drops the latch mid-stroke.
            j = wheel_between(way[-1], run[0])
            if j is not None:
                way.append((j[0], j[1]))

        way.extend(run)

        # The letters stop well short of where the pipe actually ends, so run
        # past them -- and when this pipe feeds a wheel, carry on into it so the
        # stroke cannot stop short of the connection.
        way.append(beyond(run[-1], run[-2], tail_ext))
        if i + 1 < len(runs) and runs[i + 1]:
            j = wheel_between(run[-1], runs[i + 1][0])
            if j is not None:
                way.append((j[0], j[1]))

    if len(way) < 2:
        return False

    samples = []
    for a, b in zip(way, way[1:]):
        dist = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        steps = max(1, int(dist / STEP_PX))
        for i in range(steps):
            samples.append((a[0] + (b[0] - a[0]) * i / steps,
                            a[1] + (b[1] - a[1]) * i / steps))
    samples.append(way[-1])

    anchor = runs[0][0]
    altdriver.move_mouse(anchor, duration=0.1)
    finger = altdriver.begin_touch(anchor)
    try:
        time.sleep(0.3)
        for p in samples:
            altdriver.move_mouse(p, duration=STEP_DUR)
        time.sleep(0.3)
    finally:
        altdriver.end_touch(finger)
    return True


def pipes(altdriver):
    """Solves PIPES by dragging along each correct pipe path.

    The build exposes its own answer key: `PipesStructureHandler`
    .correctPathsAutomationInfo gives, per sentence, the ordered `pipesNames`
    plus `pipesPositions` -- the segment endpoints in WORLD units
    ("x1,y1,x2,y2").

    That key lives on the panel for the CURRENT difficulty -- Pipes_Easy_Panel,
    Pipes_Medium_Panel or Pipes_Hard_Panel -- and the round switches between
    them as it progresses. Rather than hardcode the thresholds, every panel is
    checked and whichever actually holds paths is used.

    The key gives the pipes in order but not a usable route through them --
    `_pipes_trace` works that out from what is on screen. See its docstring for
    why the coordinates in the key cannot be followed directly.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    SH_C = "com.kideo.learn.english.Pipes.PipesStructureHandler"
    ASM = "Assembly-CSharp"

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def answer_key():
        """([{sentence, pipesNames, pipesPositions}, ...], difficulty).

        The key sits on whichever difficulty panel is currently live, so check
        them all -- reading only the hard panel finds nothing once the round
        moves to medium or easy.
        """
        for e in altdriver.get_all_elements(enabled=True):
            if not (e.name.startswith("Pipes_") and e.name.endswith("_Panel")):
                continue
            try:
                v = e.get_component_property(SH_C, "correctPathsAutomationInfo", ASM)
                if v:
                    return v, e.name.replace("Pipes_", "").replace("_Panel", "")
            except Exception:
                pass
        return [], ""


    done, total = progress()
    print("[info] starting pipes at %d/%d" % (done, total))
    stuck = 0
    solved = set()

    for _ in range(60):
        done, total = progress()
        if total and done >= total:
            print("[info] all %d sentences solved." % total)
            break

        key, panel = answer_key()
        if not key:
            stuck += 1
            if stuck > 8:
                print("[warn] no correct paths exposed — stopping.")
                break
            time.sleep(1.5)
            continue

        # Medium exposes more than one sentence at a time, and a solved one can
        # still appear in the key, so skip anything already traced.
        before = done
        for path in key:
            sentence = path.get("sentence") or ""
            if sentence in solved:
                continue
            print("[act] [%s] %s" % (panel, sentence[:52]))
            try:
                if not _pipes_trace(altdriver, path, panel):
                    continue
            except Exception as e:
                print("[warn] drag failed: %s" % e)
                continue
            time.sleep(2.0)
            now, total = progress()
            if now != before:
                print("[info] progress %d/%d" % (now, total))
                solved.add(sentence)
                before = now
                time.sleep(2.5)   # let the next board finish rebuilding
                break             # the board reshuffles after a solve — re-read

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




def word_connect(altdriver, words=None, card_name=None, sleep_after_word=0.25):
    """Swipe the board's words. Reads BOTH the words and the card name from the
    game unless they are passed in.

    The defaults used to be a literal ("HIT", "GET", "EIGHTY", ...) taken from
    whatever puzzle this was written against, so calling it directly -- from the
    console, say -- tried to spell words the board could not spell, and failed
    with "Missing letter 'H'" on a board dealing B I S T C U I. The words belong
    to the puzzle, so they are asked of the puzzle.
    """
    if words is None or card_name is None:
        from Utilities import utilsdemo as _u          # local: avoids a cycle
        if card_name is None:
            _cards, _letters, found = _u._word_connect_cards(altdriver)
            card_name = found or "WordsConnectCard_4 Variant(Clone)"
        if words is None:
            words = _u.word_connect_words(altdriver)
            if not words:
                raise Exception(
                    "[ERROR] word_connect: the board's words could not be read "
                    "from the game, and none were given. Pass words=[...] or "
                    "run it where WordConnect.WordsConnect is readable.")
            print(f"[INFO] word_connect: words read from the game: {list(words)}")

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

    print(f"Matrix size: {number_of_rows}x{number_of_columns}")

    # Initialize empty matrix and letter panel mapping
    matrix = [['empty' for _ in range(number_of_columns)] for _ in range(number_of_rows)]
    letter_panels = {}
    letter_objects = {}  # Store actual AltDriver objects for swiping

    # Get all letter panels
    texts = altdriver.find_objects(By.NAME, 'Text - RTLTMP')

    # Where a letter sits is decided by WHERE IT IS, not by arithmetic on its
    # name. AltTester disambiguates same-named objects with a "_N" suffix, so
    # the old rule (base + offset) made "LetterPanel (5)_1" and "LetterPanel
    # (6)" both mean 6: panels overwrote each other and the highest positions
    # were never filled — a 9x10 board came back with its whole last row empty
    # and lost a word. A square board hid it, because the collisions landed
    # inside the grid.
    cells = []
    for text in texts:
        try:
            parent = text.get_parent()
            letter = (text.get_text() or "").strip()
            if 'LetterPanel' not in parent.name or not letter:
                continue
            cells.append({'x': float(parent.x), 'y': float(parent.y),
                          'letter': letter, 'object': parent,
                          'panel_name': parent.name})
        except Exception:                            # noqa: BLE001
            continue

    def bands(values, expected, reverse=False):
        """Cluster coordinates into ``expected`` lines of the grid.

        The tolerance is half a cell, taken from the board's OWN spread, so it
        holds at any resolution. Both axes are banded by POSITION: assigning a
        column by counting letters across a row would compact a row that has a
        blank cell and shift every letter after it one place left.
        """
        ordered = sorted(set(values), reverse=reverse)
        if not ordered:
            return []
        spread = abs(ordered[-1] - ordered[0])
        tolerance = (spread / max(1, expected - 1) / 2.0) if spread else 1.0
        out = []
        for value in ordered:
            if not out or abs(out[-1] - value) > tolerance:
                out.append(value)
        return out

    if cells:
        # Unity screen space counts y UP, so the largest y is row 0.
        row_bands = bands([c['y'] for c in cells], number_of_rows, reverse=True)
        col_bands = bands([c['x'] for c in cells], number_of_columns)
        for cell in cells:
            cell['row'] = min(range(len(row_bands)),
                              key=lambda r: abs(row_bands[r] - cell['y']))
            cell['col'] = min(range(len(col_bands)),
                              key=lambda c: abs(col_bands[c] - cell['x']))

        if len(row_bands) != number_of_rows or len(col_bands) != number_of_columns:
            print(f"[WARN] crossword: the board shows "
                  f"{len(row_bands)}x{len(col_bands)} but the activity reports "
                  f"{number_of_rows}x{number_of_columns}")

        for cell in cells:
            row, col = cell['row'], cell.get('col')
            if col is None or row >= number_of_rows or col >= number_of_columns:
                continue
            matrix[row][col] = cell['letter']
            letter_panels[(row, col)] = {
                'letter': cell['letter'], 'panel_name': cell['panel_name'],
                'row': row, 'col': col, 'object': cell['object'],
            }
            letter_objects[(row, col)] = cell['object']

    filled = sum(1 for r in matrix for c in r if c != 'empty')
    print(f"[INFO] crossword: mapped {filled}/{number_of_rows * number_of_columns} cells "
          f"from {len(cells)} lettered panel(s)")

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


def tetris(altdriver):
    """Solves TETRIS: steer falling letter cubes to build the target word.

    Letter cubes (singles like 'e' or duos like 'pi') fall down the centre of a
    grid; Left/Right arrows shift the falling piece one column per tap and the
    Down arrow hard-drops it. The word is complete the moment its letters sit
    contiguously, in order, on the bottom row -- then the board clears and the
    next word loads. Wrong-letter cubes fall too and must be kept away.

    What this activity needed, all found against the live build:

    1. The answer. RTLTMPWordPanel's TMProWordPanel uses TWO data models across
       words: phrase model (Word.word='take a picture' / Text='take a _______',
       same length -- zip the blanks) and word model (Word.word='arrive' while
       Text still shows the PREVIOUS word's stale mask -- the answer is all of
       Word.word). Handling only the first model stalls forever on the second.

    2. The game's tiling. Words arrive split into consecutive PAIRS from the
       left with a final single only for odd lengths ('ta'+'ke', 'of'+'f',
       'pi'+'ct'+'ur'+'e'). Placement must match TILES, not letters: a stray
       single 'k' must be dumped even though 'k' is the next letter of 'take',
       because the real 'ke' duo needs both its columns free. A frontier
       fallback still accepts prefix-continuing pieces if no tile shows up for
       20s, in case a word is ever split differently.

    3. Physical ground truth. The bottom row is re-read every cycle: a correct
       letter at its word column counts as placed however it got there, and a
       placed letter that vanishes means the game RESET the board (dump stacks
       reaching the ceiling do that on long words like 'comfortable') -- the
       tile is then rebuilt when the game cycles it around again.

    4. Closed-loop movement. Arrow taps can be dropped by the game, so after
       tapping the piece's real column is re-read (only within the word/spawn
       corridor -- dump stacks to the right would masquerade as the piece) and
       the shortfall corrected. Dumps go strictly RIGHT of the corridor.

    5. Geometry is live. Grid columns/rows come from the CellPanel cells (the
       grid is sized to the longest word, so nothing is hardcoded), the spawn
       column is the centre, and a reference cell's x acts as a resize sentinel
       to re-derive everything if the window changes.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    ASM = "Assembly-CSharp"
    RUN_S = 600.0
    REF_CELL = "CellPanel (7)"      # stable named grid cell = resize sentinel
    geo = {"colx": [], "rowy": [], "row_h": 50.0, "spawn": 0, "ref_x": None}

    def _bands(vals, tol=25):
        vals = sorted(vals)
        bs = []
        for v in vals:
            if bs and abs(v - bs[-1][-1]) <= tol:
                bs[-1].append(v)
            else:
                bs.append([v])
        return [sum(b) / len(b) for b in bs]

    def capture_geometry():
        xs, ys = [], []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name.startswith("CellPanel"):
                p = e.get_screen_position()
                xs.append(p[0])
                ys.append(p[1])
        if not xs:
            return False
        geo["colx"] = _bands(xs)
        geo["rowy"] = _bands(ys)
        R = len(geo["rowy"])
        geo["row_h"] = ((geo["rowy"][-1] - geo["rowy"][0]) / max(1, R - 1)
                        if R > 1 else 50.0)
        geo["spawn"] = len(geo["colx"]) // 2   # cubes spawn at the centre column
        try:
            geo["ref_x"] = altdriver.find_object(
                By.NAME, REF_CELL).get_screen_position()[0]
        except Exception:
            geo["ref_x"] = None
        return True

    def maybe_recapture():
        if geo["ref_x"] is None:
            return
        try:
            x = altdriver.find_object(By.NAME, REF_CELL).get_screen_position()[0]
            if abs(x - geo["ref_x"]) > 20:
                capture_geometry()
        except Exception:
            pass

    def col(x):
        cx = geo["colx"]
        return min(range(len(cx)), key=lambda i: abs(x - cx[i]))

    def row(y):
        ry = geo["rowy"]
        return min(range(len(ry)), key=lambda i: abs(y - ry[i]))

    ctl = {}

    def fetch_controls():
        try:
            ctl["left"] = altdriver.find_object(By.NAME, "LeftArrow")
            ctl["right"] = altdriver.find_object(By.NAME, "RightArrow ")
            ctl["down"] = altdriver.find_object(By.NAME, "DownArrow")
            return True
        except Exception:
            return False

    def progress():
        try:
            a, b = altdriver.find_object(
                By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def read_word():
        try:
            wp = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
            full = (wp.get_component_property("TMProWordPanel", "Word.word", ASM) or "")
            mask = (wp.get_component_property("TMProWordPanel", "Text", ASM) or "")
            return full, mask
        except Exception:
            return "", ""

    def target_of(full, mask):
        return "".join(fc for fc, mc in zip(full, mask) if mc == "_").lower()

    def letters_now():
        """Single-letter cubes inside the play area: (letter, x, y)."""
        out = []
        cx, ry, rh = geo["colx"], geo["rowy"], geo["row_h"]
        x_lo, x_hi = cx[0] - rh, cx[-1] + rh
        y_lo, y_hi = ry[0] - rh, ry[-1] + rh
        for e in altdriver.get_all_elements(enabled=True):
            if e.name == "Text":
                try:
                    t = (e.get_text() or "").strip().lower()
                except Exception:
                    t = ""
                if len(t) == 1 and t.isalpha():
                    p = e.get_screen_position()
                    if x_lo <= p[0] <= x_hi and y_lo <= p[1] <= y_hi:
                        out.append((t, p[0], p[1]))
        return out

    def bottom_row_letters():
        """col -> letter resting on the bottom row: the physical ground truth
        of what has been built (also reveals board resets)."""
        out = {}
        for (t, x, y) in letters_now():
            if row(y) == 0:
                out[col(x)] = t
        return out

    def active_piece():
        """The game-controlled falling piece = highest cube(s) AT the spawn
        columns (a single spawns at SPAWN, a duo at SPAWN/SPAWN+1). Capped at
        two cubes so landed neighbours never merge into a bogus piece."""
        sp = geo["spawn"]
        near = [(t, x, y) for (t, x, y) in letters_now() if col(x) in (sp, sp + 1)]
        if not near:
            return None
        top_y = max(y for (_, _, y) in near)
        if row(top_y) < 2:
            return None
        grp = sorted([(t, x) for (t, x, y) in near
                      if abs(y - top_y) < geo["row_h"] * 0.5],
                     key=lambda z: z[1])[:2]
        return ("".join(t for (t, _) in grp),
                col(min(x for (_, x) in grp)), row(top_y))

    def compute_tiles(target):
        """The game's split: consecutive pairs from the left, odd tail single.
        'picture' -> [(0,'pi'),(2,'ct'),(4,'ur'),(6,'e')]."""
        tiles, i = [], 0
        while i < len(target):
            n = 2 if i + 1 < len(target) else 1
            tiles.append((i, target[i:i + n]))
            i += n
        return tiles

    def top_anchor(max_col):
        """Leftmost column of the highest cube(s) within cols 0..max_col --
        restricted to the corridor so dump stacks never look like the piece."""
        letters = [(t, x, y) for (t, x, y) in letters_now() if col(x) <= max_col]
        if not letters:
            return None
        top_y = max(y for (_, _, y) in letters)
        if row(top_y) < 2:
            return None
        xs = [x for (t, x, y) in letters if abs(y - top_y) < geo["row_h"] * 0.5]
        return col(min(xs))

    def move_to(anchor, tc, bound):
        """Closed-loop move: spaced taps toward the target, then re-read the
        piece's real column and correct any dropped tap. Returns column reached."""
        cur = anchor
        for _ in range(5):
            shift = tc - cur
            if shift == 0:
                return cur
            btn = ctl["right"] if shift > 0 else ctl["left"]
            for _ in range(abs(shift)):
                btn.tap()
                time.sleep(0.14)
            time.sleep(0.06)
            a = top_anchor(bound)
            if a is None:
                return cur
            cur = a
        return cur

    def dump_move(anchor, tc):
        """Open-loop shove of a discarded piece (precision doesn't matter)."""
        shift = tc - anchor
        btn = ctl["right"] if shift > 0 else ctl["left"]
        for _ in range(abs(shift)):
            btn.tap()
            time.sleep(0.1)

    # ---- start early: begin the loop the moment grid+controls+word exist, so
    # the FIRST falling piece is caught high and never lands unsteered --------
    time.sleep(0.5)
    ready = False
    for _ in range(100):                    # up to ~30s for the intro
        if capture_geometry() and fetch_controls():
            full, mask = read_word()
            if target_of(full, mask) or (full and " " not in full.strip()):
                ready = True
                break
        time.sleep(0.3)
    if not ready:
        print("[warn] tetris: play screen never became ready.")
        return
    G = len(geo["colx"])
    R = len(geo["rowy"])
    print("[info] tetris: grid %dx%d, spawn col %d" % (G, R, geo["spawn"]))

    # ---- main solve loop (state persists per word) --------------------------
    t0 = time.time()
    last_log = 0.0
    dump_i = 0
    cur_full = None
    target = ""
    W = 0
    placed = []
    placed_at = []
    tiles = []
    blank_idx = []
    last_place = time.time()
    DUMP_START = G - 1

    while time.time() - t0 < RUN_S:
        maybe_recapture()
        G = len(geo["colx"])
        full, mask = read_word()
        a, b = progress()
        if b and a >= b:
            print("[info] tetris: all %d words complete." % b)
            return
        if not full:
            time.sleep(0.3)
            continue

        if full != cur_full:
            # two data models (see docstring): phrase+mask zip, or bare word
            if mask and len(full) == len(mask) and "_" in mask:
                blank_idx = [i for i, mc in enumerate(mask) if mc == "_"]
                target = "".join(full[i] for i in blank_idx).lower()
            elif " " not in full.strip():
                blank_idx = []
                target = full.strip().lower()
            else:
                if time.time() - last_log > 2.0:
                    print("   [wait] transition full=%r mask=%r" % (full, mask))
                    last_log = time.time()
                time.sleep(0.15)
                continue
            cur_full = full
            W = len(target)
            placed = [False] * W
            placed_at = [0.0] * W
            tiles = compute_tiles(target)
            last_place = time.time()
            # dumps go strictly RIGHT of the word columns AND the spawn pair
            DUMP_START = min(G - 1, max(W, geo["spawn"] + 2))
            print("[act] word %r -> build %r tiles=%s (prog %d/%d)"
                  % (full, target, tiles, a, b))
        if not target:
            time.sleep(0.3)
            continue

        # physical ground truth: reconcile with the bottom row (see docstring)
        onboard = bottom_row_letters()
        now_t = time.time()
        for j in range(W):
            if onboard.get(j) == target[j]:
                placed[j] = True
                placed_at[j] = now_t
            elif placed[j] and now_t - placed_at[j] > 3.0:
                print("   [reset] pos%d %r vanished; will rebuild" % (j, target[j]))
                placed[j] = False
        mask_fill = [(j < len(blank_idx) and blank_idx[j] < len(mask)
                      and mask[blank_idx[j]] != "_") for j in range(W)]
        filled = [placed[j] or mask_fill[j] for j in range(W)]
        if all(filled):
            time.sleep(0.4)
            continue                       # built; wait for the game to advance

        piece = active_piece()
        if piece is None:
            time.sleep(0.12)
            continue
        pl, anchor, tr = piece
        tdone = [all(filled[c] for c in range(s, s + len(lt)))
                 for (s, lt) in tiles]
        hit = next((idx for idx, (s, lt) in enumerate(tiles)
                    if lt == pl and not tdone[idx]), None)
        if hit is None:
            # frontier fallback for unexpected tilings (see docstring)
            np_ = next((j for j in range(W) if not filled[j]), W)
            if (time.time() - last_place > 20.0 and np_ < W
                    and np_ + len(pl) <= W and pl == target[np_:np_ + len(pl)]):
                tiles = tiles + [(np_, pl)]
                tdone = tdone + [False]
                hit = len(tiles) - 1
                print("   [fallback] accepting %r at frontier pos%d" % (pl, np_))
        if hit is not None:
            s, lt = tiles[hit]
            last_place = time.time()
            reached = move_to(anchor, s, bound=max(W - 1, geo["spawn"] + 1))
            ctl["down"].tap()
            if reached == s:
                for i in range(len(lt)):
                    placed[s + i] = True
                    placed_at[s + i] = time.time()
            print("   place %r cols%d..%d reached%d"
                  % (pl, s, s + len(lt) - 1, reached))
        else:
            dump_col = DUMP_START + (dump_i % max(1, G - DUMP_START))
            dump_i += 1
            dump_move(anchor, dump_col)
            ctl["down"].tap()
        time.sleep(0.5)

    a, b = progress()
    print("[warn] tetris: time budget exhausted at %d/%d." % (a, b))


def exam_swap_letters(altdriver, max_swaps_per_word=40, row_attempts=3):
    """Solve the "swap letters" exam page.

    Each row shows one word scrambled; dragging letter A onto letter B swaps
    them (verified live — a non-adjacent drag swaps, it does not insert). The
    answer for every row is on the row itself, so nothing is guessed:

        SwapWord(Clone)       -> com.kideo.learn.english.SwapTestWord.word
        SwapLetterText(Clone) -> com.kideo.learn.english.SwapTestLetter (draggable)

    Three things this has to get right, each learned the hard way on the app:

    * **Rows are addressed by INDEXED PATH**, never by matching letters to a row
      by y. The list scrolls, and a y-match across two queries silently pairs one
      row's letters with another row's word (dictionary once "solved" as repeat).
    * **The list is scrolled with the ScrollRect**, not the mouse wheel, so the
      row being worked on is really in view — a drag at off-screen coordinates
      does nothing.
    * **The gesture is a MOUSE press-move-release.** On WindowsEditor the
      EventSystem is mouse-driven and simulated touch is ignored.

    Each row is verified against the game and retried before moving to the next,
    so a drag that does not register is caught immediately rather than leaving
    the page unsolvable (the page refuses to advance while any row is wrong).
    """
    def rows_count():
        return len(altdriver.find_objects(By.NAME, "SwapWord(Clone)"))

    def row_word(i):
        try:
            row = altdriver.find_object(By.PATH, f"//SwapWord(Clone)[{i}]")
            return row.get_component_property(
                "com.kideo.learn.english.SwapTestWord", "word", "Assembly-CSharp")
        except Exception:
            return None

    def row_letters(i):
        """The letter objects of row i only — by hierarchy, so never mismatched."""
        try:
            return altdriver.find_objects(By.PATH, f"//SwapWord(Clone)[{i}]/LettersContainer/*")
        except Exception:
            return []

    def texts(objs):
        out = []
        for o in objs:
            try:
                # a blank slot is the space in a phrase ("find out")
                out.append(((o.get_text() or " ").strip() or " ").lower())
            except Exception:
                out.append(" ")
        return out

    def scroll_to_row(i, total):
        """Put row i in view. 1.0 is the top of the list, 0.0 the bottom."""
        if total < 2:
            return
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            value = max(0.0, min(1.0, 1.0 - (i / float(total - 1))))
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI", value)
            time.sleep(0.45)
        except Exception as e:
            print(f"[WARN] could not scroll to row {i}: {e}")

    def swap(a, b):
        altdriver.move_mouse([a.x, a.y], duration=0.1, wait=True)
        altdriver.key_down(alttester.AltKeyCode.Mouse0)
        time.sleep(0.15)
        altdriver.move_mouse([b.x, b.y], duration=0.25, wait=True)
        time.sleep(0.15)
        altdriver.key_up(alttester.AltKeyCode.Mouse0)
        time.sleep(0.4)

    total = rows_count()
    words = [row_word(i) for i in range(total)]
    print(f"[INFO] swap-letters exam: {total} word(s) -> {words}")

    unsolved = []
    for i, word in enumerate(words):
        if not word:
            continue
        want = list(word.lower())
        solved = False

        for attempt in range(1, row_attempts + 1):
            scroll_to_row(i, total)
            have = texts(row_letters(i))
            if have == want:
                solved = True
                break
            if len(have) != len(want):
                print(f"[WARN] '{word}': {len(have)} letters on screen, expected {len(want)}")
                break

            swaps = 0
            for k in range(len(want)):
                if have[k] == want[k]:
                    continue
                j = next((m for m in range(k + 1, len(have)) if have[m] == want[k]), None)
                if j is None:
                    break
                objs = row_letters(i)              # fresh coordinates for this drag
                if len(objs) != len(have):
                    break
                swap(objs[k], objs[j])
                have[k], have[j] = have[j], have[k]
                swaps += 1
                if swaps >= max_swaps_per_word:
                    break

            # verify against the GAME before moving on, not against my own model
            actual = texts(row_letters(i))
            if actual == want:
                print(f"[INFO] '{word}' solved ({swaps} swap(s), attempt {attempt})")
                solved = True
                break
            print(f"[WARN] '{word}' is '{''.join(actual)}' after attempt {attempt} — retrying")

        if not solved:
            unsolved.append(word)

    if unsolved:
        print(f"[WARN] rows still unsolved: {unsolved}")
    else:
        print("[INFO] all rows solved")


def exam_shuffled_context(altdriver, question_attempts=3):
    """Solve the shuffled-context (sentence building) exam page.

    Each question is a sentence with blanks and a bank of words underneath.
    Nothing has to be guessed, because both sides name themselves:

        WordSpace(Clone)             -> SpaceToFillWithWord.word    (what this blank wants)
        WordInShuffledContext(Clone) -> WordInShuffledContext.word  (what this tile is)

    so every bank tile is dragged onto the blank carrying the same word. A tile
    already sitting on its blank is left alone.

    Same three rules as the swap-letters page, for the same reasons: questions
    are addressed by INDEXED PATH (never matched by y), the list is scrolled
    with the ScrollRect so the question is really in view, and the gesture is a
    MOUSE press-move-release. Each question is verified and retried before
    moving to the next.
    """
    Q = "//QuestionInShuffledContextTest(Clone)"

    def questions():
        return len(altdriver.find_objects(By.NAME, "QuestionInShuffledContextTest(Clone)"))

    def slots(i):
        try:
            return altdriver.find_objects(By.PATH, f"{Q}[{i}]/SpacesPanel/*")
        except Exception:
            return []

    def tiles(i):
        try:
            return altdriver.find_objects(By.PATH, f"{Q}[{i}]/WordsPanel/*")
        except Exception:
            return []

    def word_of(obj, component):
        try:
            return (obj.get_component_property(component, "word", "Assembly-CSharp") or "").strip()
        except Exception:
            return ""

    def on_slot(tile, slot):
        """A tile is in a blank when it is sitting on top of it."""
        return abs(tile.x - slot.x) < 25 and abs(tile.y - slot.y) < 30

    def scroll_to(i, total):
        if total < 2:
            return
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI",
                                        max(0.0, min(1.0, 1.0 - (i / float(total - 1)))))
            time.sleep(0.45)
        except Exception as e:
            print(f"[WARN] could not scroll to question {i}: {e}")

    def drag(a, b):
        altdriver.move_mouse([a.x, a.y], duration=0.1, wait=True)
        altdriver.key_down(alttester.AltKeyCode.Mouse0)
        time.sleep(0.15)
        altdriver.move_mouse([b.x, b.y], duration=0.3, wait=True)
        time.sleep(0.15)
        altdriver.key_up(alttester.AltKeyCode.Mouse0)
        time.sleep(0.4)

    def missing(i):
        """[(slot, wanted_word)] for blanks that have no tile on them."""
        sl, tl = slots(i), tiles(i)
        out = []
        for s in sl:
            if not any(on_slot(t, s) for t in tl):
                out.append((s, word_of(s, "SpaceToFillWithWord")))
        return out

    # --- reaching a tile that is not on screen -----------------------------
    # A long sentence pushes the bottom of the word bank past the viewport. The
    # tile still EXISTS in the hierarchy, so the drag was issued happily — at
    # coordinates outside the visible area, where it does nothing. The blank
    # then stayed empty, every retry repeated it, and the page stalled. So the
    # rule is the same one the language picker needed: prove it is reachable
    # before acting on it.
    try:
        screen_w, screen_h = (float(v) for v in altdriver.get_application_screensize())
    except Exception as e:                       # noqa: BLE001
        print(f"[WARN] could not read the screen size: {e}")
        screen_w = screen_h = 0.0

    def visible(obj, margin=0.05):
        """Is this object inside the viewport, so a gesture can reach it?"""
        if not screen_h:
            return True                          # unknown screen: don't block
        mx, my = screen_w * margin, screen_h * margin
        return (mx <= obj.x <= screen_w - mx) and (my <= obj.y <= screen_h - my)

    def scroll_position(delta=None):
        """Read (or nudge by ``delta``) the list's scroll. Returns it, or None."""
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            pos = float(view.get_component_property(
                "UnityEngine.UI.ScrollRect", "verticalNormalizedPosition", "UnityEngine.UI"))
            if delta is None:
                return pos
            pos = max(0.0, min(1.0, pos + delta))
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI", pos)
            time.sleep(0.3)
            return pos
        except Exception:
            return None

    def settled(i, slot_idx, tile_idx, tries=6, pause=0.25):
        """(slot, tile) once the board has STOPPED moving under them.

        Placing a word takes it out of the bank and the words still waiting
        REFLOW into the gap. A position read while that is happening describes
        where the tile WAS, so the drag starts from empty space and silently
        does nothing — which is exactly how one word of a long sentence stayed
        behind while every shorter sentence passed.
        """
        previous = None
        for _ in range(tries):
            sl, tl = slots(i), tiles(i)
            if slot_idx >= len(sl) or tile_idx >= len(tl):
                return None, None
            slot, tile = sl[slot_idx], tl[tile_idx]
            here = (tile.x, tile.y, slot.x, slot.y)
            if previous == here:
                return slot, tile
            previous = here
            time.sleep(pause)
        return slot, tile

    def place(i, slot_idx, tile_idx, wanted, attempts=3):
        """Drag one word into its blank and PROVE it landed. Returns bool.

        Verified per WORD, not per pass: an unverified drag left the whole
        question to be replayed, and the replay read the same moving board and
        failed the same way, three times over.
        """
        for attempt in range(1, attempts + 1):
            target, pick = settled(i, slot_idx, tile_idx)
            if target is None or pick is None:
                return False
            if on_slot(pick, target):
                return True                      # already there
            if not (visible(target) and visible(pick)):
                target, pick = in_view(i, slot_idx, tile_idx)
                if target is None or pick is None or not (visible(target) and visible(pick)):
                    print(f"[WARN] q{i + 1}: could not bring '{wanted}' into view")
                    return False
            drag(pick, target)
            sl, tl = slots(i), tiles(i)
            if (slot_idx < len(sl) and tile_idx < len(tl)
                    and on_slot(tl[tile_idx], sl[slot_idx])):
                return True
            print(f"[WARN] q{i + 1}: '{wanted}' did not land (attempt {attempt}/{attempts})")
        return False

    def in_view(i, slot_idx, tile_idx, steps=10):
        """(slot, tile) once BOTH are on screen, re-found after each nudge.

        Re-finding matters: an AltObject's x/y is a snapshot from when it was
        found, so positions read before a scroll describe where things WERE.
        """
        for _ in range(steps):
            sl, tl = slots(i), tiles(i)
            if slot_idx >= len(sl) or tile_idx >= len(tl):
                return None, None
            slot, tile = sl[slot_idx], tl[tile_idx]
            if visible(slot) and visible(tile):
                return slot, tile
            off = tile if not visible(tile) else slot
            # Unity screen space puts y=0 at the BOTTOM, so a small y means the
            # object sits below the viewport and the list must scroll down
            # (verticalNormalizedPosition: 1 = top, 0 = bottom).
            if scroll_position(-0.08 if off.y < screen_h / 2 else 0.08) is None:
                break
        sl, tl = slots(i), tiles(i)
        if slot_idx < len(sl) and tile_idx < len(tl):
            return sl[slot_idx], tl[tile_idx]
        return None, None

    total = questions()
    print(f"[INFO] shuffled-context exam: {total} question(s)")

    unsolved = []
    for i in range(total):
        sentence = " ".join(word_of(s, "SpaceToFillWithWord") for s in slots(i))
        done = False

        for attempt in range(1, question_attempts + 1):
            scroll_to(i, total)
            gaps = missing(i)
            if not gaps:
                done = True
                break

            # Read every word ONCE per attempt. The old loop re-queried the
            # slots and tiles for each gap and asked each tile for its word
            # again, so a question with a dozen blanks and a dozen tiles cost
            # hundreds of round trips — and paid them again on every retry.
            sl, tl = slots(i), tiles(i)
            slot_words = [word_of(s, "SpaceToFillWithWord") for s in sl]
            tile_words = [word_of(t, "WordInShuffledContext") for t in tl]
            # Tiles already sitting in a blank are not available to move.
            used = {ti for ti, t in enumerate(tl) if any(on_slot(t, s) for s in sl)}

            for si, slot in enumerate(sl):
                if any(on_slot(t, slot) for t in tl):
                    continue                     # this blank is already filled
                wanted = slot_words[si]
                ti = next((k for k, w in enumerate(tile_words)
                           if k not in used and w == wanted), None)
                if ti is None:
                    print(f"[WARN] q{i + 1}: no free tile for '{wanted}'")
                    continue
                used.add(ti)
                place(i, si, ti, wanted)

            gaps_after = missing(i)
            if not gaps_after:
                print(f"[INFO] q{i + 1} solved (attempt {attempt}): {sentence}")
                done = True
                break
            print(f"[WARN] q{i + 1} still missing "
                  f"{[w for _s, w in gaps_after]} after attempt {attempt}")

        if not done:
            unsolved.append(sentence)

    if unsolved:
        print(f"[WARN] questions still unsolved: {unsolved}")
    else:
        print("[INFO] all questions solved")


def signs(altdriver, max_rounds=12, round_timeout=25, play_all_modes=False, max_entries=3):
    """Letters Sorting ("signs"). See _signs_entry for how a board is solved.

    ``play_all_modes=False`` (default): solve the round that is open and return.
    Unchanged behaviour for solve_activity_in_level and the lesson-range runs,
    which navigate themselves.

    ``play_all_modes=True``: also handle the navigation between modes — the
    modes do not follow each other in place, so after each entry this goes back
    ONE screen to the activity selection and re-enters the same activity. The
    activity is found by trying thumbs until the LettersSorting scene loads
    again, which works whatever language the thumb titles are in (this account
    shows them in Arabic).
    """
    played = _signs_entry(altdriver, max_rounds=max_rounds, round_timeout=round_timeout)
    if not play_all_modes:
        return played

    total_boards = played
    for entry in range(2, max_entries + 1):
        if not _reenter_signs(altdriver):
            print("[INFO] no further Signs mode to play")
            break
        print(f"[INFO] Signs entry {entry}")
        played = _signs_entry(altdriver, max_rounds=max_rounds, round_timeout=round_timeout)
        total_boards += played
        if played == 0:
            break
    print(f"[INFO] Signs activity complete — {total_boards} board(s) across all modes")
    return total_boards


def _reenter_signs(altdriver, timeout=40):
    """Leave a finished Signs entry and open the activity again.

    ONE back click reaches the activity selection (two would drop to the map).
    The right thumb is found by opening thumbs until LettersSorting loads, so
    no thumb title has to be recognised — titles are localised.
    """
    # Only leave if we are actually inside an activity — calling the exit from
    # the selection screen just logs failed clicks.
    try:
        inside = altdriver.get_current_scene() != "ActivitySelectionScene"
    except Exception:
        inside = True
    if inside:
        try:
            when_finish_activity(altdriver)
        except Exception as e:
            print(f"[WARN] could not leave the activity: {e}")
        time.sleep(4)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if altdriver.get_current_scene() == "ActivitySelectionScene":
            break
        time.sleep(1.5)
    else:
        print(f"[WARN] activity selection not reached "
              f"(now: {altdriver.get_current_scene()})")
        return False

    for index in range(6):
        # Re-read the thumbs every time: backing out of the wrong activity
        # reloads the screen, and the handles from before are stale.
        activities = list_level_activities(altdriver)
        if index >= len(activities):
            break
        activity = activities[index]
        try:
            activity["thumb"].click()
        except Exception as e:
            print(f"[WARN] thumb {index} click failed: {e}")
            continue
        time.sleep(7)
        scene = altdriver.get_current_scene()
        if scene == "LettersSorting":
            print(f"[INFO] re-entered Signs via thumb {index} "
                  f"({activity.get('title') or 'untitled'})")
            return True
        # wrong activity — back out and try the next thumb
        print(f"[INFO] thumb {index} opened '{scene}', not Signs; going back")
        try:
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:
            when_finish_activity(altdriver)
        time.sleep(5)
    return False


# ----------------------------------------------------------------
# LETTERS_TRACING — "Magic Trace"
#
# The board is the IndieStudio EnglishTracingBook rig:
#
#   <X>-letter-shape            [Shape]        completed = whole letter done
#     Content/Paths
#       Path-1-2                [TracingPath]  completed / tracedPoints
#         Curve                 [Curve]        ENABLED only while this stroke
#           Point0..PointN                     is the one to draw next
#       Path-2-3 ... Path-N-M
#       FirstNumber / SecondNumber (the numbered circles, one pair per path)
#
# The strokes are ordered and the game hands them out one at a time: the only
# stroke you may draw is the one whose Curve is enabled. Its Point children are
# the collider dots the finger has to cross, and AltTester reports their live
# screen position — so the solver reads every coordinate off a named object and
# never assumes a resolution or a letter shape. A curved stroke simply carries
# more Points, and tracing through them in order follows the curve.
#
# A letter is drawn 4 times (ProgressText "n/4"); the same shape object is reset
# between repetitions rather than replaced. When the capital round is done the
# game switches to the lower round and the same loop draws the small letter.
# ----------------------------------------------------------------
_LT_ASM = "Assembly-CSharp"
_LT_PATH = "IndieStudio.EnglishTracingBook.Game.TracingPath"
_LT_MANAGER = "com.kideo.learn.english.LettersTracingGameManager"

# Floor for a stroke gesture, in seconds. Measured live: 0.10 tunnels past the
# point colliders and the stroke does not register, 0.15 and 0.30 both land.
_LT_MIN_SWIPE = 0.25

# Extra samples held on the stroke's last point so the finger registers there
# before it lifts. Without them a stroke ends on tracedPoints=1 of 2.
_LT_END_DWELL = 6


def _lt_read_board(altdriver):
    """Every stroke of the letter on screen, in drawing order.

    Points are read with enabled=False too: the game disables the dots of every
    stroke but the current one, and we still want their positions so a stroke
    can be recognised before it goes live.
    """
    try:
        elements = altdriver.get_all_elements(enabled=False)
    except Exception:
        # The board is torn down the moment the activity ends; a read that
        # lands mid-teardown is "no strokes left", not a failure.
        return []
    children = {}
    for obj in elements:
        children.setdefault(obj.transformParentId, []).append(obj)

    paths_nodes = [o for o in elements if o.name == "Paths" and o.enabled]
    if not paths_nodes:
        return []

    def path_order(obj):
        return [int(n) for n in re.findall(r"\d+", obj.name)]

    def point_order(obj):
        return int(re.sub(r"\D", "", obj.name) or 0)

    board = []
    for path in sorted([c for c in children.get(paths_nodes[0].transformId, [])
                        if c.name.startswith("Path-")], key=path_order):
        points, live = [], False
        for curve in [c for c in children.get(path.transformId, []) if c.name == "Curve"]:
            live = live or curve.enabled
            for dot in sorted([d for d in children.get(curve.transformId, [])
                               if d.name.startswith("Point")], key=point_order):
                points.append((float(dot.x), float(dot.y)))
        board.append({"obj": path, "name": path.name, "live": live, "points": points})
    return board


def _lt_path_completed(path):
    try:
        return bool(path["obj"].get_component_property(_LT_PATH, "completed", _LT_ASM))
    except Exception:
        return False


def _lt_path_alive(path):
    """False once the stroke's object is gone.

    The letter shape is rebuilt at activity start and whenever the round flips,
    which leaves the handles from an earlier board pointing at destroyed
    objects. Retracing those coordinates draws nothing; the board has to be
    read again instead.
    """
    try:
        path["obj"].get_component_property(_LT_PATH, "completed", _LT_ASM)
        return True
    except Exception:
        return False


def _lt_active(board):
    """The stroke the game is waiting for, or None."""
    for path in board:
        if path["live"] and len(path["points"]) >= 2 and not _lt_path_completed(path):
            return path
    return None


def _lt_progress(altdriver):
    """(done, total) off ProgressText, or (None, None) while it is missing."""
    try:
        done, total = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(done), int(total)
    except Exception:
        return None, None


def _lt_round(altdriver):
    """Name + letterType (0 = capital, 1 = small) of the round being played."""
    try:
        manager = altdriver.find_object(By.NAME, "LettersTracingGameManager")
        current = manager.get_component_property(_LT_MANAGER, "currentRound", _LT_ASM, max_depth=1)
        return current.get("name"), current.get("letterType")
    except Exception:
        return None, None


def _lt_feedback_up(altdriver):
    """True once the end-of-activity feedback is on screen."""
    try:
        return altdriver.find_object(By.NAME, _LT_FEEDBACK) is not None
    except Exception:
        return False


def _lt_wait_for_letter(altdriver, timeout=30.0, poll=0.25, stable_reads=3):
    """Every stroke of the next letter, once it is live AND has stopped moving.

    Returns the WHOLE letter rather than one stroke: within a letter the shape
    does not move, so reading it once and then drawing 1->2, 3->4, 5->6 in order
    costs one board read instead of one per stroke. A board read is the most
    expensive call in this solver (~0.35s over ~2800 objects), so this is where
    most of the time went.

    The letter still animates in after every repetition and again when the round
    flips to the small letter; dots grabbed mid-animation trace a path that is
    no longer where the letter is, and the ease-out tail means two matching
    reads can still catch it drifting — hence three in a row before it counts as
    settled.
    """
    deadline = time.time() + timeout
    previous, repeats = None, 0
    while time.time() < deadline:
        # The finished activity keeps a board on screen behind the feedback, so
        # without this the solver traces the same letter over and over into a
        # game that has already ended, then waits out the whole idle timeout.
        if _lt_feedback_up(altdriver):
            return None
        board = _lt_read_board(altdriver)
        if _lt_active(board) is not None:
            current = [path["points"] for path in board]
            repeats = repeats + 1 if previous == current else 1
            previous = current
            if repeats >= stable_reads:
                return board
        else:
            previous, repeats = None, 0
        time.sleep(poll)
    return None


def _lt_trace(altdriver, points, height):
    """Draw one stroke as a single gesture: press on the first point, glide
    through the rest, release on the last one.

    `swipe()` presses and lifts on every call, so a stroke built out of swipes
    is really N separate taps and the game drops it. A held begin/move/end
    works but costs a round trip per sample — ~70 of them, 1.2s, for one
    stroke. `multipoint_swipe` is the same gesture in ONE command.

    Duration is what actually decides whether it registers, not the number of
    samples: the engine walks the gesture over that many seconds of frames, and
    measured live, 0.10s tunnels straight past the point colliders while 0.15s
    and 0.30s both land. So the duration is scaled to the stroke's own length
    with a floor well above the failing edge.
    """
    step = max(4.0, height * 0.02)
    samples = [points[0]]
    span = 0.0
    for start, end in zip(points, points[1:]):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        span += length
        slices = max(1, int(length / step))
        for i in range(1, slices + 1):
            ratio = i / slices
            samples.append((start[0] + (end[0] - start[0]) * ratio,
                            start[1] + (end[1] - start[1]) * ratio))

    # Sit on the last point for a few frames before letting go, so the release
    # is not simulated in the same instant the finger arrives.
    #
    # Honest note: this was added to cure the stroke that comes back
    # tracedPoints=1 of 2, and it did NOT cure it -- that stumble still happens
    # on the first stroke after a letter resets. It is kept because it costs six
    # samples inside a gesture that is sent as one command, and ending a drag
    # with a dwell is the safer shape either way. The real cause is still open.
    samples.extend([samples[-1]] * _LT_END_DWELL)

    duration = max(_LT_MIN_SWIPE, span / height * 0.6)
    altdriver.multipoint_swipe([list(sample) for sample in samples], duration=duration)


def _lt_wait_completed(path, timeout=1.0, poll=0.05):
    """Poll the stroke's own `completed` flag instead of sleeping a fixed beat.

    A completed stroke confirms in ~0.02s, so the old flat 0.6s wait after every
    stroke was almost entirely dead time.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _lt_path_completed(path):
            return True
        time.sleep(poll)
    return False


def _lt_dismiss_dialogs(altdriver):
    """Clear the confirm/booster popups that swallow touches while they are open."""
    for dialog, button in (("ResetShapeConfirmDialog", "NoButton"),
                           ("RenewHelpBoosterDialog", "NoButton")):
        try:
            popup = altdriver.find_object(By.NAME, dialog)
            if not popup.get_component_property("UnityEngine.GameObject", "activeInHierarchy",
                                                "UnityEngine.CoreModule"):
                continue
        except Exception:
            continue
        try:
            popup.find_object_from_object(By.NAME, button).click()
            print(f"[INFO] dismissed {dialog}")
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] could not dismiss {dialog}: {e}")


_LT_FEEDBACK = "FeedbackPopup(Clone)"


def _lt_exit_feedback(altdriver, timeout=25.0, poll=1.0):
    """Close the end-of-activity feedback so the app returns to activity selection.

    The run ends on FeedbackPopup(Clone); until its ExitButton is clicked the
    app sits in LETTERS_TRACING behind the popup and whatever runs next opens
    on top of it. Nothing on this screen is read or graded — it is only closed.
    The button is clicked as an object, never at a coordinate.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            popup = altdriver.find_object(By.NAME, _LT_FEEDBACK)
            popup.find_object_from_object(By.NAME, "ExitButton").click()
            print("[INFO] closed the final feedback popup")
            return True
        except Exception:
            time.sleep(poll)
    print("[WARN] final feedback popup never appeared — nothing to close")
    return False


def letters_tracing(altdriver, stroke_attempts=3, idle_timeout=30.0):
    """Trace every letter of the Magic Trace activity, capital round then small.

    Reads the letter once, then draws its strokes in the order the letter is
    written — 1 to 2, then 3 to 4, then 5 to 6 — each as one gesture that
    releases on its final point. Still state driven: the letter, the number of
    strokes, the repetitions and the rounds all come from the board, so it
    follows however the activity is configured without being told any of them.
    """
    print("[INFO] LETTERS_TRACING: starting")

    _width, height = (float(v) for v in altdriver.get_application_screensize())

    strokes = 0
    letters = 0
    rounds_seen = []
    last_round, last_type = _lt_round(altdriver)
    if last_round:
        rounds_seen.append(last_round)
        print(f"[INFO] round '{last_round}' "
              f"({'capital' if last_type == 0 else 'small'} letters)")

    while True:
        _lt_dismiss_dialogs(altdriver)

        board = _lt_wait_for_letter(altdriver, timeout=idle_timeout)
        if board is None:
            print("[INFO] no stroke offered any more — activity finished")
            break

        # A new round means the small-letter half started; say so, it is the
        # part of this activity that is easiest to silently skip.
        name, letter_type = _lt_round(altdriver)
        if name and name != last_round:
            rounds_seen.append(name)
            print(f"[INFO] round changed to '{name}' "
                  f"({'capital' if letter_type == 0 else 'small'} letters)")
            last_round, last_type = name, letter_type

        # Walk the strokes in writing order off the one board read.
        for index in range(len(board)):
            stroke = board[index]
            if _lt_path_completed(stroke):
                continue                      # already drawn, e.g. after a retry

            drawn = False
            for attempt in range(1, stroke_attempts + 1):
                _lt_trace(altdriver, stroke["points"], height)
                if _lt_wait_completed(stroke):
                    strokes += 1
                    drawn = True
                    break
                stale = not _lt_path_alive(stroke)
                print(f"[WARN] {stroke['name']} did not register "
                      f"(attempt {attempt}/{stroke_attempts}) — "
                      f"{'board went stale, re-reading' if stale else 'retrying'}")
                # A settled letter is worth simply drawing again: one gesture,
                # far cheaper than going back to the board. But a stale handle
                # can only be fixed by re-reading, and retracing it would draw
                # into nothing — so that case never waits for a second failure.
                if stale or attempt >= 2:
                    refreshed = _lt_wait_for_letter(altdriver, timeout=12.0)
                    if refreshed is not None and index < len(refreshed):
                        board = refreshed
                        stroke = board[index]
            if not drawn:
                raise AssertionError(
                    f"LETTERS_TRACING: stroke {stroke['name']} would not complete "
                    f"after {stroke_attempts} attempts")

        done, total = _lt_progress(altdriver)
        if done is not None and done != letters:
            letters = done
            print(f"[INFO] letter traced — progress {done}/{total} in '{last_round}'")

    done, total = _lt_progress(altdriver)
    closed = _lt_exit_feedback(altdriver)

    print(f"LETTERS_TRACING RESULT: {strokes} strokes drawn across rounds "
          f"{rounds_seen or ['unknown']}; final progress {done}/{total}; "
          f"final feedback {'closed' if closed else 'not seen'}. "
          f"Traced with real finger drags over the game's own stroke points; "
          f"the score and stars on the feedback screen are not asserted.")
