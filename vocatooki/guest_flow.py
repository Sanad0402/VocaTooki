"""The guest (free trial) flow: onboarding wizard, level walk, exam, subscribe gate.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import re
import time
from alttester import By

from vocatooki import activity_runner, evidence_screenshots, exam_solver, instructions_parrot, login_session, map_navigation, scene_names, scenes, ui_actions


# ---------------------------------------------------------------------------
# Guest flow ("Start FREE trial") — no account, no login
# ---------------------------------------------------------------------------
# Walked end to end against the live app on 2026-08-13 through the AltTester
# CLI. Every control here is addressed BY OBJECT NAME or by the TEXT it prints —
# never by screen coordinates, which stop landing on the control as soon as the
# resolution or the layout changes.
#
# Three things make this flow unlike the rest of the app:
#
# 1. The entry only EXISTS while nobody is logged in. During a live session
#    "Free Trial" and "PlayAsGuest" are disabled and off-screen, so a guest test
#    has to log the current user out through the UI first
#    (LogoutButton -> YesNoPopup(Clone) -> YesButton).
# 2. The onboarding asks its questions in a DIFFERENT ORDER from the Rally case:
#    child's name -> gender (Toggle/Toggle_1) -> native language -> English
#    level. So the wizard is walked by matching each screen against the labels
#    still outstanding rather than by assuming a fixed order.
# 3. Gender is asked a SECOND time after the wizard, as GenderSelectPopup(Clone)
#    on the hub, whose options are plain objects named "Male" and "Female".
#
# Nothing in this section calls login(), ensure_logged_in() or
# AltTesterUtils.Logout: a guest has no credentials, so a session torn down
# mid-test cannot be recreated.

# Object names read off the live app (scene NewStartScene, 2026-08-13).
GUEST_ENTRY = {
    "trial":        "Free Trial",            # yellow "Start FREE trial"
    "lets_start":   "Button",                # "Let's Start" on the Welcome panel
    "first_name":   "InputField - RTLTMP",   # "What is your child's name?" (top)
    "last_name":    "InputField - RTLTMP_1",
    "next":         "Button_2",
    "prev":         "Button_1",
    "gender_popup": "GenderSelectPopup(Clone)",
}


# The parrot's question at the top of every wizard screen ("Choose your native
# language"). It changes on every step, which makes it the proof Next advanced.
GUEST_PROMPT = "TookiCloudText"


# Objects that prove the logged-out welcome screen is up.
GUEST_WELCOME_MARKERS = ("Free Trial", "SignUpButton")


# The wizard's option rows are Toggle, Toggle_1, Toggle_2, ... in screen order.
GUEST_TOGGLE_PREFIX = "Toggle"


# The hub popup's gender BUTTONS are still named Male/Female.
GUEST_GENDERS = ("Male", "Female")


# How the wizard PRINTS each gender. 4.6.0 asks "Hello <name>, you are a:" and
# offers "Boy" / "Girl" (measured live 2026-09-14); earlier builds printed
# "Male" / "Female". A case keeps saying "Male" and is understood on either.
GUEST_GENDER_LABELS = {"male": ("Male", "Boy"), "female": ("Female", "Girl")}


def _option_labels(label):
    """Every printed spelling a case's option can take on a wizard screen."""
    label = (label or "").strip()
    return GUEST_GENDER_LABELS.get(label.lower(), (label,) if label else ())


def _norm_label(text):
    """A printed label reduced for comparison: no rich-text tags, one space, lower."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip().lower()


def guest_entry_available(altdriver):
    """True when the logged-out welcome screen with the trial entry is showing."""
    return ui_actions.find_any(altdriver, GUEST_ENTRY["trial"]) is not None


def _guest_toggles(altdriver, limit=12):
    """The option toggles VISIBLE on the current wizard screen, in screen order.

    Every name is looked up in full and only on-screen matches are kept: the
    start scene has other active objects called "Toggle" (the welcome carousel's
    page dots), and a first-match lookup can hand back one of those instead.
    """
    found = []
    for i in range(limit):
        name = GUEST_TOGGLE_PREFIX if i == 0 else f"{GUEST_TOGGLE_PREFIX}_{i}"
        try:
            objs = altdriver.find_objects(By.NAME, name)
        except Exception:                            # noqa: BLE001
            objs = []
        for obj in objs:
            if ui_actions.is_on_screen(altdriver, obj):
                found.append((name, obj))
                break
    return found


def _toggle_is_on(toggle_obj):
    """True/False from the toggle's own ``isOn``, or None when it cannot be read."""
    try:
        value = toggle_obj.get_component_property("UnityEngine.UI.Toggle", "isOn",
                                                  "UnityEngine.UI")
    except Exception:                                # noqa: BLE001
        return None
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


# --- the wizard's SCROLL PICKER (native language, English level) -----------
# These screens are NOT lists of buttons. The option that sits between the two
# guide lines IS the selection, and the only way to change it is to DRAG the
# list: the mouse wheel does nothing, and a press does nothing either. Worse,
# every option exists in the hierarchy even while it is off screen, so
# find-by-text "succeeds" on a row that is nowhere near the viewport and a
# press on it reports success. That is exactly how a Turkish case registered an
# Arabic guest and still PASSED — Arabic is simply what the picker starts on.
#
# Everything below is measured from the LIVE app on every call — the band from
# the line objects, the row position from the row itself, the travel limits
# from the reported screen size. No pixel constant, no assumed resolution, and
# no coordinate is ever typed in: the drag is computed from where the app says
# its own objects are.
GUEST_PICKER_LINE_TOP = "LineTop"


GUEST_PICKER_LINE_BOTTOM = "LineBottom"


