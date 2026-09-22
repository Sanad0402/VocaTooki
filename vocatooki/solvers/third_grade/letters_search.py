"""3rd grade - LETTERS_SEARCH: find the letters in the grid.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def search_3rd(altdriver):
    time.sleep(10)
    """Performs the letter search activity (3rd grade version) – clicks words that match, start with, or contain the target letter."""

    try:
        # Step 1: Get the activity mode (to know if it's 1 round or 2 rounds)
        mode = int(altdriver.find_object(By.NAME, "LettersSearch_activity")\
            .get_component_property("com.kideo.learn.english.LettersSearchActivityManagement",
                                    "sessionData_.LettersActivityPlayMode", "Assembly-CSharp"))
    except Exception as e:
        print(f"[ERROR] Failed to get play mode: {e}")
        return

    # Step 2: Get the target letter from the first WordPanel
    try:
        target_wordpanel = altdriver.find_objects(By.NAME, "WordPanel")[0]
        target_letter_raw = target_wordpanel.get_component_property("WordPanel", "Word.letter", "Assembly-CSharp")

        if not target_letter_raw:
            print("[ERROR] Target letter is None or empty! Exiting activity.")
            return

        target = target_letter_raw.lower()
        print(f"[INFO] Target letter: '{target}'")
    except Exception as e:
        print(f"[ERROR] Failed to get target letter: {e}")
        return

    # Step 3: Determine number of rounds
    rounds = 2 if mode == 1 else 1

    # Step 4: Play each round
    for round_num in range(rounds):
        print(f"[INFO] Starting round {round_num + 1} of {rounds}...")

        try:
            word_panels = altdriver.find_objects(By.NAME, "WordPanel")
        except Exception as e:
            print(f"[ERROR] Failed to find WordPanels: {e}")
            continue

        for i, word_panel in enumerate(word_panels):
            if i == 0:
                continue  # Skip the first WordPanel (it's the target letter display)

            try:
                text_raw = word_panel.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
                if not text_raw:
                    print(f"[WARN] Word {i}: 'Word.word' is None or empty, skipping...")
                    continue

                text = text_raw.lower()

                if text == target or text.startswith(target) or target in text:
                    word_panel.click()
                    print(f"[INFO] Clicked word {i}: '{text}'")
                    time.sleep(0.5)

            except Exception as e:
                print(f"[ERROR] Could not process word {i}: {e}")

        # Wait between rounds if needed
        if round_num < rounds - 1:
            print("[INFO] Waiting for next round...")
            time.sleep(6)

    print("[INFO] Search_3rd activity complete ✅")
