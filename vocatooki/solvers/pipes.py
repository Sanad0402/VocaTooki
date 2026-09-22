"""PIPES.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import re
import time

from alttester import By


def _pipes_trace(altdriver, path, difficulty=""):
    """Trace one sentence along its pipes. Returns True if a stroke was made.

    Four things about this activity are not obvious, all found against the live
    build. They apply to every difficulty -- the world-segment touch drag this
    replaced scored 0 on hard and medium as well as easy:

    1. The stroke needs BOTH input systems. The pipes carry an EventTrigger
       listening for Drag/EndDrag; `move_touch` never reaches that handler
       (`beingHeld` stays False for every point on the path), while `move_mouse`
       alone just slides an unpressed pointer around. Holding a touch open sets
       `beingHeld` and the handler then follows the mouse, so `begin_touch`
       latches, `move_mouse` steers, `end_touch` releases. The press must land
       ON a pipe, so it is anchored to the first letter.

    2. `pipesPositions` is only a straight nominal segment (both endpoints share
       one y) while the pipes are drawn as S-curves, so following that line
       leaves the pipe. The real curve is spelled out by the letter tiles
       (`PipeTextPref(Clone)`) lying along it. They stop short of the end caps,
       so each run is extended along its own tangent -- ending early scores
       nothing -- by an amount scaled to the letter spacing, because the board
       is laid out at different sizes between rounds.

    3. The wheels joining consecutive pipes are named Junction, Junction_1,
       Junction_2 ... and the path only counts if the stroke passes through
       them, so each gap is crossed via the nearest wheel, and a pipe that feeds
       a wheel is followed all the way into it.

    4. Only the FIRST pipe gets a head extension. A later pipe is entered from
       the wheel it comes out of; extrapolating backwards from its first letter
       lands outside the pipe and drops the latch mid-stroke, which is what made
       medium trace two pipes and then stall on the third.
    """
    HEAD_GAPS, HEAD_MIN, HEAD_MAX = 4.0, 40.0, 140.0
    TAIL_GAPS, TAIL_MIN, TAIL_MAX = 8.0, 90.0, 300.0
    # On easy the final pipe runs much further past its last letter than on the
    # other boards, so the stroke stops short of the closing junction unless the
    # last tail is driven harder. Easy only -- medium and hard are correct as is.
    LAST_TAIL_GAPS, LAST_TAIL_MAX = 20.0, 700.0
    JUNCTION_RADIUS = 120.0
    STEP_PX, STEP_DUR = 10.0, 0.03
    easy = "easy" in (difficulty or "").lower()

    pipes_at, letters, junctions = {}, [], []
    for e in altdriver.get_all_elements(enabled=True):
        name = e.name
        try:
            if name.startswith("Pipe_") and name.split("_")[-1].isdigit():
                pipes_at[name] = e.get_screen_position()
            elif "PipeTextPref" in name:
                text = (e.get_text() or "").strip()
                if text:
                    p = e.get_screen_position()
                    letters.append((p[0], p[1], text))
            elif name.startswith("Junction"):
                junctions.append(e.get_screen_position())
        except Exception:
            continue

    by_pipe = {}
    for x, y, text in letters:
        best, best_d = None, float("inf")
        for name, centre in pipes_at.items():
            d2 = (centre[0] - x) ** 2 + (centre[1] - y) ** 2
            if d2 < best_d:
                best, best_d = name, d2
        by_pipe.setdefault(best, []).append((x, y, text))

    # order each pipe's tiles so they spell the sentence; that also confirms the
    # right tiles were picked, since decoy words sit on the other pipes
    want = re.sub(r"\s+", "", path.get("sentence") or "")
    runs, spelled = [], ""
    for name in path.get("pipesNames") or []:
        tiles = sorted(by_pipe.get(name) or [], key=lambda r: r[0])
        for candidate in (tiles, list(reversed(tiles))):
            if want[len(spelled):].startswith("".join(r[2] for r in candidate)):
                tiles = candidate
                break
        spelled += "".join(r[2] for r in tiles)
        runs.append([(r[0], r[1]) for r in tiles])

    if spelled != want or not runs or not runs[0]:
        print("[warn] letters do not spell the sentence yet — waiting")
        return False

    def beyond(end, prev, dist):
        dx, dy = end[0] - prev[0], end[1] - prev[1]
        mag = (dx * dx + dy * dy) ** 0.5 or 1.0
        return (end[0] + dx / mag * dist, end[1] + dy / mag * dist)

    def wheel_between(a, b):
        """The junction joining two points, if there is one."""
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        gap = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        near = [j for j in junctions
                if ((j[0] - mid[0]) ** 2 + (j[1] - mid[1]) ** 2) ** 0.5
                <= max(gap, JUNCTION_RADIUS)]
        if not near:
            return None
        return min(near, key=lambda q: (q[0] - mid[0]) ** 2 + (q[1] - mid[1]) ** 2)

    way = []
    for i, run in enumerate(runs):
        if len(run) < 2:
            way.extend(run)
            continue
        gap_px = (((run[-1][0] - run[0][0]) ** 2 +
                   (run[-1][1] - run[0][1]) ** 2) ** 0.5 / max(1, len(run) - 1))
        head_ext = max(HEAD_MIN, min(HEAD_MAX, gap_px * HEAD_GAPS))
        if easy and i == len(runs) - 1:
            tail_ext = max(TAIL_MIN, min(LAST_TAIL_MAX, gap_px * LAST_TAIL_GAPS))
        else:
            tail_ext = max(TAIL_MIN, min(TAIL_MAX, gap_px * TAIL_GAPS))

        if i == 0:
            # only the first pipe needs its own start cap covered
            way.append(beyond(run[0], run[1], head_ext))
        else:
            # Entry to any later pipe is the wheel it comes out of.
            # Extrapolating backwards from its first letter (as the first pipe
            # does) lands outside the pipe and drops the latch mid-stroke.
            j = wheel_between(way[-1], run[0])
            if j is not None:
                way.append((j[0], j[1]))

        way.extend(run)

        # The letters stop well short of where the pipe actually ends, so run
        # past them -- and when this pipe feeds a wheel, carry on into it so the
        # stroke cannot stop short of the connection.
        way.append(beyond(run[-1], run[-2], tail_ext))
        if i + 1 < len(runs) and runs[i + 1]:
            j = wheel_between(run[-1], runs[i + 1][0])
            if j is not None:
                way.append((j[0], j[1]))

    if len(way) < 2:
        return False

    samples = []
    for a, b in zip(way, way[1:]):
        dist = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        steps = max(1, int(dist / STEP_PX))
        for i in range(steps):
            samples.append((a[0] + (b[0] - a[0]) * i / steps,
                            a[1] + (b[1] - a[1]) * i / steps))
    samples.append(way[-1])

    anchor = runs[0][0]
    altdriver.move_mouse(anchor, duration=0.1)
    finger = altdriver.begin_touch(anchor)
    try:
        time.sleep(0.3)
        for p in samples:
            altdriver.move_mouse(p, duration=STEP_DUR)
        time.sleep(0.3)
    finally:
        altdriver.end_touch(finger)
    return True


def pipes(altdriver):
    """Solves PIPES by dragging along each correct pipe path.

    The build exposes its own answer key: `PipesStructureHandler`
    .correctPathsAutomationInfo gives, per sentence, the ordered `pipesNames`
    plus `pipesPositions` -- the segment endpoints in WORLD units
    ("x1,y1,x2,y2").

    That key lives on the panel for the CURRENT difficulty -- Pipes_Easy_Panel,
    Pipes_Medium_Panel or Pipes_Hard_Panel -- and the round switches between
    them as it progresses. Rather than hardcode the thresholds, every panel is
    checked and whichever actually holds paths is used.

    The key gives the pipes in order but not a usable route through them --
    `_pipes_trace` works that out from what is on screen. See its docstring for
    why the coordinates in the key cannot be followed directly.

    NOTE: the app must have OS focus while this runs -- Unity pauses play mode
    when the window is in the background.
    """
    SH_C = "com.kideo.learn.english.Pipes.PipesStructureHandler"
    ASM = "Assembly-CSharp"

    def progress():
        try:
            a, b = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
            return int(a), int(b)
        except Exception:
            return 0, 0

    def answer_key():
        """([{sentence, pipesNames, pipesPositions}, ...], difficulty).

        The key sits on whichever difficulty panel is currently live, so check
        them all -- reading only the hard panel finds nothing once the round
        moves to medium or easy.
        """
        for e in altdriver.get_all_elements(enabled=True):
            if not (e.name.startswith("Pipes_") and e.name.endswith("_Panel")):
                continue
            try:
                v = e.get_component_property(SH_C, "correctPathsAutomationInfo", ASM)
                if v:
                    return v, e.name.replace("Pipes_", "").replace("_Panel", "")
            except Exception:
                pass
        return [], ""


    done, total = progress()
    print("[info] starting pipes at %d/%d" % (done, total))
    stuck = 0
    solved = set()

    for _ in range(60):
        done, total = progress()
        if total and done >= total:
            print("[info] all %d sentences solved." % total)
            break

        key, panel = answer_key()
        if not key:
            stuck += 1
            if stuck > 8:
                print("[warn] no correct paths exposed — stopping.")
                break
            time.sleep(1.5)
            continue

        # Medium exposes more than one sentence at a time, and a solved one can
        # still appear in the key, so skip anything already traced.
        before = done
        for path in key:
            sentence = path.get("sentence") or ""
            if sentence in solved:
                continue
            print("[act] [%s] %s" % (panel, sentence[:52]))
            try:
                if not _pipes_trace(altdriver, path, panel):
                    continue
            except Exception as e:
                print("[warn] drag failed: %s" % e)
                continue
            time.sleep(2.0)
            now, total = progress()
            if now != before:
                print("[info] progress %d/%d" % (now, total))
                solved.add(sentence)
                before = now
                time.sleep(2.5)   # let the next board finish rebuilding
                break             # the board reshuffles after a solve — re-read

        if before == done:
            stuck += 1
            if stuck > 8:
                print("[warn] no progress — stopping.")
                break
        else:
            stuck = 0

    done, total = progress()
    print("[done] pipes finished at %d/%d" % (done, total))
