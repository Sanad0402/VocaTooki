"""Quiz-style activities: fill-in, sentence translation (spiders), echo order, translation wiz,
gap guru, type-it-right, words matching (moving), unscramble (lexi match).

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.solvers.text_utils import is_rtl, normalize_text
from vocatooki.ui_actions import click_by_name


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
