"""PUZZLES: build the sentence from its pieces on the 168-slot board.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By
from collections import Counter


# How many rearrange passes one sentence gets before the solver moves on. A
# pass is a full sweep over the sentence, so a solvable board is done in one or
# two; this only ever stops a board that CANNOT be assembled from the pieces
# the solver can read.
MAX_PASSES_PER_SENTENCE = 12


# Pieces of one sentence row share a y; this is how far apart two pieces may
# sit and still count as the same row.
ROW_HEIGHT_TOLERANCE = 30


def _puzzle_progress(progress_object):
    """How many sentences the game says are done, or None if unreadable."""
    try:
        return int(progress_object.get_text().split("/")[0])
    except (AttributeError, IndexError, ValueError):
        return None


def _screen_width(altdriver):
    """The game window's width in pixels, or None if it cannot be read."""
    try:
        return float(altdriver.call_static_method(
            "UnityEngine.Screen", "get_width", "UnityEngine.CoreModule"))
    except Exception:
        return None


def solve_puzzles(altdriver):
    time.sleep(10)
    print("[INFO] Puzzle solver started...")
    altdriver.wait_for_object(By.NAME, "ProgressText", timeout=15)
    progress = altdriver.find_object(By.NAME, "ProgressText")
    manager = altdriver.find_object(By.NAME, "PuzzlesManager")

    # "3/6" — the second half is how many sentences this puzzle has.
    raw = progress.get_text()
    try:
        total = int(raw.split("/")[1])
    except (IndexError, ValueError) as e:
        raise AssertionError(
            f"PUZZLES: ProgressText read {raw!r}, which is not 'done/total' - "
            f"the sentence count is unknown, so the puzzle cannot be played.") from e
    print(f"[INFO] Total sentences: {total}")

    # Sentences that could not be assembled; reported together at the end.
    unsolved = []
    # Consecutive sentences in which no click moved a single piece.
    dead_boards = 0
    # First piece id of each run already claimed by a sentence. Two sentences of
    # one puzzle can read word for word the same, and without this the second
    # would be handed the first one's pieces and never move.
    used_windows = set()
    # Pieces of sentences already built. A solved sentence KEEPS its words on
    # the board, and on a hard board two sentences share the same rows (the
    # grid is 14 columns, 7 on screen): sentence 7's slots are 140-146/154-160,
    # sentence 1's are 147-153/161-167. Both hold 'like' and 'to', so without
    # this the solver clicked sentence 1's locked, off-screen pieces and
    # nothing moved -- the "stuck at sentence 6/7" failure.
    solved_ids = set()
    # Only pieces inside the window can be the sentence being played; the
    # board scrolls, and the rest of the grid sits off screen.
    screen_w = _screen_width(altdriver)

    def playable(e):
        if e.name in solved_ids:
            return False
        if screen_w is not None and not (0 <= float(e.x) <= screen_w):
            return False
        return True

    # ===== Timer Extension for Hard =====
    if total > 6:
        try:
            timer = altdriver.find_object(By.NAME, "LenearTimer")
            timer.set_component_property(
                "com.kideo.learn.english.LenearTimerScript",
                "timeLeft",
                "Assembly-CSharp",
                1700
            )
            print("[INFO] Timer extended to 1700 for hard level.")
        except Exception as e:
            print(f"[WARNING] Failed to set timer: {e}")

    # ===== Difficulty Ranges =====
    if total == 4:  # EASY
        group_ranges = [(42, 55), (28, 41), (14, 27), (0, 13)]
    elif total == 6:  # NORMAL
        group_ranges = [(70, 83), (56, 69), (42, 55),
                        (28, 41), (14, 27), (0, 13)]
    elif total > 6:  # HARD
        group_ranges = [
            (147, 167), (119, 139), (91, 111), (63, 83),
            (35, 55), (7, 27), (140, 160), (112, 132),
            (84, 104), (56, 76), (28, 48), (0, 20)
        ]
    else:
        group_ranges = [(0, 9999)]

    def read_pieces(target_words, start_idx, end_idx):
        freq = Counter(target_words)
        pieces = []
        for e in reversed(altdriver.get_all_elements()):
            if not e.name.isdigit():
                continue
            num = int(e.name)
            if num < start_idx or num > end_idx or not e.enabled or not playable(e):
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if freq.get(word, 0) > 0:
                pieces.append({"obj": e, "text": word})
                freq[word] -= 1
            if sum(freq.values()) == 0:
                break
        pieces.sort(key=lambda p: (-p["obj"].y, p["obj"].x))
        return pieces

    def piece_map():
        """``{piece id: word}`` for every readable piece on the board."""
        out = {}
        for e in altdriver.get_all_elements():
            if not e.name.isdigit() or not e.enabled or not playable(e):
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if word:
                out[int(e.name)] = word
        return out

    def find_window(target_words, used):
        """The run of pieces that IS this sentence, as ``(first id, last id)``.

        The board is one grid of slots (168 of them on a hard puzzle) and a
        sentence owns a CONTIGUOUS run of piece ids -- which is what the
        `group_ranges` table above was guessing at. Guessing it is the whole
        bug: when the guess drifts, the solver picks up same-word pieces
        belonging to a neighbouring sentence and swaps those instead, so the
        sentence it is trying to build never changes. Two sentences of a puzzle
        can read word for word the same, so `used` keeps the second one from
        being handed the first one's pieces.
        """
        pieces = piece_map()
        ids = sorted(pieces)
        want = Counter(target_words)
        size = len(target_words)
        for start in range(len(ids) - size + 1):
            run = ids[start:start + size]
            if run[-1] - run[0] != size - 1:         # must be consecutive slots
                continue
            if run[0] in used:
                continue
            if Counter(pieces[k] for k in run) == want:
                return run[0], run[-1]
        return None

    def read_rows(target_words):
        """The board's ROWS that hold this sentence, top row first.

        The index windows above are per-difficulty guesses. When one drifts,
        `read_pieces` happily returns pieces belonging to a DIFFERENT row --
        and clicking those does nothing at all, because they are not the row
        being played. Two sentences with the same words (the puzzle repeats
        them) make that certain rather than unlucky. Pieces of one row share a
        y, so grouping by y gives the real candidates to try instead.
        """
        by_row = {}
        for e in altdriver.get_all_elements():
            if not e.name.isdigit() or not e.enabled or not playable(e):
                continue
            try:
                word = e.get_component_property("PuzzlePiece", "text.text", "Assembly-CSharp")
            except Exception:
                continue
            if word:
                by_row.setdefault(round(float(e.y) / ROW_HEIGHT_TOLERANCE), []).append(
                    {"obj": e, "text": word})

        want = Counter(target_words)
        rows = []
        for key, row in sorted(by_row.items(), key=lambda kv: -kv[0]):
            if Counter(p["text"] for p in row) == want:
                row.sort(key=lambda p: (-p["obj"].y, p["obj"].x))
                rows.append(row)
        return rows

    # A retry resumes a part-done board: start counting at the sentence the
    # game is on, so the messages and the fallback window match it (it used to
    # restart at 1 and call sentence 7 "sentence 2/7").
    first = _puzzle_progress(progress) or 0
    for i in range(min(first, total), total):
        # The puzzle may already be part-done (a retry resumes a board that a
        # previous attempt got most of the way through), and it ENDS the moment
        # the count is full. Without this the loop kept playing phantom
        # sentences on a finished board and called that a failure.
        done_now = _puzzle_progress(progress)
        if done_now is not None and done_now >= total:
            print(f"[DONE] the puzzle is complete ({done_now}/{total}).")
            break

        print(f"\n--- Sentence {i+1}/{total} ---")
        time.sleep(0.5)

        target = manager.get_component_property(
            "com.kideo.learn.english.PuzzlesManager",
            "currentSentence_",
            "Assembly-CSharp"
        ).split()
        print("[TARGET]", " ".join(target))

        # Which pieces ARE this sentence: found on the board, not guessed from
        # a difficulty table. The guessed table stays as a fallback for a board
        # this cannot read.
        window = find_window(target, used_windows)
        if window is not None:
            used_windows.add(window[0])
            print(f"[PIECES] sentence {i+1} is pieces {window[0]}-{window[1]}")
        else:
            window = group_ranges[i] if i < len(group_ranges) else (0, 9999)
            print(f"[PIECES] no run of pieces spells this sentence - falling back "
                  f"to the guessed window {window[0]}-{window[1]}")

        # A sentence is rearranged in PASSES, and the pass count is bounded.
        # Nothing here guarantees the board can reach the target: the index
        # windows above are per-difficulty guesses, so a window that misses a
        # piece leaves `pieces` shorter than the sentence, every index falls
        # through `idx >= len(pieces)`, and no click is ever made. That is how
        # `while True` used to sit on the puzzle forever with the run hung.
        solved = False
        previous = None
        stalled = 0
        # Did ANY click move this board? A puzzle that has ended (or timed out)
        # keeps its pieces on screen and keeps reporting a currentSentence_,
        # but ignores every click -- see the dead-board check after the loop.
        first_seen = None
        moved = False
        # None = the guessed index window (what has always worked); 0, 1, ... =
        # the board's rows holding this sentence, tried in turn when the window
        # picks a row whose pieces do not respond to a click.
        row_choice = None

        def read_now():
            nonlocal window
            if row_choice is not None:
                rows = read_rows(target)
                return rows[row_choice] if row_choice < len(rows) else []
            found = read_pieces(target, *window)
            if len(found) < len(target) and window != (0, 9999):
                # The window missed pieces - read the WHOLE board rather than
                # spin on a view that can never match the sentence. It stays
                # widened for the rest of this sentence, so the re-reads after
                # each swap below see the same pieces this pass did.
                print(f" [WIDEN] window {window[0]}-{window[1]} found "
                      f"{len(found)}/{len(target)} pieces - reading every piece.")
                window = (0, 9999)
                found = read_pieces(target, *window)
            return found

        for _pass in range(1, MAX_PASSES_PER_SENTENCE + 1):
            pieces = read_now()
            current = [p["text"] for p in pieces]
            print("[CURRENT]", " ".join(current))

            if first_seen is None:
                first_seen = current
            elif current != first_seen:
                moved = True

            if current == target:
                print(f"[OK] Sentence solved.")
                solved = True
                solved_ids.update(p["obj"].name for p in pieces)
                break

            # Two passes that change nothing will not start working on a third:
            # the swap rule is deterministic, so the same board makes the same
            # moves. A row that does not move under a click is the WRONG row,
            # so switch to the next candidate rather than giving up on the
            # sentence -- that is what left "The uncle lives in Berlin." unbuilt
            # while its pieces sat one row away.
            if current == previous:
                stalled += 1
                if stalled >= 2:
                    row_choice = 0 if row_choice is None else row_choice + 1
                    if row_choice >= len(read_rows(target)):
                        print(f" [STALL] no row of the board responds - giving up "
                              f"on sentence {i + 1}.")
                        break
                    print(f" [ROW] that row does not move under a click - "
                          f"trying board row {row_choice} instead.")
                    # Reading a DIFFERENT row changes `current` without a single
                    # piece having moved, so the movement check restarts here.
                    # Otherwise switching rows looks like progress and the
                    # dead-board exit below never fires.
                    stalled, previous, first_seen = 0, None, None
                    continue
            else:
                stalled = 0
            previous = current

            visited = set()

            for idx, want in enumerate(target):
                if idx >= len(pieces):
                    continue

                have = pieces[idx]["text"]
                if have == want:
                    visited.add(idx)
                    continue

                cand_idx = None
                for j in range(idx + 1, len(pieces)):
                    if pieces[j]["text"] != want:
                        continue
                    if j in visited:
                        continue
                    if j < len(target) and pieces[j]["text"] == target[j]:
                        continue
                    cand_idx = j
                    break

                if cand_idx is None:
                    continue

                visited.add(idx)
                # ASCII only: this solver has to survive a cp1252 console. A
                # '<->' here used to be a U+2194, and printing it killed the
                # run mid-sentence outside the panel (which sets UTF-8 itself).
                print(f" [SWAP] '{have}' <-> '{want}' (idx={idx}, j={cand_idx})")
                a_obj, b_obj = pieces[idx]["obj"], pieces[cand_idx]["obj"]

                try:
                    a_obj.click()
                    time.sleep(0.2)
                    b_obj.click()
                    time.sleep(1)
                except Exception:
                    print(" [WARNING] Swap click failed.")
                    continue

                pieces = read_now()
                current = [p["text"] for p in pieces]
                print("[AFTER SWAP]", " ".join(current))

                if idx < len(current) and current[idx] == want:
                    print(f" [VALID] '{want}' now correctly placed.")
                else:
                    print(f" [REVERT] '{want}' not correct - reverting.")
                    try:
                        a_obj.click()
                        time.sleep(1)
                        b_obj.click()
                        time.sleep(1)
                    except Exception:
                        print(" [WARNING] Revert failed.")

                    pieces = read_now()
                    current = [p["text"] for p in pieces]
                    print("[AFTER REVERT]", " ".join(current))

            time.sleep(0.5)

        if not solved:
            unsolved.append(i + 1)
            print(f"[WARN] Sentence {i+1}/{total} was not assembled - moving on.")

        # A puzzle that has ENDED -- finished, or its timer ran out -- leaves
        # the pieces on screen and keeps answering currentSentence_, but takes
        # no clicks at all. Grinding through the remaining sentences on a board
        # like that buys nothing, so stop as soon as it is recognisable: two
        # sentences running where not one click moved anything.
        if not solved and not moved:
            dead_boards += 1
            if dead_boards >= 2:
                raise AssertionError(
                    f"PUZZLES: the board stopped responding at sentence "
                    f"{i + 1}/{total} (ProgressText {progress.get_text()!r}). No "
                    f"click moved a piece across two sentences, so the puzzle is "
                    f"over or frozen -- there is nothing left to play.")
        else:
            dead_boards = 0

        print("[NEXT] Clicking next button...")
        try:
            time.sleep(1.5)
            next_btn = altdriver.find_object(By.NAME, "nextButton")
            next_btn.click()
        except Exception:
            print("[WARNING] Failed to click Next.")

        print("[WAIT] Waiting 5s for next sentence to load...")
        time.sleep(6.5)

    # Say what happened instead of reporting success for a board that was left
    # half-built. Raising hands it to the caller's 3-attempt retry (utilsdemo),
    # which re-reads the board — and a failure that is REPORTED can be chased,
    # where a hang could only be killed.
    if unsolved:
        raise AssertionError(
            f"PUZZLES: {len(unsolved)} of {total} sentence(s) could not be "
            f"assembled (sentence {unsolved}). The pieces the solver could read "
            f"never matched the target sentence.")

    print("\n[SUCCESS] All puzzles processed!")
