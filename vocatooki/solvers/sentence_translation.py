"""SENTENCE_TRANSLATION_QUIZ (spiders): match the sentence to its translation.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


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
