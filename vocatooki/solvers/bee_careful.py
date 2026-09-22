"""BEE_CAREFUL: drop the right picture on the hive once no fly is near it.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import math
import time

from alttester import By


def bee(altdriver):
    """Solves Bee Careful by dragging the correct word to the hive."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    bg_name = altdriver.find_object(By.NAME, "BeeCareful_activity").get_component_property(
        "com.kideo.learn.english.BeeCarefulActivityManagement",
        "sessionData_.CurrentGeographyName",
        "Assembly-CSharp"
    )

    background_map = {
        "Sea": "DraggableObjectB_Sea(Clone)", "FairyTales": "DraggableObjectB_FairyTales(Clone)",
        "Dinosaurs": "DraggableObjectB_Farm(Clone)", "Space": "DraggableObjectB_Farm(Clone)",
        "Candy": "DraggableObjectB_Candy(Clone)", "Farm": "DraggableObjectB_Farm(Clone)",
        "Desert": "DraggableObjectB_Desert(Clone)", "Pole": "DraggableObjectB_Farm(Clone)"
    }
    obj_name = background_map.get(bg_name, "DraggableObjectB(Clone)")

    # Driven by the PROGRESS, not by a fixed count of rounds. The old loop made
    # num_words passes and silently skipped any pass whose picture was not
    # there, so it "finished" at 2/6 (measured on 4.6.0, 2026-09-14).
    #
    # The flies are the trap. FlyEnemyPrefB(Clone) objects hover over the hive,
    # and a picture dropped while one is there costs a heart; three of those
    # and the game is lost behind FailureFeedbackPopup(Clone). So a drop only
    # happens once no fly is near the hive, and each one must move the
    # progress — waiting it out got a Jungle board to 6/6 with no heart lost.
    hive_name = "Vector Smart Object_3"
    try:
        width, _height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:
        width = 0.0
    fly_clearance = 0.15 * width                     # a fraction of the screen, any resolution

    def progress():
        done, total = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(done), int(total)

    def game_lost():
        return bool(altdriver.find_objects(By.NAME, "FailureFeedbackPopup(Clone)"))

    deadline = time.time() + 60 + 30 * num_words
    while time.time() < deadline:
        if game_lost():
            print("[ERROR] Bee Careful: the game was lost (FailureFeedbackPopup)")
            return
        done, total = progress()
        if done >= total:
            break

        target_word = altdriver.find_object(By.NAME, 'WordPanel')\
            .get_component_property("WordPanel", "<wordObj_>k__BackingField.word", "Assembly-CSharp")
        match = next((o for o in altdriver.find_objects(By.NAME, obj_name)
                      if o.get_component_property("com.kideo.learn.english.BeeCarefulObject",
                                                  "word", "Assembly-CSharp") == target_word), None)
        hive = altdriver.find_object(By.NAME, hive_name)
        flies_near = [f for f in altdriver.find_objects_which_contain(By.NAME, "FlyEnemy")
                      if fly_clearance and math.hypot(f.x - hive.x, f.y - hive.y) < fly_clearance]
        if match is None or flies_near:
            time.sleep(0.7)                          # the picture is not out yet / a fly is on the hive
            continue

        pos = hive.get_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule")
        match.set_component_property("UnityEngine.Transform", "localScale", "UnityEngine.CoreModule",
                                     {"x": 0.3, "y": 0.3, "z": 0.3})
        match.set_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule", pos)
        match.click()

        # A drop that does not move the progress is retried on the next pass.
        settle_end = time.time() + 6
        while time.time() < settle_end and progress()[0] <= done and not game_lost():
            time.sleep(0.4)

    done, total = progress()
    if done >= total:
        print(f"[INFO] Bee activity complete ({done}/{total})")
    else:
        print(f"[ERROR] Bee Careful stopped at {done}/{total}")


'''
s = altdriver.find_objects(By.NAME,'DraggableObjectB(Clone)')
s.set_component_property("UnityEngine.Transform", "localScale", "UnityEngine.CoreModule", {"x": 1, "y": 2, "z": 1})

'''
