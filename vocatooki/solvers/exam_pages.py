"""Exam page solvers - one per exam page type; exam_solver picks which to run.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import alttester
import time
import unicodedata

from alttester import By


def _read_matchables(objects, component=None, lift=0):
    """``[(text, object, position)]`` for one side of a matching exam.

    ``component`` reads the word off a component property; without it the
    printed label is used. ``lift`` raises the target point, which is how these
    exams have always aimed at a shape's drop area.
    """
    out = []
    for obj in objects or []:
        try:
            text = (obj.get_component_property(component, 'word', 'Assembly-CSharp')
                    if component else obj.get_text())
            x, y = obj.get_screen_position()
            out.append(((text or "").strip(), obj, (x, y - lift)))
        except Exception:                            # noqa: BLE001 - skip unreadable
            continue
    return out


def solve_match_exam(altdriver, read_board, label, attempts=3, match=None,
                     tolerance=(60, 80), duration=2.3):
    """Drag each word onto the shape that wants it, and PROVE each one landed.

    Shared by every match-and-swipe exam page. ``read_board()`` returns
    ``(words, shapes)`` READ FRESH FROM THE APP each time — a screen position
    captured before a swipe describes where the word WAS, so a second pass that
    reuses it would drag from empty space.

    Why the verification matters: the app refuses to advance or submit a page
    that is not fully answered. A solver that swipes once and prints "completed"
    therefore does not fail — it strands the whole exam later, on a page nobody
    can leave. One unplaced word ("black", seen live) is enough.

    Returns the list of words it could not place (empty means all placed).
    """
    same = match or (lambda w, s: (w or "").strip().lower() == (s or "").strip().lower())
    tol_x, tol_y = tolerance

    def placed(word_pos, shape_pos):
        return (abs(word_pos[0] - shape_pos[0]) < tol_x
                and abs(word_pos[1] - shape_pos[1]) < tol_y)

    def outstanding(words, shapes):
        """Words that are not sitting on the shape that wants them."""
        left, used = [], set()
        for text, obj, pos in words:
            index = next((i for i, (s_text, _o, _p) in enumerate(shapes)
                          if i not in used and same(text, s_text)), None)
            if index is None:
                continue                             # no shape wants this word
            used.add(index)
            if not placed(pos, shapes[index][2]):
                left.append((text, obj, pos, shapes[index][2]))
        return left

    left = []
    for attempt in range(1, max(1, attempts) + 1):
        words, shapes = read_board()
        if not words:
            raise Exception(f"Not a {label} exam")
        pending = outstanding(words, shapes)
        if not pending:
            break
        for text, obj, word_pos, target in pending:
            altdriver.swipe(word_pos, target, duration)
            time.sleep(0.4)
            try:
                obj.click()
            except Exception:                        # noqa: BLE001
                pass
        time.sleep(0.8)
        words, shapes = read_board()                 # which of them actually landed?
        left = [t for t, _o, _p, _g in outstanding(words, shapes)]
        if not left:
            break
        print(f"[WARN] {label}: {left} not placed (attempt {attempt})")

    if left:
        print(f"[WARN] {label} finished with {left} unplaced")
    else:
        print(f"[INFO] {label} completed")
    return left


def exams_word_to_meaning(altdriver, attempts=3):
    """Match words to their meaning shapes by swiping, verifying each one."""
    time.sleep(1)

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordMeaningObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordMeaningObject(Clone)'))
        shapes = altdriver.find_objects(By.NAME, 'WordMeaningShape(Clone)')
        return (_read_matchables(words),
                _read_matchables(shapes, 'com.kideo.learn.english.WordMeaningShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_word_to_meaning", attempts=attempts)


def exams_word_to_image(altdriver, attempts=3):
    """Match words to images by swiping, verifying each one."""
    time.sleep(1)

    def read_board():
        words = altdriver.find_objects(By.NAME, 'MatchWordText(Clone)')
        shapes = altdriver.find_objects(By.NAME, 'MatchShapeImage(Clone)')
        return (_read_matchables(words),
                _read_matchables(shapes, 'com.kideo.learn.english.MatchTestShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_word_to_image", attempts=attempts)


def exams_3rd_letter_to_word_image_match(altdriver, attempts=3):
    """Match a letter shape to a word that contains it ('G' -> 'giraffe')."""
    time.sleep(1)

    def read_board():
        words = altdriver.find_objects(By.NAME, 'LetterWordText Variant(Clone)')
        shapes = altdriver.find_objects(By.NAME, 'LetterShapeImage Variant(Clone)')
        if not words or not shapes:
            raise Exception("Missing words or shapes for letter-to-word matching")
        return (_read_matchables(words, 'com.kideo.learn.english.MatchTestWord'),
                _read_matchables(shapes, 'com.kideo.learn.english.MatchTestShape', lift=100))

    # The pairing rule is CONTAINMENT here, not equality: the shape carries a
    # letter and the word is the one spelled with it.
    solve_match_exam(altdriver, read_board, "letter-to-word image matching",
                     attempts=attempts,
                     match=lambda w, s: bool(s) and (s or "").strip().lower()
                     in (w or "").strip().lower())


def exams_3rd_audio_to_letter_matrix(altdriver):
    "Generically matches words to images based on shared letters (e.g. 'G' -> 'giraffe')."

    time.sleep(1)
    audio_obj = altdriver.find_object(By.NAME, 'LetterTestPanel(Clone)')
    audio_text = audio_obj.get_component_property(
        'com.kideo.learn.english.LetterTest', 'alphabet.letter', 'Assembly-CSharp'
    ).lower()

    letters_objs = altdriver.find_objects(By.NAME, 'WordPanel')

    for letter in letters_objs[1:10]:  # start from index 1
        letter_text = letter.get_component_property(
            'WordPanel', 'textControl.text', 'Assembly-CSharp'
        ).lower()

        if letter_text == audio_text:
            letter.click()
              # optional: stop after first match

    print("[INFO] Letter-to-word image matching completed.")


def exams_audio_to_meaning(altdriver, attempts=3):
    """Match audio meanings to word labels by swiping, verifying each one."""
    time.sleep(1)

    def audio_shapes():
        return (altdriver.find_objects(By.NAME, 'WordAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'WordAudioShape_RTL(Clone)'))

    shapes = audio_shapes()
    if not shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")
    # Each shape has to be played once before it can be matched.
    for shape in shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'WordAudioObject_RTL(Clone)'))
        if not words:
            raise Exception("[ERROR] No word objects found.")
        return (_read_matchables(words, 'com.kideo.learn.english.WordAudioObject'),
                _read_matchables(audio_shapes(),
                                 'com.kideo.learn.english.WordAudioShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_audio_to_meaning", attempts=attempts)


def _spelling_bare_letter(text):
    """The base letter, with any combining marks removed.

    `missingLetters` carries the word's diacritics (Hebrew 'mem + hiriq' is two
    code points), but the on-screen keyboard offers only bare letters, so looking
    a pointed letter up straight misses every time. Worse than missing: the game
    fills the first empty slot whatever key is pressed, so the few letters that DO
    match land in the leading slots and the word reads back reversed.

    Pressing the bare letter is what the game expects -- IsWordCompleted() accepts
    a slot matching either wordLetters[i] or RemoveDiacritics(word)[i]. Used only
    as a FALLBACK after an exact match fails, so a keyboard that really does offer
    accented tiles keeps working, and English (no combining marks) is untouched.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


