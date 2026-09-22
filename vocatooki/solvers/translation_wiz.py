"""TRANSLATION_WIZ: build the translated sentence from word tiles.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.ui_actions import click_by_name


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
