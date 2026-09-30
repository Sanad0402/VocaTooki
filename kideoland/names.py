"""Kideo Land scene and object names, surveyed live 2026-09-29 and read off the game source.

Leaf module: constants only, no imports from the rest of the package.
"""

ASSEMBLY = "Assembly-CSharp"

# ---- scenes (GameSceneCatalog/KideoLandSceneCatalog.asset) -------------------
START_SCENE = "KideoLandStartScene_new"
MAP_SCENE = "KideoLandMap"
CUT_SCENE = "KideoLandCutScene"
WORDLIST_SCENE = "KideoLandWordListScene"
SLOT_MACHINE_SCENE = "KideoLandActivitiesSlotMachine"
SELECTION_SCENE = "KideoLandActivitySelectionScene"
TESTS_SCENE = "KideoLandTests"
AVATAR_SCENE = "Avatar3DBuilderScene"

# ---- login -------------------------------------------------------------------
# The login choice screen. The Button is the `Fitter` child; `Login` itself is a
# layout box that answers nothing.
LOGIN_CHOICE_BUTTON_PATH = "//ChoosePanel/Login/Fitter"
# First entry only: "you are" (component GenderSelectPopup, buttons Male/Female).
GENDER_POPUP = "KideoLandGenderSelectPopup(Clone)"
GENDER_OPTIONS = ("Male", "Female")

# ---- start scene islands -----------------------------------------------------
ISLAND_PREFIX = "CivilizationIsland_"
ISLAND_ICON = "IslandIcon"                       # EventTrigger -> CivilizationIslandIcon.Click()
ISLAND_ICON_COMPONENT = "CivilizationIslandIcon"
ISLAND_LOCK = "Locked-Group"                     # active = the island is locked
LESSONS_PER_ISLAND = 5

# ---- island map --------------------------------------------------------------
LEVEL_ICON = "KideoLandLevelMapIcon(Clone)"      # easy / medium / hard levels
LEVEL_ICON_COMPONENT = "LevelMapIcon"
EXAM_ICON = "KideoLandTestMapIcon(Clone)"        # the lesson's exam
EXAM_ICON_COMPONENT = "TestMapIcon"
ICON_NUMBER = "Text - RTLTMP"                    # the printed level number (levelIndex + 1)
ICON_LOCKED, ICON_CURRENT, ICON_DONE = 0, 1, 2   # MapLevelIconBase.IconState
LEVEL_TYPE_LESSON, LEVEL_TYPE_EXAM = 1, 2        # LevelBaseData.Type
DIFFICULTIES = ("easy", "medium", "hard")        # level 1, 2, 3 of a lesson

# ---- level flow --------------------------------------------------------------
NEXT_BUTTON = "nextButton"                       # word list -> slot machine
SPIN_BUTTON = "SpinButton"                       # the slot machine (Voca Tooki: Toggle)
ACTIVITY_SLOT = "KideoLandActivityPanelSlot(Clone)"
ACTIVITY_SLOT_COMPONENT = "VTActivitySlot"          # what the slot object reports
# activityInfo_ and finishedToggle are PRIVATE fields of the base class, and are
# read through it: asked through VTActivitySlot they come back empty.
ACTIVITY_SLOT_BASE_COMPONENT = "ActivitySlot"
ACTIVITY_SLOT_BUTTON = "ActivityThumb"
SELECTION_BACK = "Back"

# ---- results -----------------------------------------------------------------
FEEDBACK_POPUP = "KideoLandFeedbackPopup(Clone)"
FAILURE_FEEDBACK_POPUP = "KideoLandFailureFeedbackPopup(Clone)"

# ActivityID (voca_tooki_infra/Data/ActivitiesData.cs) -- the enum NAME is the
# key of the shared solver table, exactly as Voca Tooki's GetCurrentActivity
# reports it.
ACTIVITY_IDS = {
    0: "MISSING_BUBBLE", 1: "TURTLE_ISLAND", 2: "MISSING_STAR", 3: "MEMMORY_CARDS",
    4: "WORD_IMAGE", 5: "CROSSWORD", 6: "SPACE_SHOOTER", 7: "MATCH_PAIRS", 8: "DARK_ROOM",
    9: "TETRIS", 10: "ROOM_SEARCH", 11: "FISHER", 12: "STACK", 13: "SPEECH_RECOGNITION",
    14: "WORD_SOUND", 15: "RADAR", 16: "BEE_CAREFUL", 17: "LISTEN_FIND", 18: "DAY_NIGHT",
    19: "SEARCH", 20: "PARASHOOT", 21: "PUZZLES", 22: "ROCKETS", 23: "SNAKE", 24: "WORDTREE",
    25: "UNSCRAMBLE_QUIZ", 26: "PIPES", 27: "BRICKOUT", 28: "FROGGER", 29: "CROSSWORD2",
    30: "WORDS_MATCHING_QUIZ", 31: "SENTENCE_COMPLETION_QUIZ", 32: "SENTENCE_TRANSLATION_QUIZ",
    33: "RINGS", 34: "HANGWORDS", 35: "ISPY", 36: "SHARKS", 37: "SENTENCE_COMPLETION_OPENNING",
    38: "SENTENCE_TRANSLATION_OPENNING", 39: "WORDS_MATCHING_OPENNING", 40: "UNSCRAMPLE_OPENNING",
    41: "LETTERS_BUBBLES", 42: "LETTERS_SEARCH", 43: "LETTERS_TRACING", 44: "LETTERS_SORTING",
    45: "LETTERS_RACER", 46: "LETTERS_SLIDER_TRACING", 47: "BALLOONS", 48: "CARDS",
    49: "DELIVERY_TRUCK", 50: "MOLES", 51: "WORDLE", 52: "WORDSCONNECT", 53: "TRANSLATION_WIZ",
    54: "SOUNT_IT_OUT", 55: "GAP_GURU", 56: "ECHO_ORDER", 57: "TYPE_IT_RIGHT",
    58: "BALLOONS_SPEAKING", 59: "CARDS_SPEAKING", 60: "DELIVERY_TRUCK_SPEAKING",
    61: "MOLES_SPEAKING", 62: "ROCKETS_SPEAKING", 63: "EGGS", 64: "HANGING_BRIDGE",
    65: "SPIDER_WEB_RESCUE", 66: "WORD_FACTORY", 67: "LETTER_FISHING",
}
