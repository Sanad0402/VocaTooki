"""3rd grade - LETTERS_SORTING (signs): sort the letters onto their signs.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.activity_runner import list_level_activities, read_activity_progress, when_finish_activity
from vocatooki.ui_actions import call_method


def _signs_entry(altdriver, max_rounds=12, round_timeout=25):
    """Letters Sorting ("signs"): solve whichever round is currently open.

    By default this is a SOLVER ONLY — it does not navigate. It works out which
    round it has been dropped into and plays it; getting into the activity (and
    back out again) is the caller's job, so it composes with
    solve_activity_in_level, the lesson range runs and anything else that drives
    the map.

    Pass ``play_all_modes=True`` to play the whole activity in one call: after
    an entry is finished it goes back ONE screen to the activity selection,
    re-enters this same activity and plays the next mode, up to three entries.
    That is opt-in precisely because the callers above do their own navigation.

    The activity has three modes, and they do NOT follow each other in place:
    the activity has to be left and re-entered to get the next one. So this
    plays the board(s) of the current entry and returns.

        listen & find                signs show letters, either case counts
        find capital / find small    one entry, split into TWO boards — the
                                     second appears in place, so it is played
                                     without re-entering
        find images                  signs show pictures; the correct ones are
                                     the letter's own words, matched BY ID
                                     ("kite" belongs to "I" by sound, which no
                                     spelling rule would catch)

    Nothing is read once: every board re-reads its target and its nine signs,
    and the loop follows the activity's progress counter ("0/5") rather than any
    fixed count. A sign takes TWO clicks — the first turns it round, the second
    selects it — and each sign is addressed by its own path
    (//GO-Monkey_i//Bn-Local_Root) so one can never be mistaken for another.
    """
    def target():
        """(letter, word_ids) for the current board.

        The letter drives the letter rounds. ``word_ids`` drives the images
        round, where the signs show PICTURES: the letter's data lists the ids of
        the words that belong to it, so the right signs are matched by id rather
        than by spelling — "kite" belongs to "I" by sound, and no string rule
        would ever catch that.
        """
        try:
            wp = altdriver.find_object(By.NAME, "WordPanel")
            word = wp.get_component_property("WordPanel", "Word", "Assembly-CSharp") or {}
            level = word.get("levelData") or {}
            letter = (level.get("letter") or "").strip().lower()
            ids = [int(i) for i in (level.get("words") or [])]
            return letter, ids
        except Exception as e:
            print(f"[ERROR] could not read the target: {e}")
            return "", []

    def signs_on_board():
        """[(name, shown, word_id)] for the nine signs, read fresh.

        ``shown`` is the letter in the letter rounds and the word in the images
        round; ``word_id`` identifies the word behind the picture.
        """
        out = []
        for i in range(9):
            name = "GO-Monkey" if i == 0 else f"GO-Monkey_{i}"
            try:
                monkey = altdriver.find_object(By.NAME, name)
                alphabet = monkey.get_component_property(
                    "SortingMonkeyController", "alphabet", "Assembly-CSharp") or {}
            except Exception:
                continue
            # A LETTER sign carries `letter`; a PICTURE sign carries a word and
            # no letter. `word` is not reliable for letter signs — it comes back
            # empty in some rounds — so the letter field decides which it is.
            letter = str(alphabet.get("letter") or "").strip()
            shown = letter or str(alphabet.get("word") or "").strip()
            try:
                obj_id = int(alphabet.get("id"))
            except (TypeError, ValueError):
                obj_id = None
            out.append((name, shown, obj_id, bool(letter)))
        return out

    def diagnose(board, word_ids):
        """Name the round we are in, from what is actually on the board.

        The four round objects (ListenFindRound / FindLowerCase /
        FindUpperCase / FindImages) all report enabled=True at once, so they
        cannot be asked. What distinguishes them is the board:

        * signs showing WORDS whose ids belong to the letter -> find images
        * signs showing LETTERS with an AudioButton on screen  -> listen & find
        * signs showing LETTERS with no audio                  -> the find
          capital / find small round (which half it is cannot be told apart
          from the data — and does not matter, because each half only shows the
          case it asks for, so matching on the letter is right either way)
        """
        if any(not is_letter for _n, _w, _i, is_letter in board):
            return "find images (matching by word id)"
        try:
            has_audio = bool(altdriver.find_objects(By.NAME, "AudioButton"))
        except Exception:
            has_audio = False
        if has_audio:
            return "listen & find (either case counts)"
        return "find capital / find small letters"

    def click_sign(name):
        """Turn the sign, then select it."""
        path = f"//{name}//Bn-Local_Root"
        try:
            altdriver.find_object(By.PATH, path).click()   # turns it round
        except Exception as e:
            print(f"[WARN] {name}: first click failed: {e}")
            return False
        time.sleep(1.2)
        try:
            altdriver.find_object(By.PATH, path).click()   # selects it
        except Exception as e:
            print(f"[WARN] {name}: second click failed: {e}")
            return False
        time.sleep(0.8)
        return True

    def activity_open():
        """Is the Letters Sorting board still on screen?

        This used to compare the scene name against "LettersSorting", which is
        the VOCA TOOKI scene. Kideo Land runs the very same activity inside
        `KideoLandOldActivityScene`, so the check failed on the first pass and
        the solver returned "0 boards played" without ever reading a board --
        every object it needs was present and correct.

        Asking whether the board itself is there works for both apps and for any
        future scene name. `WordPanel` is the target panel this solver already
        depends on in `target()`, so if it is gone the activity is gone.
        """
        try:
            return bool(altdriver.find_objects(By.NAME, "WordPanel"))
        except Exception:
            return True      # unreadable -> assume open; the timeout still bounds the wait

    def wait_for_round(timeout=30):
        """Wait for a round to be ready.

        Returns (letter, done, total), or None when this entry has no more
        rounds. Two different things end a round:

        * The find-upper/lower mode is split in half — when the first half is
          done a SECOND board appears in the same entry, so a completed
          progress bar is not necessarily the end.
        * The modes themselves (listen & find -> upper/lower -> images) do NOT
          follow each other in place: the activity has to be left and re-entered
          from the activity selection screen to get the next one. So once a
          board is finished and no new one appears, this returns and the caller
          re-enters for the next mode.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not activity_open():
                return None                         # activity closed
            letter, word_ids = target()
            done, total = read_activity_progress(altdriver)
            if letter and total and done < total:
                # The counter and the target appear BEFORE the signs finish
                # populating — a board read too early looks like nine blank
                # signs and nothing to click.
                if any(shown for _n, shown, _o, _l in signs_on_board()):
                    return letter, word_ids, done, total
            time.sleep(1.5)
        return None

    print("[INFO] Signs activity: starting")
    rounds_played = 0

    for rnd in range(1, max_rounds + 1):
        # Generous wait for the FIRST board (the activity is still loading),
        # short afterwards: a second board only appears for the split
        # upper/lower mode, otherwise this entry is done.
        ready = wait_for_round(timeout=30 if rnd == 1 else 10)
        if ready is None:
            break
        letter, word_ids, done, total = ready

        board = signs_on_board()
        print(f"[INFO] round {rnd}: {diagnose(board, word_ids)}")
        # A LETTER sign is correct when it shows the target letter; a PICTURE
        # sign when its word is one of the letter's words. The two are kept
        # apart deliberately: word ids and letter ids overlap (the word "red"
        # and the letter "I" are both id 10), so matching on id alone would
        # click the wrong sign in the images round.
        matches = [n for n, shown, oid, is_letter in board
                   if (shown.lower() == letter if is_letter
                       else (oid is not None and oid in word_ids))]
        print(f"[INFO] round {rnd}: target '{letter}' ({done}/{total}) — "
              f"signs {[shown for _n, shown, _o, _l in board]} -> clicking {len(matches)}")
        if not matches:
            print("[WARN] no sign carries the target letter; stopping")
            break

        for name in matches:
            click_sign(name)

        # Wait for this round to be counted complete.
        deadline = time.time() + round_timeout
        while time.time() < deadline:
            done, total = read_activity_progress(altdriver)
            if total and done >= total:
                break
            time.sleep(1.5)
        rounds_played += 1
        print(f"[INFO] round {rnd} finished at {done}/{total}")

    print(f"[INFO] Signs entry complete — {rounds_played} board(s) played")
    return rounds_played


def signs(altdriver, max_rounds=12, round_timeout=25, play_all_modes=False, max_entries=3):
    """Letters Sorting ("signs"). See _signs_entry for how a board is solved.

    ``play_all_modes=False`` (default): solve the round that is open and return.
    Unchanged behaviour for solve_activity_in_level and the lesson-range runs,
    which navigate themselves.

    ``play_all_modes=True``: also handle the navigation between modes — the
    modes do not follow each other in place, so after each entry this goes back
    ONE screen to the activity selection and re-enters the same activity. The
    activity is found by trying thumbs until the LettersSorting scene loads
    again, which works whatever language the thumb titles are in (this account
    shows them in Arabic).
    """
    played = _signs_entry(altdriver, max_rounds=max_rounds, round_timeout=round_timeout)
    if not play_all_modes:
        return played

    total_boards = played
    for entry in range(2, max_entries + 1):
        if not _reenter_signs(altdriver):
            print("[INFO] no further Signs mode to play")
            break
        print(f"[INFO] Signs entry {entry}")
        played = _signs_entry(altdriver, max_rounds=max_rounds, round_timeout=round_timeout)
        total_boards += played
        if played == 0:
            break
    print(f"[INFO] Signs activity complete — {total_boards} board(s) across all modes")
    return total_boards


def _reenter_signs(altdriver, timeout=40):
    """Leave a finished Signs entry and open the activity again.

    ONE back click reaches the activity selection (two would drop to the map).
    The right thumb is found by opening thumbs until LettersSorting loads, so
    no thumb title has to be recognised — titles are localised.
    """
    # Only leave if we are actually inside an activity — calling the exit from
    # the selection screen just logs failed clicks.
    try:
        inside = altdriver.get_current_scene() != "ActivitySelectionScene"
    except Exception:
        inside = True
    if inside:
        try:
            when_finish_activity(altdriver)
        except Exception as e:
            print(f"[WARN] could not leave the activity: {e}")
        time.sleep(4)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if altdriver.get_current_scene() == "ActivitySelectionScene":
            break
        time.sleep(1.5)
    else:
        print(f"[WARN] activity selection not reached "
              f"(now: {altdriver.get_current_scene()})")
        return False

    for index in range(6):
        # Re-read the thumbs every time: backing out of the wrong activity
        # reloads the screen, and the handles from before are stale.
        activities = list_level_activities(altdriver)
        if index >= len(activities):
            break
        activity = activities[index]
        try:
            activity["thumb"].click()
        except Exception as e:
            print(f"[WARN] thumb {index} click failed: {e}")
            continue
        time.sleep(7)
        scene = altdriver.get_current_scene()
        if scene == "LettersSorting":
            print(f"[INFO] re-entered Signs via thumb {index} "
                  f"({activity.get('title') or 'untitled'})")
            return True
        # wrong activity — back out and try the next thumb
        print(f"[INFO] thumb {index} opened '{scene}', not Signs; going back")
        try:
            call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:
            when_finish_activity(altdriver)
        time.sleep(5)
    return False