def picker_band(altdriver):
    """``(low_y, high_y)`` of the picker's selection band, or None.

    None means this screen is not a picker (the gender screen, for instance),
    which is the signal to fall back to pressing a toggle.
    """
    top = ui_actions.find_any(altdriver, GUEST_PICKER_LINE_TOP)
    bottom = ui_actions.find_any(altdriver, GUEST_PICKER_LINE_BOTTOM)
    if top is None or bottom is None:
        return None
    try:
        low, high = sorted((float(bottom.y), float(top.y)))
    except (TypeError, ValueError):
        return None
    return (low, high) if high > low else None


def _drag_picker(altdriver, x, delta, duration=0.5):
    """Drag the picker list by ``delta`` screen units. Returns what was asked.

    The gesture stays inside the app's own reported screen, with a margin taken
    as a FRACTION of the height, so it holds at any resolution. A drag that
    cannot cover the whole distance in one go covers what it can — the caller
    re-measures and goes again.
    """
    try:
        _width, height = altdriver.get_application_screensize()
        height = float(height)
    except Exception as e:                          # noqa: BLE001
        logging.error(f"[Guest] could not read the screen size: {e}")
        return 0.0

    margin = height * 0.12                          # keep clear of the edges
    lo, hi = margin, height - margin
    if hi <= lo:
        return 0.0
    start = min(max(height / 2.0 - delta / 2.0, lo), hi)
    end = min(max(start + delta, lo), hi)
    start = min(max(end - delta, lo), hi)           # keep the full span if it fits
    if abs(end - start) < 1:
        return 0.0
    try:
        altdriver.swipe({"x": x, "y": start}, {"x": x, "y": end}, duration=duration)
    except Exception as e:                          # noqa: BLE001
        logging.error(f"[Guest] could not drag the option list: {e}")
        return 0.0
    return end - start


def _row_position(altdriver, label):
    """``(x, y)`` of the row printing ``label`` once it has STOPPED moving.

    The list glides and snaps after a drag. A position read mid-glide can still
    be carried past the band, so "it is between the lines" is only meaningful
    once two consecutive readings agree — otherwise the run would accept a row
    that ends up settling one place further on.
    """
    prev = None
    for _ in range(8):
        row = ui_actions._find_by_text(altdriver, label)
        if row is None:
            return None
        try:
            x, y = float(row.x), float(row.y)
        except (TypeError, ValueError):
            return None
        if prev is not None and abs(y - prev) < 1.0:
            return x, y
        prev = y
        time.sleep(0.25)
    return (x, y) if prev is not None else None


def scroll_option_into_band(altdriver, label, attempts=12):
    """Drag the picker until ``label`` sits between the lines. Returns bool.

    Landing in the band IS selecting: the picker snaps the nearest row to the
    centre and the app reads whatever is there when Next is pressed. Every
    position is taken from a list that has come to rest.
    """
    for attempt in range(attempts):
        band = picker_band(altdriver)
        if band is None:
            return False
        low, high = band
        at = _row_position(altdriver, label)
        if at is None:
            return False
        x, y = at
        if low <= y <= high:
            logging.info(f"[Guest] '{label}' is in the selection band "
                         f"(y={y:.0f} in [{low:.0f},{high:.0f}])")
            return True

        if not _drag_picker(altdriver, x, (low + high) / 2.0 - y):
            logging.error(f"[Guest] could not drag towards '{label}'")
            return False

        # A drag that changes nothing means the list is at its end, or the
        # gesture is not reaching it — stop instead of spinning.
        after = _row_position(altdriver, label)
        if after is None:
            return False
        if abs(after[1] - y) < 1.0:
            logging.error(f"[Guest] the list did not move towards '{label}' "
                          f"(still y={y:.0f}) on attempt {attempt + 1}")
            return False
    logging.error(f"[Guest] '{label}' never reached the selection band")
    return False


def _select_visible_option(altdriver, label, settle=1.0):
    """Choose ``label`` on the current wizard screen, and PROVE it took.

    A picker screen is driven by dragging (the band decides); every other
    screen is driven by pressing its toggle. Never reports success for a press
    that cannot have selected anything.
    """
    if picker_band(altdriver) is not None:
        # The picker is the native-language list. A gender or an English level
        # is never one of its rows, and trying one would drag the list towards
        # a label printed on some other (hidden) panel.
        low = (label or "").strip().lower()
        if low in GUEST_GENDER_LABELS or low.endswith(("literacy", "proficiency")):
            return False
        return scroll_option_into_band(altdriver, label)

    # A toggle screen (gender, English level). NOT done by pressing a label
    # found by text: every wizard panel stays alive in the hierarchy, so on the
    # gender screen "Hebrew" and "Beginning Literacy" both answer a find, the
    # press "succeeds" on a row nobody can see, and the wizard moves on with no
    # gender chosen — how TC1174 and TC1172 drifted off the wizard on 4.6.0
    # (2026-09-13/14). Only a visible toggle whose label matches EXACTLY is
    # pressed ("male" is inside "female"), and it must then read isOn.
    wants = {_norm_label(w) for w in _option_labels(label)}
    toggles = _guest_toggles(altdriver)
    if not wants or not toggles:
        return False

    target = next(((n, o) for n, o in toggles
                   if _norm_label(ui_actions.toggle_label(altdriver, o)) in wants), None)
    if target is None:
        # The label is printed BESIDE its toggle rather than inside it (the
        # 4.6.0 gender screen): take the toggle nearest the visible label.
        for spelling in _option_labels(label):
            text_obj = ui_actions._visible_text_object(altdriver, spelling)
            if text_obj is not None:
                target = min(toggles, key=lambda t: (float(t[1].x) - float(text_obj.x)) ** 2
                             + (float(t[1].y) - float(text_obj.y)) ** 2)
                break
    if target is None:
        return False

    name, obj = target
    if not ui_actions._press(obj):
        return False
    time.sleep(settle)
    on = _toggle_is_on(obj)
    if on is not True:
        logging.error(f"[Guest] pressed {name} for '{label}' but it is "
                      + ("not on" if on is False else "unreadable (isOn)"))
        return False
    logging.info(f"[Guest] option '{label}' -> {name} (on)")
    return True


