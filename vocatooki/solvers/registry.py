"""THE activity scene -> solver table. One table, used by every path that plays an activity.

(It used to be written out twice — inside run_activity and in
get_activity_solver_map — and the two had to be kept in step by hand.)

Map a new activity here only after its solver has passed easy, medium AND
hard live.
"""

from vocatooki.solvers import (
    bee_careful, brickout, crosswords, echo_order, frogger, gap_guru, hang_words, ispy,
    listen_find, memory_cards, missing_bubble, parashoot, pipes, puzzles, radar, rings, search,
    sentence_completion, sentence_translation, sharks, tetris, translation_wiz, turtle_island,
    type_it_right, unscramble, words_matching,
)
from vocatooki.solvers.third_grade import (
    letters_bubbles, letters_search, letters_sorting, letters_tracing,
)

SOLVERS = {
    "MEMMORY_CARDS": memory_cards.memory,
    "LISTEN_FIND": listen_find.megaphone,
    "SENTENCE_COMPLETION_QUIZ": sentence_completion.fill_in,
    "SENTENCE_TRANSLATION_QUIZ": sentence_translation.spiders,
    "SEARCH": search.search,
    "MISSING_BUBBLE": missing_bubble.bubbels,
    "RADAR": radar.radar,
    "UNSCRAMBLE_QUIZ": unscramble.lexi_match,
    "GAP_GURU": gap_guru.gap_guru,
    "TYPE_IT_RIGHT": type_it_right.type_it_right,
    "TRANSLATION_WIZ": translation_wiz.translation_wiz,
    "ECHO_ORDER": echo_order.echo_order,
    "FROGGER": frogger.frogger,
    "HANGWORDS": hang_words.hang_words,
    "WORDS_MATCHING_QUIZ": words_matching.moving,
    "BEE_CAREFUL": bee_careful.bee,
    "ISPY": ispy.ispy,
    "LETTERS_SEARCH": letters_search.search_3rd,
    "LETTERS_BUBBLES": letters_bubbles.bubbels_activity_3rd,
    "LETTERS_SORTING": letters_sorting.signs,
    "CROSSWORD2": crosswords.crosswords2,
    "CROSSWORD": crosswords.crosswords,
    "PUZZLES": puzzles.solve_puzzles,
    "TURTLE_ISLAND": turtle_island.turtle_island,
    "BRICKOUT": brickout.brickout,
    "PIPES": pipes.pipes,
    "RINGS": rings.rings,
    "PARASHOOT": parashoot.parashoot,
    "TETRIS": tetris.tetris,
    "LETTERS_TRACING": letters_tracing.letters_tracing,
    "LETTERS_SLIDER_TRACING": letters_tracing.letters_slider_tracing,
    "SHARKS": sharks.sharks,
}
