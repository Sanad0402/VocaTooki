"""Front door of the VocaTooki test framework — kept for compatibility.

The framework lives in the ``vocatooki`` package, one module per domain:

    ui_actions            find / press / read UI objects by name
    scenes                scene names and "is this screen ready" waits
    instructions_parrot   the instructions parrot (blocker, bubble)
    evidence_screenshots  the ordered picture walkthrough of a test case
    login_session         log in / out, first-entry gender popup
    map_navigation        the lesson map, levels, app features
    activity_runner       open + solve activities, finish-to-pass, evidence frames
    lesson_modes          full / express / express-hard lesson runs
    exam_solver           exams: open, recognise pages, solve, submit
    exam_results_api      exam results from the backend
    guest_flow            the guest (free trial) flow
    events, daily_games, tasks, treasure_island, pretest_gate
    backend_api           which API host every call goes to

Every name those modules define is re-exported here, so the generated Rally
tests, the runner, the page objects and the solvers keep working unchanged.
New code should import from ``vocatooki`` directly.

Values a run REASSIGNS (the chosen API, the logged-in user) are not copied
here — they are served live by ``__getattr__`` at the bottom.
"""

# Kept exactly as before: Activities/activitiesDemo.py does
# ``from Utilities.utilsdemo import *`` and uses some of these (logging,
# AltKeyCode, AltDriver) without importing them itself.
import logging  # noqa: F401
import random  # noqa: F401
import re  # noqa: F401
import requests  # noqa: F401
import io  # noqa: F401
import time  # noqa: F401
import os  # noqa: F401
from datetime import datetime  # noqa: F401
from alttester import By, AltKeyCode, AltDriver  # noqa: F401
from alttester.exceptions import ComponentNotFoundException  # noqa: F401

from vocatooki import backend_api as _backend
from vocatooki import login_session as _login_session

from vocatooki.backend_api import (  # noqa: F401
    backend_pinned, _CLASS_MAP_HOST, current_backend, get_class_map, get_user_state,
    set_backend, VT_BACKEND_AUTO, VT_BACKENDS, _VT_DATA_API_DEFAULT,
    _VT_DATA_API_HOSTS_DEFAULT, _vt_data_bases, _VT_ENV_AT_IMPORT, _VT_TASKS_API_DEFAULT,
)

from vocatooki.ui_actions import (  # noqa: F401
    assert_text_by_name, assert_text_by_path, call_method, capture_failure_screenshot,
    click_by_name, click_by_path, component_property, find_any, _find_by_text, find_element,
    get_text_by_name, get_text_by_path, is_on_screen, POPUP_CLICK_DELAY, POPUP_MESSAGE_OBJECT,
    popup_text, _press, _press_candidates, PRESS_CHILD_FIRST, _PRESS_CHILD_PATHS,
    _press_confirmed, press_label, press_object, PRESS_PROBE_SECONDS, RTL_TEXT_COMPONENTS,
    _score_int, SCREEN_TEXT_NAMES, screen_texts, _slugish, tap_empty_area, _text_of,
    _TEXT_SCAN_PATHS, _text_variants, toggle_label, _visible_text_object, visible_texts,
    wait_for_any,
)

from vocatooki.scene_names import (  # noqa: F401
    ACTIVITY_SELECTION_SCENE, ACTIVITY_SELECTION_SCENE_MARKER, AVATAR_SCENE, MAP_SCENE,
    PRETEST_SCENE, START_SCENE,
)

from vocatooki.scenes import (  # noqa: F401
    app_health, app_state, _current_scene, GUEST_ERROR_POPUPS, GUEST_WIZARD_MARKERS,
    HUB_MARKERS, in_app, LOGIN_SCREEN_FIELDS, _login_screen_visible, onboarding_visible,
    SCENE_READY_POLL_SECONDS, SCENE_READY_STABLE_SECONDS, SCENE_READY_TIMEOUT,
    START_SCENE_BUTTONS, START_SCENE_POLL_SECONDS, START_SCENE_READY_TIMEOUT,
    START_SCENE_STABLE_SECONDS, _wait_for_login_screen, wait_for_scene, wait_for_scene_ready,
    wait_for_start_scene_ready, _wait_leaves_scene,
)

from vocatooki.instructions_parrot import (  # noqa: F401
    dismiss_help_popup, dismiss_replay_popup, dismiss_screen_blocker, parrot_bubble_shown,
    PARROT_BUBBLES, parrot_instructions_text, PARROT_TEXT_NODE, SCREEN_BLOCKER,
)

