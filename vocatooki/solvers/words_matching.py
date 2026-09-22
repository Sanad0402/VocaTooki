"""WORDS_MATCHING_QUIZ (moving): match each word to its meaning.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


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
