"""LETTERS_TRACING and LETTERS_SLIDER_TRACING: stroke tracing, then the slide puzzle.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import heapq
import math
import re
import time

from alttester import By


# ----------------------------------------------------------------
# LETTERS_TRACING — "Magic Trace"
#
# The board is the IndieStudio EnglishTracingBook rig:
#
#   <X>-letter-shape            [Shape]        completed = whole letter done
#     Content/Paths
#       Path-1-2                [TracingPath]  completed / tracedPoints
#         Curve                 [Curve]        ENABLED only while this stroke
#           Point0..PointN                     is the one to draw next
#       Path-2-3 ... Path-N-M
#       FirstNumber / SecondNumber (the numbered circles, one pair per path)
#
# The strokes are ordered and the game hands them out one at a time: the only
# stroke you may draw is the one whose Curve is enabled. Its Point children are
# the collider dots the finger has to cross, and AltTester reports their live
# screen position — so the solver reads every coordinate off a named object and
# never assumes a resolution or a letter shape. A curved stroke simply carries
# more Points, and tracing through them in order follows the curve.
#
# A letter is drawn 4 times (ProgressText "n/4"); the same shape object is reset
# between repetitions rather than replaced. When the capital round is done the
# game switches to the lower round and the same loop draws the small letter.
# ----------------------------------------------------------------
_LT_ASM = "Assembly-CSharp"


_LT_PATH = "IndieStudio.EnglishTracingBook.Game.TracingPath"


_LT_MANAGER = "com.kideo.learn.english.LettersTracingGameManager"


# Floor for a stroke gesture, in seconds. Measured live: 0.10 tunnels past the
# point colliders and the stroke does not register, 0.15 and 0.30 both land.
_LT_MIN_SWIPE = 0.25


# Extra samples held on the stroke's end so the release is not simulated in the
# same instant the finger arrives.
_LT_END_DWELL = 6


# How far past the final point to carry the finger, as a fraction of screen
# height (~10px at 849). A stroke is completed by its FILL, not by its points,
# and stopping exactly on the last point leaves the fill a thousandth short.
_LT_OVERSHOOT = 0.012


def _lt_read_board(altdriver):
    """Every stroke of the letter on screen, in drawing order.

    Points are read with enabled=False too: the game disables the dots of every
    stroke but the current one, and we still want their positions so a stroke
    can be recognised before it goes live.
    """
    try:
        elements = altdriver.get_all_elements(enabled=False)
    except Exception:
        # The board is torn down the moment the activity ends; a read that
        # lands mid-teardown is "no strokes left", not a failure.
        return []
    children = {}
    for obj in elements:
        children.setdefault(obj.transformParentId, []).append(obj)

    # ONE Paths node per letter, and a board can show several. "Th" is two --
    # `T-letter-shape Variant` and `h-letter-shape Variant`, both under
    # `Th-sentence` -- and each numbers its OWN circles from 1. Reading only the
    # first node traced the T and left the h untouched for ever.
    paths_nodes = [o for o in elements if o.name == "Paths" and o.enabled]
    if not paths_nodes:
        return []

    def point_order(obj):
        return int(re.sub(r"\D", "", obj.name) or 0)

    board = []
    for group_index, paths_node in enumerate(sorted(paths_nodes, key=lambda o: o.x)):
        siblings = children.get(paths_node.transformId, [])
        # The numbered circles are siblings of the strokes, not children of them.
        # Each stroke starts on one, so they pair up by position.
        first_numbers = [c for c in siblings if c.name == "FirstNumber"]
        # `path.enabled` matters as much as the curve's. A letter shape can carry
        # strokes belonging to a form it is not drawing -- lowercase `g` ships
        # three Path objects for its two numbered strokes, the spare being the
        # alternative single-storey tail. That spare is a DISABLED object whose
        # Curve is still enabled, so filtering on the curve alone offers it as
        # the next stroke, and tracing it registers nothing (tracedPoints 0).
        for path in [c for c in siblings if c.name.startswith("Path-") and c.enabled]:
            dots, live, curve_obj, flipped = [], False, None, False
            for curve in [c for c in children.get(path.transformId, []) if c.name == "Curve"]:
                live = live or curve.enabled
                curve_obj = curve
                for dot in sorted([d for d in children.get(curve.transformId, [])
                                   if d.name.startswith("Point")], key=point_order):
                    # World coordinates too: they calibrate the curve's own samples,
                    # which are published in world space, onto the screen.
                    dots.append((float(dot.x), float(dot.y),
                                 float(dot.worldX), float(dot.worldY)))
            points = [(dot[0], dot[1]) for dot in dots]
            def sits_on(node, point):
                return abs(node.x - point[0]) <= 2 and abs(node.y - point[1]) <= 2

            circle = None
            if points:
                circle = next((n for n in first_numbers if sits_on(n, points[0])), None)
                if circle is None:
                    # Some strokes are stored END-TO-START: the opening circle sits
                    # on the LAST point, not the first. Capital G's crossbar is one
                    # -- circle 5 is on points[-1] and circle 6 on points[0]. Drawn
                    # as stored it runs backwards, the game refuses it, and the
                    # circle lookup below misses too, which silently switches the
                    # writing-order sort off. Flip it to the direction the numbers
                    # ask for.
                    circle = next((n for n in first_numbers if sits_on(n, points[-1])), None)
                    if circle is not None:
                        points.reverse()
                        dots.reverse()
                        flipped = True
            # The digit is on the circle's Text (TMP) child, not on the circle.
            label = None
            if circle is not None:
                label = next(iter(children.get(circle.transformId, [])), circle)
            board.append({"obj": path, "name": path.name, "live": live,
                          "points": points, "label": label, "dots": dots,
                          "curve": curve_obj, "flipped": flipped,
                          "letter": group_index, "letter_x": paths_node.x})
    return board


def _lt_curve_polyline(entry):
    """The stroke's real curve in screen coordinates, or None to keep the dots.

    The Point children are sparse CONTROL points -- 8 for a capital G, 15 for a
    lowercase g bowl -- and joining them with straight chords cuts across the
    inside of every bend. `Curve.bezierPoints` is the same stroke sampled
    properly (21 and 32 respectively), but published in WORLD space, so it is
    calibrated onto the screen using the dots, which carry both coordinates.
    That keeps it resolution independent.

    Honest note: this was written to cure a capital G that would not complete,
    and it did NOT cure it -- the cause there was the fill threshold, see the
    overshoot in `_lt_trace`. It is kept because following the real curve is
    simply more faithful than chording across bends, and it costs one property
    read per stroke, once the letter has settled.
    """
    dots = entry.get("dots") or []
    curve = entry.get("curve")
    if curve is None or len(dots) < 2:
        return None
    try:
        bezier = curve.get_component_property(
            "IndieStudio.EnglishTracingBook.Game.Curve", "bezierPoints",
            _LT_ASM, max_depth=1)
    except Exception:
        return None
    if not bezier or len(bezier) <= len(dots):
        return None                       # no finer than what we already have

    def fit(world_index, screen_index):
        """Least-squares world -> screen for one axis, or None if it is flat."""
        world = [dot[world_index] for dot in dots]
        screen = [dot[screen_index] for dot in dots]
        mean_w = sum(world) / len(world)
        mean_s = sum(screen) / len(screen)
        variance = sum((w - mean_w) ** 2 for w in world)
        if variance < 1e-6:
            return None                   # a straight vertical/horizontal stroke
        scale = sum((w - mean_w) * (s - mean_s) for w, s in zip(world, screen)) / variance
        return scale, mean_s - scale * mean_w

    fit_x, fit_y = fit(2, 0), fit(3, 1)
    if fit_x is None and fit_y is None:
        return None
    # The mapping is uniform, so a flat axis can borrow the other's scale.
    if fit_x is None:
        scale = abs(fit_y[0])
        fit_x = (scale, sum(d[0] for d in dots) / len(dots)
                 - scale * sum(d[2] for d in dots) / len(dots))
    if fit_y is None:
        scale = abs(fit_x[0])
        fit_y = (scale, sum(d[1] for d in dots) / len(dots)
                 - scale * sum(d[3] for d in dots) / len(dots))

    try:
        line = [(fit_x[0] * point["x"] + fit_x[1], fit_y[0] * point["y"] + fit_y[1])
                for point in bezier]
    except Exception:
        return None
    # bezierPoints run in the curve's own direction, which is the direction the
    # dots came in before any flip.
    if entry.get("flipped"):
        line.reverse()
    return line


def _lt_writing_order(board):
    """The strokes sorted the way the letter is written: 1 to 2, then 3 to 4...

    Sort by the number PRINTED on each stroke's starting circle, never by the
    object's name. `Path-1-2`/`Path-2-3` are node ids, not an order: on a
    lowercase `d` the bowl is `Path-2-3` and carries circle 1 while the stem is
    `Path-1-2` and carries circle 3, so name order draws the stem first, into a
    stroke the game has not offered yet. It registers nothing (tracedPoints
    stays 0) and the letter never completes. Capital `A` hid this because there
    the two orders happen to agree.

    Falls back to the order the strokes appear in when a circle cannot be read,
    which is the same thing for letters whose numbering is already sequential.

    The sort is WITHIN each letter and never across them. A board can show more
    than one letter -- "Th" is a T and an h side by side -- and each numbers its
    own circles from 1, so sorting the whole board by the printed digit would
    interleave them (T's 1, h's 1, T's 3, h's 3) and draw neither. Letters are
    taken whole, the one the game is currently offering first and the rest left
    to right.
    """
    def printed(entry):
        label = entry.get("label")
        if label is None:
            return None
        try:
            digits = re.sub(r"\D", "", label.get_text() or "")
            return int(digits) if digits else None
        except Exception:
            return None

    letters = {}
    for index, entry in enumerate(board):
        letters.setdefault(entry.get("letter", 0), []).append((printed(entry), index, entry))

    def live_first(item):
        _key, strokes = item
        offered = any(entry["live"] and not _lt_path_completed(entry)
                      for _, _, entry in strokes)
        return (0 if offered else 1, strokes[0][2].get("letter_x", 0))

    ordered = []
    for _key, strokes in sorted(letters.items(), key=live_first):
        if any(number is None for number, _, _ in strokes):
            ordered.extend(entry for _, _, entry in strokes)     # leave as found
        else:
            ordered.extend(entry for _, _, entry in
                           sorted(strokes, key=lambda item: item[0]))
    return ordered


def _lt_path_completed(path):
    try:
        return bool(path["obj"].get_component_property(_LT_PATH, "completed", _LT_ASM))
    except Exception:
        return False


def _lt_path_alive(path):
    """False once the stroke's object is gone.

    The letter shape is rebuilt at activity start and whenever the round flips,
    which leaves the handles from an earlier board pointing at destroyed
    objects. Retracing those coordinates draws nothing; the board has to be
    read again instead.
    """
    try:
        path["obj"].get_component_property(_LT_PATH, "completed", _LT_ASM)
        return True
    except Exception:
        return False


def _lt_active(board):
    """The stroke the game is waiting for, or None."""
    for path in board:
        if path["live"] and len(path["points"]) >= 2 and not _lt_path_completed(path):
            return path
    return None


def _lt_progress(altdriver):
    """(done, total) off ProgressText, or (None, None) while it is missing."""
    try:
        done, total = altdriver.find_object(By.NAME, "ProgressText").get_text().split("/")
        return int(done), int(total)
    except Exception:
        return None, None


def _lt_round(altdriver):
    """Name + letterType (0 = capital, 1 = small) of the round being played."""
    try:
        manager = altdriver.find_object(By.NAME, "LettersTracingGameManager")
        current = manager.get_component_property(_LT_MANAGER, "currentRound", _LT_ASM, max_depth=1)
        return current.get("name"), current.get("letterType")
    except Exception:
        return None, None


def _lt_feedback_up(altdriver):
    """True once the end-of-activity feedback is on screen."""
    try:
        return altdriver.find_object(By.NAME, _LT_FEEDBACK) is not None
    except Exception:
        return False


def _lt_wait_for_letter(altdriver, timeout=30.0, poll=0.25, stable_reads=3):
    """Every stroke of the next letter, once it is live AND has stopped moving.

    Returns the WHOLE letter rather than one stroke: within a letter the shape
    does not move, so reading it once and then drawing 1->2, 3->4, 5->6 in order
    costs one board read instead of one per stroke. A board read is the most
    expensive call in this solver (~0.35s over ~2800 objects), so this is where
    most of the time went.

    The letter still animates in after every repetition and again when the round
    flips to the small letter; dots grabbed mid-animation trace a path that is
    no longer where the letter is, and the ease-out tail means two matching
    reads can still catch it drifting — hence three in a row before it counts as
    settled.
    """
    deadline = time.time() + timeout
    previous, repeats = None, 0
    while time.time() < deadline:
        # The finished activity keeps a board on screen behind the feedback, so
        # without this the solver traces the same letter over and over into a
        # game that has already ended, then waits out the whole idle timeout.
        if _lt_feedback_up(altdriver):
            return None
        board = _lt_read_board(altdriver)
        if _lt_active(board) is not None:
            current = [path["points"] for path in board]
            repeats = repeats + 1 if previous == current else 1
            previous = current
            if repeats >= stable_reads:
                # Read the printed numbers and the curve samples only here,
                # once the letter has settled, so the polling above stays cheap.
                ordered = _lt_writing_order(board)
                for entry in ordered:
                    finer = _lt_curve_polyline(entry)
                    if finer:
                        entry["points"] = finer
                return ordered
        else:
            previous, repeats = None, 0
        time.sleep(poll)
    return None


def _lt_trace(altdriver, points, height):
    """Draw one stroke as a single gesture: press on the first point, glide
    through the rest, release on the last one.

    `swipe()` presses and lifts on every call, so a stroke built out of swipes
    is really N separate taps and the game drops it. A held begin/move/end
    works but costs a round trip per sample — ~70 of them, 1.2s, for one
    stroke. `multipoint_swipe` is the same gesture in ONE command.

    Duration is what actually decides whether it registers, not the number of
    samples: the engine walks the gesture over that many seconds of frames, and
    measured live, 0.10s tunnels straight past the point colliders while 0.15s
    and 0.30s both land. So the duration is scaled to the stroke's own length
    with a floor well above the failing edge.
    """
    step = max(4.0, height * 0.02)
    samples = [points[0]]
    span = 0.0
    for start, end in zip(points, points[1:]):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        span += length
        slices = max(1, int(length / step))
        for i in range(1, slices + 1):
            ratio = i / slices
            samples.append((start[0] + (end[0] - start[0]) * ratio,
                            start[1] + (end[1] - start[1]) * ratio))

    # Carry the finger a little PAST the final point before releasing.
    #
    # What completes a stroke is its FILL reaching `completeOffset`, not its
    # points. Measured live on a capital G: ending exactly on the last point
    # leaves fillAmount at 0.848946 against an offset of 0.85 -- short by one
    # thousandth. Every point registers (tracedPoints 8 of 8) and the stroke is
    # still refused, so retrying it is futile; it fails identically forever.
    # Reaching ~10px further along the last segment takes the fill to 1.0.
    if len(samples) >= 2:
        (prev_x, prev_y), (last_x, last_y) = samples[-2], samples[-1]
        delta_x, delta_y = last_x - prev_x, last_y - prev_y
        length = math.hypot(delta_x, delta_y)
        if length > 1e-6:
            overshoot = max(6.0, height * _LT_OVERSHOOT)
            for i in range(1, max(1, int(overshoot / step)) + 1):
                reach = overshoot * i / max(1, int(overshoot / step))
                samples.append((last_x + delta_x / length * reach,
                                last_y + delta_y / length * reach))

    # Then sit still for a few frames so the release is not simulated in the
    # same instant the finger arrives.
    samples.extend([samples[-1]] * _LT_END_DWELL)

    duration = max(_LT_MIN_SWIPE, span / height * 0.6)
    altdriver.multipoint_swipe([list(sample) for sample in samples], duration=duration)


def _lt_wait_completed(path, timeout=1.0, poll=0.05):
    """Poll the stroke's own `completed` flag instead of sleeping a fixed beat.

    A completed stroke confirms in ~0.02s, so the old flat 0.6s wait after every
    stroke was almost entirely dead time.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _lt_path_completed(path):
            return True
        time.sleep(poll)
    return False