def exam_spelling(altdriver):
    """Completes the spelling activity by clicking missing letters."""
    # ✅ Corrected missing_words fallback logic
    missing_words = altdriver.find_objects(By.NAME, "FillWord(Clone)")
    if not missing_words:
        missing_words = altdriver.find_objects(By.NAME, 'KL_FillWord(Clone)')
    if not missing_words:  # second fallback
        missing_words = altdriver.find_objects(By.NAME, "VTFillWord_RTL(Clone)")

    missing_letters_list = []

    for obj in missing_words:
        raw_letters = obj.get_component_property(
            "com.kideo.learn.english.FillMissingWord",
            "missingLetters",
            "Assembly-CSharp"
        )
        try:
            # ✅ Safer parsing (no risky eval)
            if isinstance(raw_letters, str):
                import ast
                letters = ast.literal_eval(raw_letters)
            elif isinstance(raw_letters, list):
                letters = raw_letters
            else:
                raise ValueError()
            missing_letters_list.append([l.lower() for l in letters])
        except Exception:
            raise ValueError(f"Invalid format: {raw_letters}")

    toggles = altdriver.find_objects(By.NAME, "FillWordToggle")
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }

    for i, letters in enumerate(missing_letters_list):
        if i < len(toggles):
            toggles[i].click()
            time.sleep(0.4)  # ✅ small delay for UI update
            for letter in letters:
                tile = letters_map.get(letter)
                if tile is None:
                    bare = _spelling_bare_letter(letter).lower()
                    tile = letters_map.get(bare)
                if tile is not None:
                    tile.click()
                    time.sleep(0.2)
                else:
                    print(f"[WARN] Letter '{letter}' not found in map.")

    print("[INFO] exam_spelling completed")


