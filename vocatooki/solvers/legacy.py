"""Solvers and helpers nothing calls today. Kept (not deleted) so no caller can break;
remove one only after checking it is truly unused.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from Utilities.utils_audio import init_audio, say


def _safe_exists(altdriver, name: str) -> bool:
    try:
        altdriver.find_object(By.NAME, name)
        return True
    except Exception:
        return False


def _wait_until_exists(altdriver, name: str, timeout: float = 10.0, poll: float = 0.2) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _safe_exists(altdriver, name):
            return True
        time.sleep(poll)
    return False


def Cards(altdriver, lang="en-US", max_rounds=8):
    """Speaks all words from cards and exits when done."""
    init_audio()

    print("[INFO] Cards activity started")

    for _ in range(max_rounds):
        word_objs = altdriver.find_objects(By.NAME, "RTLTMPWordPanel")

        for word in word_objs:
            word_text = word.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
            word_text = str(word_text).strip()
            if not word_text:
                continue

            print(f"[INFO] Speaking card word: {word_text}")
            say(word_text, lang=lang, wait=True)
            time.sleep(0.35)  # small settle time for recognition pipeline

        # Try exit
        try:
            altdriver.find_object(By.NAME, "ExitButton").click()
            print("[INFO] Cards activity complete")
            return
        except:
            print("[INFO] Waiting for final feedback...")
            time.sleep(0.5)

    raise RuntimeError("[FAIL] Cards did not complete / ExitButton never appeared.")


def Delivery_truck(altdriver):
    """Speaks out loud each new word in the delivery truck boxes."""
    total_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])
    previous = None

    for _ in range(total_words):
        retries = 0
        while retries < 20:
            try:
                box = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
                word = box.get_component_property("TMProWordPanel", "TMPTextControl.OriginalText", "Assembly-CSharp")

                if word != previous:
                    say(word)
                    previous = word
                    break
                else:
                    print("[INFO] Waiting for next word to load...")
            except Exception as e:
                print(f"[WARN] Failed to retrieve text: {e}")

            retries += 1
            time.sleep(0.5)

    print("[INFO] Delivery_truck activity complete")


def moles(altdriver):
    """Speaks each word as it appears from the mole."""
    time.sleep(2)

    while True:
        try:
            mole = altdriver.wait_for_object(By.NAME, "RTLTMPWordPanel")
            word = mole.get_component_property("TMProWordPanel", "Word.word", "Assembly-CSharp")
            if word.strip():
                say(word)
            else:
                print("[INFO] Empty word detected. Waiting...")
        except Exception as e:
            print(f"[INFO] Mole game ended: {e}")
            break

    print("[INFO] Moles activity complete")


def _as_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes"}


def _button_interactable(next_btn):
    try:
        return _as_bool(next_btn.get_component_property(
            "UnityEngine.UI.Button", "interactable", "UnityEngine.UI"
        ))
    except Exception:
        return getattr(next_btn, "enabled", False)