def _lt_dismiss_dialogs(altdriver):
    """Clear the confirm/booster popups that swallow touches while they are open."""
    for dialog, button in (("ResetShapeConfirmDialog", "NoButton"),
                           ("RenewHelpBoosterDialog", "NoButton")):
        try:
            popup = altdriver.find_object(By.NAME, dialog)
            if not popup.get_component_property("UnityEngine.GameObject", "activeInHierarchy",
                                                "UnityEngine.CoreModule"):
                continue
        except Exception:
            continue
        try:
            popup.find_object_from_object(By.NAME, button).click()
            print(f"[INFO] dismissed {dialog}")
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] could not dismiss {dialog}: {e}")


_LT_FEEDBACK = "FeedbackPopup(Clone)"


def _lt_exit_feedback(altdriver, timeout=25.0, poll=1.0):
    """Close the end-of-activity feedback so the app returns to activity selection.

    The run ends on FeedbackPopup(Clone); until its ExitButton is clicked the
    app sits in LETTERS_TRACING behind the popup and whatever runs next opens
    on top of it. Nothing on this screen is read or graded — it is only closed.
    The button is clicked as an object, never at a coordinate.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            popup = altdriver.find_object(By.NAME, _LT_FEEDBACK)
            popup.find_object_from_object(By.NAME, "ExitButton").click()
            print("[INFO] closed the final feedback popup")
            return True
        except Exception:
            time.sleep(poll)
    print("[WARN] final feedback popup never appeared — nothing to close")
    return False


def letters_tracing(altdriver, stroke_attempts=6, idle_timeout=30.0,
                    reread_timeout=25.0):
    """Trace every letter of the Magic Trace activity, capital round then small.

    Reads the letter once, then draws its strokes in the order the letter is
    written — 1 to 2, then 3 to 4, then 5 to 6 — each as one gesture that
    releases on its final point. Still state driven: the letter, the number of
    strokes, the repetitions and the rounds all come from the board, so it
    follows however the activity is configured without being told any of them.
    """
    print("[INFO] LETTERS_TRACING: starting")

    _width, height = (float(v) for v in altdriver.get_application_screensize())

    strokes = 0
    letters = 0
    rounds_seen = []
    last_round, last_type = _lt_round(altdriver)
    if last_round:
        rounds_seen.append(last_round)
        print(f"[INFO] round '{last_round}' "
              f"({'capital' if last_type == 0 else 'small'} letters)")

    while True:
        _lt_dismiss_dialogs(altdriver)

        board = _lt_wait_for_letter(altdriver, timeout=idle_timeout)
        if board is None:
            print("[INFO] no stroke offered any more — activity finished")
            break

        # A new round means the small-letter half started; say so, it is the
        # part of this activity that is easiest to silently skip.
        name, letter_type = _lt_round(altdriver)
        if name and name != last_round:
            rounds_seen.append(name)
            print(f"[INFO] round changed to '{name}' "
                  f"({'capital' if letter_type == 0 else 'small'} letters)")
            last_round, last_type = name, letter_type
            # The round flip tears the whole rig down and builds a new letter,
            # so the board that just went quiet is not the board that will take
            # input. This is where the solver used to fail outright. Wait for a
            # longer run of identical reads before trusting the new letter.
            settled = _lt_wait_for_letter(altdriver, timeout=idle_timeout,
                                          stable_reads=5)
            if settled is not None:
                board = settled

        # Walk the strokes in writing order off the one board read.
        restart = False
        for index in range(len(board)):
            stroke = board[index]
            if _lt_path_completed(stroke):
                continue                      # already drawn, e.g. after a retry

            drawn = False
            for attempt in range(1, stroke_attempts + 1):
                _lt_trace(altdriver, stroke["points"], height)
                # Give a stroke that missed a little longer each time round.
                if _lt_wait_completed(stroke, timeout=1.0 + 0.5 * attempt):
                    strokes += 1
                    drawn = True
                    break
                stale = not _lt_path_alive(stroke)
                print(f"[WARN] {stroke['name']} did not register "
                      f"(attempt {attempt}/{stroke_attempts}) — "
                      f"{'board went stale, re-reading' if stale else 'retrying'}")
                # A settled letter is worth simply drawing again: one gesture,
                # far cheaper than going back to the board. But a stale handle
                # can only be fixed by re-reading, and retracing it would draw
                # into nothing — so that case never waits for a second failure.
                if stale or attempt >= 2:
                    refreshed = _lt_wait_for_letter(altdriver, timeout=reread_timeout)
                    if refreshed is None:
                        restart = True
                        break
                    # Rebind by NAME, never by position. When the round flips,
                    # the board that comes back belongs to a DIFFERENT letter
                    # with its own strokes, and index 0 of the new letter is not
                    # the stroke we were drawing -- that mismatch is what made
                    # this fail three attempts in a row and give up.
                    if [p["name"] for p in refreshed] != [p["name"] for p in board]:
                        print("[INFO] a different letter is on the board now — "
                              "starting it from its first stroke")
                        restart = True
                        break
                    board = refreshed
                    stroke = next(p for p in board if p["name"] == stroke["name"])
            if restart:
                break
            if not drawn:
                raise AssertionError(
                    f"LETTERS_TRACING: stroke {stroke['name']} would not complete "
                    f"after {stroke_attempts} attempts")

        if restart:
            continue                          # re-read the letter from the top

        done, total = _lt_progress(altdriver)
        if done is not None and done != letters:
            letters = done
            print(f"[INFO] letter traced — progress {done}/{total} in '{last_round}'")

    done, total = _lt_progress(altdriver)
    closed = _lt_exit_feedback(altdriver)

    print(f"LETTERS_TRACING RESULT: {strokes} strokes drawn across rounds "
          f"{rounds_seen or ['unknown']}; final progress {done}/{total}; "
          f"final feedback {'closed' if closed else 'not seen'}. "
          f"Traced with real finger drags over the game's own stroke points; "
          f"the score and stars on the feedback screen are not asserted.")


# ----------------------------------------------------------------
# LETTERS_SLIDER_TRACING — the tracing grid that ends in a slide puzzle
#
# One board of nine tiles (`BOARD/Content/For_Wide_Res`), each a
# `Tile_With_Boarder Variant(Clone)` carrying two things:
#
#   TIle_Text            its number, 1..9 -- its place in the finished picture
#   LetterText - RTLTMP  the letter to trace; GONE once that tile is done
#
# The activity runs in two halves, and ProgressText counts them ("n/2"):
#
#   1. Tap each tile in turn. It opens the ordinary tracing rig -- the same
#      Paths/Curve/Point objects as LETTERS_TRACING -- so the letter is drawn by
#      the very same helpers, and the tile returns to the grid without its
#      letter.
#   2. With all nine traced the tiles turn into pieces of one picture and tile 9
#      switches OFF: that hidden tile is the gap of a 3x3 slide puzzle. Tapping
#      a tile next to the gap slides it in. Ordering 1..9 reveals the picture.
#
# Then the run ends on the shared FeedbackPopup(Clone), closed the same way.
# ----------------------------------------------------------------
_LST_TILE = "Tile_With_Boarder"


_LST_GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 9)      # 9 is the hidden tile, bottom right


def _lst_read_tiles(altdriver):
    """The nine tiles in reading order, with the number and letter each shows."""
    try:
        elements = altdriver.get_all_elements(enabled=False)
    except Exception:
        return []
    children = {}
    for obj in elements:
        children.setdefault(obj.transformParentId, []).append(obj)

    def descendants(node, depth=0):
        if depth > 4:
            return
        for child in children.get(node.transformId, []):
            yield child
            yield from descendants(child, depth + 1)

    tiles = []
    for tile in [o for o in elements if o.name.startswith(_LST_TILE)]:
        number = letter = None
        for node in descendants(tile):
            if node.name == "TIle_Text" and number is None:
                try:
                    number = (node.get_text() or "").strip()
                except Exception:
                    pass
            elif node.name.startswith("LetterText") and letter is None:
                try:
                    letter = (node.get_text() or "").strip() or None
                except Exception:
                    pass
        tiles.append({"obj": tile, "number": number, "letter": letter,
                      "x": float(tile.x), "y": float(tile.y), "shown": tile.enabled})
    # Screen y runs bottom-up, so the top row is the HIGHEST y.
    return sorted(tiles, key=lambda t: (-t["y"], t["x"]))


def _lst_tap(altdriver, tile):
    """Press a tile at the position it is reporting right now.

    The tiles are driven by a raycasting input handler, not by the Unity event
    system: `AltObject.click()` and `.tap()` on the tile both do nothing at all,
    and the inner `Tile` child has no handler on it either. A positional tap is
    the only press this board answers. The coordinate still comes from the named
    object, never from a constant, so it survives any resolution.
    """
    altdriver.tap((tile["x"], tile["y"]))


def _lst_grid(tiles):
    """(state, xs, ys) — the numbers in reading order plus the lattice."""
    xs = sorted({t["x"] for t in tiles})
    ys = sorted({t["y"] for t in tiles}, reverse=True)
    if len(xs) != 3 or len(ys) != 3 or len(tiles) != 9:
        return None, xs, ys
    state = [None] * 9
    for tile in tiles:
        try:
            state[ys.index(tile["y"]) * 3 + xs.index(tile["x"])] = int(tile["number"])
        except (TypeError, ValueError):
            return None, xs, ys
    return (tuple(state) if all(v is not None for v in state) else None), xs, ys


def _lst_solve(state):
    """A* over the 3x3 slide puzzle; the moves are the tiles to tap, in order."""
    def remaining(board):
        return sum(abs(i // 3 - (v - 1) // 3) + abs(i % 3 - (v - 1) % 3)
                   for i, v in enumerate(board) if v != 9)

    queue = [(remaining(state), 0, state, [])]
    best = {state: 0}
    while queue:
        _, cost, board, path = heapq.heappop(queue)
        if board == _LST_GOAL:
            return path
        gap = board.index(9)
        gap_row, gap_col = divmod(gap, 3)
        for step_row, step_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            row, col = gap_row + step_row, gap_col + step_col
            if not (0 <= row < 3 and 0 <= col < 3):
                continue
            index = row * 3 + col
            moved = list(board)
            moved[gap], moved[index] = moved[index], moved[gap]
            moved = tuple(moved)
            if best.get(moved, 1 << 30) <= cost + 1:
                continue
            best[moved] = cost + 1
            heapq.heappush(queue, (cost + 1 + remaining(moved), cost + 1,
                                   moved, path + [index]))
    return None


def _lst_wait_for_grid(altdriver, timeout=25.0, poll=0.4):
    """The tiles, once the tracing view has closed and the board is back."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _lt_read_board(altdriver):
            tiles = _lst_read_tiles(altdriver)
            if len(tiles) == 9:
                return tiles
        time.sleep(poll)
    return None


