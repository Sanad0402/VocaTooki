"""Treasure Island: missions, islands, buildings, and the mission check.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import random
import time
from alttester import By

from vocatooki import activity_runner, evidence_screenshots, login_session, map_navigation, scenes, ui_actions


# --- Treasure Island: missions, islands, and the buildings on them ---------
#
# Surveyed live 2026-08-17. The whole feature is reachable BY OBJECT, which is
# what makes it automatable at all (see the no-coordinate-clicks rule).
TREASURE_ISLAND_SCENE = "TreasureIsland"


TI_INTRO_SKIP = "Skip"                    # the first-entry intro's pager


TI_MISSIONS_BUTTON = "TaskSummary"        # the clipboard, top left


TI_LEVEL_TEXT = "LevelText"               # "Level 1"


TI_PERCENT_TEXT = "PercentText"           # "0%"


TI_ROW = "CategorySummaryRow(Clone)"      # one per required skill


TI_ROW_PLAY = "PlayButton"                # gone once the skill is complete


TI_PANEL_PLAY = "PlayButton"              # the SAME name on a building's panel


TI_MISSIONS_EXIT = "ExitButton"


TI_ISLAND_PREFIX = "Category_"            # Category_3-Context, ...


TI_LOCK_HOLDER = "Lock-Place_Holder"


TI_LOCK_FOG = "GO-TI-Lock_Fog"


TI_BUILDING_PREFIX = "GO-TI-"


# The mission row names a SKILL; the island object names a CATEGORY, and they
# are not always the same word — the "Sentences" row is `Category_3-Context`.
# Anything not listed here matches the island whose name ends with the skill.
TI_ISLAND_ALIASES = {"sentences": "context"}


# There is no solver for Speaking anywhere in this framework. The rule the user
# set: skip it, and SAY SO in the result — never silently ignore it.
TI_NO_AUTOMATION = ("speaking",)


# A mission slider is 0.0 .. 1.0; this is what counts as finished.
TI_COMPLETE = 0.999


# How long the building's activity panel is given to finish fading in before
# its Play is pressed, and how many times that press is repeated when the
# activity does not start. Both measured live (2026-08-17).
TI_PANEL_SETTLE_SECONDS = 3.0


TI_PLAY_ATTEMPTS = 3


def _ti_short(building):
    """`GO-TI-Break_Out Variant(Clone)` -> `Break_Out`, for a readable filename."""
    return (str(building).replace(TI_BUILDING_PREFIX, "")
            .replace(" Variant(Clone)", "").strip() or "building")


def ti_skip_intro(altdriver):
    """Press the intro's Skip when it is showing. True if it was pressed."""
    if ui_actions.find_any(altdriver, TI_INTRO_SKIP) is None:
        return False
    return ui_actions.press_object(altdriver, TI_INTRO_SKIP, settle=2.0)


def ti_open_missions(altdriver, timeout=30):
    """Open the mission list from the clipboard. True once it is readable."""
    ti_skip_intro(altdriver)
    if ui_actions.find_any(altdriver, TI_LEVEL_TEXT) is not None:
        return True                              # already open
    ui_actions.press_object(altdriver, TI_MISSIONS_BUTTON, settle=2.5)
    return ui_actions.wait_for_any(altdriver, (TI_LEVEL_TEXT,), timeout=timeout)


def ti_level(altdriver):
    """``("Level 1", "0%")`` from the open mission list."""
    level = ui_actions.find_any(altdriver, TI_LEVEL_TEXT)
    percent = ui_actions.find_any(altdriver, TI_PERCENT_TEXT)
    return (ui_actions._text_of(level) if level else "",
            ui_actions._text_of(percent) if percent else "")


