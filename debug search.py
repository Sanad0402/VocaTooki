import time
from alttester import AltDriver, By, altdriver

"""Automates the Search activity by matching and tapping letters."""
altdriver = AltDriver(
    host="127.0.0.1",
    port=13000,
    enable_logging=True
)

progress = altdriver.find_object(By.NAME, "ProgressText").get_text()
number_of_words = int(progress.split('/')[1])
print(f"[DEBUG] Number of words: {number_of_words}")

for _ in range(number_of_words):
    time.sleep(2)
    full_text = altdriver.find_object(By.NAME, "WordPanel") \
        .get_component_property("WordPanel", "Word.ToLower", "Assembly-CSharp")
    current_text = altdriver.find_object(By.NAME, "RTLTMPWordPanel") \
        .get_component_property("TMProWordPanel", "Text", "Assembly-CSharp")

    differences = [char2 for char1, char2 in zip(current_text, full_text) if char1 == "_" and char2 != "_"]

    letters = altdriver.find_objects(By.NAME, "SearchObj(Clone)")
    covers = altdriver.find_objects(By.NAME, "CoverObj")

    letter_obj_pairs = [
        (l.get_component_property("com.kideo.learn.english.SearchObj", "letter", "Assembly-CSharp"), o)
        for l, o in zip(letters, covers)
    ]

    for letter in differences:
        for idx, (ltr, obj) in enumerate(letter_obj_pairs):
            if ltr == letter:
                obj.tap(count=1, interval=1.5, wait=True)
                letter_obj_pairs.pop(idx)
                print(f"[ACTION] Clicked letter: {letter}")
                break

print("[INFO] Search activity complete ✅")


