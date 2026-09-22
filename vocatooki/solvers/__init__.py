"""Activity and exam-page solvers — one module per activity, named after the activity.

    Activity scene                  Module
    ------------------------------  -------------------------------------------
    SEARCH                          search
    MEMMORY_CARDS                   memory_cards
    SENTENCE_COMPLETION_QUIZ        sentence_completion   (fill in)
    SENTENCE_TRANSLATION_QUIZ       sentence_translation  (spiders)
    MISSING_BUBBLE                  missing_bubble
    LISTEN_FIND                     listen_find           (megaphone)
    ECHO_ORDER                      echo_order
    TRANSLATION_WIZ                 translation_wiz
    FROGGER                         frogger
    GAP_GURU                        gap_guru
    BEE_CAREFUL                     bee_careful
    RADAR                           radar
    TYPE_IT_RIGHT                   type_it_right
    HANGWORDS                       hang_words
    WORDS_MATCHING_QUIZ             words_matching        (moving)
    UNSCRAMBLE_QUIZ                 unscramble            (lexi match)
    ISPY                            ispy
    CROSSWORD, CROSSWORD2           crosswords
    PUZZLES                         puzzles
    RINGS / PARASHOOT / PIPES       rings / parashoot / pipes
    BRICKOUT / TETRIS               brickout / tetris
    TURTLE_ISLAND                   turtle_island
    SHARKS                          sharks

    3rd grade (third_grade/)
    LETTERS_SEARCH                  third_grade.letters_search
    LETTERS_BUBBLES                 third_grade.letters_bubbles
    LETTERS_SORTING                 third_grade.letters_sorting
    LETTERS_TRACING,
    LETTERS_SLIDER_TRACING          third_grade.letters_tracing

    exam_pages          every exam page type (exam_solver picks which one runs)
    daily_game_solvers  Wordle, Word Connect
    text_utils          shared text helpers (normalise Arabic/Hebrew, right-to-left)
    legacy              functions nothing calls today, kept so no caller breaks

The scene -> solver table itself is vocatooki.activity_runner.get_activity_solver_map().
Every solver is still reachable as Activities.activitiesDemo.<name>.
"""
