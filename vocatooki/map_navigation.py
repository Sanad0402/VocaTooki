"""The lesson map: level icons, entering levels, app features, getting back to the map.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import backend_api, instructions_parrot, login_session, pretest_gate, scene_names, scenes, ui_actions


# API Utilities
def extract_lesson_titles(user_state):
    return [lesson["title"] for lesson in user_state.get("lessons", {}).get("lessons", [])]


def get_level(class_id, lesson_number, type="lesson", difficulty=-1):
    logging.info(f"[Level Resolver] Fetching level for class_id={class_id}, lesson={lesson_number}, type={type}, difficulty={difficulty}")

    # Normalize difficulty to lowercase string
    if isinstance(difficulty, str):
        difficulty = difficulty.lower()

    # Fetch map data
    map_data = backend_api.get_class_map(class_id, map_id=1)
    if not map_data or "map" not in map_data or "levels" not in map_data["map"]:
        logging.error("[Level Resolver] Invalid or missing map data structure.")
        return -1

    levels = map_data["map"]["levels"]

    if lesson_number >= len(levels):
        logging.error(f"[Level Resolver] Lesson index {lesson_number} is out of range. Total lessons: {len(levels)}")
        return -1

    lesson_levels = levels[lesson_number]
    logging.debug(f"[Level Resolver] Available levels: {lesson_levels}")

    for level in lesson_levels:
        logging.debug(f"[Level Resolver] Checking level: {level}")
        if type == "lesson" and level.get("difficulty", "").lower() == difficulty:
            logging.info(f"[Level Resolver] Found lesson level: {level.get('level')}")
            return level.get("level")
        if type == "exam" and level.get("type") == "exam":
            logging.info(f"[Level Resolver] Found exam level: {level.get('level')}")
            return level.get("level")

    logging.warning(f"[Level Resolver] No matching level found for type='{type}' and difficulty='{difficulty}'")
    return -1


def enter_to_level(altdriver, class_id, lesson_number, type="lesson", difficulty=-1):
    logging.info(
        f"[Map Navigation] Attempting to enter level: class_id={class_id}, lesson={lesson_number}, type={type}, difficulty={difficulty}"
    )

    level_num = get_level(class_id, lesson_number, type, difficulty)
    if level_num < 0:
        logging.error(f"[Map Navigation] Invalid level number: {level_num}. Cannot proceed.")
        return False

    try:
        # Anchored search, so a new map prefab needs no code change. Every map so
        # far (MainMap, 5thMap, Map_4, ...) puts its icons under the same
        # Levels/level_icons node, and _find_level_icons keeps the rooted paths
        # as fallbacks. Hunting prefab by prefab is what made Map_4 a code edit.
        level_objs = _find_level_icons(altdriver)

        if not level_objs:
            logging.error(f"[Map Navigation] No level icons on the current map "
                          f"(scene: {scenes._current_scene(altdriver)})")
            return False

        if level_num >= len(level_objs):
            logging.error(f"[Map Navigation] Level index {level_num} out of range ({len(level_objs)} icons).")
            return False

        # --- Click the target level ---
        level_objs[level_num].click()
        time.sleep(4)
        logging.info(f"[Map Navigation] Entered level index {level_num} successfully.")
        return True

    except Exception as e:
        logging.error(f"[Map Navigation] Exception while clicking level: {e}")
        return False


def _find_level_icons(altdriver):
    """Level icons of whichever map is currently loaded.

    The anchored search works for every map prefab (MainMap, 5thMap, ...);
    the two explicit paths are kept as fallbacks.
    """
    for path in ("//Levels/level_icons/*",
                 "/MainMap(Clone)/Map Backgrounds/Levels/level_icons/*",
                 "/5thMap(Clone)/Map Backgrounds/Levels/level_icons/*",
                 "/Map_4(Clone)/Map Backgrounds/Levels/level_icons/*"):
        try:
            objs = altdriver.find_objects(By.PATH, path)
            if objs:
                return objs
        except Exception:
            pass
    return []


# A map node's prefab name says what kind of level it is, and every icon is
# suffixed with the level number it opens ("TestLevelIcon(Clone) 40").
# Read off the live map: 248 nodes, exams every 4-5 levels.
LEVEL_ICON_KINDS = {
    "LessonLevelIcon": "lesson",        # the usual 3-activity level
    "TestLevelIcon": "exam",            # 4, 8, 13, 17, 22, 26, 31, 35, 40, ...
    "DialogueLevelIcon": "dialogue",
    "AiDialogueLevelIcon": "ai_dialogue",
    "RCLevelIcon": "reading",           # reading comprehension
    "TaskLevelIcon": "task",
}


def _level_icon_by_number(altdriver, level_num):
    """The map icon that opens ``level_num``, whatever kind of level it is.

    Icons are named after the level they open, so this beats counting: it
    cannot drift when the map has gaps, a different prefab, or an ordering the
    icon list doesn't reflect. Every prefab kind is tried, because an exam node
    ("TestLevelIcon(Clone) 40") is not a lesson node.

    Returns ``(AltObject|None, name|None, kind|None)``.
    """
    for prefab, kind in LEVEL_ICON_KINDS.items():
        for name in (f"{prefab}(Clone) {level_num}",
                     f"{prefab} Variant(Clone) {level_num}"):
            obj = ui_actions.find_element(altdriver, name)
            if obj is not None:
                return obj, name, kind
    return None, None, None


def level_kind(altdriver, level_num):
    """What kind of level ``level_num`` is on the map ("lesson", "exam", ...).

    Lets a test say out loud what it expects — an exam case pointed at a lesson
    node is a Rally data mistake worth failing on, not a mystery timeout.
    Returns None when the map is not showing or the level does not exist.
    """
    _obj, _name, kind = _level_icon_by_number(altdriver, level_num)
    return kind


# Every feature reachable from the start screen, surveyed on the live app.
# button  - what to click on the start screen
# scene   - the scene it loads ("" when it opens a popup on the start screen)
# markers - objects that prove the feature is really open
# back    - how to leave it (None: no back control exists, needs ensure_on_map)
APP_FEATURES = {
    # NOT BackButton: nearly every screen in the app has one, so it proved
    # nothing — it reported the map "open" while the app was on PretestScene.
    "map":            {"button": "GO-Map", "scene": scene_names.MAP_SCENE,
                       "markers": ["Levels", "level_icons", "CountersPanel"],
                       "back": "BackButton"},
    "tasks":          {"button": "GO-Tasks", "scene": "TasksSelectionScene",
                       "markers": ["ALL-NavigationTab", "Open-NavigationTab"], "back": "prev"},
    "events":         {"button": "GO-Events", "scene": "EventSelectionScene",
                       "markers": ["EventCard(Clone)", "StartButton", "WinnersButton"],
                       "back": "BackButton"},
    "audiobook":      {"button": "GO-Audiobook", "scene": "AudiobookLibraryScene",
                       "markers": ["BookCard(Clone)", "PlayButton"], "back": "BackButton"},
    "competitions":   {"button": "GO-Competitions", "scene": "TournamentSelectionScene",
                       "markers": ["Toggles"], "back": "BackButton"},
    "treasure island": {"button": "GO-Treasure_Island", "scene": "TreasureIsland",
                        "markers": ["GO-TI-Progress_Bar-Tube (1)"], "back": None},
    "daily games":    {"button": "GO-Daily", "scene": "DailyGamesSelection",
                       "markers": ["WinnersCards", "Ctrl-Card_1st"], "back": "prev"},
    "dialogue":       {"button": "GO-Dialogue", "scene": "DialogueSelectionScene",
                       "markers": ["DialogueSelectionButton(Clone)"], "back": "BackButton"},
    "multiplayer":    {"button": "GO-Multiplayer", "scene": "MultiplayerHub",
                       "markers": ["Head_to_Head-Enter_Button", "DraWin-Enter_Button"],
                       "back": None},
    "avatar builder": {"button": "GO-Avatar_Builder", "scene": "AvatarBuilderScene",
                       "markers": ["Level1_ButtonGroup"], "back": "BackButton"},
    "settings":       {"button": "SettingsButton", "scene": "",
                       "markers": ["SoundOnButton", "MusicOnButton", "LanguageToggleGroup"],
                       "back": "Exit"},
    "word list":      {"button": "WordListButton", "scene": "WordListScene",
                       "markers": ["audioButton", "upButton", "downButton"],
                       "back": "nextButton"},
    "user state":     {"button": "UserStateButton", "scene": "",
                       "markers": ["Button"], "back": "Button"},
}


# How long a start-screen feature button is waited for before the hub is
# declared to be missing it.
FEATURE_BUTTON_TIMEOUT = 20


# How long to let a feature press work before deciding it was swallowed and
# pressing again. Long enough that a slow scene load is never mistaken for a
# dead press.
FEATURE_PRESS_RETRY_AFTER = 10


def open_feature(altdriver, feature, username=None, password=None, timeout=40,
                 skip_pretest=True):
    """Open a start-screen feature by name ("events", "tasks", ...).

    Goes back to the start screen first (from wherever the app is), clicks the
    feature's button, and waits until its scene loads or one of its marker
    objects appears. Returns True only when the feature is really showing —
    a click that lands nowhere is a failure, not a pass.
    """
    spec = APP_FEATURES.get((feature or "").strip().lower())
    if not spec:
        logging.error(f"[Feature] unknown feature '{feature}'")
        return False

    if username:
        login_session.ensure_logged_in(altdriver, username, password)
    if not login_session.return_to_start(altdriver):
        ensure_on_map(altdriver, username, password)
        login_session.return_to_start(altdriver)

    # WAIT for the button rather than asking once. The hub reports itself ready
    # before it has finished spawning its buttons, so a single lookup here fails
    # a run that is perfectly healthy — seen live: "signed in as vt233632"
    # followed immediately by "'GO-Treasure_Island' is not on the start screen",
    # on the same account that had opened it minutes earlier.
    if not ui_actions.wait_for_any(altdriver, (spec["button"],), timeout=FEATURE_BUTTON_TIMEOUT):
        logging.error(f"[Feature] '{spec['button']}' is not on the start screen "
                      f"after {FEATURE_BUTTON_TIMEOUT}s (scene: {scenes._current_scene(altdriver)})")
        return False
    # A first-run greeting can sit over the hub and eat the press. Clear any
    # blocker we know about before pressing, so the common case needs no retry.
    instructions_parrot.dismiss_screen_blocker(altdriver)
    ui_actions.click_by_name(altdriver, spec["button"])

    deadline = time.time() + timeout
    swallowed_deadline = time.time() + FEATURE_PRESS_RETRY_AFTER
    retried = False
    while time.time() < deadline:
        here = scenes._current_scene(altdriver)
        # The placement pretest is a KNOWN destination, not a slow load. Sitting
        # out the whole timeout before noticing it cost 40s of every gated
        # login (measured end to end at 59.7s, nearly all of it here), so leave
        # at once and let the handler after this loop deal with it.
        if here == scene_names.PRETEST_SCENE:
            logging.info(f"[Feature] landed on {scene_names.PRETEST_SCENE} — not waiting "
                         f"the rest of the timeout out")
            break
        # Still sitting on the hub well after the press means the press went
        # nowhere -- on a NEW account Voca's introduction bubble covers the hub
        # and swallows it. Waiting the full timeout just turns that into a slow
        # failure, so press once more with the blocker cleared. Guarded on being
        # on the START scene so this can never double-fire mid-navigation.
        if (not retried and here == scene_names.START_SCENE
                and time.time() > swallowed_deadline):
            logging.info(f"[Feature] still on {scene_names.START_SCENE} — the press was "
                         f"swallowed; clearing blockers and pressing "
                         f"'{spec['button']}' again")
            instructions_parrot.dismiss_screen_blocker(altdriver)
            ui_actions.click_by_name(altdriver, spec["button"])
            retried = True
        if spec["scene"] and here == spec["scene"]:
            # Opened is not the same as ready — let it finish building before
            # anything presses into a half-built screen.
            scenes.wait_for_scene_ready(altdriver, label=spec["scene"])
            logging.info(f"[Feature] '{feature}' open (scene {spec['scene']})")
            return True
        # Markers only get a say when the feature has no scene of its own (a
        # popup over the start screen) or the scene cannot be read. Letting an
        # object vouch for a feature while the app sits in a DIFFERENT known
        # scene is how "map is open" came back true on PretestScene.
        if not spec["scene"] or not here:
            for marker in spec["markers"]:
                if ui_actions.find_element(altdriver, marker) is not None:
                    scenes.wait_for_scene_ready(altdriver, label=feature)
                    logging.info(f"[Feature] '{feature}' open (found {marker})")
                    return True
        time.sleep(2)

    here = scenes._current_scene(altdriver)
    if here == scene_names.PRETEST_SCENE:
        # The account's class is configured for a pretest in the CRM and the map
        # is behind it. It does NOT have to be sat: five node entries make a Skip
        # appear, and taking it lands on the map (user, 2026-09-01).
        if skip_pretest:
            logging.info(f"[Feature] '{feature}' is behind the placement "
                         f"PRETEST — skipping it")
            if pretest_gate.pretest_skip(altdriver) and scenes._current_scene(altdriver) == scene_names.MAP_SCENE:
                scenes.wait_for_scene_ready(altdriver, label=scene_names.MAP_SCENE)
                logging.info(f"[Feature] pretest skipped — '{feature}' reached")
                return feature == "map"
            logging.error(f"[Feature] could not get past the placement pretest "
                          f"(scene: {scenes._current_scene(altdriver)})")
            return False
        # Named explicitly so the failure says WHY: nothing is broken and no
        # wait will fix it. Depends on the class config, not on the account
        # being new — another account may not hit this at all.
        logging.error(f"[Feature] '{feature}' is behind the placement PRETEST: "
                      f"this account's class is configured for a pretest in the "
                      f"CRM and it has not been taken, so the map cannot be "
                      f"reached. Take it, or run the case on an account whose "
                      f"class has no pretest.")
        return False
    logging.error(f"[Feature] '{feature}' did not open (scene: {here})")
    return False


# How long to stand still after ARRIVING on the map, before pressing anything on
# it. The icons appear before the map has finished arranging itself, and a press
# that lands in that window is swallowed silently — which is why an icon press
# could look like it did nothing at all.
MAP_SETTLE_SECONDS = 5.0


def _map_ready(altdriver, timeout=30):
    """Is the map loaded AND usable — i.e. are its level ICONS there?

    The scene name flips to MapScene before the icons spawn, so "the scene is
    the map" is not enough: a level lookup made in that window finds nothing
    and reports the level as missing from the map. Waiting on the icons is what
    the callers actually need, since every one of them is about to press one.
    """
    end = time.time() + timeout
    while True:
        if scenes._current_scene(altdriver) == scene_names.MAP_SCENE and _find_level_icons(altdriver):
            # The icons exist, but the map is still arranging itself for a
            # moment longer. Every caller here is about to press one, so the
            # settle belongs in this one place rather than at each press.
            time.sleep(MAP_SETTLE_SECONDS)
            return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


def ensure_on_map(altdriver, username=None, password=None, max_rounds=4):
    """Get to the level map from WHEREVER the app currently is.

    A generated test can start anywhere: on the map, on the start screen, deep
    inside an activity, on a feedback popup, or logged out. Rather than assume,
    this escalates one step at a time:

      1. level icons visible          -> done
      2. login screen                 -> log in (needs credentials)
      3. start screen (GO-Map)        -> press it
      4. anywhere else                -> press back/close one screen at a time
                                         (``return_to_map``)
      5. still stuck                  -> keep backing out to the START screen
                                         (``return_to_start``), then GO-Map
      6. still stuck, creds available -> log out and back in

    Returns True when the map is showing. Never raises.
    """
    for rnd in range(max_rounds):
        if _find_level_icons(altdriver):
            return True

        if scenes._login_screen_visible(altdriver):
            if not username:
                logging.error("[Map Navigation] On the login screen and no credentials given.")
                return False
            logging.info("[Map Navigation] On the login screen — logging in")
            login_session.login(altdriver, username, password)
            time.sleep(2)
            continue

        if scenes._current_scene(altdriver) == scene_names.START_SCENE or ui_actions.find_element(altdriver, "GO-Map") is not None:
            logging.info("[Map Navigation] On the start screen — clicking GO-Map")
            ui_actions.click_by_name(altdriver, "GO-Map")
            time.sleep(12)              # the map scene takes a while to load
            continue

        # Somewhere inside a level/activity/exam: walk out like a user.
        logging.info(f"[Map Navigation] Not on the map (round {rnd + 1}) — backing out")
        if return_to_map(altdriver):
            return True

        # Keep going back: the start screen is always reachable that way, and
        # GO-Map from there is a known-good route to the map.
        if login_session.return_to_start(altdriver):
            logging.info("[Map Navigation] At the start screen — clicking GO-Map")
            ui_actions.click_by_name(altdriver, "GO-Map")
            time.sleep(12)
            continue

        # Last resort: a clean session beats a stuck screen.
        if username:
            logging.warning("[Map Navigation] Still stuck — logging out and back in")
            try:
                ui_actions.call_method(altdriver, "AltTesterUtils", "Logout")
                time.sleep(3)
            except Exception as e:
                logging.warning(f"[Map Navigation] Logout failed: {e}")
            login_session._LAST_LOGIN_USER = None      # force a real login next time
            login_session.login(altdriver, username, password)
            time.sleep(2)

    ok = bool(_find_level_icons(altdriver))
    if not ok:
        try:
            scene = altdriver.get_current_scene()
        except Exception:
            scene = "unknown"
        logging.error(f"[Map Navigation] Could not reach the map (scene: {scene}).")
    return ok


def enter_level_number(altdriver, level_num, retries=3, username=None, password=None):
    """Open the map level labelled ``level_num``, from wherever the app is.

    Navigation is self-recovering: ``ensure_on_map`` first walks the app back to
    the map (backing out of an activity, or logging in again if the session
    dropped), then the icon is picked BY NAME — icons are named after the level
    they open, so no counting. The 0-based index is kept as a fallback for
    builds whose icons aren't named that way (label N is index N-1).
    """
    logging.info(f"[Map Navigation] Entering level number {level_num}")
    try:
        if not ensure_on_map(altdriver, username=username, password=password,
                             max_rounds=max(retries, 2)):
            return False

        obj, name, kind = _level_icon_by_number(altdriver, level_num)
        if obj is not None:
            obj.click()
            time.sleep(4)
            logging.info(f"[Map Navigation] Entered level {level_num} "
                         f"({kind} level, icon '{name}').")
            return True

        level_objs = _find_level_icons(altdriver)
        index = level_num - 1          # label 44 -> icon index 43
        if index < 0 or index >= len(level_objs):
            logging.error(f"[Map Navigation] Level {level_num} out of range ({len(level_objs)} icons).")
            return False
        level_objs[index].click()
        time.sleep(4)
        logging.info(f"[Map Navigation] Entered level {level_num} (icon index {index}).")
        return True
    except Exception as e:
        logging.error(f"[Map Navigation] Exception clicking level {level_num}: {e}")
        return False


def open_level_to_activities(altdriver, timeout=90):
    """From a just-clicked level, reach ActivitySelectionScene.

    Same route as handle_level_flow — an already-opened level goes straight to
    the activity selection, a level opened for the FIRST time shows the intro
    (nextButton) and then the vending machine (Toggle) — but driven as a loop
    instead of one shot per step. That matters for a not-yet-opened level: the
    intro can be more than one page, and both the vending scene and the
    selection screen take several seconds to load, so a single "click next,
    look once" pass gets stuck on whatever is still loading.

    Never raises (click_by_name swallows misses); returns True once the
    activity selection screen is showing.
    """
    deadline = time.time() + timeout
    last_scene = object()          # sentinel: log the first scene we see
    while time.time() < deadline:
        try:
            scene = altdriver.get_current_scene()
        except Exception as e:     # scene swap in progress
            logging.debug(f"[Level Flow] get_current_scene failed: {e}")
            scene = None

        if scene == 'ActivitySelectionScene':
            return True
        if scene != last_scene:
            logging.info(f"[Level Flow] on '{scene}' — opening the level")
            last_scene = scene

        if scene == 'VendingMachineScene':
            # First visit to a level: pick a prize to get past the machine.
            ui_actions.click_by_name(altdriver, "Toggle")
            time.sleep(12)
            continue

        # Level intro: keep pressing next for as long as one is on screen.
        if ui_actions.find_element(altdriver, "nextButton") is not None:
            ui_actions.click_by_name(altdriver, "nextButton")
            time.sleep(3)
            continue

        time.sleep(2)              # still loading — look again

    try:
        now = altdriver.get_current_scene()
    except Exception:
        now = "unknown"
    logging.error(f"[Level Flow] ActivitySelectionScene not reached in {timeout}s (now: {now})")
    return False


# Buttons a real user presses to leave a screen, most specific first: the
# activity/feedback exit ("prev"), close/X popups, "Exit" (how Settings and the
# location popup are closed — matched EXACTLY so it can never hit the start
# screen's ExitButton_1, which quits the app), generic back, then the home
# screen's GO-Map. Whichever exists on the current screen gets clicked.
_BACK_BUTTON_NAMES = ("prev", "X", "x", "CloseButton", "close", "Close", "Exit",
                      "BackButton", "backButton", "Back", "HomeButton", "GO-Map",
                      # Last resort: the word list has no back/close at all —
                      # "next" is how you leave it (same button that carries the
                      # level intro forward). Tried only when nothing else fits,
                      # so it can't skip a step on a screen that has a real back.
                      "nextButton")


def return_to_map(altdriver, max_steps=8):
    """Clean state between chained test cases: go back to the level map.

    Navigates the way a user would — pressing back / close (X) / home buttons
    one screen at a time — until the map's level icons are visible. No direct
    scene loading. Never raises; the next test's enter_level_number can still
    self-recover.
    """
    for step in range(max_steps):
        if _find_level_icons(altdriver):
            logging.info("[Map Navigation] Back on the map.")
            return True
        clicked = None
        for name in _BACK_BUTTON_NAMES:
            try:
                obj = altdriver.find_object(By.NAME, name)
            except Exception:
                continue
            try:
                obj.click()
                clicked = name
                break
            except Exception:
                continue
        if clicked:
            logging.info(f"[Map Navigation] step {step + 1}: clicked '{clicked}'")
        else:
            logging.warning(f"[Map Navigation] step {step + 1}: no back/close/home button found")
        time.sleep(4)
    if _find_level_icons(altdriver):
        logging.info("[Map Navigation] Back on the map.")
        return True
    logging.warning("[Map Navigation] Map not reached; continuing anyway.")
    return False
