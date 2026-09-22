"""Daily game solvers: Wordle and Word Connect.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def wordle(altdriver):
    # 1️⃣ Read target word from Gameplay Manager
    gm = altdriver.find_object(By.NAME, "Gameplay Manager")
    word = gm.get_component_property(
        "KaelmixStudioGameAssets.TemplateWordGuess.GameplayManager",
        "word",
        "Assembly-CSharp"
    ).upper()

    print(f"[INFO] Target word: {word}")

    # 2️⃣ Type each character by finding Key(<letter>)
    for index, letter in enumerate(word):
        key_name = f"Key ({letter})"   # 🟢 Construct object name dynamically

        print(f"[INFO] Clicking letter {index+1}/{len(word)}: {letter} -> {key_name}")

        key_obj = altdriver.find_object(By.NAME, key_name)
        key_obj.tap()  # 👈 Click the key

        time.sleep(0.2)  # ⏱️ Small delay for realism

    # 3️⃣ Press ENTER
    enter_btn = altdriver.find_object(By.NAME, "Enter")
    enter_btn.tap()
    print("[INFO] Submitted the word successfully!")


def word_connect(altdriver, words=None, card_name=None, sleep_after_word=0.25):
    """Swipe the board's words. Reads BOTH the words and the card name from the
    game unless they are passed in.

    The defaults used to be a literal ("HIT", "GET", "EIGHTY", ...) taken from
    whatever puzzle this was written against, so calling it directly -- from the
    console, say -- tried to spell words the board could not spell, and failed
    with "Missing letter 'H'" on a board dealing B I S T C U I. The words belong
    to the puzzle, so they are asked of the puzzle.
    """
    if words is None or card_name is None:
        from Utilities import utilsdemo as _u          # local: avoids a cycle
        if card_name is None:
            _cards, _letters, found = _u._word_connect_cards(altdriver)
            card_name = found or "WordsConnectCard_4 Variant(Clone)"
        if words is None:
            words = _u.word_connect_words(altdriver)
            if not words:
                raise Exception(
                    "[ERROR] word_connect: the board's words could not be read "
                    "from the game, and none were given. Pass words=[...] or "
                    "run it where WordConnect.WordsConnect is readable.")
            print(f"[INFO] word_connect: words read from the game: {list(words)}")

    print("[INFO] word_connect: Fetching cards...")
    cards = altdriver.find_objects(By.NAME, card_name)
    print(f"[INFO] Found {len(cards)} cards")

    # Build: letter -> [card objects]
    cards_by_letter = {}
    for idx, card in enumerate(cards):
        # IMPORTANT: no ".//*" here ('.' breaks PATH parsing); use "//Letter"
        letter_obj = card.find_object_from_object(By.PATH, "//Letter")  #
        letter = letter_obj.get_text().strip().upper()
        print(f"[INFO] Card[{idx}] = {letter}")
        cards_by_letter.setdefault(letter, []).append(card)

    print(f"[INFO] Available letters: {sorted(cards_by_letter.keys())}")

    # Swipe each target word
    for raw_word in words:
        word = raw_word.strip().upper()
        if not word:
            continue

        # For safety, allow repeated letters in a word by "consuming" card instances
        pool = {k: v[:] for k, v in cards_by_letter.items()}

        positions = []
        for ch in word:
            if ch not in pool or not pool[ch]:
                raise Exception(f"[ERROR] Missing letter '{ch}' on cards. Word='{word}'")

            card = pool[ch].pop(0)
            positions.append(card.get_screen_position())

        duration = max(4, 1.7 * len(positions))
        print(f"[INFO] Swiping '{word}' with {len(positions)} points, duration={duration}")

        altdriver.multipoint_swipe(positions, duration=duration, wait=True)  #
        time.sleep(sleep_after_word)
