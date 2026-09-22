"""BRICKOUT.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import AltKeyCode, By


def brickout(altdriver):
    """Solves BRICKOUT: catch ONLY the required words, let the decoys pass.

    Unlike the other activities (which tap objects directly) this is a live
    arcade game. A ball breaks word-bricks and the words fall toward the paddle.
    Catching a word that is NOT in the target list costs a heart, so the paddle
    must intercept the needed words and actively stay clear of the rest.

    Movement uses short `press_key(duration=...)` bursts sized to the distance.
    A held key (`key_down`/`key_up`) was tried and is worse here: any slow poll
    overshoots and slams the paddle into the wall, whereas a burst self-limits.

    NOTE: the app must have OS focus while this runs — Unity pauses play mode
    when the window is in the background and the ball simply freezes.
    """
    from alttester import AltKeyCode

    ASM = "Assembly-CSharp"
    PADDLE_SPEED = 950.0   # px/sec, measured against the live build
    MAX_BURST = 0.22       # sec; keep bursts short so we re-read often
    DEADZONE = 35          # px; don't jitter when roughly aligned
    FALL_EPS = 4           # px; y must drop at least this much to count as falling
    SAFE_GAP = 260         # px of clearance to keep from a falling decoy
    BOARD_MIN, BOARD_MAX = 120, 1450   # px; playable range of the paddle

    def targets():
        """Words still listed as needed (collected ones leave the panel list)."""
        out = set()
        for e in altdriver.get_all_elements(enabled=True):
            if e.name == "WordPanel(Clone)":
                try:
                    w = e.get_component_property("WordPanel", "Word.word", ASM)
                    if w:
                        out.add(str(w).strip().lower())
                except Exception:
                    pass
        return out

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def paddle_x():
        try:
            return altdriver.find_object(By.NAME, "Paddle").get_screen_position()[0]
        except Exception:
            return None

    def move_to(px, tx):
        delta = tx - px
        if abs(delta) <= DEADZONE:
            return
        key = AltKeyCode.RightArrow if delta > 0 else AltKeyCode.LeftArrow
        try:
            altdriver.press_key(key, duration=min(abs(delta) / PADDLE_SPEED, MAX_BURST))
        except Exception:
            pass

    need = targets()
    done, total = progress()
    print("[info] start %d/%d | need(%d): %s" % (done, total, len(need), sorted(need)))

    last_done = done
    stalled = 0
    prev_word_y = {}       # object id -> last y, to tell falling from parked

    for _ in range(3000):
        done, total = progress()
        if total and done >= total:
            print("[info] all %d words collected." % total)
            break

        if done != last_done:
            need = targets()
            print("[info] progress %d/%d | remaining %d" % (done, total, len(need)))
            last_done, stalled = done, 0
        else:
            stalled += 1
            if stalled > 1500:
                print("[warn] stalled — stopping.")
                break

        px = paddle_x()
        if px is None:
            time.sleep(0.15)
            continue

        # --- find falling words -------------------------------------------
        # A word counts as falling only if its y is DECREASING. A fixed y
        # threshold does not work: the layout shifts between builds/resolutions
        # and the parked grid can sit below it, which made the paddle chase
        # static bricks (usually on the left) and abandon the ball.
        falling = []
        seen_y = {}
        try:
            for e in altdriver.get_all_elements(enabled=True):
                if e.name != "BrickWord":
                    continue
                try:
                    pos = e.get_screen_position()
                except Exception:
                    continue
                oid = getattr(e, "id", None)
                seen_y[oid] = pos[1]
                was = prev_word_y.get(oid)
                if was is None or pos[1] >= was - FALL_EPS:
                    continue                  # parked in the grid (or new)
                txt = ""
                try:
                    txt = (e.get_text() or "").strip().lower()
                except Exception:
                    pass
                if txt:
                    falling.append((pos[1], pos[0], txt))
        except Exception:
            pass
        prev_word_y = seen_y

        # Where is the ball? None while it respawns after a lost heart.
        ball_x = None
        try:
            ball_x = altdriver.find_object(By.NAME, "Ball").get_screen_position()[0]
        except Exception:
            pass

        if falling:
            falling.sort()                    # lowest y == closest to the paddle
            y, x, word = falling[0]
            if word in need:
                move_to(px, x)                # CATCH it
            elif abs(x - px) < SAFE_GAP:
                # Decoy heading for us. Never dodge while the ball is missing:
                # that is how the paddle used to get stranded at a wall after a
                # lost heart and then drop every remaining one.
                if ball_x is not None:
                    # Step just clear of the decoy rather than running to the
                    # wall, and prefer the side that keeps us nearer the ball.
                    step = SAFE_GAP + 40
                    spots = [max(BOARD_MIN, min(BOARD_MAX, px - step)),
                             max(BOARD_MIN, min(BOARD_MAX, px + step))]
                    safe = [s for s in spots if abs(s - x) >= SAFE_GAP]
                    if safe:
                        move_to(px, min(safe, key=lambda s: abs(s - ball_x)))
            continue

        # nothing falling -> keep the ball alive so more bricks get broken
        if ball_x is not None:
            move_to(px, ball_x)
        else:
            time.sleep(0.1)

    done, total = progress()
    print("[done] finished at %d/%d" % (done, total))
