"""SEARCH: find the words in the letter grid.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.solvers.text_utils import is_rtl


def search(altdriver):
    """Automates the Search activity by matching and tapping letters."""
    progress = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progress.split('/')[1])

    for _ in range(number_of_words):

        # Wait for screen to settle
        time.sleep(1)

        full_text = altdriver.find_object(By.NAME, "WordPanel") \
            .get_component_property("WordPanel", "Word.ToLower", "Assembly-CSharp")

        current_text = altdriver.find_object(By.NAME, "RTLTMPWordPanel") \
            .get_component_property("TMProWordPanel", "Text", "Assembly-CSharp")

        # Hebrew/Arabic: the RTL panel reports its Text in visual (reversed)
        # order while WordPanel.Word is logical order, so reverse current_text
        # to align the underscores with full_text before diffing.
        if is_rtl(full_text):
            current_text = current_text[::-1]

        differences = [char2 for char1, char2 in zip(current_text, full_text)
                       if char1 == "_" and char2 != "_"]

        for letter in differences:

            # Re-scan before each click → sequential clicking
            letters = altdriver.find_objects(By.NAME, "SearchObj(Clone)")
            covers = altdriver.find_objects(By.NAME, "CoverObj")

            letter_obj_pairs = [
                (l.get_component_property("com.kideo.learn.english.SearchObj", "letter", "Assembly-CSharp").lower(), o)
                for l, o in zip(letters, covers)
            ]

            for ltr, obj in letter_obj_pairs:
                if ltr == letter:
                    obj.tap(count=1, interval=0.5, wait=True)

                    # Wait for Unity to update between letters
                    time.sleep(0.7)
                    break

        # ✅ Wait 5 seconds before going to the next word
        time.sleep(5)

    print("[INFO] Search activity complete")
