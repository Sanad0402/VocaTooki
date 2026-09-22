"""UNSCRAMBLE_QUIZ (lexi match): unscramble the letters into the word.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


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
