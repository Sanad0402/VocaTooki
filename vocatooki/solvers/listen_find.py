"""LISTEN_FIND (megaphone): click the word that was said, round after round.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def megaphone(altdriver):
    """Solves the Listen & Find activity using correct word sequence and background layout."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    geo_name = altdriver.find_object(By.NAME, "ListenFind_activity").get_component_property(
        "com.kideo.learn.english.ListenFindActivityManagement", "sessionData_.CurrentGeographyName", "Assembly-CSharp"
    )

    leaf_map = {
        "Sea": "LeafPref_Sea(Clone)", "FairyTales": "LeafPref(Clone)", "Dinosaurs": "LeafPref_Dinosaurs(Clone)",
        "Space": "LeafPref_Moon(Clone)", "Candy": "LeafPref_Candy(Clone)", "Farm": "LeafPref(Clone)",
        "Desert": "LeafPref_Desert(Clone)", "Pole": "LeafPref_Pole(Clone)","Islam":"LeafPref_Islam(Clone)","China":"LeafPref_Rome(Clone)"
    }
    leaf_name = leaf_map.get(geo_name, "LeafPref(Clone)")

    # Driven by the PROGRESS. `usedWords` only grows a round at a time — three
    # words, then all six once the first round is scored — so the old fixed
    # "2 passes, 4s apart" read the second round before it existed and stopped
    # at 3/6 (measured on 4.6.0, 2026-09-14). A word already scored also stays
    # on the board for a moment, so what was scored is remembered rather than
    # clicked again.
    def progress():
        done, total = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(done), int(total)

    def board():
        pairs = []
        for obj in (altdriver.find_objects(By.NAME, "PaperPref(Clone)")
                    + altdriver.find_objects(By.NAME, leaf_name)):
            try:
                pairs.append((obj.get_component_property(
                    "com.kideo.learn.english.ListenFindObject", "word.word", "Assembly-CSharp"), obj))
            except Exception:
                continue
        return pairs

    scored, missed = [], ""
    deadline = time.time() + 60 + 25 * num_words
    while time.time() < deadline:
        done, total = progress()
        if done >= total:
            break
        used_words = altdriver.find_object(By.NAME, "ListenFindGameManager").get_component_property(
            "com.kideo.learn.english.ListenFindGameManager", "usedWords", "Assembly-CSharp"
        ) or []
        pending = list(used_words)
        for word in scored:                          # a word can come round twice
            if word in pending:
                pending.remove(word)
        if missed in pending and len(pending) > 1:  # the word that did not take goes last
            pending.remove(missed)
            pending.append(missed)
        on_board = board()
        target = next(((w, o) for w in pending for t, o in on_board if t == w), None)
        if target is None:
            time.sleep(1)                            # the next round is not out yet
            continue

        word, obj = target
        obj.click()
        settle_end = time.time() + 6
        while time.time() < settle_end and progress()[0] <= done:
            time.sleep(0.4)
        if progress()[0] > done:
            scored.append(word)
            missed = ""
        else:
            missed = word
            time.sleep(1)                            # not taken yet — re-read and go again

    done, total = progress()
    if done >= total:
        print(f"[INFO] Megaphone activity complete ({done}/{total})")
    else:
        print(f"[ERROR] Megaphone stopped at {done}/{total}")
