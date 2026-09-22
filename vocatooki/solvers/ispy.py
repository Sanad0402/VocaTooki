"""ISPY: find the object that matches the word.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def ispy(altdriver):
    """
    Solves the Ispy activity by detecting and clicking correct objects.
    Supports fallback for white and brown text/image variants.
    """
    print("[INFO] Starting Ispy activity...")

    def find_first_available_objects(name_variants):
        """Tries each object name until one returns results."""
        for name in name_variants:
            objs = altdriver.find_objects(By.NAME, name)
            if objs:
                print(f"[DEBUG] Found {len(objs)} objects with name: {name}")
                return objs
            else:
                print(f"[DEBUG] No objects found for: {name}")
        return []

    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    numberOfwords = int(progresstext.split('/')[1])
    print(f"[INFO] Total items to find: {numberOfwords}")

    for i in range(numberOfwords):
        print(f"[INFO] Solving item {i + 1} of {numberOfwords}")
        time.sleep(5)

        text_variants = [
            'GridElementWithText(Clone)',
            'GridElementWithText white(Clone)',
            'GridElementWithText brown(Clone)',
        ]
        image_variants = [
            'GridElementWithImage(Clone)',
            'GridElementWithImage white(Clone)',
            'GridElementWithImage brown(Clone)',
        ]

        objs_with_text = find_first_available_objects(text_variants)
        objs_with_image = find_first_available_objects(image_variants)

        answers = objs_with_text + objs_with_image
        current_word = altdriver.find_object(By.NAME, 'Canvas')
        current_word_text = current_word.get_component_property('ISpyLevelGenerator', 'currentQuestion.word.word','Assembly-CSharp')
        print(f"[DEBUG] Total answer objects found: {len(answers)}")

        print('Current word : ',current_word_text)

        flag = False
        for answer in answers:
            if flag:
                continue
            try:
                is_correct_answer = answer.get_component_property(
                    'ClickHandeler', 'onClick.Method.Name', 'Assembly-CSharp'
                )
                if is_correct_answer == 'OnCorrectClick':
                    answer.click()
                    print("[INFO] Correct answer clicked")
                    flag = True
                    time.sleep(2)
            except Exception as e:
                print(f"[WARN] Error processing answer: {e}")

    print("[INFO] Ispy activity complete")
