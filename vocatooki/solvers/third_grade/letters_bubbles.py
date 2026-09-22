"""3rd grade - LETTERS_BUBBLES: pop the bubbles holding the right letters.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import logging
import time

from alttester import By


def bubbels_activity_3rd(altdriver, max_rounds=10):
    """
    Solves the LettersBubbles activity by clicking correct letter bubbles,
    without relying on the Exit button to break the loop.
    """
    logging.info("[Bubbles] Starting LettersBubbles activity")
    time.sleep(2)

    # Get the mode if needed (unused in logic currently)
    activity = altdriver.find_object(By.NAME, "LettersBubbles_activity")
    mode = int(activity.get_component_property(
        "com.kideo.learn.english.LettersBubblesActivityManagement",
        "sessionData_.LettersActivityPlayMode", "Assembly-CSharp"))

    # Get the target letter
    target = altdriver.find_objects(By.NAME, "WordPanel")[0]\
        .get_component_property("WordPanel", "Word.letter", "Assembly-CSharp").lower().strip()

    rounds = 0
    while rounds < max_rounds:
        bubbles = altdriver.find_objects(By.NAME, "LettersBubble(Clone)")
        found_match = False

        for bubble in bubbles:
            text = None
            try:
                text = bubble.get_component_property("com.kideo.learn.english.LettersBubble", "alphabet.letter", "Assembly-CSharp")
            except:
                pass
            if not text:
                try:
                    text = bubble.get_component_property("com.kideo.learn.english.LettersBubble", "alphabet.word", "Assembly-CSharp")
                except:
                    continue

            if text:
                text = text.lower().strip()
                if text == target or text.startswith(target):
                    try:
                        bubble.click()
                        found_match = True
                        logging.debug(f"[Bubbles] Clicked on bubble with text: {text}")
                    except:
                        logging.warning(f"[Bubbles] Failed to click bubble with text: {text}")

        if not found_match:
            logging.info("[Bubbles] No more matching bubbles found. Assuming activity is done.")
            break

        time.sleep(3)
        rounds += 1

    logging.info("[Bubbles] Activity complete, attempting to exit")