from vocatooki.evidence_screenshots import (  # noqa: F401
    capture_evidence, EVIDENCE_KEY, EVIDENCE_MAX_PER_CASE, EVIDENCE_PROOF, EVIDENCE_STEP,
    evidence_trail, _EVIDENCE_TRAILS, EvidenceTrail, reset_evidence_trail,
)

from vocatooki.login_session import (  # noqa: F401
    AVATAR_BUILDER_SCENE, ensure_logged_in, fresh_login, GENDER_OPTIONS, GENDER_POPUP,
    GENDER_POPUP_TIMEOUT, handle_gender_select, login, LOGIN_SETTLE_SECONDS, logout_via_ui,
    return_to_start,
)

from vocatooki.map_navigation import (  # noqa: F401
    APP_FEATURES, _BACK_BUTTON_NAMES, ensure_on_map, enter_level_number, enter_to_level,
    extract_lesson_titles, FEATURE_BUTTON_TIMEOUT, FEATURE_PRESS_RETRY_AFTER,
    _find_level_icons, get_level, _level_icon_by_number, LEVEL_ICON_KINDS, level_kind,
    _map_ready, MAP_SETTLE_SECONDS, open_feature, open_level_to_activities, return_to_map,
)

from vocatooki.activity_runner import (  # noqa: F401
    activity_completed, ACTIVITY_EXITS, activity_finished, activity_frame, ACTIVITY_FRAMES,
    ACTIVITY_GENERIC_MARKERS, ACTIVITY_INTRO_QUIET, ACTIVITY_INTRO_TIMEOUT,
    ACTIVITY_LOAD_TIMEOUT, activity_report, ACTIVITY_RESULT_MARKERS, ACTIVITY_RESULT_TIMEOUT,
    ACTIVITY_UI_MARKERS, ACTIVITY_UI_TITLES, back_to_activity_list, clear_activity_intro,
    FAILED_ACTIVITIES, find_activity_thumb, get_activity_solver_map,
    _get_current_activity_with_retry, handle_level_flow, _infer_scene_from_title,
    list_level_activities, _MID, _mid_activity_frame, MID_FRAME_FALLBACK_SECONDS,
    _play_activity, read_activity_progress, retry_lost_activity, run_activity,
    solve_activity_in_level, _solve_activity_once, _solve_open_activity, _TITLE_X_TOLERANCE,
    validate_activity_ui, wait_for_activity_board, wait_for_activity_result,
    wait_for_finish_feedback, _watch_mid_frame, when_finish_activity, write_activity_report,
)

from vocatooki.lesson_modes import (  # noqa: F401
    solve_lesson, solve_lesson_express, solve_lesson_express_hard, solve_lesson_levels,
    solve_lesson_levels_express, solve_lesson_levels_express_hard, solve_lessons_express_hard,
    solve_level, solve_level_express, solve_level_express_hard,
)

from vocatooki.exam_solver import (  # noqa: F401
    detect_exam_type, detect_exam_type_settled, EXAM_APPEAR_SETTLE_SECONDS,
    EXAM_RESULT_MARKERS, open_exam, run_all_exams, solve_exam, solve_exam_pages,
)

from vocatooki.exam_results_api import (  # noqa: F401
    extract_user_id_from_userid_examid, format_exam_timestamp, get_auth_headers,
    get_user_exam_by_userid_examid, _load_project_env, login_and_get_vt_token, _TOKEN_CACHE,
    VT_GAME, VT_LOGIN_URL, VT_PASSWORD, VT_USERNAME,
)

from vocatooki.guest_flow import (  # noqa: F401
    dismiss_gender_popup, _drag_picker, enter_guest_mode, GUEST_ACTIVITY_SETTLE_SECONDS,
    _guest_back_to_map, guest_clear_data_notice, GUEST_ENTRY, guest_entry_available,
    GUEST_EXAM_SETTLE_SECONDS, guest_first_exam_level, GUEST_GATE_FOLLOWUP_OK, GUEST_GATE_OK,
    GUEST_GATE_PANEL, GUEST_GATE_TEXT, GUEST_GATE_TEXT_PROPERTY, GUEST_GENDER_LABELS,
    GUEST_GENDERS, guest_level_locked, GUEST_LOCK_MARKERS, _GUEST_NON_ACTIVITY_SCENES,
    guest_open_level, GUEST_PICKER_LINE_BOTTOM, GUEST_PICKER_LINE_TOP, GUEST_PROMPT,
    _guest_screen_offers, guest_subscribe_gate, guest_take_exam, GUEST_TOGGLE_PREFIX,
    _guest_toggles, guest_walk_levels, GUEST_WELCOME_MARKERS, _norm_label, _option_labels,
    picker_band, reset_guest_data, _row_position, scroll_option_into_band, select_guest_option,
    _select_visible_option, _toggle_is_on,
)

