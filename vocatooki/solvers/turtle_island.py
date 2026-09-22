"""TURTLE_ISLAND: remove wrong letters, then drag one turtle onto another.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import re
import time

from alttester import By

from vocatooki.solvers.text_utils import is_rtl


def turtle_island(altdriver):
    def detect_rtl():
        """Solve direction comes from the WORD'S SCRIPT, not from an object name.

        RTLTMPWordPanel is the TMP panel that *supports* RTL; it exists in both
        VocaTooki and Kideo Land regardless of language, so its mere presence is
        not evidence the word is Hebrew/Arabic.
        """
        try:
            panel = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        except Exception:
            return False
        for comp, prop in (("TMProWordPanel", "Word.word"), ("TMProWordPanel", "Text")):
            try:
                text = panel.get_component_property(comp, prop, "Assembly-CSharp")
                if text and str(text).strip():
                    return is_rtl(str(text))
            except Exception:
                continue
        try:
            return is_rtl(panel.get_text() or "")
        except Exception:
            return False

    def parse_true_order(true_raw):
        """
        supports:
          - "3"
          - "[1, 2]"
          - "System.Int32[] { 1, 2 }"
          - any string containing integers
        returns:
          - int if single
          - list[int] if multiple
          - None if missing
        """
        if true_raw is None:
            return None
        s = str(true_raw).strip()
        if s == "" or s.lower() == "null":
            return None

        nums = [int(n) for n in re.findall(r"-?\d+", s)]
        if not nums:
            return None
        return nums if len(nums) > 1 else nums[0]

    def as_allowed_set(true_order):
        if true_order is None:
            return set()
        if isinstance(true_order, (list, tuple, set)):
            return set(int(x) for x in true_order)
        try:
            return {int(true_order)}
        except:
            return set()

    def dist_to_allowed(pos, allowed):
        if not allowed:
            return 999999
        return min(abs(pos - a) for a in allowed)

    def press_point(turtle):
        """Where to GRAB a turtle for a drag.

        Not its transform. The transform sits at the BOTTOM EDGE of the turtle's
        collider -- BoxCollider2D.offset.y = +1.08 with size.y = 2.17 -- so a
        drag begun there is never picked up. Measured live 2026-09-02: dragging
        transform -> transform did nothing across swipe/multipoint/held-drag at
        every duration tried, while dragging the `shield` child (the body
        centre, about 58px higher) swapped the letters on the first attempt.

        `shield` is a child of the turtle, so this stays object-derived and does
        not assume a resolution.
        """
        try:
            return turtle.find_object_from_object(By.NAME, "shield").get_screen_position()
        except Exception:
            return turtle.get_screen_position()

    print("[info] starting turtle island activity...")

    # get total words
    progress_obj = altdriver.find_object(By.NAME, "ProgressText")
    total = int(progress_obj.get_text().split('/')[1])
    print(f"[info] total words to solve: {total}")

    # main word loop
    for word_i in range(total):
        print(f"\n====== solving word {word_i + 1}/{total} ======")
        time.sleep(2)

        # Re-read per word: the lesson's language decides the solve direction.
        is_rtl_word = detect_rtl()
        print(f"[info] direction: {'RTL (Hebrew/Arabic)' if is_rtl_word else 'LTR (English)'}")

        # remove false-letter turtles
        all_objs = altdriver.get_all_elements()
        turtles = [t for t in all_objs if t.name.startswith("turtle_") and t.name.replace("turtle_", "").isdigit()]

        for t in turtles:
            try:
                true_raw = t.get_component_property(
                    "com.kideo.learn.english.TurtleScript",
                    "turtleLetter.trueOrders", "Assembly-CSharp"
                )
                if true_raw is None or str(true_raw).strip().lower() == "null":
                    print(f"[action] removing {t.name} (false letter)")
                    t.tap()
                    time.sleep(2)
            except:
                pass

        # swap loop
        MAX_SWAPS = 80  # a bit higher for harder/double-letter cases

        for _ in range(MAX_SWAPS):
            # refresh turtles
            all_objs = altdriver.get_all_elements()
            turtles = [t for t in all_objs if t.name.startswith("turtle_") and t.name.replace("turtle_", "").isdigit()]
            if not turtles:
                break

            # build info list with visual positions
            info_list = []
            for t in turtles:
                # true orders -> allowed set
                try:
                    true_raw = t.get_component_property(
                        "com.kideo.learn.english.TurtleScript",
                        "turtleLetter.trueOrders", "Assembly-CSharp"
                    )
                    true_order = parse_true_order(true_raw)
                except:
                    true_order = None

                allowed = as_allowed_set(true_order)

                # current x -> visual index
                try:
                    pos = t.get_screen_position()
                    x = pos["x"] if isinstance(pos, dict) else getattr(pos, "x", pos[0])
                except:
                    x = 999999

                info_list.append({
                    "obj": t,
                    "name": t.name,
                    "allowed": allowed,
                    "x": x,
                })

            # sort by x => visual index
            info_list.sort(key=lambda c: c["x"])

            # RTL (Hebrew/Arabic): reverse visual indices (position 0 is rightmost)
            if is_rtl_word:
                for i, info in enumerate(info_list):
                    info["visual"] = len(info_list) - 1 - i
                    info["correct"] = (info["visual"] in info["allowed"]) if info["allowed"] else False
            else:
                # LTR (English): normal left-to-right indexing
                for i, info in enumerate(info_list):
                    info["visual"] = i
                    info["correct"] = (i in info["allowed"]) if info["allowed"] else False

            # if all turtles with known allowed sets are correct -> done
            wrongs = [i for i in info_list if i["allowed"] and not i["correct"]]
            if not wrongs:
                print("[info] all turtles in correct order.")
                break

            # pick first wrong turtle
            wrong = wrongs[0]

            # choose best swap candidate:
            # 1) maximize correctness delta for the two swapped turtles
            # 2) if no improvement, minimize wrong distance to allowed after swap
            best = None
            best_delta = -999999

            a_vis = wrong["visual"]
            a_allowed = wrong["allowed"]
            a_correct_before = a_vis in a_allowed

            for cand in info_list:
                if cand["name"] == wrong["name"]:
                    continue

                b_vis = cand["visual"]
                b_allowed = cand["allowed"]

                b_correct_before = (b_vis in b_allowed) if b_allowed else False

                a_correct_after = (b_vis in a_allowed)
                b_correct_after = (a_vis in b_allowed) if b_allowed else b_correct_before

                delta = (int(a_correct_after) + int(b_correct_after)) - (int(a_correct_before) + int(b_correct_before))

                if delta > best_delta:
                    best_delta = delta
                    best = cand

            # if we found no candidate (shouldn't happen), break
            if best is None:
                print("[warn] no swap candidate found.")
                break

            # if swap doesn't improve correctness, do a "closest" swap to escape duplicates deadlocks
            if best_delta <= 0:
                best = min(
                    (c for c in info_list if c["name"] != wrong["name"]),
                    key=lambda c: dist_to_allowed(c["visual"], wrong["allowed"])
                )
                print("[warn] no improving swap found, using fallback swap (duplicate letters case).")

            print(
                f"[swap] {wrong['name']} (pos={wrong['visual']}, allowed={sorted(list(wrong['allowed']))}) "
                f"↔ {best['name']} (pos={best['visual']}, allowed={sorted(list(best['allowed'])) if best['allowed'] else []})"
            )

            # perform swap
            try:
                start = press_point(wrong["obj"])
                end = press_point(best["obj"])
                altdriver.swipe(start, end, 1.0)
                time.sleep(1.5)
            except Exception as e:
                print(f"[error] swap failed: {e}")
                time.sleep(1.5)

        print("[info] word completed.\n")

    print("\n✔✔✔ turtle island completed ✔✔✔")
