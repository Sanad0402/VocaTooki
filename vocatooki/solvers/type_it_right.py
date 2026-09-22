"""TYPE_IT_RIGHT: type the word letter by letter.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.solvers.text_utils import is_rtl, normalize_text
from vocatooki.ui_actions import click_by_name


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