def _guest_screen_offers(altdriver):
    """What the current wizard screen asks and offers, for a failure message."""
    prompt = ""
    obj = ui_actions.find_any(altdriver, GUEST_PROMPT)
    if obj is not None:
        try:
            prompt = re.sub(r"<[^>]+>", "", obj.get_text() or "").strip()
        except Exception:                            # noqa: BLE001
            prompt = ""
    labels = [ui_actions.toggle_label(altdriver, o) for _n, o in _guest_toggles(altdriver)]
    return prompt, [l for l in labels if l]


def select_guest_option(altdriver, label, settle=1.0, retries=2):
    """Pick the option matching ``label`` on the current wizard screen.

    Both kinds of screen are handled by ``_select_visible_option``: a picker is
    dragged until the row is between the guide lines, anything else has its
    toggle pressed. The retry is for a screen still building itself, not for
    hunting: the mouse wheel was measured against the live app and moves the
    picker not at all, so scrolling with it only cost ~30s per screen and
    jostled the UI.

    Never falls back to "the first option" — on a language or level screen the
    wrong pick silently changes what the rest of the test measures.
    """
    for attempt in range(max(1, retries)):
        if _select_visible_option(altdriver, label, settle=settle):
            return True
        time.sleep(0.8)
        logging.info(f"[Guest] '{label}' not selectable yet "
                     f"(attempt {attempt + 1}/{max(1, retries)})")
    logging.error(f"[Guest] '{label}' is not on this screen")
    return False


def dismiss_gender_popup(altdriver, gender="", timeout=20):
    """The post-wizard "You are" popup, whose options are named Male/Female."""
    if not ui_actions.wait_for_any(altdriver, GUEST_ENTRY["gender_popup"], timeout=timeout):
        return False
    wanted = (gender or "").strip().title()
    for name in ([wanted] if wanted in GUEST_GENDERS else []) + list(GUEST_GENDERS):
        if ui_actions.find_any(altdriver, name) is not None:
            logging.info(f"[Guest] gender popup -> {name}")
            return ui_actions.press_object(altdriver, name, settle=1.0,
                                gone=(GUEST_ENTRY["gender_popup"],))
    return False


def reset_guest_data(altdriver, timeout=45):
    """Leave the app ready for the NEXT guest run: log out, THEN clear data.

    The order matters. Clearing Unity's PlayerPrefs while a guest session is
    still live leaves that session in memory, so the next run RESUMES the old
    guest (landing straight on the hub) instead of being offered the
    registration wizard — "Start FREE trial" only registers when there is no
    guest yet. Verified live 2026-08-13: logout -> welcome screen -> clear.
    """
    ok = login_session.logout_via_ui(altdriver, timeout=timeout)
    try:
        altdriver.delete_player_pref()          # Unity "clear data"
        logging.info("[Guest] cleared Unity data (PlayerPrefs)")
    except Exception as e:                      # noqa: BLE001
        logging.error(f"[Guest] clear data failed: {e}")
        return False
    time.sleep(3)
    logging.info("[Guest] data cleared — RESTART the app before the next guest "
                 "registration: the old guest survives in memory until then")
    return ok