def exam_multiple_choice(altdriver):
    """Clicks toggle by index across all questions using pre-collected toggle lists."""

    # --- Find all question templates ---
    questions = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')
    if not questions:
        questions = altdriver.find_objects(By.NAME, 'QuestionTemplate_RTL(Clone)')
    if not questions:
        questions = altdriver.find_objects(By.NAME, 'KL_QuestionTemplate(Clone)')
    if not questions:
        raise Exception("[ERROR] No question templates found in the scene.")

    correct_indexes = []

    # Step 1: Get correct index for each question
    for q in questions:
        index = q.get_component_property("ContextWithMissingWordQuestion", "answerIndex", "Assembly-CSharp")
        correct_indexes.append(index)

    # Step 2: Get all toggles globally (lists)
    toggles0 = altdriver.find_objects(By.NAME, 'Toggle0')
    toggles1 = altdriver.find_objects(By.NAME, 'Toggle1')
    toggles2 = altdriver.find_objects(By.NAME, 'Toggle2')
    toggles3 = altdriver.find_objects(By.NAME, 'Toggle3')

    toggle_lists = [toggles0, toggles1, toggles2, toggles3]

    # Step 3: Click correct toggle per question
    for i, correct_index in enumerate(correct_indexes):
        try:
            target_toggle = toggle_lists[correct_index][i]
            target_toggle.click()
            print(f"[INFO] Question {i+1}: Clicked Toggle{correct_index}[{i}]")
        except Exception as e:
            print(f"[ERROR] Question {i+1}: Failed to click Toggle{correct_index}[{i}] - {e}")


# Example of how to run the script:
# from altdriver import AltDriver
# alt_driver = AltDriver()
# solve_puzzles(alt_driver)
def exams_image_to_audio(altdriver, attempts=3):
    """Match audio shapes to their word labels by swiping, verifying each one."""
    time.sleep(1)

    def audio_shapes():
        return (altdriver.find_objects(By.NAME, 'ImageAudioShape(Clone)')
                or altdriver.find_objects(By.NAME, 'KL_WordAudioShape(Clone)'))

    shapes = audio_shapes()
    if not shapes:
        raise Exception("[ERROR] No audio shapes found. Not an audio-to-meaning exam.")
    # Each shape has to be played once before it can be matched.
    for shape in shapes:
        try:
            shape.click()
            time.sleep(0.8)
        except Exception as e:
            print(f"[WARN] Failed to click shape: {e}")

    def read_board():
        words = (altdriver.find_objects(By.NAME, 'WordAudioObject(Clone)')
                 or altdriver.find_objects(By.NAME, 'KL_WordAudioObject(Clone)'))
        if not words:
            raise Exception("[ERROR] No word objects found.")
        return (_read_matchables(words, 'com.kideo.learn.english.WordAudioObject'),
                _read_matchables(audio_shapes(),
                                 'com.kideo.learn.english.WordAudioShape', lift=100))

    solve_match_exam(altdriver, read_board, "exams_image_to_audio", attempts=attempts)


