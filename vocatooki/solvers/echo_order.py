"""ECHO_ORDER: put the words in the order they were said.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.solvers.text_utils import normalize_text
from vocatooki.ui_actions import click_by_name


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
