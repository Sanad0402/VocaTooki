"""FROGGER: fill every blank by position, fix a wrong backpack, then check and cross.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By

from vocatooki.activity_runner import read_activity_progress
from vocatooki.solvers.text_utils import is_rtl, normalize_text
from vocatooki.ui_actions import click_by_name


def _frog_key(word):
    """A word as Frogger compares it: normalized, no edge punctuation, any case."""
    text = normalize_text(word or "")
    return text.strip(".,!?;:\"'()[]“”‘’«»¿¡،؛؟").casefold()


def _frogger_tiles(altdriver):
    """(word, clickable tile) for every word tile ON SCREEN right now."""
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
    except Exception:
        width = height = 0.0
    tiles = []
    for t in altdriver.find_objects(By.NAME, "Text"):
        if width and not (0 <= t.x <= width and 0 <= t.y <= height):
            continue                                  # a hidden copy clicks nothing
        try:
            tiles.append((_frog_key(t.get_text()), t.get_parent()))
        except Exception:
            continue
    return tiles


def _frogger_has_empty_blank(altdriver):
    """True while a blank in the sentence is still unfilled.

    Each blank is a `DummyText(Clone)` printing "_____", and it KEEPS printing
    that after it is filled — the word lands in a child, `DummyText(Clone)(Clone)`
    (measured live 2026-09-22). So a blank is empty when there are fewer filled
    children than "___" blanks; counting the underscores alone reads every blank
    as empty forever and the frog never crosses.
    """
    try:
        blanks = len(altdriver.find_objects_which_contain(By.TEXT, "___"))
    except Exception:
        return False
    try:
        filled = sum(1 for o in altdriver.find_objects(By.NAME, "DummyText(Clone)(Clone)")
                     if (o.get_text() or "").strip())
    except Exception:
        filled = 0
    return filled < blanks


def _frogger_blank_words(altdriver, sentence):
    """The words that belong in the BLANKS, in blank order — or None if unreadable.

    The sentence bar holds one `DummyText(Clone)` per word, and the blanks are
    the ones printing "_____". Taking the word at each blank's POSITION is what
    keeps a repeated word right: in "Sandra is wearing pink shoes, and a pink
    hat" the blanks are Sandra / shoes / the SECOND pink — clicking every word
    in sentence order put the first "pink" into the second blank and swapped
    shoes and pink (seen live 2026-09-22).
    """
    try:
        slots = altdriver.find_objects(By.NAME, "DummyText(Clone)")
    except Exception:
        return None
    tokens = [w for w in sentence.split(' ') if w.strip()]
    if not slots or len(slots) != len(tokens):
        return None
    rtl = is_rtl(sentence)
    # Reading order: top row first, then along the row (right-to-left for RTL).
    slots = sorted(slots, key=lambda o: (-round(o.y / 10), -o.x if rtl else o.x))
    words = []
    for slot, token in zip(slots, tokens):
        try:
            text = slot.get_text() or ""
        except Exception:
            text = ""
        if "___" in text:
            words.append(_frog_key(token))
    return words


def _frogger_bag(altdriver):
    """The words in the backpack, in slot order (PlaceHolder0, 1, ...)."""
    bag = []
    for i in range(12):
        try:
            slot = altdriver.find_object(By.NAME, f"PlaceHolder{i}")
            bag.append(_frog_key(slot.find_object_from_object(By.NAME, "Text(Clone)").get_text()))
        except Exception:
            break
    return bag


def _frogger_fix_bag(altdriver, expected):
    """Keep the backpack's correct START, take the rest out; return what is left to add.

    Pressing a slot (`PlaceHolderN`, the word with the red bin) removes that word
    and puts its tile back on the river (measured live 2026-09-22). Words are
    taken out from the END, so the slots before them keep their numbers.
    """
    bag = _frogger_bag(altdriver)
    keep = 0
    while keep < len(bag) and keep < len(expected) and bag[keep] == expected[keep]:
        keep += 1
    for i in reversed(range(keep, len(bag))):
        try:
            altdriver.find_object(By.NAME, f"PlaceHolder{i}").click()
            print(f"[INFO] Frogger: took '{bag[i]}' out of the backpack (slot {i + 1})")
            time.sleep(1.2)
        except Exception:
            break
    return list(expected[keep:])


def frogger(altdriver):
    """Solves Frogger activity with RTL-aware word clicking order."""
    num_words = int(altdriver.find_object(By.NAME, "ProgressText").get_text().split('/')[1])

    # Driven by the PROGRESS, not a fixed count: a sentence the game rejects is
    # played again instead of using up one of the rounds.
    rounds = 0
    while rounds < num_words * 2 + 2:
        done, total = read_activity_progress(altdriver)
        if total and done >= total:
            break
        if altdriver.find_objects(By.NAME, "FailureFeedbackPopup(Clone)"):
            print("[ERROR] Frogger: the game was lost")
            break
        rounds += 1
        time.sleep(3)

        sentence = altdriver.find_object(By.NAME, 'FroggerGameManager')\
            .get_component_property('com.kideo.learn.english.Frogger.FroggerGameManager', 'selectedSentence', 'Assembly-CSharp')
        print('Current sentence to solve:', sentence)

        # Only the words that go in the blanks, taken by the blank's position.
        # Compared WITHOUT punctuation: the sentence ends "summer." while the
        # tile says "summer".
        words = _frogger_blank_words(altdriver, sentence)
        exact = words is not None               # we know exactly what each blank takes
        if not exact:                           # sentence bar unreadable: old way
            words = [w for w in (_frog_key(w) for w in sentence.split(' ')) if w]
        if is_rtl(sentence):
            words = words[::-1]  # reverse only for Hebrew/Arabic

        # Fill EVERY blank before the frog moves: click the words, then look
        # for an empty blank ("___") still in the sentence; if one is left,
        # read the board again and retry.
        # With the blank words known, a wrong word already in the backpack (a
        # retry, or a repeated word placed in the wrong blank) is taken out
        # first, and the words go in strictly in blank order.
        remaining = list(words)
        for _pass in range(4):
            if exact:
                remaining = _frogger_fix_bag(altdriver, words)
            if not remaining and not _frogger_has_empty_blank(altdriver):
                break
            tiles = _frogger_tiles(altdriver)
            used = set()
            for word in list(remaining):
                hit = next((idx for idx, (text, _o) in enumerate(tiles)
                            if text == word and idx not in used), None)
                if hit is None:
                    if exact:
                        break                   # never fill a later blank first
                    continue
                tiles[hit][1].click()
                used.add(hit)
                remaining.remove(word)
                time.sleep(1.8)
            if (not _frogger_has_empty_blank(altdriver)
                    and (not exact or _frogger_bag(altdriver) == list(words))):
                break
            time.sleep(1.5)
        if (_frogger_has_empty_blank(altdriver)
                or (exact and _frogger_bag(altdriver) != list(words))):
            print(f"[ERROR] Frogger: blanks not filled right ({_frogger_bag(altdriver)} "
                  f"vs {list(words)}) — not checking this sentence")
            continue

        click_by_name(altdriver, "CheckSentenceButton")
        time.sleep(2)

        # Move frog to final line
        frog = altdriver.find_object(By.NAME, "Frogger")
        final_line = altdriver.find_object(By.NAME, "FinalLine")\
            .get_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule")
        frog.set_component_property("UnityEngine.Transform", "position", "UnityEngine.CoreModule", final_line)

        click_by_name(altdriver, "UpButton")
        time.sleep(5)

    print("[INFO] Frogger activity complete")