def exams_image_for_voices(altdriver):
    """Automates toggle click per question based on answerIndex and question index."""
    time.sleep(1)
    questions = altdriver.find_objects(By.NAME, 'QuestionTemplate(Clone)')

    for i, question in enumerate(questions):
        try:
            answer_index = int(question.get_component_property(
                'ImageWithAudioChoicesQuestion', 'answerIndex', 'Assembly-CSharp'))

            toggle_name = f'Toggle{answer_index}'
            toggles = altdriver.find_objects(By.NAME, toggle_name)

            if i < len(toggles):
                toggles[i].click()
                print(f"[INFO] Question {i}: Clicked {toggle_name}[{i}]")
            else:
                print(f"[WARN] {toggle_name}[{i}] not found. Skipping.")

            time.sleep(0.5)

        except Exception as e:
            print(f"[ERROR] Question {i}: {e}")


def _exam_prefab_name(altdriver, *candidates):
    """The name a shared exam prefab actually has in the game that is running.

    Voca Tooki and Kideo Land ship the SAME exam pages -- same scripts, same
    fields, same `com.kideo.learn.english.*` components -- but Kideo Land
    prefixes the prefab names: `SwapWord(Clone)` there is `KL_SwapWord(Clone)`.
    A solver that hardcodes one name finds nothing in the other game, and
    "found nothing" quietly reads as "nothing left to do".

    Returns the first candidate that is on screen, or None.
    """
    for name in candidates:
        try:
            if altdriver.find_objects(By.NAME, name):
                return name
        except Exception:
            continue
    return None


