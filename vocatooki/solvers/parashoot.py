"""PARASHOOT.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import math
import time

from alttester import By


def parashoot(altdriver):
    """Solves PARASHOOT: complete each word by shooting the falling letter crates.

    A word shows with blank letters (e.g. "c_t_h"). Crates parachute down, each
    showing a letter on a rotating cube; some crates hold a bird/bomb/fruit
    instead of a letter. The cannon at the bottom pivots left/right and fires a
    laser straight along its barrel. Hitting a needed letter fills a blank;
    hitting a wrong letter -- or a hazard crate -- costs a life. Letting a crate
    fall past is free.

    What this activity needed, all found against the live build:

    1. The answer. `ParashootGameManager.staticChosenWord` is the full word while
       `chosenWord` is the masked version (same idea as the bubbles solver's
       newWord). The missing letters are the blanks: zip the two and take the
       full-word letter wherever the mask has "_". Recomputed after every hit,
       so doubled letters (two blanks needing the same letter) are handled
       naturally -- the letter stays in the set until every blank is filled.

    2. Trust only the VISIBLE letter. The crates are rotating cubes with several
       letter faces, so the letter a crate "has" changes; the only reliable
       reading is the front-face Text on screen right now. Crates are targeted
       by that Text, not by guessing a cube's letter.

    3. Aim by ANGLE, not position. The cannon does not translate -- it pivots
       (left/right buttons rotate its barrel ~+-56 degrees). To hit a crate the
       barrel is rotated to point at the crate, so far-left/right lanes are
       reachable even though the cannon body barely moves. The tilt range is
       measured live at start.

    4. Never fire unless the shot is safe. Only fire when the front-most crate
       along the beam is the target letter and no hazard or wrong-letter crate
       sits on the beam before it -- and only at crates actually on screen
       (screen height from the camera; crates spawn above the top).

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    ASM = "Assembly-CSharp"
    GM = "com.kideo.learn.english.ParashootGameManager"
    RT = "UnityEngine.RectTransform"
    CO = "UnityEngine.CoreModule"

    gm = altdriver.find_object(By.NAME, "ParashootGameManager")

    def prop(f):
        try:
            return gm.get_component_property(GM, f, ASM)
        except Exception:
            return None

    def txt(n):
        try:
            return altdriver.find_object(By.NAME, n).get_text()
        except Exception:
            return None

    def P(n):
        return altdriver.find_object(By.NAME, n).get_screen_position()

    def progress():
        t = txt("ProgressText") or "0/0"
        try:
            a, b = t.split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def lives():
        try:
            return int(txt("LifesNumber"))
        except Exception:
            return -1

    # ---- live geometry (resolution independent) ----
    GUN = P("Gun_1")                       # pivot
    zoneW = P("RightDetector")[0] - P("LeftDetector")[0]
    BOXR = zoneW * 0.42                    # crate half-size
    SCREEN_H = 824.0
    for cam in ("Main Camera", "Camera"):
        try:
            v = altdriver.find_object(By.NAME, cam).get_component_property(
                "UnityEngine.Camera", "pixelHeight", CO)
            if v:
                SCREEN_H = float(v)
                break
        except Exception:
            pass
    TOP = SCREEN_H * 0.96                  # fully-on-screen ceiling
    ANGLE_TOL = 2.5

    def missing():
        full = (prop("staticChosenWord") or "")
        mask = (prop("chosenWord") or "")
        return set(c2.lower() for c1, c2 in zip(mask, full)
                   if c1 == "_" and c2 != "_")

    def scene():
        """(letters[(letter,x,y)], hazards[(x,y)]) on screen, above the gun.

        Letters are the visible front-face Texts. Hazards are cubes with no
        letter face showing -- bird / bomb / fruit crates.
        """
        cubes, letters = [], []
        for e in altdriver.get_all_elements(enabled=True):
            try:
                nm = e.name
                if nm == "Cube (2) 1(Clone)":
                    p = e.get_screen_position()
                    if GUN[1] + BOXR*0.3 < p[1] < TOP:
                        cubes.append((p[0], p[1]))
                elif nm == "Text":
                    t = (e.get_text() or "").strip().lower()
                    if len(t) == 1 and t.isalpha():
                        p = e.get_screen_position()
                        if GUN[1] < p[1] < TOP:
                            letters.append((t, p[0], p[1]))
            except Exception:
                continue
        hazards = [(cx, cy) for (cx, cy) in cubes
                   if not any(abs(lx-cx) < BOXR and abs(ly-cy) < BOXR
                              for (_, lx, ly) in letters)]
        return letters, hazards

    def gun_tilt():
        try:
            e = altdriver.find_object(By.NAME, "Gun_1").get_component_property(
                RT, "localEulerAngles", CO)
            z = e["z"] if isinstance(e, dict) else 0.0
        except Exception:
            z = 0.0
        return z if z <= 180 else z - 360     # signed: + = left, - = right

    def desired_tilt(bx, by):
        return -math.degrees(math.atan2(bx - GUN[0], max(1.0, by - GUN[1])))

    def nudge(err):
        """One proportional rotation step toward the target angle.

        `err` is (desired - current) tilt in degrees; negative means the target
        is to the right (barrel must rotate right). The hold time scales with
        the error so a large gap closes quickly and the last degrees are eased
        in. One step per control-loop pass, so the aim keeps tracking a crate
        that is still swaying and falling rather than committing to a stale spot.
        """
        btn = "RightButton" if err < 0 else "LeftButton"
        # The barrel turns ~85 deg/s while held, so hold for most of the time
        # the gap needs (err/95) -- a big gap is closed in one long hold instead
        # of many short taps -- then ease in near the target, capped so a single
        # hold cannot overshoot wildly.
        dt = min(0.5, max(0.03, abs(err) / 95.0))
        fid = altdriver.begin_touch(P(btn))
        time.sleep(dt)
        altdriver.end_touch(fid)

    def path_clear(target, letters, hazards):
        """No hazard / wrong-letter crate lies on the aim ray before the target.

        The laser travels along the barrel toward the target, so a crate whose
        body overlaps that ray at any point closer than the target is hit first.
        The perpendicular threshold is a full crate half-width (plus a margin)
        because it is the crate's *edge*, not its centre, that has to clear the
        beam -- a wrong crate grazing the beam still costs a life.
        """
        Tx, Ty, Tl = target
        gx, gy = GUN
        ux, uy = Tx - gx, Ty - gy
        L = math.hypot(ux, uy) or 1.0
        ux, uy = ux/L, uy/L
        blockers = [(x, y, l) for (l, x, y) in letters] + \
                   [(x, y, None) for (x, y) in hazards]
        for (cx, cy, lab) in blockers:
            if abs(cx-Tx) < 1 and abs(cy-Ty) < 1:
                continue
            vx, vy = cx - gx, cy - gy
            along = vx*ux + vy*uy
            if along <= 0 or along >= L - BOXR*0.3:
                continue                      # behind gun or at/after target
            if abs(vx*uy - vy*ux) < BOXR*1.2 and lab != Tl:
                return False                  # crate overlaps the beam first
        return True

    def fire():
        altdriver.find_object(By.NAME, "FireButton").tap()

    # The cannon rotates freely with no hard stop -- holding a button long
    # enough spins the barrel all the way around, past horizontal and down.
    # That must never happen: it may only aim UP at the falling crates. Every
    # on-screen crate is above the gun, so its aim angle is always within the
    # up hemisphere; MAX_TILT keeps commanded angles there and off the
    # near-horizontal edge where a shot would rake sideways.
    MAX_TILT = 78.0
    print("[info] parashoot: screen_h=%.0f max_tilt=%.0f" % (SCREEN_H, MAX_TILT))

    def reachable(bx, by):
        return abs(desired_tilt(bx, by)) <= MAX_TILT

    def relocate(committed, ms, letters, hazards):
        """Keep tracking the committed crate if it is still a valid shot.

        Returns the crate's fresh position, or None to pick a new one. Staying
        on one crate stops the cannon from swinging between several correct
        letters -- focus on one, and only move to another once this one is shot
        or has fallen past.
        """
        if not committed or committed[0] not in ms:
            return None
        cl, cx, cy = committed
        same = [(l, x, y) for (l, x, y) in letters
                if l == cl and abs(x-cx) < BOXR*1.6 and abs(y-cy) < BOXR*2.2]
        if not same:
            return None                        # shot or fell past -> next crate
        l, x, y = min(same, key=lambda z: (z[1]-cx)**2 + (z[2]-cy)**2)
        if not reachable(x, y):
            return None
        return (l, x, y)

    def pick(ms, letters, hazards):
        """Highest crate whose beam is clear of any wrong / hazard crate.

        Prefer the crate FARTHEST from the cannon (highest on screen): it has the
        longest fall left, giving the most time to aim precisely and land the
        shot rather than rushing a crate about to pass the cannon.
        """
        cand = [(l, x, y) for (l, x, y) in letters
                if l in ms and reachable(x, y)
                and path_clear((x, y, l), letters, hazards)]
        if not cand:
            return None
        return max(cand, key=lambda z: z[2])   # farthest from cannon = highest y

    done, total = progress()
    print("[info] starting parashoot at %d/%d, lives=%d" % (done, total, lives()))
    stuck = 0
    committed = None

    while True:
        done, total = progress()
        if total and done >= total:
            print("[info] all %d words complete." % total)
            break
        if stuck > 600:
            print("[warn] no clean shot for a while — stopping.")
            break
        stuck += 1

        ms = missing()
        if not ms:
            committed = None
            continue
        letters, hazards = scene()
        cur_tilt = gun_tilt()

        def try_fire(tl, tx, ty):
            """Fire, log a real hit, and report whether the mask advanced."""
            before, m0 = done, prop("chosenWord")
            fire()
            time.sleep(0.12)                   # brief — then immediately re-scan
            now, total = progress()
            m1 = prop("chosenWord")
            if m1 != m0 or now != before:
                print("[act] hit '%s' mask %r->%r prog %d/%d lives=%d"
                      % (tl, m0, m1, now, total, lives()))
                return True
            return False

        # Opportunistic: fire any reachable, clear, missing-letter crate the
        # barrel is ALREADY pointing at -- a free shot needs no travel, so grab
        # it (even if it is not the far crate we are heading for) for speed.
        ready = [(l, x, y) for (l, x, y) in letters
                 if l in ms and reachable(x, y)
                 and abs(desired_tilt(x, y) - cur_tilt) <= ANGLE_TOL
                 and path_clear((x, y, l), letters, hazards)]
        if ready:
            tl, tx, ty = min(ready,
                             key=lambda z: abs(desired_tilt(z[1], z[2]) - cur_tilt))
            stuck = 0
            if try_fire(tl, tx, ty):
                committed = None
            continue

        # Otherwise travel toward the committed crate (kept across passes so the
        # cannon follows one crate instead of swinging between several); prefer
        # the farthest so there is time to aim.
        target = relocate(committed, ms, letters, hazards) or pick(ms, letters, hazards)
        if not target:
            committed = None
            continue
        committed = target
        stuck = 0
        tl, tx, ty = target

        # Closed-loop: one rotation step toward the crate's CURRENT position (it
        # is re-measured every pass, so the aim tracks the still-swaying crate).
        err = desired_tilt(tx, ty) - cur_tilt
        if abs(err) > ANGLE_TOL:
            nudge(err)
            continue
        if path_clear((tx, ty, tl), letters, hazards) and try_fire(tl, tx, ty):
            committed = None

    done, total = progress()
    print("[done] parashoot finished at %d/%d, lives=%d" % (done, total, lives()))
