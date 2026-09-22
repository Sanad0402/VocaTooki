"""SENTENCE_COMPLETION_QUIZ (fill in): pick the word that completes the sentence.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


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