def exam_swap_letters(altdriver, max_swaps_per_word=40, row_attempts=3):
    """Solve the "swap letters" exam page.

    Each row shows one word scrambled; dragging letter A onto letter B swaps
    them (verified live — a non-adjacent drag swaps, it does not insert). The
    answer for every row is on the row itself, so nothing is guessed:

        SwapWord(Clone)       -> com.kideo.learn.english.SwapTestWord.word
        SwapLetterText(Clone) -> com.kideo.learn.english.SwapTestLetter (draggable)

    Three things this has to get right, each learned the hard way on the app:

    * **Rows are addressed by INDEXED PATH**, never by matching letters to a row
      by y. The list scrolls, and a y-match across two queries silently pairs one
      row's letters with another row's word (dictionary once "solved" as repeat).
    * **The list is scrolled with the ScrollRect**, not the mouse wheel, so the
      row being worked on is really in view — a drag at off-screen coordinates
      does nothing.
    * **The gesture is a MOUSE press-move-release.** On WindowsEditor the
      EventSystem is mouse-driven and simulated touch is ignored.

    Each row is verified against the game and retried before moving to the next,
    so a drag that does not register is caught immediately rather than leaving
    the page unsolvable (the page refuses to advance while any row is wrong).
    """
    row_name = _exam_prefab_name(altdriver, "SwapWord(Clone)", "KL_SwapWord(Clone)")
    if row_name is None:
        raise AssertionError(
            "swap-letters exam: no word rows on the page — looked for "
            "SwapWord(Clone) and KL_SwapWord(Clone). Nothing was solved.")

    def rows_count():
        return len(altdriver.find_objects(By.NAME, row_name))

    def row_word(i):
        try:
            row = altdriver.find_object(By.PATH, f"//{row_name}[{i}]")
            return row.get_component_property(
                "com.kideo.learn.english.SwapTestWord", "word", "Assembly-CSharp")
        except Exception:
            return None

    def row_letters(i):
        """The letter objects of row i only — by hierarchy, so never mismatched."""
        try:
            return altdriver.find_objects(By.PATH, f"//{row_name}[{i}]/LettersContainer/*")
        except Exception:
            return []

    def texts(objs):
        out = []
        for o in objs:
            try:
                # a blank slot is the space in a phrase ("find out")
                out.append(((o.get_text() or " ").strip() or " ").lower())
            except Exception:
                out.append(" ")
        return out

    def scroll_to_row(i, total):
        """Put row i in view. 1.0 is the top of the list, 0.0 the bottom."""
        if total < 2:
            return
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            value = max(0.0, min(1.0, 1.0 - (i / float(total - 1))))
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI", value)
            time.sleep(0.45)
        except Exception as e:
            print(f"[WARN] could not scroll to row {i}: {e}")

    def swap(a, b):
        altdriver.move_mouse([a.x, a.y], duration=0.1, wait=True)
        altdriver.key_down(alttester.AltKeyCode.Mouse0)
        time.sleep(0.15)
        altdriver.move_mouse([b.x, b.y], duration=0.25, wait=True)
        time.sleep(0.15)
        altdriver.key_up(alttester.AltKeyCode.Mouse0)
        time.sleep(0.4)

    total = rows_count()
    words = [row_word(i) for i in range(total)]
    print(f"[INFO] swap-letters exam: {total} word(s) -> {words}")

    unsolved = []
    for i, word in enumerate(words):
        if not word:
            continue
        want = list(word.lower())
        solved = False

        for attempt in range(1, row_attempts + 1):
            scroll_to_row(i, total)
            have = texts(row_letters(i))
            if have == want:
                solved = True
                break
            if len(have) != len(want):
                print(f"[WARN] '{word}': {len(have)} letters on screen, expected {len(want)}")
                break

            swaps = 0
            for k in range(len(want)):
                if have[k] == want[k]:
                    continue
                j = next((m for m in range(k + 1, len(have)) if have[m] == want[k]), None)
                if j is None:
                    break
                objs = row_letters(i)              # fresh coordinates for this drag
                if len(objs) != len(have):
                    break
                swap(objs[k], objs[j])
                have[k], have[j] = have[j], have[k]
                swaps += 1
                if swaps >= max_swaps_per_word:
                    break

            # verify against the GAME before moving on, not against my own model
            actual = texts(row_letters(i))
            if actual == want:
                print(f"[INFO] '{word}' solved ({swaps} swap(s), attempt {attempt})")
                solved = True
                break
            print(f"[WARN] '{word}' is '{''.join(actual)}' after attempt {attempt} — retrying")

        if not solved:
            unsolved.append(word)

    if unsolved:
        raise AssertionError(
            f"swap-letters exam: {len(unsolved)} of {total} row(s) still wrong: {unsolved}")
    print(f"EXAM_SWAP_LETTERS RESULT: {total} word(s) put in order — {words}. "
          f"Each row was read back from the game after its swaps; the page's own "
          f"score screen is not asserted.")