def _ti_percent(text):
    """``"75%"`` -> ``75.0``. Unreadable -> ``0.0``."""
    try:
        return float(str(text).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def ti_missions(altdriver):
    """The mission rows: ``[{"index", "skill", "progress", "automatable"}]``.

    Rows are walked by INDEXED PATH rather than by scanning loose objects, so a
    skill always keeps its own progress bar even though every row uses the same
    object names.
    """
    rows = []
    try:
        found = altdriver.find_objects(By.NAME, TI_ROW) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read the mission rows: {e}")
        return rows

    for i in range(len(found)):
        skill, progress = "", None
        try:
            skill = ui_actions._text_of(altdriver.find_object(
                By.PATH, f"//{TI_ROW}[{i}]//CategoryText")) or ""
        except Exception:                            # noqa: BLE001
            pass
        try:
            slider = altdriver.find_object(
                By.PATH, f"//{TI_ROW}[{i}]//Progress//Slider")
            progress = float(slider.get_component_property(
                "UnityEngine.UI.Slider", "value", "UnityEngine.UI"))
        except Exception:                            # noqa: BLE001
            pass

        # A FINISHED skill swaps its row to the completion layer, and the
        # slider stops answering — reading that as "progress unknown" would
        # send the run off to replay a skill it had already completed.
        # A FINISHED skill's row loses its Play button, its Progress and its
        # slider outright — measured live, they stop resolving. That absence is
        # the completion signal: `completedIcon` is no use because it exists on
        # every row finished or not, and its active flag cannot be read (the
        # property raises on these objects).
        has_play = True
        try:
            altdriver.find_object(By.PATH, f"//{TI_ROW}[{i}]//{TI_ROW_PLAY}")
        except Exception:                            # noqa: BLE001
            has_play = False
        done = progress is None and not has_play
        if done:
            progress = 1.0

        rows.append({
            "index": i,
            "skill": skill,
            "progress": progress,
            "done": done,
            "automatable": skill.strip().lower() not in TI_NO_AUTOMATION,
        })
    return rows


def ti_press_row_play(altdriver, index, settle=4.0):
    """Press one mission row's Play. Rows are addressed by INDEXED PATH.

    Not ``press_object``: every row's button is called `PlayButton`, so a press
    by name would play whichever row the app hands back first.
    """
    try:
        button = altdriver.find_object(By.PATH, f"//{TI_ROW}[{index}]//PlayButton")
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] row {index} has no Play button: {e}")
        return False
    if not ui_actions._press(button):
        return False
    logging.info(f"[TI] pressed Play on row {index}")
    time.sleep(settle)
    return True


def _ti_elements(altdriver):
    """``(elements, by_id)`` for one walk of the scene tree, INACTIVE included.

    ``get_all_elements()`` defaults to ``enabled=True``, and that breaks the
    walk from a building up to its island: one inactive node in the chain and
    the walk simply stops. That is how a live run reported "Category_2-Reading
    has no buildings to play" about an island covered in them.
    """
    try:
        elements = altdriver.get_all_elements(enabled=False) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read the scene: {e}")
        return [], {}
    return elements, {e.id: e for e in elements}


def ti_island_for_skill(altdriver, skill):
    """The island object for a mission row's skill, or "".

    Play does NOT change scene — it zooms the camera — and every island's
    buildings stay findable whichever one is in front. So the island a skill
    belongs to has to be resolved by NAME here; there is no "what is on screen"
    to ask.
    """
    wanted = TI_ISLAND_ALIASES.get(skill.strip().lower(), skill.strip().lower())
    elements, _by_id = _ti_elements(altdriver)
    for element in elements:
        if not element.name.startswith(TI_ISLAND_PREFIX):
            continue
        # "Category_3-Context" -> "context"
        if element.name.split("-", 1)[-1].strip().lower() == wanted:
            return element.name
    return ""


def ti_island_locked(altdriver, island):
    """Is this island still fogged over?

    The lock is PER ISLAND (`Category_N-X/Lock-Place_Holder/GO-TI-Lock_Fog`), so
    a bare search for the fog object answers about whichever island happens to
    be locked rather than about this one.

    Measured live: the fog object EXISTS only under a locked island (Writing had
    one, the four open islands had none), so its presence is the answer and no
    active flag has to be read — which matters, because reading one off these
    objects raises.
    """
    try:
        return bool(altdriver.find_objects(By.PATH, f"//{island}//{TI_LOCK_FOG}"))
    except Exception:                                # noqa: BLE001
        return False


def ti_buildings(altdriver, island):
    """The activity buildings on one island, by object name.

    Found by PATH, under the island itself. Walking up from a building instead
    cannot work: an object's ``transformParentId`` is a TRANSFORM id while its
    ``id`` is a GameObject id, so the two never match and every island came
    back empty.

    The buildings are NAMED FOR THEIR ACTIVITY, which is the whole reason this
    is automatable: `GO-TI-Puzzles Variant(Clone)` opens the puzzles activity,
    for which a solver already exists.
    """
    try:
        found = altdriver.find_objects(By.PATH, f"//{island}//Cntrl_Resize/*") or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[TI] could not read {island}'s buildings: {e}")
        return []
    names = {obj.name for obj in found
             if obj.name.startswith(TI_BUILDING_PREFIX)
             and "Variant(Clone)" in obj.name}       # not locks, tubes or bars
    if not names:
        logging.error(f"[TI] no buildings found under '{island}'")
    return sorted(names)


