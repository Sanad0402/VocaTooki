"""Front door of the activity solvers — kept for compatibility.

The solvers live in ``vocatooki/solvers/``, one module per activity family:

    quizzes, word_finding, bubbles, frogger, bee_careful, crosswords, puzzles,
    rings, parashoot, pipes, brickout, turtle_island, tetris, letter_sorting,
    letters_tracing, sharks, exam_pages, daily_game_solvers, text_utils, legacy

Every solver is re-exported here, so the runner (``A.frogger``), the exam
solver, the daily games and the tests keep working unchanged. The imports
below are kept exactly as they were, because callers also read framework
names THROUGH this module (it has always star-imported utilsdemo).
"""

import alttester  # noqa: F401
import inflect  # noqa: F401
import unicodedata  # noqa: F401
import time  # noqa: F401
import re  # noqa: F401
import math  # noqa: F401
import heapq  # noqa: F401
from collections import Counter  # noqa: F401
from alttester import By  # noqa: F401
from langdetect import detect  # noqa: F401
from Utilities.utilsdemo import *  # noqa: F401,F403
from Utilities.utilsdemo import click_by_name  # noqa: F401
from vocatooki.text_to_speech import say, init_audio  # noqa: F401
from Utilities import utilsdemo as _utilsdemo

from vocatooki.solvers.text_utils import (  # noqa: F401
    base_arabic_mapping, is_rtl, normalize_text,
)

from vocatooki.solvers.search import (  # noqa: F401
    search,
)

from vocatooki.solvers.memory_cards import (  # noqa: F401
    find_matching_pairs, memory,
)

from vocatooki.solvers.sentence_completion import (  # noqa: F401
    fill_in,
)

from vocatooki.solvers.missing_bubble import (  # noqa: F401
    bubbels,
)

from vocatooki.solvers.sentence_translation import (  # noqa: F401
    spiders,
)

from vocatooki.solvers.listen_find import (  # noqa: F401
    megaphone,
)

from vocatooki.solvers.echo_order import (  # noqa: F401
    echo_order,
)

from vocatooki.solvers.translation_wiz import (  # noqa: F401
    translation_wiz,
)

from vocatooki.solvers.frogger import (  # noqa: F401
    _frog_key, frogger, _frogger_bag, _frogger_blank_words, _frogger_fix_bag,
    _frogger_has_empty_blank, _frogger_tiles,
)

from vocatooki.solvers.gap_guru import (  # noqa: F401
    gap_guru,
)

from vocatooki.solvers.bee_careful import (  # noqa: F401
    bee,
)

from vocatooki.solvers.radar import (  # noqa: F401
    radar,
)

from vocatooki.solvers.type_it_right import (  # noqa: F401
    type_it_right,
)

from vocatooki.solvers.hang_words import (  # noqa: F401
    hang_words,
)

from vocatooki.solvers.words_matching import (  # noqa: F401
    moving,
)

from vocatooki.solvers.unscramble import (  # noqa: F401
    lexi_match,
)

from vocatooki.solvers.ispy import (  # noqa: F401
    ispy,
)

from vocatooki.solvers.crosswords import (  # noqa: F401
    crosswords, crosswords2, crosswords2_kl, _CW_CELL_ASSEMBLY, _CW_CELL_COMPONENT,
    _cw_cell_is_filled, _CW_GENERATOR, _cw_grid_shape, _cw_letters_to_press, _cw_selected_word,
)

from vocatooki.solvers.puzzles import (  # noqa: F401
    MAX_PASSES_PER_SENTENCE, _puzzle_progress, ROW_HEIGHT_TOLERANCE, solve_puzzles,
)

from vocatooki.solvers.rings import (  # noqa: F401
    _bare_letters, rings,
)

from vocatooki.solvers.parashoot import (  # noqa: F401
    parashoot,
)

from vocatooki.solvers.pipes import (  # noqa: F401
    pipes, _pipes_trace,
)

from vocatooki.solvers.brickout import (  # noqa: F401
    brickout,
)

from vocatooki.solvers.turtle_island import (  # noqa: F401
    turtle_island,
)

from vocatooki.solvers.tetris import (  # noqa: F401
    tetris,
)

from vocatooki.solvers.sharks import (  # noqa: F401
    sharks, _SHARKS_ASM, _sharks_board, _sharks_dodge, _sharks_hazards, _sharks_hearts,
    _sharks_islands, _SHARKS_LEAD, _sharks_offshore, _sharks_pick, _sharks_pixels_per_unit,
    _sharks_progress, _SHARKS_RAFT, _sharks_route, _sharks_sail_to, _sharks_take_retry,
)

from vocatooki.solvers.third_grade.letters_search import (  # noqa: F401
    search_3rd,
)

from vocatooki.solvers.third_grade.letters_bubbles import (  # noqa: F401
    bubbels_activity_3rd,
)

from vocatooki.solvers.third_grade.letters_sorting import (  # noqa: F401
    _reenter_signs, signs, _signs_entry,
)

from vocatooki.solvers.third_grade.letters_tracing import (  # noqa: F401
    letters_slider_tracing, letters_tracing, _LST_GOAL, _lst_grid, _lst_order_pieces,
    _lst_read_tiles, _lst_solve, _lst_tap, _LST_TILE, _lst_trace_round, _lst_wait_for_grid,
    _lst_wait_for_letters, _lt_active, _LT_ASM, _lt_curve_polyline, _lt_dismiss_dialogs,
    _LT_END_DWELL, _lt_exit_feedback, _LT_FEEDBACK, _lt_feedback_up, _LT_MANAGER,
    _LT_MIN_SWIPE, _LT_OVERSHOOT, _LT_PATH, _lt_path_alive, _lt_path_completed, _lt_progress,
    _lt_read_board, _lt_round, _lt_trace, _lt_wait_completed, _lt_wait_for_letter,
    _lt_writing_order,
)

from vocatooki.solvers.exam_pages import (  # noqa: F401
    exam_multiple_choice, _exam_prefab_name, exam_shuffled_context, exam_spelling,
    exam_swap_letters, exams_3rd_audio_to_letter_matrix, exams_3rd_letter_to_word_image_match,
    exams_audio_to_meaning, exams_image_for_voices, exams_image_to_audio, exams_word_to_image,
    exams_word_to_meaning, _read_matchables, solve_match_exam, _spelling_bare_letter,
)

from vocatooki.solvers.daily_game_solvers import (  # noqa: F401
    word_connect, wordle,
)

from vocatooki.solvers.legacy import (  # noqa: F401
    _as_bool, _button_interactable, Cards, Delivery_truck, moles, _safe_exists,
    _wait_until_exists,
)



def __getattr__(name):
    """Run-time values (the chosen API) that `import *` cannot copy: read live."""
    if name in _utilsdemo._LIVE_NAMES:
        return getattr(_utilsdemo, name)
    raise AttributeError(f"module 'Activities.activitiesDemo' has no attribute {name!r}")
