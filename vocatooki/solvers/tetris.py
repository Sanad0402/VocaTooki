"""TETRIS.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def tetris(altdriver):
    """Solves TETRIS: steer falling letter cubes to build the target word.

    Letter cubes (singles like 'e' or duos like 'pi') fall down the centre of a
    grid; Left/Right arrows shift the falling piece one column per tap and the
    Down arrow hard-drops it. The word is complete the moment its letters sit
    contiguously, in order, on the bottom row -- then the board clears and the
    next word loads. Wrong-letter cubes fall too and must be kept away.

    What this activity needed, all found against the live build:

    1. The answer. RTLTMPWordPanel's TMProWordPanel uses TWO data models across
       words: phrase model (Word.word='take a picture' / Text='take a _______',
       same length -- zip the blanks) and word model (Word.word='arrive' while
       Text still shows the PREVIOUS word's stale mask -- the answer is all of
       Word.word). Handling only the first model stalls forever on the second.

    2. The game's tiling. Words arrive split into consecutive PAIRS from the
       left with a final single only for odd lengths ('ta'+'ke', 'of'+'f',
       'pi'+'ct'+'ur'+'e'). Placement must match TILES, not letters: a stray
       single 'k' must be dumped even though 'k' is the next letter of 'take',
       because the real 'ke' duo needs both its columns free. A frontier
       fallback still accepts prefix-continuing pieces if no tile shows up for
       20s, in case a word is ever split differently.

    3. Physical ground truth. The bottom row is re-read every cycle: a correct
       letter at its word column counts as placed however it got there, and a
       placed letter that vanishes means the game RESET the board (dump stacks
       reaching the ceiling do that on long words like 'comfortable') -- the
       tile is then rebuilt when the game cycles it around again.

    4. Closed-loop movement. Arrow taps can be dropped by the game, so after
       tapping the piece's real column is re-read (only within the word/spawn
       corridor -- dump stacks to the right would masquerade as the piece) and
       the shortfall corrected. Dumps go strictly RIGHT of the corridor.

    5. Geometry is live. Grid columns/rows come from the CellPanel cells (the
       grid is sized to the longest word, so nothing is hardcoded), the spawn
       column is the centre, and a reference cell's x acts as a resize sentinel
       to re-derive everything if the window changes.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    ASM = "Assembly-CSharp"
    RUN_S = 600.0
    REF_CELL = "CellPanel (7)"      # stable named grid cell = resize sentinel
    geo = {"colx": [], "rowy": [], "row_h": 50.0, "spawn": 0, "ref_x": None}

    def _bands(vals, tol=25):
        vals = sorted(vals)
        bs = []
        for v in vals:
            if bs and abs(v - bs[-1][-1]) <= tol:
                bs[-1].append(v)
            else:
                bs.append([v])
        return [sum(b) / len(b) for b in bs]

    def capture_geometry():
        xs, ys = [], []
        for e in altdriver.get_all_elements(enabled=True):
            if e.name.startswith("CellPanel"):
                p = e.get_screen_position()
                xs.append(p[0])
                ys.append(p[1])
        if not xs:
            return False
        geo["colx"] = _bands(xs)
        geo["rowy"] = _bands(ys)
        R = len(geo["rowy"])
        geo["row_h"] = ((geo["rowy"][-1] - geo["rowy"][0]) / max(1, R - 1)
                        if R > 1 else 50.0)
        geo["spawn"] = len(geo["colx"]) // 2   # cubes spawn at the centre column
        try:
            geo["ref_x"] = altdriver.find_object(
                By.NAME, REF_CELL).get_screen_position()[0]
        except Exception:
            geo["ref_x"] = None
        return True

    def maybe_recapture():
        if geo["ref_x"] is None:
            return
        try:
            x = altdriver.find_object(By.NAME, REF_CELL).get_screen_position()[0]
            if abs(x - geo["ref_x"]) > 20:
                capture_geometry()
        except Exception:
            pass

    def col(x):
        cx = geo["colx"]
        return min(range(len(cx)), key=lambda i: abs(x - cx[i]))

    def row(y):
        ry = geo["rowy"]
        return min(range(len(ry)), key=lambda i: abs(y - ry[i]))

    ctl = {}

    def fetch_controls():
        try:
            ctl["left"] = altdriver.find_object(By.NAME, "LeftArrow")
            ctl["right"] = altdriver.find_object(By.NAME, "RightArrow ")
            ctl["down"] = altdriver.find_object(By.NAME, "DownArrow")
            return True
        except Exception:
            return False

    def progress():
        try:
            a, b = altdriver.find_object(
                By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def read_word():
        try:
            wp = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
            full = (wp.get_component_property("TMProWordPanel", "Word.word", ASM) or "")
            mask = (wp.get_component_property("TMProWordPanel", "Text", ASM) or "")
            return full, mask
        except Exception:
            return "", ""

    def target_of(full, mask):
        return "".join(fc for fc, mc in zip(full, mask) if mc == "_").lower()

    def letters_now():
        """Single-letter cubes inside the play area: (letter, x, y)."""
        out = []
        cx, ry, rh = geo["colx"], geo["rowy"], geo["row_h"]
        x_lo, x_hi = cx[0] - rh, cx[-1] + rh
        y_lo, y_hi = ry[0] - rh, ry[-1] + rh
        for e in altdriver.get_all_elements(enabled=True):
            if e.name == "Text":
                try:
                    t = (e.get_text() or "").strip().lower()
                except Exception:
                    t = ""
                if len(t) == 1 and t.isalpha():
                    p = e.get_screen_position()
                    if x_lo <= p[0] <= x_hi and y_lo <= p[1] <= y_hi:
                        out.append((t, p[0], p[1]))
        return out

    def bottom_row_letters():
        """col -> letter resting on the bottom row: the physical ground truth
        of what has been built (also reveals board resets)."""
        out = {}
        for (t, x, y) in letters_now():
            if row(y) == 0:
                out[col(x)] = t
        return out

    def active_piece():
        """The game-controlled falling piece = highest cube(s) AT the spawn
        columns (a single spawns at SPAWN, a duo at SPAWN/SPAWN+1). Capped at
        two cubes so landed neighbours never merge into a bogus piece."""
        sp = geo["spawn"]
        near = [(t, x, y) for (t, x, y) in letters_now() if col(x) in (sp, sp + 1)]
        if not near:
            return None
        top_y = max(y for (_, _, y) in near)
        if row(top_y) < 2:
            return None
        grp = sorted([(t, x) for (t, x, y) in near
                      if abs(y - top_y) < geo["row_h"] * 0.5],
                     key=lambda z: z[1])[:2]
        return ("".join(t for (t, _) in grp),
                col(min(x for (_, x) in grp)), row(top_y))

    def compute_tiles(target):
        """The game's split: consecutive pairs from the left, odd tail single.
        'picture' -> [(0,'pi'),(2,'ct'),(4,'ur'),(6,'e')]."""
        tiles, i = [], 0
        while i < len(target):
            n = 2 if i + 1 < len(target) else 1
            tiles.append((i, target[i:i + n]))
            i += n
        return tiles

    def top_anchor(max_col):
        """Leftmost column of the highest cube(s) within cols 0..max_col --
        restricted to the corridor so dump stacks never look like the piece."""
        letters = [(t, x, y) for (t, x, y) in letters_now() if col(x) <= max_col]
        if not letters:
            return None
        top_y = max(y for (_, _, y) in letters)
        if row(top_y) < 2:
            return None
        xs = [x for (t, x, y) in letters if abs(y - top_y) < geo["row_h"] * 0.5]
        return col(min(xs))

    def move_to(anchor, tc, bound):
        """Closed-loop move: spaced taps toward the target, then re-read the
        piece's real column and correct any dropped tap. Returns column reached."""
        cur = anchor
        for _ in range(5):
            shift = tc - cur
            if shift == 0:
                return cur
            btn = ctl["right"] if shift > 0 else ctl["left"]
            for _ in range(abs(shift)):
                btn.tap()
                time.sleep(0.14)
            time.sleep(0.06)
            a = top_anchor(bound)
            if a is None:
                return cur
            cur = a
        return cur

    def dump_move(anchor, tc):
        """Open-loop shove of a discarded piece (precision doesn't matter)."""
        shift = tc - anchor
        btn = ctl["right"] if shift > 0 else ctl["left"]
        for _ in range(abs(shift)):
            btn.tap()
            time.sleep(0.1)

    # ---- start early: begin the loop the moment grid+controls+word exist, so
    # the FIRST falling piece is caught high and never lands unsteered --------
    time.sleep(0.5)
    ready = False
    for _ in range(100):                    # up to ~30s for the intro
        if capture_geometry() and fetch_controls():
            full, mask = read_word()
            if target_of(full, mask) or (full and " " not in full.strip()):
                ready = True
                break
        time.sleep(0.3)
    if not ready:
        print("[warn] tetris: play screen never became ready.")
        return
    G = len(geo["colx"])
    R = len(geo["rowy"])
    print("[info] tetris: grid %dx%d, spawn col %d" % (G, R, geo["spawn"]))

    # ---- main solve loop (state persists per word) --------------------------
    t0 = time.time()
    last_log = 0.0
    dump_i = 0
    cur_full = None
    target = ""
    W = 0
    placed = []
    placed_at = []
    tiles = []
    blank_idx = []
    last_place = time.time()
    DUMP_START = G - 1

    while time.time() - t0 < RUN_S:
        maybe_recapture()
        G = len(geo["colx"])
        full, mask = read_word()
        a, b = progress()
        if b and a >= b:
            print("[info] tetris: all %d words complete." % b)
            return
        if not full:
            time.sleep(0.3)
            continue

        if full != cur_full:
            # two data models (see docstring): phrase+mask zip, or bare word
            if mask and len(full) == len(mask) and "_" in mask:
                blank_idx = [i for i, mc in enumerate(mask) if mc == "_"]
                target = "".join(full[i] for i in blank_idx).lower()
            elif " " not in full.strip():
                blank_idx = []
                target = full.strip().lower()
            else:
                if time.time() - last_log > 2.0:
                    print("   [wait] transition full=%r mask=%r" % (full, mask))
                    last_log = time.time()
                time.sleep(0.15)
                continue
            cur_full = full
            W = len(target)
            placed = [False] * W
            placed_at = [0.0] * W
            tiles = compute_tiles(target)
            last_place = time.time()
            # dumps go strictly RIGHT of the word columns AND the spawn pair
            DUMP_START = min(G - 1, max(W, geo["spawn"] + 2))
            print("[act] word %r -> build %r tiles=%s (prog %d/%d)"
                  % (full, target, tiles, a, b))
        if not target:
            time.sleep(0.3)
            continue

        # physical ground truth: reconcile with the bottom row (see docstring)
        onboard = bottom_row_letters()
        now_t = time.time()
        for j in range(W):
            if onboard.get(j) == target[j]:
                placed[j] = True
                placed_at[j] = now_t
            elif placed[j] and now_t - placed_at[j] > 3.0:
                print("   [reset] pos%d %r vanished; will rebuild" % (j, target[j]))
                placed[j] = False
        mask_fill = [(j < len(blank_idx) and blank_idx[j] < len(mask)
                      and mask[blank_idx[j]] != "_") for j in range(W)]
        filled = [placed[j] or mask_fill[j] for j in range(W)]
        if all(filled):
            time.sleep(0.4)
            continue                       # built; wait for the game to advance

        piece = active_piece()
        if piece is None:
            time.sleep(0.12)
            continue
        pl, anchor, tr = piece
        tdone = [all(filled[c] for c in range(s, s + len(lt)))
                 for (s, lt) in tiles]
        hit = next((idx for idx, (s, lt) in enumerate(tiles)
                    if lt == pl and not tdone[idx]), None)
        if hit is None:
            # frontier fallback for unexpected tilings (see docstring)
            np_ = next((j for j in range(W) if not filled[j]), W)
            if (time.time() - last_place > 20.0 and np_ < W
                    and np_ + len(pl) <= W and pl == target[np_:np_ + len(pl)]):
                tiles = tiles + [(np_, pl)]
                tdone = tdone + [False]
                hit = len(tiles) - 1
                print("   [fallback] accepting %r at frontier pos%d" % (pl, np_))
        if hit is not None:
            s, lt = tiles[hit]
            last_place = time.time()
            reached = move_to(anchor, s, bound=max(W - 1, geo["spawn"] + 1))
            ctl["down"].tap()
            if reached == s:
                for i in range(len(lt)):
                    placed[s + i] = True
                    placed_at[s + i] = time.time()
            print("   place %r cols%d..%d reached%d"
                  % (pl, s, s + len(lt) - 1, reached))
        else:
            dump_col = DUMP_START + (dump_i % max(1, G - DUMP_START))
            dump_i += 1
            dump_move(anchor, dump_col)
            ctl["down"].tap()
        time.sleep(0.5)

    a, b = progress()
    print("[warn] tetris: time budget exhausted at %d/%d." % (a, b))
