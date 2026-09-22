"""RINGS.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time
import unicodedata

from alttester import By


def _bare_letters(text):
    """`text` with any combining marks removed; identity when there are none.

    Hebrew arrives pointed from both sides of the RINGS match and the points are
    NOT letters: a cover named `CoverHolder-<ayin><tsere><final-tsadi>` is three
    code points for a two-letter word, so the path finder hunts the vowel point
    across the board as though it were a letter and never completes a ring.
    Measured live on a Kideo Land board: 0 of 6 rings found before normalising
    both sides, 6 of 6 after.

    English has no combining marks, so this returns the text unchanged and the
    comparisons it feeds are bit-identical to before -- Voca Tooki is unaffected.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


def rings(altdriver):
    """Solves RINGS: drag each structure onto the ring of letters it spells.

    The board is a hex grid of letters; each target word snakes through it as a
    connected ring. The right-hand panel holds one pre-shaped cover per word
    (CoverHolder-<word>), scrollable, with several off screen at any time.

    Three things had to be right, all learned the hard way against the build:

    1. Engaging the drag. A cover only lifts after a long press followed by
       GRADUAL nudges; one large jump does nothing and a plain vertical drag is
       swallowed by the panel's scroll view.
    2. Steering. Once lifted, the cover travels ~2x the finger delta, so it is
       steered closed-loop off its measured position with the gain re-estimated
       live. Dead reckoning overshoots straight off the screen.
    3. Cells are exclusive. Every word owns its own hexes, so a ring already
       under a placed structure must not be reused. That is re-measured from
       live state each round -- a remembered list goes stale when the round
       regenerates and ends up blocking the entire fresh grid.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    SETTLE = 4.0          # the score animation lags - reading earlier lies
    REGEN_WAIT = 5.0      # past halfway the round spawns fresh structures

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def geometry():
        """Derive the layout constants from the live scene, not fixed pixels.

        The window is not always the same size, and every one of these used to
        be a magic pixel value tuned for one resolution. When the window grew,
        the hex spacing (~101px) sailed past a hardcoded ADJ of 75, so the path
        finder saw every cell as isolated and nothing was ever placeable. These
        are now measured each run:

        * ADJ    -- from the median nearest-neighbour spacing of the board hexes
        * PANEL_X-- the gap between the board's right edge and the inventory
        * board bbox -- so a placed cover is recognised anywhere on the board
        * VIS band  -- the inventory's reachable y-range, taken from the scroll
                       arrows that bracket the panel
        * inv_x  -- where to press to scroll the inventory (over the panel, not
                    the board)
        """
        # Fallbacks, used only when a measurement fails outright (no Letter
        # hexes on screen, no scroll arrows). They were tuned on a 1600x900
        # window, so they are scaled to the window in use rather than left as
        # values that are simply wrong on any other size.
        try:
            sw, sh = altdriver.get_application_screensize()
        except Exception:
            sw, sh = 1600.0, 900.0
        fx, fy = float(sw) / 1600.0, float(sh) / 900.0
        g = {"ADJ": 75.0 * fx, "PANEL_X": 980.0 * fx, "inv_x": 1057.0 * fx,
             "SPACING": 101.0 * fx, "PITCH": 150.0 * fy,
             "bx0": -1e9, "bx1": 1e9, "by0": -1e9, "by1": 1e9,
             "VIS_LO": 120.0 * fy, "VIS_HI": 500.0 * fy}

        bx, by = [], []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name != "Letter":
                continue
            try:
                p = e.get_screen_position()
                if (e.get_text() or "").strip():
                    bx.append(p[0]); by.append(p[1])
            except Exception:
                pass
        if len(bx) >= 4:
            g["bx0"], g["bx1"] = min(bx), max(bx)
            g["by0"], g["by1"] = min(by), max(by)
            cells = list(zip(bx, by))
            nn = []
            for i, a in enumerate(cells):
                best = 1e9
                for j, b in enumerate(cells):
                    if i != j:
                        best = min(best, ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5)
                nn.append(best)
            nn.sort()
            g["ADJ"] = max(75.0 * fx, nn[len(nn)//2] * 1.35)
            g["SPACING"] = nn[len(nn)//2]        # raw hex spacing, for scaling

        hx = []
        cover_pts = []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name.startswith("CoverHolder-"):
                try:
                    pos = e.get_screen_position()
                except Exception:
                    continue
                hx.append(pos[0])
                cover_pts.append(pos)
        if hx:
            hx.sort()
            g["inv_x"] = hx[len(hx)//2]
            if g["bx1"] > -1e8:
                g["PANEL_X"] = (g["bx1"] + min(hx)) / 2.0

        # How far apart the inventory covers sit: scrolling by exactly one
        # pitch advances the list by exactly one cover, whatever the window
        # size. A fixed step scrolls a fraction of a cover on a large window
        # and several on a small one.
        cover_ys = sorted(p[1] for p in cover_pts)
        gaps = [b - a for a, b in zip(cover_ys, cover_ys[1:]) if b - a > 1]
        if gaps:
            g["PITCH"] = sorted(gaps)[len(gaps)//2]

        arrows = {}
        for e in altdriver.get_all_elements(enabled=True):
            if e.name in ("Up Arrow", "Down Arrow"):
                try:
                    arrows[e.name] = e.get_screen_position()
                except Exception:
                    pass
        if "Up Arrow" in arrows and "Down Arrow" in arrows:
            lo = min(arrows["Up Arrow"][1], arrows["Down Arrow"][1])
            hi = max(arrows["Up Arrow"][1], arrows["Down Arrow"][1])
            margin = (hi - lo) * 0.07
            g["VIS_LO"], g["VIS_HI"] = lo + margin, hi - margin

        return g

    geom = geometry()
    ADJ = geom["ADJ"]
    PANEL_X = geom["PANEL_X"]
    VIS_LO, VIS_HI = geom["VIS_LO"], geom["VIS_HI"]

    # The gesture constants below were tuned when the board's hex spacing was
    # ~101px. The window is not always that size (it has been seen at 2153x1093,
    # where the spacing is 135), and a nudge that is proportionally too small
    # never engages the drag — the "drag never engaged" failure. Scale them off
    # the live board instead of leaving them as pixels.
    SCALE = max(0.5, geom["SPACING"] / 101.0)
    NUDGES = tuple(int(round(n * SCALE)) for n in (10, 25, 45, 70))
    ENGAGE_EPS = 8.0 * SCALE          # "did it move?" threshold
    PITCH = geom["PITCH"]             # one inventory cover
    # "same cell" radius: a quarter of the hex spacing, so it means the same
    # thing on every board size (it was a flat 25px, which is a quarter of a
    # hex at spacing 101 but under a fifth at 135).
    SAME_CELL_R2 = (0.25 * geom["SPACING"]) ** 2
    print("[info] rings scale: spacing=%.0f x%.2f nudges=%s pitch=%.0f"
          % (geom["SPACING"], SCALE, NUDGES, PITCH))
    TOL = max(16.0, ADJ * 0.16)
    print("[info] rings geometry: ADJ=%.0f PANEL_X=%.0f VIS=[%.0f,%.0f] inv_x=%.0f"
          % (ADJ, PANEL_X, VIS_LO, VIS_HI, geom["inv_x"]))

    def read_grid():
        """[(x, y, letter)] for every letter hex on the board."""
        out = []
        for e in altdriver.get_all_elements(enabled=False):
            if e.name != "Letter":
                continue
            try:
                p = e.get_screen_position()
                t = (e.get_text() or "").strip().lower()
            except Exception:
                continue
            if t:
                out.append((p[0], p[1], t))
        return out

    def occupied():
        """Cells under an already-placed structure, measured from live state."""
        pts = []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            # a placed cover sits within the board's bounding box; the covers
            # still in the inventory are further right (x ~ inv_x) and excluded
            if (p[0] <= PANEL_X
                    and geom["by0"] - ADJ < p[1] < geom["by1"] + ADJ):
                pts.append((p[0], p[1]))
        return pts

    def path_finder(cells, blocked_pts=()):
        blocked = set()
        for i, c in enumerate(cells):
            for q in blocked_pts:
                if ((c[0]-q[0])**2 + (c[1]-q[1])**2) ** 0.5 < 30:
                    blocked.add(i)
                    break

        nbr = {i: [] for i in range(len(cells))}
        for i, a in enumerate(cells):
            for j, b in enumerate(cells):
                if i != j and ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5 <= ADJ:
                    nbr[i].append(j)

        exact_letters = [c[2] for c in cells]
        bare_letters = [_bare_letters(t) for t in exact_letters]

        def walk(letters, w):
            def dfs(idx, pos, used):
                if pos == len(w):
                    return list(used)
                for k in nbr[idx]:
                    if k in used or k in blocked or letters[k] != w[pos]:
                        continue
                    used.append(k)
                    r = dfs(k, pos+1, used)
                    if r:
                        return r
                    used.pop()
                return None

            for i in range(len(cells)):
                if i in blocked or letters[i] != w[0]:
                    continue
                r = dfs(i, 1, [i])
                if r:
                    return r
            return None

        def find(word):
            """Match on exact letters first; only then retry ignoring marks.

            Hebrew (and Arabic) arrive POINTED on both sides and the points are
            not letters, so an exact walk can never complete a ring -- measured
            live, 0 of 6. Stripping marks fixes that.

            But the app also targets pt, es, de and tr, where a marked character
            IS its own letter: Spanish 'ano' and 'anno-with-tilde' are different
            words, Turkish dotless i is not i, German umlauts are distinct. There
            the board carries the accented tile itself, so a stripped match could
            walk a wrong-but-similar path.

            Trying exact first means those languages resolve on pass one and never
            reach the fallback, while pointed scripts still get solved. The
            fallback is skipped entirely when stripping changes nothing.
            """
            w_exact = "".join(word.split()).lower()
            found = walk(exact_letters, w_exact)
            if found:
                return found

            w_bare = _bare_letters(w_exact)
            if w_bare == w_exact and bare_letters == exact_letters:
                return None  # nothing to strip; the retry would be identical
            return walk(bare_letters, w_bare)

        return find

    def holders():
        """word -> screen position of its cover, e.g. CoverHolder-tasty.

        The holder name IS the word: a card reading "all the ___" still only
        places the blank, so the name must not be expanded to the phrase.
        """
        out = {}
        for e in altdriver.get_all_elements(enabled=False):
            if e.name.startswith("CoverHolder-"):
                try:
                    out[e.name.split("-", 1)[1].lower()] = e.get_screen_position()
                except Exception:
                    pass
        return out

    def cover_near(pt):
        best, bd = None, 1e9
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            dd = ((p[0]-pt[0])**2 + (p[1]-pt[1])**2) ** 0.5
            if dd < bd:
                best, bd = e, dd
        return best, bd

    def pos_of(cid):
        for e in altdriver.get_all_elements(enabled=True):
            if e.id == cid:
                try:
                    return e.get_screen_position()
                except Exception:
                    return None
        return None

    def scroll_inventory(dy=None):
        """A vertical drag inside the panel scrolls it to reach hidden covers.

        Always the same direction: alternating merely oscillates between two
        positions and never cycles the list.
        """
        dy = -PITCH if dy is None else dy   # one cover per scroll, whatever the size
        x = geom["inv_x"]                 # press over the panel, not the board
        y0 = (VIS_LO + VIS_HI) / 2.0
        altdriver.move_mouse((x, y0), duration=0.15)
        finger = altdriver.begin_touch((x, y0))
        try:
            time.sleep(0.2)
            for i in range(1, 13):
                pt = (x, y0 + dy*i/12.0)
                altdriver.move_touch(finger, pt)
                altdriver.move_mouse(pt, duration=0.01)
                time.sleep(0.03)
            time.sleep(0.3)
        finally:
            altdriver.end_touch(finger)
        time.sleep(1.2)

    def dragged_centroid(hpos, ring_size, busy):
        """Centroid of the cover being dragged, from its hex pieces on the board.

        A cover is a rigid group of hexes shaped like its ring; we only hold one
        of them. The pieces already placed (busy) and the ones still in the
        inventory are excluded, then the `ring_size` pieces nearest the held hex
        are the dragged cover. Aligning this centroid -- not the single held hex
        -- is what actually snaps the cover: the held hex can sit at the ring
        centre while the shape as a whole is a hex or two off, and then nothing
        registers.
        """
        pts = []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name != "Original HexCover(Clone)":
                continue
            try:
                p = e.get_screen_position()
            except Exception:
                continue
            if p[0] > PANEL_X:                       # still in the inventory
                continue
            if any((p[0]-q[0])**2 + (p[1]-q[1])**2 < SAME_CELL_R2 for q in busy):
                continue                             # an already-placed cover
            pts.append((p[0], p[1]))
        pts.sort(key=lambda p: (p[0]-hpos[0])**2 + (p[1]-hpos[1])**2)
        grp = pts[:ring_size]
        if not grp:
            return None
        return (sum(p[0] for p in grp) / len(grp),
                sum(p[1] for p in grp) / len(grp))

    def place(holder_pos, target, ring_size, busy):
        cov, dist = cover_near(holder_pos)
        if cov is None or dist > 2.0 * ADJ:      # scales with the hex size
            print(f"[warn] no cover at holder ({dist:.0f}px away)")
            return False
        cid = cov.id
        start = cov.get_screen_position()
        altdriver.move_mouse(start, duration=0.25)
        time.sleep(0.35)
        finger = [start[0], start[1]]
        touch = altdriver.begin_touch(tuple(finger))
        try:
            time.sleep(0.6)                       # long press to grab
            for n in NUDGES:                      # gradual nudges to engage
                finger[0] = start[0] - n
                altdriver.move_touch(touch, tuple(finger))
                altdriver.move_mouse(tuple(finger), duration=0.01)
                time.sleep(0.12)
            here = pos_of(cid)
            if here and abs(here[0]-start[0]) < ENGAGE_EPS and abs(here[1]-start[1]) < ENGAGE_EPS:
                print("[warn] drag never engaged")
                return False

            # Coarse: drive the held hex to the ring centre. This gets the whole
            # cover onto the board, roughly over the ring, and clear of the
            # inventory so its cluster can be measured cleanly.
            gain = 2.0                            # cover moves ~2x the finger
            prev_f, prev_c = list(finger), here
            for _ in range(28):
                c = pos_of(cid)
                if not c:
                    break
                ex, ey = target[0]-c[0], target[1]-c[1]
                if (ex*ex + ey*ey) ** 0.5 <= TOL:
                    break
                if prev_c:
                    dfx, dcx = finger[0]-prev_f[0], c[0]-prev_c[0]
                    if abs(dfx) > 3 and abs(dcx) > 3:
                        g = abs(dcx/dfx)
                        if 0.3 < g < 6:
                            gain = 0.5*gain + 0.5*g
                prev_f, prev_c = list(finger), c
                finger[0] += (ex/gain) * 0.55
                finger[1] += (ey/gain) * 0.55
                altdriver.move_touch(touch, tuple(finger))
                altdriver.move_mouse(tuple(finger), duration=0.01)
                time.sleep(0.16)

            # Fine: align the cover's whole cluster to the ring centre. The held
            # hex is usually off-centre in the shape, so centring it leaves the
            # cluster a hex or two adrift; correct that here or it will not snap.
            for _ in range(16):
                h = pos_of(cid)
                if not h:
                    break
                cc = dragged_centroid(h, ring_size, busy)
                if not cc:
                    break
                ex, ey = target[0]-cc[0], target[1]-cc[1]
                if (ex*ex + ey*ey) ** 0.5 <= 6.0:
                    break
                finger[0] += ex / gain
                finger[1] += ey / gain
                altdriver.move_touch(touch, tuple(finger))
                altdriver.move_mouse(tuple(finger), duration=0.01)
                time.sleep(0.16)
            time.sleep(0.4)
        finally:
            altdriver.end_touch(touch)
        return True

    done, total = progress()
    print(f"[info] starting rings at {done}/{total}")
    failed, idle = {}, 0
    placed = set()          # words done this batch; a placed holder can linger
    regen_done = False

    for _ in range(90):
        done, total = progress()
        if total and done >= total:
            print(f"[info] all {total} structures placed.")
            break

        # A hard round (>8 words) does not show all its structures at once: once
        # half are placed it wipes the panel and spawns a fresh batch, and the
        # board regenerates with them. Handle that transition like a fresh start
        # -- wait for the new structures to settle, forget the old fail counts,
        # then fall through and re-read the whole scene.
        if total > 8 and not regen_done and done >= total / 2.0:
            print("[info] halfway reset — waiting for the new structures to spawn")
            time.sleep(REGEN_WAIT)
            failed.clear()
            placed.clear()          # the fresh batch may reuse a word
            idle = 0
            regen_done = True
            continue

        cells = read_grid()
        busy = occupied()
        find = path_finder(cells, busy)
        hs = holders()

        cand = None
        for w, p in sorted(hs.items(), key=lambda kv: -kv[1][1]):
            if w in placed or failed.get(w, 0) >= 2:
                continue
            if VIS_LO < p[1] < VIS_HI and find(w):
                cand = (w, p)
                break

        if not cand:
            idle += 1
            if idle > 24:
                print("[warn] nothing placeable — stopping.")
                break
            if idle % 3 == 0:
                scroll_inventory()
            else:
                # the round generates fresh structures as it goes
                failed.clear()
                time.sleep(REGEN_WAIT)
            continue
        idle = 0

        word, holder_pos = cand
        ring = [cells[i] for i in find(word)]
        tx = sum(p[0] for p in ring) / len(ring)
        ty = sum(p[1] for p in ring) / len(ring)
        print(f"[act] {word}: ring of {len(ring)} cells at ({tx:.0f},{ty:.0f}), "
              f"{len(busy)} cells already covered")

        before = done
        if place(holder_pos, (tx, ty), len(ring), busy):
            time.sleep(SETTLE)
            now, total = progress()
            if now > before:
                failed.pop(word, None)
                placed.add(word)        # its holder may linger; don't re-drag it
                print(f"[info] progress {now}/{total}")
            else:
                failed[word] = failed.get(word, 0) + 1
        else:
            failed[word] = failed.get(word, 0) + 1

    done, total = progress()
    print(f"[done] rings finished at {done}/{total}")
