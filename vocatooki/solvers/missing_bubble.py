"""MISSING_BUBBLE: pop the bubbles holding the missing word.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import alttester
import time

from alttester import By

from vocatooki.solvers.text_utils import normalize_text


def bubbels(altdriver):
    """Solves the Missing Bubble activity by identifying and clicking missing letters with detailed logs."""
    print("[INFO] Starting Bubbels activity...")

    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    print(f"[INFO] Total words to solve: {num_words}")

    for i in range(num_words):
        print(f"[INFO] Solving word {i + 1} of {num_words}")
        time.sleep(4.5)

        full_word = altdriver.find_object(By.NAME, "BubblesGameManager").get_component_property(
            "com.kideo.learn.english.BubblesGameManager", "newWord", "Assembly-CSharp"
        )
        print(f"[CONTEXT] Full target word: {full_word}")

        partial_word = altdriver.find_object(By.NAME, "text").get_text()
        print(f"[DEBUG] Partial word shown to user: {partial_word}")

        bg_name = altdriver.find_object(By.NAME, "bubbles_activity").get_component_property(
            "com.kideo.learn.english.BubblesActivityManagerScript", "currentBackground_.name", "Assembly-CSharp"
        )

        bubble_path = f"Bubble_{bg_name}" if bg_name in ['FairyTales(Clone)', 'Moon(Clone)', 'Candy(Clone)'] else "Bubble(Clone)"
        text_path = "Text_1"

        missing_letters = [c2 for c1, c2 in zip(partial_word, full_word) if c1 == "_" and c2 != "_"]
        print(f"[DEBUG] Missing letters to find: {missing_letters}")

        while missing_letters:
            try:
                bubbles = list(zip(
                    altdriver.find_objects(By.NAME, text_path),
                    altdriver.find_objects(By.NAME, bubble_path)
                ))
                for letter in missing_letters[:]:
                    for label, obj in bubbles:
                        label_text = normalize_text(label.get_text())
                        target_letter = normalize_text(letter)

                        if label_text == target_letter:
                            obj.click()
                            print(f"[INFO] Clicked bubble: {letter}")
                            missing_letters.remove(letter)
                            break
            except alttester.exceptions.NotFoundException:
                print("[WARN] Bubble objects not found, retrying...")
                time.sleep(0.5)
            time.sleep(0.5)

        print(f"[INFO] Word {i + 1} ('{full_word}') completed")

    print("[INFO] Bubbels activity complete")
