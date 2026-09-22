"""CROSSWORD and CROSSWORD2 (shared by Voca Tooki and Kideo Land).

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


# --- CROSSWORD2 board reading -------------------------------------------------
# Crossword words INTERSECT: a cell can already be filled by an earlier word.
# The game fills the first cell whose text component is inactive --
#
#   for (; currentPos < TextLengthExcludingDiacritics(word); currentPos++)
#       if (!wordCards[word][currentPos].GetComponentInChildren<RTLTextMeshPro>()
#               .isActiveAndEnabled) break;
#
# -- so it skips crossing cells itself, but it still counts EVERY keypress and
# stops accepting input at `collectedKeyboardString.Length >= word.Length`.
# Pressing one key per letter therefore overflows on any word that crosses a
# solved one, and the surplus press is written into the next cell as a wrong
# letter. Confirmed live on Hebrew 'kniya' (two yods, one already on the board
# from a crossing word): 5 presses for 4 empty cells and the word scored wrong.
_CW_GENERATOR = "CrossWords.CrossWordsGenerator"


_CW_CELL_COMPONENT = "RTLTMPro.RTLTextMeshPro"


_CW_CELL_ASSEMBLY = "RTLTMPro"


def _cw_selected_word(altdriver):
    """The generator's own selected word, as (word, [(row, col), ...]).

    Read `lastSelectedWord` rather than `RTLTMPWordPanel`: the panel reports RTL
    words MIRRORED ('kniya' arrives reversed), which is what the old reverse-order
    pass existed to undo. `lastSelectedWord.word` is always in logical order.
    """
    for canvas in altdriver.find_objects(By.NAME, "Canvas"):
        try:
            sel = canvas.get_component_property(
                _CW_GENERATOR, "lastSelectedWord", "Assembly-CSharp", max_depth=2
            )
        except Exception:
            continue
        if isinstance(sel, dict) and sel.get("word"):
            points = [
                (int(p["x"]), int(p["y"]))
                for p in (sel.get("wordPointsInMatrix") or [])
                if isinstance(p, dict) and "x" in p and "y" in p
            ]
            return sel["word"], points
    return None, None


def _cw_cell_is_filled(cell):
    """The game's own test for a filled cell.

    NOT the cell's text: a cleared board keeps its old letters in `m_text` with
    the component disabled, so reading text reports empty cells as full and the
    solver then presses nothing at all.
    """
    try:
        return bool(cell.get_component_property(
            _CW_CELL_COMPONENT, "isActiveAndEnabled", _CW_CELL_ASSEMBLY))
    except Exception:
        return False  # unreadable -> treat as empty -> press it, as before


def _cw_grid_shape(cells):
    """(rows, cols) if `find_objects` returned the grid in row-major order, else None.

    The generator indexes cells as (row, col); `find_objects` returns them in
    instantiation order, which is that same row-major order -- verified live on a
    169-cell board. Which screen corner holds (0, 0) depends on text direction
    (col 0 sits on the right for Hebrew, the left for English), so only the ORDER
    is relied on, never the geometry. This proves the order really is a grid, and
    recovers its shape, before an index into it is trusted. Rows and columns are
    counted separately so a non-square board still works.
    """
    xs = sorted({c.x for c in cells})
    ys = sorted({c.y for c in cells})
    rows, cols = len(ys), len(xs)
    if rows * cols != len(cells):
        return None
    for x_axis in (xs, list(reversed(xs))):
        for y_axis in (ys, list(reversed(ys))):
            xi = {v: i for i, v in enumerate(x_axis)}
            yi = {v: i for i, v in enumerate(y_axis)}
            if all((i // cols, i % cols) == (yi[c.y], xi[c.x])
                   for i, c in enumerate(cells)):
                return rows, cols
    return None


def _cw_letters_to_press(altdriver, word, points):
    """Letters whose cells are still empty, in press order.

    Returns None when the board cannot be read confidently; the caller then
    presses every letter, which is exactly the old behaviour, so a board this
    cannot parse is never made worse.
    """
    if not word or not points or len(points) != len(word):
        return None

    cells = altdriver.find_objects(By.NAME, "Letter")
    if not cells:
        return None
    shape = _cw_grid_shape(cells)
    if shape is None:
        print("[WARN] crossword: cell order is not a grid, pressing every letter")
        return None
    _rows, cols = shape

    to_press = []
    for ch, (row, col) in zip(word, points):
        index = row * cols + col
        if not (0 <= index < len(cells)):
            return None
        if not _cw_cell_is_filled(cells[index]):
            to_press.append(ch)
    return to_press


def crosswords2(altdriver):
    """Solve all crossword items based on ProgressText."""
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progresstext.split('/')[1])
    print(f"[INFO] Total words to solve: {number_of_words}")

    # Build the letters map once - the keyboard holds one tile per letter.
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }
    print(f"[DEBUG] Available letters : {list(letters_map.keys())}")

    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Stop once the board is done. The loop is sized from ProgressText, but
        # the activity can finish on an earlier pass; without this the last pass
        # finds no selected word, falls back to the panel's MIRRORED text and
        # presses junk into a completed board.
        try:
            solved = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[0])
        except Exception:
            solved = None
        if solved is not None and solved >= number_of_words:
            print(f"[INFO] crossword: all {number_of_words} words solved, stopping")
            break

        word, points = _cw_selected_word(altdriver)
        if word:
            word = word.lower()
            to_press = _cw_letters_to_press(altdriver, word, points)
        else:
            # No generator state: fall back to the panel exactly as before.
            word = altdriver.find_object(By.NAME, "RTLTMPWordPanel").get_component_property(
                'TMProWordPanel', 'Word.word', 'Assembly-CSharp'
            ).lower()
            to_press = None
        print(f"[DEBUG] Target word: {word}")

        if to_press is None:
            to_press = list(word)
        elif len(to_press) != len(word):
            print(f"[INFO] crossword: {len(word) - len(to_press)} cell(s) already filled "
                  f"by crossing words, pressing {len(to_press)}/{len(word)} letters")

        for letter in to_press:
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")


        # Wait for next round to load
def crosswords2_kl(altdriver):
    """Solve all crossword items based on ProgressText (click letters in reverse order)."""
    progresstext = altdriver.find_object(By.NAME, "ProgressText").get_text()
    number_of_words = int(progresstext.split('/')[1])
    print(f"[INFO] Total words to solve: {number_of_words}")

    # ✅ Step 1: Build the letters map once
    letters_map = {
        letter.get_component_property("TMPro.TextMeshProUGUI", "m_text", "Unity.TextMeshPro").lower(): letter
        for letter in altdriver.find_objects(By.NAME, 'FillLetter')
    }
    print(f"[DEBUG] Available letters: {list(letters_map.keys())}")

    # ✅ Step 2: Iterate through each word
    for i in range(number_of_words):
        print(f"[INFO] Solving word {i + 1} of {number_of_words}")
        time.sleep(3)

        # Get current target word
        current_word_obj = altdriver.find_object(By.NAME, "RTLTMPWordPanel")
        current_word_text = current_word_obj.get_component_property(
            "TMProWordPanel", "Word.word", "Assembly-CSharp"
        ).lower()
        print(f"[DEBUG] Target word: {current_word_text}")

        # ✅ Step 3: Click letters in reverse order
        for letter in reversed(current_word_text):
            if letter in letters_map:
                letters_map[letter].click()
                print(f"[ACTION] Clicked letter: {letter}")
                time.sleep(0.2)
            else:
                print(f"[WARNING] Letter not found: {letter}")

        # Wait before next word loads
        time.sleep(1)

    print("[INFO] Crosswords2 activity complete ✅")


def crosswords(altdriver):

    # Get activity and matrix size
    activity = altdriver.find_object(By.NAME, 'CrosswordActivity')
    number_of_columns = activity.get_component_property(
        'com.kideo.learn.english.CrosswordActivityManager',
        'numberOfColumns',
        'Assembly-CSharp'
    )
    number_of_rows = activity.get_component_property(
        'com.kideo.learn.english.CrosswordActivityManager',
        'numberOfRows',
        'Assembly-CSharp'
    )

    print(f"Matrix size: {number_of_rows}x{number_of_columns}")

    # Initialize empty matrix and letter panel mapping
    matrix = [['empty' for _ in range(number_of_columns)] for _ in range(number_of_rows)]
    letter_panels = {}
    letter_objects = {}  # Store actual AltDriver objects for swiping

    # Get all letter panels
    texts = altdriver.find_objects(By.NAME, 'Text - RTLTMP')

    # Where a letter sits is decided by WHERE IT IS, not by arithmetic on its
    # name. AltTester disambiguates same-named objects with a "_N" suffix, so
    # the old rule (base + offset) made "LetterPanel (5)_1" and "LetterPanel
    # (6)" both mean 6: panels overwrote each other and the highest positions
    # were never filled — a 9x10 board came back with its whole last row empty
    # and lost a word. A square board hid it, because the collisions landed
    # inside the grid.
    cells = []
    for text in texts:
        try:
            parent = text.get_parent()
            letter = (text.get_text() or "").strip()
            if 'LetterPanel' not in parent.name or not letter:
                continue
            cells.append({'x': float(parent.x), 'y': float(parent.y),
                          'letter': letter, 'object': parent,
                          'panel_name': parent.name})
        except Exception:                            # noqa: BLE001
            continue

    def bands(values, expected, reverse=False):
        """Cluster coordinates into ``expected`` lines of the grid.

        The tolerance is half a cell, taken from the board's OWN spread, so it
        holds at any resolution. Both axes are banded by POSITION: assigning a
        column by counting letters across a row would compact a row that has a
        blank cell and shift every letter after it one place left.
        """
        ordered = sorted(set(values), reverse=reverse)
        if not ordered:
            return []
        spread = abs(ordered[-1] - ordered[0])
        tolerance = (spread / max(1, expected - 1) / 2.0) if spread else 1.0
        out = []
        for value in ordered:
            if not out or abs(out[-1] - value) > tolerance:
                out.append(value)
        return out

    if cells:
        # Unity screen space counts y UP, so the largest y is row 0.
        row_bands = bands([c['y'] for c in cells], number_of_rows, reverse=True)
        col_bands = bands([c['x'] for c in cells], number_of_columns)
        for cell in cells:
            cell['row'] = min(range(len(row_bands)),
                              key=lambda r: abs(row_bands[r] - cell['y']))
            cell['col'] = min(range(len(col_bands)),
                              key=lambda c: abs(col_bands[c] - cell['x']))

        if len(row_bands) != number_of_rows or len(col_bands) != number_of_columns:
            print(f"[WARN] crossword: the board shows "
                  f"{len(row_bands)}x{len(col_bands)} but the activity reports "
                  f"{number_of_rows}x{number_of_columns}")

        for cell in cells:
            row, col = cell['row'], cell.get('col')
            if col is None or row >= number_of_rows or col >= number_of_columns:
                continue
            matrix[row][col] = cell['letter']
            letter_panels[(row, col)] = {
                'letter': cell['letter'], 'panel_name': cell['panel_name'],
                'row': row, 'col': col, 'object': cell['object'],
            }
            letter_objects[(row, col)] = cell['object']

    filled = sum(1 for r in matrix for c in r if c != 'empty')
    print(f"[INFO] crossword: mapped {filled}/{number_of_rows * number_of_columns} cells "
          f"from {len(cells)} lettered panel(s)")

    # Print the matrix
    print("\nCrossword Matrix:")
    print("-" * (number_of_columns * 8))
    for row in matrix:
        print(" ".join(f"{cell:>6}" for cell in row))
    print("-" * (number_of_columns * 8))

    # Get words to find
    words_to_find_panel = altdriver.find_object(By.NAME, 'WordsToFindPanel')
    words_to_find_list = words_to_find_panel.get_component_property(
        'com.kideo.learn.english.CrossWordToFindManager',
        'cleanedWordsList_',
        'Assembly-CSharp'
    )

    print(f"\nWords to find: {words_to_find_list}")

    # Define all 8 directions
    directions = {
        'horizontal': (0, 1),
        'vertical': (1, 0),
        'diagonal-down-right': (1, 1),
        'diagonal-down-left': (1, -1),
        'horizontal-reverse': (0, -1),
        'vertical-reverse': (-1, 0),
        'diagonal-up-right': (-1, 1),
        'diagonal-up-left': (-1, -1)
    }

    found_words = []

    # Find and solve each word
    for word in words_to_find_list:
        word_lower = word.lower()
        word_len = len(word)
        word_found = False

        # Search in all positions
        for row in range(number_of_rows):
            if word_found:
                break
            for col in range(number_of_columns):
                if word_found:
                    break

                # Try all directions
                for dir_name, (dr, dc) in directions.items():
                    # Check if word fits in the matrix
                    end_row = row + dr * (word_len - 1)
                    end_col = col + dc * (word_len - 1)

                    if end_row < 0 or end_row >= number_of_rows or end_col < 0 or end_col >= number_of_columns:
                        continue

                    # Check each letter
                    match = True
                    for i, letter in enumerate(word_lower):
                        curr_row = row + dr * i
                        curr_col = col + dc * i
                        cell_value = matrix[curr_row][curr_col]

                        if cell_value == 'empty' or cell_value.lower() != letter:
                            match = False
                            break

                    # If word found, swipe it
                    if match:
                        print(f"Found '{word}' at ({row},{col}) going {dir_name}")

                        start_obj = letter_objects.get((row, col))
                        end_obj = letter_objects.get((end_row, end_col))

                        if start_obj and end_obj:
                            try:
                                altdriver.swipe(
                                    start=start_obj.get_screen_position(),
                                    end=end_obj.get_screen_position(),
                                    duration=0.5
                                )
                                print(f"✓ Swiped '{word}' successfully")

                                found_words.append({
                                    'word': word,
                                    'start': (row, col),
                                    'end': (end_row, end_col),
                                    'direction': dir_name
                                })

                                # Sleep 2 seconds after finding a word
                                time.sleep(2)

                            except Exception as e:
                                print(f"✗ Error swiping '{word}': {e}")

                        word_found = True
                        break

    print(f"\n✓ Solved {len(found_words)} out of {len(words_to_find_list)} words")

    return {
        'matrix': matrix,
        'letter_panels': letter_panels,
        'matrix_size': (number_of_rows, number_of_columns),
        'words_to_find': words_to_find_list,
        'found_words': found_words
    }