def enter_guest_mode(altdriver, first_name="", last_name="", options=(),
                     max_screens=8, timeout=45):
    """Register as a guest and land in the app. Never logs in.

    ``options`` are the labels this case asks for on the wizard's option screens
    ("Male", "Arabic", "Beginning Literacy") in any order: each screen is
    matched against whatever is still outstanding, so the app's own ordering
    (which differs from the Rally step order) does not matter.

    Returns ``{"ok", "failed_at", "note", "picked", "trace"}`` and never raises,
    so the calling test can assert with the whole route in the message.
    """
    trace, picked = [], []
    wanted = [o for o in options if o]
    gender = next((o for o in wanted if o.strip().title() in GUEST_GENDERS), "")

    def result(ok, failed_at="", note=""):
        return {"ok": ok, "failed_at": failed_at, "note": note,
                "picked": picked, "trace": trace}

    if not login_session.logout_via_ui(altdriver, timeout=timeout):
        return result(False, "logout", "could not reach the logged-out welcome screen")
    trace.append("welcome screen")

    # A guest already registered on this device is RESUMED rather than
    # registered, so the wizard never appears and the app lands on the hub. The
    # cure is the documented reset — log out, then clear Unity's data — after
    # which the trial entry offers registration again.
    # Confirm with a POSITIVE marker: the trial panel opens ON TOP of the login
    # panel, so "Free Trial" stays findable afterwards and its disappearance is
    # not a signal (that mistake made a working press look like a failure).
    if not ui_actions.press_object(altdriver, GUEST_ENTRY["trial"], settle=0.5,
                        expect=(GUEST_ENTRY["lets_start"],), confirm=20):
        return result(False, "trial",
                      f"'{GUEST_ENTRY['trial']}' did not open the trial flow")
    trace.append("trial entry")
    # The welcome panel needs a moment before it accepts input: its button
    # answers a find straight away but swallows a press that arrives too early.
    time.sleep(5)


    # "Let's Start" on the Welcome panel. Its object is a bare "Button", so the
    # printed label is tried too in case the panel is rebuilt or renamed.
    if not (ui_actions.press_object(altdriver, GUEST_ENTRY["lets_start"], settle=0.5,
                         expect=(GUEST_ENTRY["first_name"],), confirm=20)
            or ui_actions.press_label(altdriver, "Let's Start", settle=0.5,
                           expect=(GUEST_ENTRY["first_name"],))):
        # No name screen. Either a guest is already registered — in which case
        # the trial entry RESUMES it (the app lands in the hub/map and the wizard
        # never appears) and only a data clear plus an app RESTART brings
        # registration back — or the panel genuinely did not take the press.
        if scenes._current_scene(altdriver) == scene_names.MAP_SCENE or                 ui_actions.find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
            return result(False, "existing_guest",
                          "the trial entry resumed a guest that is already "
                          "registered in this app session. Clear the app data, "
                          "RESTART the app, then run this case again")
        return result(False, "lets_start", "the Let's Start panel did not advance")
    trace.append("Let's Start")

    # "What is your child's name?" — set_text works by name on these fields.
    if first_name or last_name:
        if not ui_actions.wait_for_any(altdriver, GUEST_ENTRY["first_name"], timeout=20):
            return result(False, "name_screen", "the name screen never appeared")
        for key, value in (("first_name", first_name), ("last_name", last_name)):
            if not value:
                continue
            field = ui_actions.find_any(altdriver, GUEST_ENTRY[key])
            if field is None:
                return result(False, key, f"'{GUEST_ENTRY[key]}' is not on the name screen")
            field.set_text(value)
            time.sleep(0.2)
        trace.append(f"name '{first_name} {last_name}'".replace("  ", " "))
        if not ui_actions.press_object(altdriver, GUEST_ENTRY["next"], settle=1.2):
            return result(False, "next_after_name", "Next did not accept the name")

    # Option screens, in whatever order this build presents them.
    for _ in range(max_screens):
        if ui_actions.find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
            break                                   # wizard over, hub popup is up
        if not ui_actions.find_any(altdriver, GUEST_ENTRY["next"]):
            break                                   # no Next -> wizard finished
        # First pass: try every outstanding label on THIS screen WITHOUT
        # scrolling. Scrolling per label cost ~30s per screen and jostled the
        # UI — on the gender screen it hunted for "Turkish" through the whole
        # scroll range before ever trying "Female".
        chosen = ""
        for label in list(wanted):
            if label.strip().title() in GUEST_GENDERS and \
                    ui_actions.find_any(altdriver, GUEST_ENTRY["gender_popup"]) is not None:
                continue                            # handled by the popup below
            if _select_visible_option(altdriver, label, settle=1.0):
                chosen = label
                break

        # Nothing on this screen matched: it may be the language list, which
        # shows only the first few of many, so now it is worth scrolling.
        if not chosen:
            for label in list(wanted):
                if select_guest_option(altdriver, label):
                    chosen = label
                    break

        prompt, offered = _guest_screen_offers(altdriver)
        if chosen:
            wanted.remove(chosen)
            picked.append(chosen)
            trace.append(f"picked '{chosen}'")
        elif offered or picker_band(altdriver) is not None:
            # An option screen that offers none of this case's answers. Pressing
            # Next anyway is what sent 4.6.0 runs off the wizard to the login
            # screen with no gender chosen — stop and say what the screen asked.
            return result(False, "options",
                          f"the '{prompt}' screen offers {offered or 'a picker'} "
                          f"but none of {wanted} could be selected")

        if not ui_actions.press_object(altdriver, GUEST_ENTRY["next"], settle=1.2):
            break
        trace.append("Next")

        # Prove the wizard moved on: the parrot's question changes on every
        # step and is gone once the last answer is in.
        moved_on = False
        deadline = time.time() + 10
        while time.time() < deadline:
            now, _ = _guest_screen_offers(altdriver)
            if now != prompt:
                moved_on = True
                break
            time.sleep(0.5)
        if not moved_on:
            return result(False, "next",
                          f"Next did not leave the '{prompt}' screen"
                          + (f" after picking '{chosen}'" if chosen else ""))

        # The English level is the last answer: the app then builds the profile
        # and hands over to the hub, which takes far longer than a screen change.
        if chosen and chosen.strip().lower().endswith(("literacy", "proficiency")):
            logging.info("[Guest] level submitted — waiting for the profile build")
            time.sleep(20)

    # The tail of the flow, as the app really plays it (walked live): the wizard
    # hands over to the hub, a SECOND gender prompt appears there, and the app
    # then drops into the avatar builder. Waiting on the popup specifically
    # matters — in_app() goes true the moment the wizard controls vanish, and
    # pressing on while a modal is still arriving means the next press hits it.
    if ui_actions.wait_for_any(altdriver, GUEST_ENTRY["gender_popup"], timeout=40):
        if dismiss_gender_popup(altdriver, gender):
            trace.append(f"gender popup '{gender or 'default'}'")
            if gender in wanted:
                wanted.remove(gender)
                picked.append(gender)
        else:
            return result(False, "gender_popup", "the You-are popup did not close")

    # Avatar customisation opens by itself; the Rally case leaves it with Back.
    if scenes.wait_for_scene(altdriver, scene_names.AVATAR_SCENE, timeout=25):
        if not ui_actions.press_object(altdriver, "BackButton", settle=1.0):
            return result(False, "avatar", "the avatar screen has no usable Back")
        trace.append("avatar screen (Back)")
        scenes.wait_for_scene(altdriver, scene_names.START_SCENE, timeout=30)

    state = scenes.app_state(altdriver)
    if not scenes.in_app(altdriver):
        return result(False, "not_in_app", f"onboarding ended on the {state} screen")
    if wanted:
        return result(False, "options", f"never offered: {wanted}")
    return result(True, note=f"guest '{first_name} {last_name}'".strip() + f" in the app ({state})")


# Scenes that are navigation, not an activity: reaching one of these after a
# thumb press means the activity did NOT open.
_GUEST_NON_ACTIVITY_SCENES = (scene_names.START_SCENE, scene_names.MAP_SCENE, scene_names.ACTIVITY_SELECTION_SCENE,
                              "WordListScene", "VendingMachineScene", "Tests")


# How long an activity is given to build itself before it is touched. An
# activity takes noticeably longer to settle than an exam page — its board
# animates in — so its instruction bubble is only pressed after this. The exam
# pages keep their own (shorter) timing, which was measured as fine.
GUEST_ACTIVITY_SETTLE_SECONDS = 6.0