def exam_shuffled_context(altdriver, question_attempts=3):
    """Solve the shuffled-context (sentence building) exam page.

    Each question is a sentence with blanks and a bank of words underneath.
    Nothing has to be guessed, because both sides name themselves:

        WordSpace(Clone)             -> SpaceToFillWithWord.word    (what this blank wants)
        WordInShuffledContext(Clone) -> WordInShuffledContext.word  (what this tile is)

    so every bank tile is dragged onto the blank carrying the same word. A tile
    already sitting on its blank is left alone.

    Same three rules as the swap-letters page, for the same reasons: questions
    are addressed by INDEXED PATH (never matched by y), the list is scrolled
    with the ScrollRect so the question is really in view, and the gesture is a
    MOUSE press-move-release. Each question is verified and retried before
    moving to the next.
    """
    Q = "//QuestionInShuffledContextTest(Clone)"

    def questions():
        return len(altdriver.find_objects(By.NAME, "QuestionInShuffledContextTest(Clone)"))

    def slots(i):
        try:
            return altdriver.find_objects(By.PATH, f"{Q}[{i}]/SpacesPanel/*")
        except Exception:
            return []

    def tiles(i):
        try:
            return altdriver.find_objects(By.PATH, f"{Q}[{i}]/WordsPanel/*")
        except Exception:
            return []

    def word_of(obj, component):
        try:
            return (obj.get_component_property(component, "word", "Assembly-CSharp") or "").strip()
        except Exception:
            return ""

    def on_slot(tile, slot):
        """A tile is in a blank when it is sitting on top of it."""
        return abs(tile.x - slot.x) < 25 and abs(tile.y - slot.y) < 30

    def scroll_to(i, total):
        if total < 2:
            return
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI",
                                        max(0.0, min(1.0, 1.0 - (i / float(total - 1)))))
            time.sleep(0.45)
        except Exception as e:
            print(f"[WARN] could not scroll to question {i}: {e}")

    def drag(a, b):
        altdriver.move_mouse([a.x, a.y], duration=0.1, wait=True)
        altdriver.key_down(alttester.AltKeyCode.Mouse0)
        time.sleep(0.15)
        altdriver.move_mouse([b.x, b.y], duration=0.3, wait=True)
        time.sleep(0.15)
        altdriver.key_up(alttester.AltKeyCode.Mouse0)
        time.sleep(0.4)

    def missing(i):
        """[(slot, wanted_word)] for blanks that have no tile on them."""
        sl, tl = slots(i), tiles(i)
        out = []
        for s in sl:
            if not any(on_slot(t, s) for t in tl):
                out.append((s, word_of(s, "SpaceToFillWithWord")))
        return out

    # --- reaching a tile that is not on screen -----------------------------
    # A long sentence pushes the bottom of the word bank past the viewport. The
    # tile still EXISTS in the hierarchy, so the drag was issued happily — at
    # coordinates outside the visible area, where it does nothing. The blank
    # then stayed empty, every retry repeated it, and the page stalled. So the
    # rule is the same one the language picker needed: prove it is reachable
    # before acting on it.
    try:
        screen_w, screen_h = (float(v) for v in altdriver.get_application_screensize())
    except Exception as e:                       # noqa: BLE001
        print(f"[WARN] could not read the screen size: {e}")
        screen_w = screen_h = 0.0

    def visible(obj, margin=0.05):
        """Is this object inside the viewport, so a gesture can reach it?"""
        if not screen_h:
            return True                          # unknown screen: don't block
        mx, my = screen_w * margin, screen_h * margin
        return (mx <= obj.x <= screen_w - mx) and (my <= obj.y <= screen_h - my)

    def scroll_position(delta=None):
        """Read (or nudge by ``delta``) the list's scroll. Returns it, or None."""
        try:
            view = altdriver.find_object(By.NAME, "Scroll View")
            pos = float(view.get_component_property(
                "UnityEngine.UI.ScrollRect", "verticalNormalizedPosition", "UnityEngine.UI"))
            if delta is None:
                return pos
            pos = max(0.0, min(1.0, pos + delta))
            view.set_component_property("UnityEngine.UI.ScrollRect",
                                        "verticalNormalizedPosition",
                                        "UnityEngine.UI", pos)
            time.sleep(0.3)
            return pos
        except Exception:
            return None

    def settled(i, slot_idx, tile_idx, tries=6, pause=0.25):
        """(slot, tile) once the board has STOPPED moving under them.

        Placing a word takes it out of the bank and the words still waiting
        REFLOW into the gap. A position read while that is happening describes
        where the tile WAS, so the drag starts from empty space and silently
        does nothing — which is exactly how one word of a long sentence stayed
        behind while every shorter sentence passed.
        """
        previous = None
        for _ in range(tries):
            sl, tl = slots(i), tiles(i)
            if slot_idx >= len(sl) or tile_idx >= len(tl):
                return None, None
            slot, tile = sl[slot_idx], tl[tile_idx]
            here = (tile.x, tile.y, slot.x, slot.y)
            if previous == here:
                return slot, tile
            previous = here
            time.sleep(pause)
        return slot, tile

    def place(i, slot_idx, tile_idx, wanted, attempts=3):
        """Drag one word into its blank and PROVE it landed. Returns bool.

        Verified per WORD, not per pass: an unverified drag left the whole
        question to be replayed, and the replay read the same moving board and
        failed the same way, three times over.
        """
        for attempt in range(1, attempts + 1):
            target, pick = settled(i, slot_idx, tile_idx)
            if target is None or pick is None:
                return False
            if on_slot(pick, target):
                return True                      # already there
            if not (visible(target) and visible(pick)):
                target, pick = in_view(i, slot_idx, tile_idx)
                if target is None or pick is None or not (visible(target) and visible(pick)):
                    print(f"[WARN] q{i + 1}: could not bring '{wanted}' into view")
                    return False
            drag(pick, target)
            sl, tl = slots(i), tiles(i)
            if (slot_idx < len(sl) and tile_idx < len(tl)
                    and on_slot(tl[tile_idx], sl[slot_idx])):
                return True
            print(f"[WARN] q{i + 1}: '{wanted}' did not land (attempt {attempt}/{attempts})")
        return False

    def in_view(i, slot_idx, tile_idx, steps=10):
        """(slot, tile) once BOTH are on screen, re-found after each nudge.

        Re-finding matters: an AltObject's x/y is a snapshot from when it was
        found, so positions read before a scroll describe where things WERE.
        """
        for _ in range(steps):
            sl, tl = slots(i), tiles(i)
            if slot_idx >= len(sl) or tile_idx >= len(tl):
                return None, None
            slot, tile = sl[slot_idx], tl[tile_idx]
            if visible(slot) and visible(tile):
                return slot, tile
            off = tile if not visible(tile) else slot
            # Unity screen space puts y=0 at the BOTTOM, so a small y means the
            # object sits below the viewport and the list must scroll down
            # (verticalNormalizedPosition: 1 = top, 0 = bottom).
            if scroll_position(-0.08 if off.y < screen_h / 2 else 0.08) is None:
                break
        sl, tl = slots(i), tiles(i)
        if slot_idx < len(sl) and tile_idx < len(tl):
            return sl[slot_idx], tl[tile_idx]
        return None, None

    total = questions()
    print(f"[INFO] shuffled-context exam: {total} question(s)")

    unsolved = []
    for i in range(total):
        sentence = " ".join(word_of(s, "SpaceToFillWithWord") for s in slots(i))
        done = False

        for attempt in range(1, question_attempts + 1):
            scroll_to(i, total)
            gaps = missing(i)
            if not gaps:
                done = True
                break

            # Read every word ONCE per attempt. The old loop re-queried the
            # slots and tiles for each gap and asked each tile for its word
            # again, so a question with a dozen blanks and a dozen tiles cost
            # hundreds of round trips — and paid them again on every retry.
            sl, tl = slots(i), tiles(i)
            slot_words = [word_of(s, "SpaceToFillWithWord") for s in sl]
            tile_words = [word_of(t, "WordInShuffledContext") for t in tl]
            # Tiles already sitting in a blank are not available to move.
            used = {ti for ti, t in enumerate(tl) if any(on_slot(t, s) for s in sl)}

            for si, slot in enumerate(sl):
                if any(on_slot(t, slot) for t in tl):
                    continue                     # this blank is already filled
                wanted = slot_words[si]
                ti = next((k for k, w in enumerate(tile_words)
                           if k not in used and w == wanted), None)
                if ti is None:
                    print(f"[WARN] q{i + 1}: no free tile for '{wanted}'")
                    continue
                used.add(ti)
                place(i, si, ti, wanted)

            gaps_after = missing(i)
            if not gaps_after:
                print(f"[INFO] q{i + 1} solved (attempt {attempt}): {sentence}")
                done = True
                break
            print(f"[WARN] q{i + 1} still missing "
                  f"{[w for _s, w in gaps_after]} after attempt {attempt}")

        if not done:
            unsolved.append(sentence)

    if unsolved:
        print(f"[WARN] questions still unsolved: {unsolved}")
    else:
        print("[INFO] all questions solved")