def ti_play_building(altdriver, building, timeout=90, tc_id="", trail=None):
    """Open one building and play what it starts. Never raises.

    Tapping a building opens an in-scene panel (an `ActivityCard` and a single
    `PlayButton`); that Play loads the real ACTIVITY SCENE, so the framework's
    own solvers finish the job. Returns ``{"building", "activity", "played",
    "note"}``.
    """
    out = {"building": building, "activity": "", "played": False, "note": ""}

    if not ui_actions.press_object(altdriver, building, settle=3.0):
        out["note"] = f"the building '{building}' could not be pressed"
        return out
    if not ui_actions.wait_for_any(altdriver, ("PlayButton",), timeout=15):
        out["note"] = f"'{building}' opened no activity panel"
        if trail:
            trail.shot(altdriver, f"{_ti_short(building)}-no-panel", evidence_screenshots.EVIDENCE_KEY)
        return out
    if trail:
        # WHICH building was chosen, and the card it offered.
        trail.shot(altdriver, f"{_ti_short(building)}-panel")

    # The panel fades in, and a Play pressed into that animation is SWALLOWED —
    # the panel just stays open. Measured live: the very press that did nothing
    # mid-animation started the activity once the panel had settled. So the
    # press is proven by the scene leaving Treasure Island, and repeated when
    # it is not, instead of being assumed to have landed.
    time.sleep(TI_PANEL_SETTLE_SECONDS)
    started = False
    for attempt in range(1, TI_PLAY_ATTEMPTS + 1):
        ui_actions.press_object(altdriver, TI_PANEL_PLAY, settle=2.0)
        if scenes._wait_leaves_scene(altdriver, TREASURE_ISLAND_SCENE, timeout=15):
            scenes.wait_for_scene_ready(altdriver, label="activity")
            started = True
            break
        logging.warning(f"[TI] Play did not start '{building}' "
                        f"(attempt {attempt}/{TI_PLAY_ATTEMPTS}) — the panel is still up")
        time.sleep(2)
    if not started:
        out["note"] = (f"'{building}' opened its panel but Play never started the "
                       f"activity after {TI_PLAY_ATTEMPTS} presses")
        if trail:
            trail.shot(altdriver, f"{_ti_short(building)}-play-stuck", evidence_screenshots.EVIDENCE_KEY)
        else:
            evidence_screenshots.capture_evidence(altdriver, f"ti-{building}-play-stuck", tc_id=tc_id)
        return out

    # Ask WHICH activity, not for a CHANGE of activity. The scene leaving
    # Treasure Island above already proved one started, and a run plays the
    # same building twice all the time (a skill usually needs more than one go)
    # — demanding a different name then spins through every retry wait, seven
    # minutes of "scene still UNSCRAMBLE_QUIZ", and gives up on a run that was
    # working perfectly.
    activity = activity_runner._get_current_activity_with_retry(altdriver, max_attempts=6,
                                                waits=(2, 3, 5, 8, 12))
    if not activity:
        out["note"] = f"'{building}' did not start an activity"
        return out
    out["activity"] = activity
    logging.info(f"[TI] {building} started '{activity}'")

    if trail:
        trail.shot(altdriver, f"{activity}-opened")

    out["played"] = activity_runner._solve_open_activity(altdriver, activity, label=f"TI {building}")
    # The board as the solver left it — finished or not, this is the frame that
    # shows whether the activity was really played.
    if trail:
        trail.shot(altdriver,
                   f"{activity}-{'finished' if out['played'] else 'UNFINISHED'}",
                   evidence_screenshots.EVIDENCE_PROOF if out["played"] else evidence_screenshots.EVIDENCE_KEY)
    if not out["played"]:
        out["note"] = f"the '{activity}' solver did not finish it"
        if not trail:
            evidence_screenshots.capture_evidence(altdriver, f"ti-{activity}-unfinished", tc_id=tc_id)

    # Back to the island whatever happened, so the next building is reachable.
    for _ in range(4):
        if scenes._current_scene(altdriver) == TREASURE_ISLAND_SCENE:
            break
        try:
            ui_actions.call_method(altdriver, "AltTesterUtils", "LoadPreviousScene")
        except Exception:                            # noqa: BLE001
            activity_runner.when_finish_activity(altdriver)
        scenes.wait_for_scene(altdriver, TREASURE_ISLAND_SCENE, timeout=20)
    if scenes._current_scene(altdriver) != TREASURE_ISLAND_SCENE:
        out["note"] = (out["note"] + "; " if out["note"] else "") + \
            f"stuck on {scenes._current_scene(altdriver)} after the activity"
    return out