def guest_open_level(altdriver, level, timeout=90):
    """From wherever we are, open ``level`` and reach its activity list.

    Returns ``(ok, note)``. Uses the icon's own name (icons carry their level
    number) and the shared level-intro walk, so a first visit that goes through
    the word list / vending machine is handled the same as a revisit.
    """
    # Reach the map the same way everything else does: _guest_back_to_map picks
    # the route for where we actually are ('Back' from the activity list,
    # 'GO-Map' from the hub) and does not report success until the level icons
    # are there AND the map has settled enough to accept a press.
    if not map_navigation._map_ready(altdriver, timeout=5) and not _guest_back_to_map(altdriver):
        return False, f"could not reach the map to open level {level}"

    icon, icon_name, kind = map_navigation._level_icon_by_number(altdriver, level)
    if icon is None:
        return False, f"level {level} has no icon on the guest's map"

    # PRESS AGAIN before failing. A press that arrives while the map is still
    # settling is swallowed silently, and one press followed by a long wait
    # spends the whole timeout on a click that never landed.
    for attempt in range(1, 4):
        logging.info(f"[Guest] opening level {level} ({kind}) via '{icon_name}'"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        ui_actions.press_object(altdriver, icon_name, settle=2.0)
        if map_navigation.open_level_to_activities(altdriver, timeout=timeout):
            return True, ""
        logging.warning(f"[Guest] level {level} did not reach its activity list "
                        f"(on {scenes._current_scene(altdriver)}) — pressing again")
        if not _guest_back_to_map(altdriver):
            break
        icon, icon_name, kind = map_navigation._level_icon_by_number(altdriver, level)
        if icon is None:
            break

    return False, (f"level {level} did not reach the activity list after 3 attempts "
                   f"(stuck on {scenes._current_scene(altdriver)})")


def guest_walk_levels(altdriver, levels=(1, 2, 3), complete_one=True, timeout=90):
    """Open each level in ``levels``, prove every activity starts, finish one.

    For each level: open it, then press every activity thumb in turn and wait
    for a real activity scene to load, checking after each that the app is
    healthy. One activity overall is played to completion with the proven
    solver. Returns a report and never raises, so the calling test can assert
    on the whole picture:

        {"ok": bool, "levels": {1: {...}}, "opened": [...],
         "completed": str, "problems": [...]}
    """
    report = {"ok": False, "levels": {}, "opened": [], "completed": "",
              "problems": []}

    for level in levels:
        entry = {"activities": [], "opened": [], "problems": []}
        report["levels"][level] = entry

        ok, note = guest_open_level(altdriver, level, timeout=timeout)
        if not ok:
            entry["problems"].append(note)
            report["problems"].append(f"level {level}: {note}")
            continue

        listed = activity_runner.list_level_activities(altdriver)
        entry["activities"] = [a["title"] or "(unlabelled)" for a in listed]
        logging.info(f"[Guest] level {level} offers {entry['activities']}")

        for idx in range(len(listed)):
            # Re-read the thumbs: coming back from an activity rebuilds the scene,
            # so the AltObjects captured earlier are stale. The THUMBS decide
            # whether the level has to be re-opened — an activity can hand back
            # to a list that does not report ACTIVITY_SELECTION_SCENE, and
            # re-entering the level in that case is pure round trip.
            if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is None:
                ok, note = guest_open_level(altdriver, level, timeout=timeout)
                if not ok:
                    entry["problems"].append(f"could not re-open level {level}: {note}")
                    break
            now = activity_runner.list_level_activities(altdriver)
            if idx >= len(now):
                break
            thumb = now[idx]["thumb"]
            title = now[idx]["title"] or f"thumb {idx + 1}"

            # THREE presses before an activity counts as "did not open". A press
            # that lands while the list is still rebuilding is swallowed, and
            # that is not the same as an activity that cannot start.
            scene = ""
            for attempt in range(1, 4):
                if attempt > 1:
                    if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is None:
                        ok, _note = guest_open_level(altdriver, level, timeout=timeout)
                        if not ok:
                            break
                    again = activity_runner.list_level_activities(altdriver)
                    if idx >= len(again):
                        break
                    thumb = again[idx]["thumb"]
                    logging.info(f"[Guest] '{title}' did not open — pressing again "
                                 f"(attempt {attempt}/3)")
                try:
                    thumb.click()
                except Exception as e:           # noqa: BLE001
                    if attempt == 3:
                        entry["problems"].append(f"{title}: thumb press failed ({e})")
                    continue

                deadline = time.time() + 40
                while time.time() < deadline:
                    current = scenes._current_scene(altdriver)
                    if current and current not in _GUEST_NON_ACTIVITY_SCENES:
                        scene = current
                        break
                    time.sleep(0.5)
                if scene:
                    break

            state, detail = scenes.app_health(altdriver)
            if state != "ok":
                problem = f"{title}: the app went {state} ({detail})"
                entry["problems"].append(problem)
                report["problems"].append(f"level {level} {problem}")
                return report                    # a crash ends the run, honestly

            if not scene:
                # Three presses spent and it never opened — photograph it.
                shot = ui_actions.capture_failure_screenshot(altdriver, f"L{level}_{title}_no_open")
                entry["problems"].append(
                    f"{title}: did not open after 3 attempts (still on "
                    f"{scenes._current_scene(altdriver)})"
                    + (f" [screenshot: {shot}]" if shot else ""))
                report["problems"].append(f"level {level} {title}: did not open")
                continue

            entry["opened"].append(f"{title} -> {scene}")
            report["opened"].append(f"L{level} {title} -> {scene}")
            logging.info(f"[Guest] level {level}: '{title}' opened as {scene}")

            # Let the activity finish building, then close the parrot's
            # instruction bubble — it sits over the board, so anything checked
            # underneath it is checked through a popup.
            time.sleep(GUEST_ACTIVITY_SETTLE_SECONDS)
            instructions_parrot.dismiss_help_popup(altdriver)

            # Now prove the activity actually DREW itself. The scene changing
            # only says the app navigated there.
            ui_ok, ui_known, ui_note = activity_runner.validate_activity_ui(altdriver, scene)
            if ui_ok:
                logging.info(f"[Guest] level {level}: '{title}' UI ok — {ui_note}")
            elif ui_known:
                shot = ui_actions.capture_failure_screenshot(altdriver, f"L{level}_{title}_no_ui")
                problem = (f"{title}: opened as {scene} but its UI never appeared "
                           f"({ui_note})" + (f" [screenshot: {shot}]" if shot else ""))
                entry["problems"].append(problem)
                report["problems"].append(f"level {level} {problem}")
            else:
                # No markers established for this activity — say so plainly
                # rather than failing the run on our own missing knowledge.
                logging.warning(f"[Guest] level {level}: '{title}' ({scene}) has no UI "
                                f"markers to check — {ui_note}")

            # Back to the activity list for the next thumb — the list, NOT the
            # map: walking out to the map costs a level re-entry per activity.
            if not activity_runner.back_to_activity_list(altdriver):
                map_navigation.return_to_map(altdriver)         # last resort, re-opens the level

        # Finish exactly one activity for the run, from this level's activity
        # list. solve_activity_in_level opens the right thumb by its printed
        # title and verifies the game registered the completion — this is the
        # path proven green live, so it is used rather than driving the solver
        # directly on an already-open activity.
        if complete_one and not report["completed"] and entry["opened"]:
            # Pick an activity this framework can actually finish: an activity
            # whose scene has no solver mapped can never be completed, and some
            # open on an intro scene ("WordsMatchingOpenningScene") that is not
            # in the map at all.
            solvers = activity_runner.get_activity_solver_map()
            candidates = []
            for line in entry["opened"]:
                a_title, _, a_scene = line.partition(" -> ")
                if a_scene in solvers:
                    candidates.append((a_title, a_scene))
            if not candidates:
                entry["problems"].append(
                    "no activity in this level has a solver mapped "
                    f"({[l for l in entry['opened']]})")
            for title, scene in candidates:
                if scenes._current_scene(altdriver) != scene_names.ACTIVITY_SELECTION_SCENE:
                    guest_open_level(altdriver, level, timeout=timeout)
                logging.info(f"[Guest] completing '{title}' ({scene}) in level {level}")
                try:
                    hint = title if not title.startswith(("(unlabelled)", "thumb ")) else None
                    # solve_activity_in_level already retries 3x internally, for
                    # every flow — don't wrap it in another loop or a run would
                    # spend nine attempts on one activity.
                    outcome = activity_runner.solve_activity_in_level(altdriver, scene, title_hint=hint)
                except Exception as e:           # noqa: BLE001
                    entry["problems"].append(f"{title}: solver raised ({str(e)[:100]})")
                    continue
                if activity_runner.activity_completed(outcome):
                    report["completed"] = (f"level {level}: {title} ({scene}) "
                                           f"{outcome.get('done')}/{outcome.get('total')}")
                    logging.info(f"[Guest] completed {report['completed']}")
                    break
                entry["problems"].append(
                    f"{title}: not completed after 3 attempts — "
                    f"found={outcome.get('found')} "
                    f"progress={outcome.get('done')}/{outcome.get('total')} "
                    f"feedback={outcome.get('feedback')}")

    every_level_opened = all(
        report["levels"].get(lv, {}).get("opened")
        and not report["levels"].get(lv, {}).get("problems")
        for lv in levels)
    report["ok"] = bool(every_level_opened and (report["completed"] or not complete_one))
    return report


# --- Guest: the first exam, and the levels a guest may not enter -----------
# A guest's accessible band is levels 1-5, the 5th being the first exam, and
# every higher level still has an icon on the map — the restriction is a STATE,
# not a missing icon, so it has to be proven behaviourally.

# What the app puts up when a guest presses something they have not paid for.
GUEST_LOCK_MARKERS = ("BuyButton", "ChoosePackage", "ChoosePlan", "LoginPopUp",
                      "Blocker", "BlockScreen", "BlockScreenWithoutClick")


# How long the map is given to settle before an exam icon is pressed.
GUEST_EXAM_SETTLE_SECONDS = 6.0


# The gate the app puts up once a guest finishes the free content: an "Image"
# panel whose message lives on a "Text - RTLTMP" object, in the component
# property ``originalText`` (get_text() returns the SHAPED/typed-out string,
# which is why reading the label gave a fragment), closed with "OKButton".
GUEST_GATE_PANEL = "Image"


GUEST_GATE_TEXT = "Text - RTLTMP"


GUEST_GATE_OK = "OKButton"


GUEST_GATE_TEXT_PROPERTY = "originalText"


# Closing the gate hands over to a second notice ("Web Purchase Unavailable"),
# whose own button is called "Button". It has to be cleared as well: it covers
# the map, so the locked-level press underneath would land on the popup.
GUEST_GATE_FOLLOWUP_OK = "Button"


def guest_subscribe_gate(altdriver, expect=(), settle=None, timeout=30, tc_id=""):
    """Wait for the post-exam subscribe gate, READ it, and close it.

    Returns ``{"shown", "text", "closed", "note"}`` and never raises, so the
    test can assert on the wording with the whole picture in the message.

    The text is read from ``originalText`` rather than the rendered label: the
    label types itself out, so reading it mid-animation returns a fragment —
    ``originalText`` is the whole string from the moment the panel exists.
    """
    result = {"shown": False, "text": "", "closed": False, "note": "",
              "followup": "", "followup_shown": False, "followup_closed": False,
              "shots": []}
    time.sleep(map_navigation.MAP_SETTLE_SECONDS if settle is None else settle)

    if not ui_actions.wait_for_any(altdriver, (GUEST_GATE_OK, GUEST_GATE_PANEL), timeout=timeout):
        result["note"] = (f"no subscribe gate appeared within {timeout}s "
                          f"(looked for '{GUEST_GATE_OK}' / '{GUEST_GATE_PANEL}')")
        return result
    result["shown"] = True

    # More than one object can be called "Text - RTLTMP"; take the one whose
    # text actually reads like the gate, and fall back to everything found so a
    # failure message shows what WAS on screen.
    wanted = [w.lower() for w in expect if w]
    candidates = []
    try:
        for obj in altdriver.find_objects(By.NAME, GUEST_GATE_TEXT) or []:
            text = ui_actions.component_property(obj, GUEST_GATE_TEXT_PROPERTY)
            if not text:
                try:
                    text = (obj.get_text() or "").strip()
                except Exception:                    # noqa: BLE001
                    text = ""
            if text:
                candidates.append(text)
    except Exception as e:                           # noqa: BLE001
        result["note"] = f"could not read the gate's text: {e}"

    best = next((c for c in candidates
                 if wanted and all(w in c.lower() for w in wanted)), "")
    result["text"] = best or " ".join(candidates)
    logging.info(f"[Guest] the subscribe gate says: {result['text']!r}")

    # Photograph the gate BEFORE closing it — it is gone a second later.
    shot = evidence_screenshots.capture_evidence(altdriver, "guest-gate-subscribe", tc_id=tc_id)
    if shot:
        result["shots"].append(shot)

    time.sleep(ui_actions.POPUP_CLICK_DELAY)                    # let the panel settle first
    result["closed"] = bool(ui_actions.press_object(altdriver, GUEST_GATE_OK, timeout=6, settle=1.5))
    if not result["closed"]:
        result["note"] = (result["note"] + "; " if result["note"] else "") + \
                         f"'{GUEST_GATE_OK}' did not close the gate"
        return result

    # The gate hands over to a "Web Purchase Unavailable" notice. Clear it too,
    # or the next press lands on the popup instead of the map underneath.
    if ui_actions.wait_for_any(altdriver, GUEST_GATE_FOLLOWUP_OK, timeout=8):
        result["followup_shown"] = True
        followup = ""
        try:
            for obj in altdriver.find_objects(By.NAME, GUEST_GATE_TEXT) or []:
                text = ui_actions.component_property(obj, GUEST_GATE_TEXT_PROPERTY)
                if text and len(text) > len(followup):
                    followup = text
        except Exception:                            # noqa: BLE001
            pass
        if followup:
            logging.info(f"[Guest] follow-up notice: {followup!r}")
        result["followup"] = followup
        shot = evidence_screenshots.capture_evidence(altdriver, "guest-gate-purchase-notice", tc_id=tc_id)
        if shot:
            result["shots"].append(shot)
        time.sleep(ui_actions.POPUP_CLICK_DELAY)
        result["followup_closed"] = bool(
            ui_actions.press_object(altdriver, GUEST_GATE_FOLLOWUP_OK, timeout=6, settle=1.5))
        if not result["followup_closed"]:
            result["note"] = (result["note"] + "; " if result["note"] else "") + \
                             f"the follow-up notice would not close via " \
                             f"'{GUEST_GATE_FOLLOWUP_OK}'"

    # The map with nothing in front of it: this is the frame that shows which
    # levels are actually locked, which is the point of the whole check.
    _guest_back_to_map(altdriver)
    shot = evidence_screenshots.capture_evidence(altdriver, "guest-map-after-gates", tc_id=tc_id)
    if shot:
        result["shots"].append(shot)
        logging.info(f"[Guest] map frame saved: {shot}")
    return result


def guest_clear_data_notice(tc_id=""):
    """Tell whoever is watching that the app must be reset before the next case.

    A guest run deliberately does NOT log out at the end: the registration has
    to be cleared from the device, and only a data clear plus an app restart
    does that. Logging out instead would leave the guest registered and the
    next case would resume it rather than registering its own.
    """
    banner = "=" * 72
    for line in (banner,
                 f"[Guest] {tc_id + ': ' if tc_id else ''}RUN FINISHED — the app was "
                 f"left signed in as this guest, ON PURPOSE.",
                 "[Guest] CLEAR THE APP DATA AND RESTART THE APP before the next "
                 "guest test case,",
                 "[Guest] or it will resume this guest instead of registering a new one.",
                 banner):
        logging.warning(line)
        print(line)


def _guest_back_to_map(altdriver, timeout=60):
    """Get to the map from wherever the guest is. No login, no logout.

    The route depends on WHERE the guest is. From the activity list the map is
    one 'Back' press away and there is no 'GO-Map' there at all — asking for it
    first cost ~70s per call (12s hunting the button, then 60s waiting for a
    scene change that was never coming) before the fallback pressed 'Back'
    anyway. 'GO-Map' is the hub's control, so it is used from the hub.
    """
    scene = scenes._current_scene(altdriver)
    if scene == scene_names.MAP_SCENE and map_navigation._map_ready(altdriver, timeout=15):
        return True

    if scene == scene_names.ACTIVITY_SELECTION_SCENE:
        for name in ("Back", "BackButton", "prev"):
            if ui_actions.press_object(altdriver, name, timeout=4, settle=1.0):
                if map_navigation._map_ready(altdriver, timeout=timeout):
                    return True
                break
    elif ui_actions.press_object(altdriver, "GO-Map", timeout=6, settle=10.0):
        if map_navigation._map_ready(altdriver, timeout=timeout):
            return True

    map_navigation.return_to_map(altdriver)
    return map_navigation._map_ready(altdriver, timeout=20)


def guest_first_exam_level(altdriver):
    """The lowest-numbered exam node on the map — the guest's FIRST exam.

    Which level carries the first exam is not fixed (it moves with the language
    and level the guest picked), so it is read off the map rather than assumed.
    Icons are named for the level they open, so the number comes from the name.
    Returns 0 when no exam node is on the map.
    """
    best = 0
    for obj in map_navigation._find_level_icons(altdriver) or []:
        m = re.match(r"TestLevelIcon(?:\s*Variant)?\(Clone\)\s*(\d+)",
                     getattr(obj, "name", "") or "")
        if m:
            number = int(m.group(1))
            if best == 0 or number < best:
                best = number
    if best:
        logging.info(f"[Guest] the first exam on this map is level {best}")
    else:
        logging.error("[Guest] no exam node found on the guest's map")
    return best


def guest_take_exam(altdriver, level=None, timeout=90):
    """Open the guest's exam at ``level`` and solve every page.

    An exam sits on the map like any other level but leads to the 'Tests' scene
    instead of an activity list, so it needs its own opener; from there
    ``open_exam`` and ``solve_exam_pages`` are shared with the account exam flow
    (both are login-free, so a guest can use them unchanged).

    Returns the solve_exam_pages report plus ``ok``/``note``; never raises.
    """
    if not _guest_back_to_map(altdriver):
        return {"ok": False, "note": "could not reach the map for the exam"}

    if not level:
        level = guest_first_exam_level(altdriver)
        if not level:
            return {"ok": False, "note": "no exam node on the guest's map"}

    icon, icon_name, kind = map_navigation._level_icon_by_number(altdriver, level)
    if icon is None:
        return {"ok": False, "note": f"level {level} is not on the guest's map"}
    if kind and kind != "exam":
        return {"ok": False,
                "note": f"level {level} is a '{kind}' node, not an exam — the "
                        f"guest's first exam is the one to point this at"}
    # PRESS AGAIN before failing: the exam icon can swallow a press that lands
    # while the map is still settling, and giving up on one press means a human
    # has to click it — which is exactly what happened on 2026-08-13.
    opened = False
    for attempt in range(1, 4):
        logging.info(f"[Guest] opening the exam at level {level} ('{icon_name}')"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        # Let the map finish settling before pressing. The icon answers a find
        # straight away but swallows a press that arrives while the map is
        # still arranging itself — the same trap as the trial entry.
        time.sleep(GUEST_EXAM_SETTLE_SECONDS)
        ui_actions.press_object(altdriver, icon_name, settle=2.0)
        if exam_solver.open_exam(altdriver):
            opened = True
            break
        logging.warning(f"[Guest] the exam did not open from '{icon_name}' "
                        f"(on {scenes._current_scene(altdriver)}) — pressing again")
        if not _guest_back_to_map(altdriver):
            break
        icon, icon_name, _kind = map_navigation._level_icon_by_number(altdriver, level)
        if icon is None:
            break

    if not opened:
        return {"ok": False,
                "note": f"the exam did not open after 3 attempts "
                        f"(scene {scenes._current_scene(altdriver)})"}

    report = exam_solver.solve_exam_pages(altdriver, label=f"guest exam L{level}",
                              dismiss_help=True)
    report["ok"] = bool(report.get("total")
                        and report.get("parts") == report.get("total")
                        and report.get("submitted")
                        and not report.get("problems"))
    report.setdefault("note", "")
    if not report["ok"]:
        report["note"] = (f"answered {report.get('parts')}/{report.get('total')} pages, "
                          f"submitted={report.get('submitted')}, "
                          f"problems={report.get('problems')}")
    return report


def guest_level_locked(altdriver, level=None, timeout=25):
    """Press ``level`` and prove a guest cannot get in.

    Locked levels keep their icon (a guest sees the whole map), so "the icon is
    missing" is not the check. What is: after pressing it the app must NOT leave
    the map into that level's content. A paywall/sign-up prompt appearing is
    positive evidence and is reported as such.

    Returns ``{"locked": bool, "evidence": str, "note": str}``; never raises.
    """
    if not _guest_back_to_map(altdriver):
        return {"locked": False, "evidence": "",
                "note": "could not reach the map to test the lock"}

    if not level:
        # The band ends at the first exam, so the level after it is the first
        # one a guest must not be able to enter.
        first_exam = guest_first_exam_level(altdriver)
        if not first_exam:
            return {"locked": False, "evidence": "",
                    "note": "no exam node on the map to measure the band from"}
        level = first_exam + 1

    icon, icon_name, _kind = map_navigation._level_icon_by_number(altdriver, level)
    if icon is None:
        return {"locked": False, "evidence": "",
                "note": f"level {level} has no icon on the map to press"}

    logging.info(f"[Guest] checking level {level} is locked ('{icon_name}')")
    # This press follows the exam being submitted and the app returning to the
    # map, which is the least settled the map ever is — the score/collect
    # animation is still unwinding. A press that lands in that window is
    # swallowed, and a swallowed press looks exactly like a locked level: the
    # app stays on the map, so the check would PASS without ever testing it.
    time.sleep(map_navigation.MAP_SETTLE_SECONDS)
    ui_actions.press_object(altdriver, icon_name, settle=2.0)

    deadline = time.time() + timeout
    while time.time() < deadline:
        scene = scenes._current_scene(altdriver)
        if scene and scene != scene_names.MAP_SCENE:
            return {"locked": False, "evidence": scene,
                    "note": f"level {level} opened into '{scene}' — a guest got in"}
        for marker in GUEST_LOCK_MARKERS:
            if ui_actions.find_any(altdriver, marker) is not None:
                shown = ui_actions.popup_text(altdriver)
                logging.info(f"[Guest] level {level} is gated by '{marker}'")
                logging.info(f"[Guest] the gate says: {shown!r}")
                return {"locked": True, "evidence": marker, "text": shown,
                        "note": f"level {level} put up '{marker}' instead of opening"}
        if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is not None:
            return {"locked": False, "evidence": scene_names.ACTIVITY_SELECTION_SCENE_MARKER,
                    "text": "",
                    "note": f"level {level} reached its activity list — a guest got in"}
        time.sleep(1)

    # No known marker, but the app never left the map. The subscribe prompt is
    # itself the proof, so read whatever is on screen and report it: the wording
    # is what the test asserts, and it is logged even when nothing matched so a
    # renamed popup can be seen instead of guessed at.
    shown = ui_actions.popup_text(altdriver)
    logging.info(f"[Guest] level {level} stayed on the map; screen says: {shown!r}")
    return {"locked": True, "evidence": "stayed on the map", "text": shown,
            "note": f"level {level} did not open within {timeout}s"}