def _lst_wait_for_letters(altdriver, timeout=45.0, poll=0.5):
    """The tiles of the next letter round, or None once the activity is over.

    Between rounds the board shows the finished picture for a while before the
    next set of letters is dealt, so this has to be patient -- but it gives up
    the moment the feedback screen appears, which is what actually ends the
    activity. A board with no letters left on it is a finished round, not a new
    one, so it keeps waiting.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _lt_feedback_up(altdriver):
            return None
        if not _lt_read_board(altdriver):
            tiles = _lst_read_tiles(altdriver)
            if len(tiles) == 9 and any(tile["letter"] for tile in tiles):
                return tiles
        time.sleep(poll)
    return None


def _lst_trace_round(altdriver, height, stroke_attempts, tile_attempts):
    """Trace every letter on the board in front of us. Returns (letters, strokes)."""
    letters = strokes = 0
    while True:
        tiles = _lst_wait_for_grid(altdriver)
        if tiles is None:
            raise AssertionError("LETTERS_SLIDER_TRACING: the tile board never appeared")
        pending = [tile for tile in tiles if tile["letter"]]
        if not pending:
            return letters, strokes
        tile = pending[0]

        board = None
        for attempt in range(1, tile_attempts + 1):
            _lst_tap(altdriver, tile)
            board = _lt_wait_for_letter(altdriver, timeout=15.0)
            if board:
                break
            print(f"[WARN] tile {tile['number']} did not open its letter "
                  f"(attempt {attempt}/{tile_attempts})")
            refreshed = _lst_wait_for_grid(altdriver, timeout=10.0)
            if refreshed:
                tile = next((t for t in refreshed if t["number"] == tile["number"]), tile)
        if not board:
            raise AssertionError(
                f"LETTERS_SLIDER_TRACING: tile {tile['number']} would not open")

        for stroke in board:
            if _lt_path_completed(stroke):
                continue
            for _ in range(stroke_attempts):
                _lt_trace(altdriver, stroke["points"], height)
                if _lt_wait_completed(stroke):
                    strokes += 1
                    break
            else:
                raise AssertionError(
                    f"LETTERS_SLIDER_TRACING: stroke {stroke['name']} of tile "
                    f"{tile['number']} would not complete")
        letters += 1
        print(f"[INFO] traced '{tile['letter']}' on tile {tile['number']} "
              f"({letters} this round)")


def _lst_order_pieces(altdriver, passes=4):
    """Slide the picture into 1..9 order. Returns the number of moves made."""
    moves = 0
    for attempt in range(1, passes + 1):
        tiles = _lst_wait_for_grid(altdriver)
        if tiles is None:
            return moves
        state, xs, ys = _lst_grid(tiles)
        if state is None:
            print("[WARN] could not read the tile numbers — leaving the puzzle alone")
            return moves
        if state == _LST_GOAL:
            print(f"[INFO] picture ordered in {moves} moves")
            return moves
        plan = _lst_solve(state)
        if plan is None:
            raise AssertionError(f"LETTERS_SLIDER_TRACING: puzzle {state} cannot be solved")
        print(f"[INFO] puzzle pass {attempt}: {state} — {len(plan)} moves")
        for index in plan:
            # Replay against the lattice rather than re-reading the board for
            # every move; a missed slide is caught by the next pass, which
            # re-reads and re-plans from whatever is actually on screen.
            altdriver.tap((xs[index % 3], ys[index // 3]))
            moves += 1
            time.sleep(0.45)
        time.sleep(1.0)
    raise AssertionError("LETTERS_SLIDER_TRACING: the puzzle would not come out")


def letters_slider_tracing(altdriver, stroke_attempts=4, tile_attempts=3,
                           round_timeout=45.0):
    """Trace the slider board's letters and order its picture, round after round.

    Most levels give ONE letter round -- nine tiles to trace, then the slide
    puzzle -- but some deal several, each with its own letters and its own
    picture. Nothing here is told how many: it keeps taking rounds until the
    activity puts up its feedback screen, so it follows whatever the level was
    built with.
    """
    print("[INFO] LETTERS_SLIDER_TRACING: starting")
    _width, height = (float(v) for v in altdriver.get_application_screensize())

    rounds = traced = strokes = moves = 0
    seen_letters = []

    while True:
        tiles = _lst_wait_for_letters(altdriver, timeout=round_timeout)
        if tiles is None:
            break
        rounds += 1
        letters = sorted({tile["letter"] for tile in tiles if tile["letter"]})
        seen_letters.append("".join(letters))
        print(f"[INFO] round {rounds}: letters {letters}")

        round_traced, round_strokes = _lst_trace_round(
            altdriver, height, stroke_attempts, tile_attempts)
        traced += round_traced
        strokes += round_strokes
        print(f"[INFO] round {rounds}: all {round_traced} letters traced — "
              f"ordering the picture")
        moves += _lst_order_pieces(altdriver)

    closed = _lt_exit_feedback(altdriver)
    print(f"LETTERS_SLIDER_TRACING RESULT: {rounds} round(s) "
          f"{seen_letters or ['none']}, {traced} letters traced "
          f"({strokes} strokes), pictures ordered in {moves} moves, "
          f"final feedback {'closed' if closed else 'not seen'}. "
          f"Traced with real finger drags over the game's own stroke points; "
          f"the score and stars on the feedback screen are not asserted.")
