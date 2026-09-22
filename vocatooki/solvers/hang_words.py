"""HANGWORDS: guess the word letter by letter.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


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