def treasure_island_check(altdriver, username=None, password=None, tc_id="",
                          max_plays=12, timeout=90):
    """Play Treasure Island's missions and watch its LEVEL. Never raises.

    Each required skill is played until its progress reads 100%, then the next;
    when the automatable ones are done the Treasure Island level must go up.
    SPEAKING is skipped — no solver exists for it — and the report says so
    rather than passing over it quietly.

    Returns ``{"ok", "level_before", "level_after", "skills", "skipped",
    "plays", "problems", "note"}``.
    """
    report = {"ok": False, "level_before": "", "level_after": "", "skills": {},
              "skipped": [], "plays": [], "problems": [], "note": ""}

    if username and not login_session.fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not map_navigation.open_feature(altdriver, "treasure island", username, password, timeout=timeout):
        report["note"] = "Treasure Island did not open"
        return report

    ti_skip_intro(altdriver)
    if not ti_open_missions(altdriver, timeout=timeout):
        report["note"] = "the mission list did not open from the clipboard"
        return report

    # ONE budget for the whole case, shared with any helper that calls
    # capture_evidence() on its own.
    evidence_screenshots.reset_evidence_trail(tc_id)
    trail = evidence_screenshots.evidence_trail(tc_id)
    report["level_before"], percent_before = ti_level(altdriver)
    missions = ti_missions(altdriver)
    if not missions:
        report["note"] = "the mission list has no rows"
        return report
    logging.info(f"[TI] {report['level_before']} ({percent_before}): "
                 f"{[(m['skill'], m['progress']) for m in missions]}")
    trail.shot(altdriver, "missions-BEFORE", evidence_screenshots.EVIDENCE_KEY)

    for mission in missions:
        skill = mission["skill"]
        report["skills"][skill] = {"before": mission["progress"], "after": mission["progress"]}
        if not mission["automatable"]:
            # Said out loud, in the result, exactly as the user asked.
            report["skipped"].append(skill)
            logging.warning(f"[TI] '{skill}' has NO automation in this framework — skipped")
            continue

    plays = 0
    for mission in [m for m in missions if m["automatable"]]:
        skill, index = mission["skill"], mission["index"]
        island = ti_island_for_skill(altdriver, skill)
        if not island:
            report["problems"].append(f"{skill}: no island object matches this skill")
            continue
        if ti_island_locked(altdriver, island):
            report["problems"].append(f"{skill}: its island ({island}) is still locked")
            continue

        while plays < max_plays:
            # Read the row from an OPEN mission list. Playing an activity closes
            # it, and rows read against a closed list come back empty — which
            # reads as "progress unknown" and sends the run round again.
            if not ti_open_missions(altdriver, timeout=timeout):
                report["problems"].append(f"{skill}: the mission list would not open")
                break
            current = next((m for m in ti_missions(altdriver) if m["index"] == index), None)
            progress = (current or {}).get("progress")
            report["skills"][skill]["after"] = progress
            # A finished skill has no Play button at all — its row swaps to the
            # completion layer — so "done" has to be believed before the run
            # tries to press one that is not there.
            if (current or {}).get("done") or (progress is not None
                                               and progress >= TI_COMPLETE):
                logging.info(f"[TI] '{skill}' is complete")
                report["skills"][skill]["after"] = 1.0
                break

            if not ti_press_row_play(altdriver, index):
                report["problems"].append(f"{skill}: its Play button could not be pressed")
                break
            # The island Play zoomed to, with its buildings.
            trail.shot(altdriver, f"{skill}-island")

            buildings = ti_buildings(altdriver, island)
            if not buildings:
                report["problems"].append(f"{skill}: {island} has no buildings to play")
                break
            # Any building on the island will do — the user's rule.
            building = random.choice(buildings)
            outcome = ti_play_building(altdriver, building, timeout=timeout,
                                       tc_id=tc_id, trail=trail)
            plays += 1
            report["plays"].append(
                f"{skill}: {outcome['building']} -> {outcome['activity'] or '?'}"
                f"{'' if outcome['played'] else ' (NOT finished: ' + outcome['note'] + ')'}")
            if not outcome["played"]:
                report["problems"].append(
                    f"{skill}: {outcome['building']} did not complete — {outcome['note']}")
                break

            # The TASK SUMMARY after every activity — the user asked for this
            # one by name. It is the proof that the activity moved the skill,
            # and the only frame that shows the mission list mid-run.
            ti_open_missions(altdriver, timeout=timeout)
            after = next((m for m in ti_missions(altdriver) if m["index"] == index), None)
            moved = (after or {}).get("progress")
            trail.shot(altdriver, f"missions-after-{skill}-{outcome['activity'] or 'play'}",
                       evidence_screenshots.EVIDENCE_PROOF)
            report["skills"][skill]["after"] = moved
            # Say what the activity was WORTH. Without this a skill that needs
            # several plays looks identical to one that is not advancing at all.
            logging.info(f"[TI] '{skill}' {progress} -> {moved} after "
                         f"{outcome['activity'] or outcome['building']}")
            if moved is not None and progress is not None and moved <= progress:
                report["problems"].append(
                    f"{skill}: finishing {outcome['activity']} left its progress at "
                    f"{moved} — an activity must raise the skill's progress")
                break

    # The point of the case: the LEVEL moves once the required skills are done.
    ti_open_missions(altdriver, timeout=timeout)
    report["level_after"], percent_after = ti_level(altdriver)
    trail.shot(altdriver, "missions-FINAL", evidence_screenshots.EVIDENCE_KEY)
    report["screenshots"] = trail.names
    logging.info(f"[TI] level {report['level_before']!r} -> {report['level_after']!r} "
                 f"({percent_before} -> {percent_after})")

    automatable = [s for s in report["skills"] if s not in report["skipped"]]
    done = [s for s in automatable
            if (report["skills"][s].get("after") or 0) >= TI_COMPLETE]
    report["completed"] = done
    report["percent_before"] = _ti_percent(percent_before)
    report["percent_after"] = _ti_percent(percent_after)
    report["level_rose"] = bool(report["level_after"]
                                and report["level_after"] != report["level_before"])

    # PASS = every skill this framework CAN play reads 100%, and the overall did
    # not go backwards.
    #
    # Deliberately NOT "the level went up". Measured live: the overall is the
    # mean of all four skills, Speaking included, so with no solver for Speaking
    # the ceiling is exactly 75% and LevelText never moves. Asserting the level
    # would fail every run for a reason no run can fix. `level_rose` is reported
    # so the day Speaking becomes automatable it can be asserted.
    #
    # ">= before" rather than "> before" on purpose: a re-run starts with the
    # skills already complete, plays nothing, and must still pass.
    report["ok"] = (bool(automatable) and len(done) == len(automatable)
                    and not report["problems"]
                    and report["percent_after"] >= report["percent_before"])

    # What was NOT automated is said in the note ALWAYS — on a pass as much as
    # on a failure. A green result that never mentions Speaking reads as though
    # every required skill was exercised, and it was not: there is no solver for
    # it in this framework. The user asked for this to be in the result.
    notes = []
    if report["skipped"]:
        notes.append(
            f"NOT AUTOMATED — no solver exists in this framework for: "
            f"{', '.join(report['skipped'])}. "
            f"{'That skill was' if len(report['skipped']) == 1 else 'Those skills were'} "
            f"skipped and NOT verified by this run.")
    notes.append(f"Completed: {', '.join(done) if done else 'no skill'}. "
                 f"Level {report['level_before'] or '?'} -> {report['level_after'] or '?'} "
                 f"({percent_before} -> {percent_after}).")
    if report["skipped"] and not report["level_rose"]:
        # Say WHY the level held, or the reader is left to assume a bug.
        notes.append(
            f"The Treasure Island level did NOT change: the overall percentage is the "
            f"mean of ALL required skills, so it cannot reach 100% while "
            f"{', '.join(report['skipped'])} has no automation "
            f"({percent_after} is the ceiling for this run).")
    if report["plays"]:
        notes.append(f"Played: {'; '.join(report['plays'])}.")
    if report["problems"]:
        notes.append(f"Problems: {report['problems']}.")
    # A note set earlier (the run never got started) is the whole story.
    report["note"] = report["note"] or " ".join(notes)
    logging.info(f"[TI] {report['note']}")
    return report