from vocatooki.events import (  # noqa: F401
    event_activity_scores, event_back_to_map, event_cards, event_cards_check,
    event_leaderboard, EVENT_LEADERBOARD_BUTTON, EVENT_LEVEL_ICON, EVENT_LOCKED_MARKER,
    event_next_card, EVENT_NO_RESULTS_TEXT, event_open_levels, EVENT_PLAYER_NAME_OBJECT,
    EVENT_SCENE, event_score_check, EVENT_SCORE_OBJECT, EVENT_SELECTION_SCENE,
    EVENT_START_BUTTON, EVENT_WINNERS_BUTTON, _leaderboard_rows, open_event, open_event_level,
    OVERLAY_SETTLE_SECONDS, solve_event_levels, solve_specific_event_level,
)

from vocatooki.daily_games import (  # noqa: F401
    daily_game_won, DAILY_GAMES, solve_daily_game, _WC_CARD_NAMES, _word_connect_cards,
    word_connect_words,
)

from vocatooki.tasks import (  # noqa: F401
    class_tasks, _PLAYER_CACHE, task_answer_by_data_id, task_answer_key, TASK_ANSWER_PREFIX,
    task_answer_question, task_answer_selected, task_answers, task_api_headers,
    TASK_CARD_CLOSED, TASK_CARD_OPEN, TASK_CHECKED_TIMEOUT, TASK_CONFIRM_POPUP,
    TASK_CONFIRM_YES, _task_count, TASK_MULTIPLE_CHOICE, TASK_NEXT_TIMEOUT,
    TASK_QUESTION_PREFIX, task_questions, TASK_RECORD_TIMEOUT, TASK_SCENE, TASK_STATUS_CHECKED,
    TASK_SUBMIT, task_submitted_answers, task_tab_counts, TASK_TABS, TASK_TITLE,
    _tasks_answer_key_for, tasks_check, TASKS_SCENE, _tasks_settle_for_next, _tasks_solve_one,
    user_class_id, vt_player, VT_PLAYER_EMAIL_DOMAIN, VT_PLAYER_LOGIN_URL,
    wait_for_task_checked, wait_for_task_recorded,
)

from vocatooki.treasure_island import (  # noqa: F401
    TI_BUILDING_PREFIX, ti_buildings, TI_COMPLETE, _ti_elements, TI_INTRO_SKIP,
    TI_ISLAND_ALIASES, ti_island_for_skill, ti_island_locked, TI_ISLAND_PREFIX, ti_level,
    TI_LEVEL_TEXT, TI_LOCK_FOG, TI_LOCK_HOLDER, ti_missions, TI_MISSIONS_BUTTON,
    TI_MISSIONS_EXIT, TI_NO_AUTOMATION, ti_open_missions, TI_PANEL_PLAY,
    TI_PANEL_SETTLE_SECONDS, _ti_percent, TI_PERCENT_TEXT, TI_PLAY_ATTEMPTS, ti_play_building,
    ti_press_row_play, TI_ROW, TI_ROW_PLAY, _ti_short, ti_skip_intro, treasure_island_check,
    TREASURE_ISLAND_SCENE,
)

from vocatooki.pretest_gate import (  # noqa: F401
    PRETEST_ENTRIES_FOR_SKIP, PRETEST_NODES, _pretest_object, pretest_skip, pretest_skip_ready,
    _pretest_wait_scene,
)


# Every AltTester click / tap / swipe / touch clears the instructions parrot
# first, and every newly entered scene has its intro cleared — see
# vocatooki/parrot_guard.py. Installed here so everything that imports the
# framework gets it. VT_PARROT_GUARD=0 turns it off.
from vocatooki import parrot_guard as _parrot_guard  # noqa: E402

_parrot_guard.install()

_parrot_guard.ACTION_HOOKS.append(_mid_activity_frame)



# Run-time values that live in another module and must be read LIVE: a copy
# taken at import would keep pointing at the API chosen before the run, or at
# the user logged in before it.
_LIVE_NAMES = {
    "VT_DATA_API": _backend,
    "VT_TASKS_API": _backend,
    "_VT_BACKEND": _backend,
    "_LAST_LOGIN_USER": _login_session,
}


def __getattr__(name):
    """utilsdemo.<name> for a value that lives in a vocatooki module (PEP 562)."""
    owner = _LIVE_NAMES.get(name)
    if owner is not None:
        return getattr(owner, name)
    raise AttributeError(f"module 'Utilities.utilsdemo' has no attribute {name!r}")
