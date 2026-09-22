"""Daily games (Word Connect) - solving and the win check.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import map_navigation, scenes, ui_actions


# The two Daily Games and the scene each one loads. GetCurrentActivity returns
# "Undefined" for them, so the SCENE is the only reliable identifier.
DAILY_GAMES = {
    "wordle": {"entry": "//Wordle/GameIcon", "scene": "VTWordGuess"},
    "word connect": {"entry": "//Word Connect/GameIcon", "scene": "VTWORD_CONNECT"},
}


_WC_CARD_NAMES = ("WordsConnectCard_4 Variant(Clone)", "WordsConnectCard_5 Variant(Clone)",
                  "WordsConnectCard_3 Variant(Clone)", "WordsConnectCard_6 Variant(Clone)")


def _word_connect_cards(altdriver):
    """(card objects, letters) for the Word Connect board, or ([], [])."""
    for name in _WC_CARD_NAMES:
        cards = altdriver.find_objects(By.NAME, name)
        if not cards:
            continue
        letters = []
        for c in cards:
            try:
                letters.append(c.find_object_from_object(By.PATH, "//Letter")
                               .get_text().strip().lower())
            except Exception:
                letters.append("")
        return cards, letters, name
    return [], [], ""


def word_connect_words(altdriver):
    """Today's target words, read from the game itself.

    ``WordConnect.WordsConnect`` on GameCanvas carries the whole puzzle bank as
    ``levels`` (each ``{letters, words}``) plus ``currentLevel``. The level is
    matched by the letters ACTUALLY on the cards rather than trusting the index,
    so an off-by-one or a rolled-over level can't make the solver swipe words
    that aren't on the board. Returns [] when it cannot be determined.
    """
    gc = ui_actions.find_element(altdriver, "GameCanvas")
    if gc is None:
        logging.error("[Daily] GameCanvas not found — not in Word Connect?")
        return []
    try:
        levels = gc.get_component_property(
            "WordConnect.WordsConnect", "levels", "Assembly-CSharp") or []
        index = gc.get_component_property(
            "WordConnect.WordsConnect", "currentLevel", "Assembly-CSharp")
    except Exception as e:  # noqa: BLE001
        logging.error(f"[Daily] could not read the Word Connect puzzle bank: {e}")
        return []

    _cards, letters, _name = _word_connect_cards(altdriver)
    on_board = sorted(l for l in letters if l)
    logging.info(f"[Daily] Word Connect level {index}, letters on board: {on_board}")

    def words_of(entry):
        return [str(w).upper() for w in (entry or {}).get("words", [])]

    if isinstance(index, int) and 0 <= index < len(levels):
        entry = levels[index]
        if not on_board or sorted(str(c).lower() for c in entry.get("letters", [])) == on_board:
            return words_of(entry)
        logging.warning(f"[Daily] level {index} letters {entry.get('letters')} do not match "
                        f"the board {on_board} — searching the bank by letters")

    for entry in levels:
        if sorted(str(c).lower() for c in entry.get("letters", [])) == on_board:
            return words_of(entry)

    logging.error(f"[Daily] no level in the bank matches the board {on_board}")
    return []


def solve_daily_game(altdriver, game, username=None, password=None):
    """Open a Daily Game from the start screen and play it to a win.

    ``game`` is "wordle" or "word connect". Returns
    ``{"opened", "solved", "scene", "note"}`` — never raises, so a test can
    assert on the fields and a failure leaves the app on the failing screen.

    Daily Games are once per day per account: when the game has already been
    played the entry has no Play button, which comes back as opened=False with
    a note saying so, NOT as a pass.
    """
    from Activities import activitiesDemo as A

    key = (game or "").strip().lower()
    spec = DAILY_GAMES.get(key)
    result = {"opened": False, "solved": False, "scene": None, "note": ""}
    if not spec:
        result["note"] = f"unknown daily game '{game}'"
        return result

    if not map_navigation.open_feature(altdriver, "daily games", username=username, password=password):
        result["note"] = "the Daily Games page did not open (already played today?)"
        return result

    icons = altdriver.find_objects(By.PATH, spec["entry"])
    if not icons:
        result["note"] = f"'{game}' is not on the Daily Games page"
        return result
    icons[0].tap()
    time.sleep(4)

    play = ui_actions.find_element(altdriver, "PlayNowButton")
    if play is None:
        result["note"] = f"no Play button for '{game}' — already played today"
        return result
    play.tap()

    deadline = time.time() + 45
    while time.time() < deadline:
        if scenes._current_scene(altdriver) == spec["scene"]:
            break
        time.sleep(2)
    result["scene"] = scenes._current_scene(altdriver)
    if result["scene"] != spec["scene"]:
        result["note"] = f"expected scene {spec['scene']}, got {result['scene']}"
        return result
    result["opened"] = True
    time.sleep(3)

    try:
        if key == "wordle":
            A.wordle(altdriver)                 # reads the answer off GameplayManager
        else:
            words = word_connect_words(altdriver)
            if not words:
                result["note"] = "could not read today's Word Connect words"
                return result
            logging.info(f"[Daily] solving Word Connect with {words}")
            _cards, _letters, card_name = _word_connect_cards(altdriver)
            A.word_connect(altdriver, words=words, card_name=card_name)
    except Exception as e:  # noqa: BLE001 - report, don't mask
        result["note"] = f"solver failed: {e}"
        return result

    time.sleep(5)
    result["solved"] = daily_game_won(altdriver)
    if not result["solved"]:
        result["note"] = "the game did not report a win"
    return result


def daily_game_won(altdriver, timeout=20):
    """True when the daily game shows its win/feedback screen."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ui_actions.find_element(altdriver, "DailyGamesFinalFeedback") is not None:
            return True
        for o in altdriver.find_objects(By.NAME, "Text (TMP)"):
            try:
                if "won" in (o.get_text() or "").lower():
                    return True
            except Exception:
                continue
        time.sleep(2)
    return False
