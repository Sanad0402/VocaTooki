"""GAP_GURU: choose the missing word for each gap.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.solvers.text_utils import normalize_text
from vocatooki.ui_actions import click_by_name


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
