"""MEMMORY_CARDS: turn over matching card pairs.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import time

from alttester import By


def find_matching_pairs(items):
    return [(i, j) for i in range(len(items)) for j in range(i+1, len(items)) if items[i] == items[j]]


def memory(altdriver):
    """Matches word-image pairs in the Memory activity."""
    time.sleep(17)

    text_cards = altdriver.find_objects(By.NAME, "ImageCardPrefab(Clone)")
    image_cards = altdriver.find_objects(By.NAME, "TextCardPrefab(Clone)")
    cards = image_cards + text_cards

    card_contents = [card.get_component_property("CardHandler1", "word.word", "Assembly-CSharp") for card in cards]
    pairs = find_matching_pairs(card_contents)

    for i, j in pairs:
        cards[i].click()
        time.sleep(0.5)
        cards[j].click()
        time.sleep(0.5)

    print("[INFO] Memory activity complete")
