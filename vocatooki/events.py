"""Events: cards, levels, scores and the leaderboard check.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import re
import time
from alttester import By

from vocatooki import activity_runner, evidence_screenshots, lesson_modes, login_session, map_navigation, scene_names, scenes, ui_actions


# --- Events: play an event's levels and check its leaderboard --------------
# Surveyed on the live app (2026-08-16). The leaderboard is an OVERLAY on the
# event map — get_current_scene() stays "EventScene" while it is open — so
# nothing here may wait on a scene change to know it opened.
EVENT_SELECTION_SCENE = "EventSelectionScene"


EVENT_SCENE = "EventScene"


EVENT_START_BUTTON = "StartButton"          # on the active event card


EVENT_LEADERBOARD_BUTTON = "LeaderboardButton"


EVENT_LEVEL_ICON = "LessonLevelIcon Variant(Clone) {level}"


EVENT_SCORE_OBJECT = "Score"                # "80/240" on a thumb, "80" on a row


EVENT_PLAYER_NAME_OBJECT = "PlayerName"     # a leaderboard row's player


def open_event(altdriver, username=None, password=None, timeout=60):
    """Open the active event and land on its map. Returns bool.

    The event card carrying ``StartButton`` is the one that is running; the
    finished ones carry ``WinnersButton`` instead, so pressing Start can only
    ever open the live event.
    """
    if scenes._current_scene(altdriver) == EVENT_SCENE:
        return True
    if scenes._current_scene(altdriver) != EVENT_SELECTION_SCENE:
        if not map_navigation.open_feature(altdriver, "events", username, password, timeout=timeout):
            logging.error("[Event] could not open the events screen")
            return False
    if not ui_actions.press_object(altdriver, EVENT_START_BUTTON, settle=3.0):
        logging.error(f"[Event] '{EVENT_START_BUTTON}' did not respond — "
                      f"is any event actually running?")
        return False
    ok = scenes.wait_for_scene(altdriver, EVENT_SCENE, timeout=timeout)
    if ok:
        time.sleep(map_navigation.MAP_SETTLE_SECONDS)
    return ok


def event_back_to_map(altdriver, username=None, password=None, timeout=60):
    """Return to the event MAP from wherever the event left us. Returns bool.

    Back from the leaderboard lands on the event CARDS view, not the map, so
    every exit is verified and re-entered through Start when it overshoots.
    """
    for name in ("prev", "Back", "BackButton"):
        if scenes._current_scene(altdriver) == EVENT_SCENE:
            break
        if ui_actions.find_any(altdriver, name) is None:
            continue
        ui_actions.press_object(altdriver, name, settle=2.0)
        time.sleep(2)
    if scenes._current_scene(altdriver) == EVENT_SCENE:
        return True
    return open_event(altdriver, username, password, timeout=timeout)


def open_event_level(altdriver, level, timeout=90):
    """Open one event level and reach its activity list. ``(ok, note)``."""
    icon = EVENT_LEVEL_ICON.format(level=level)
    if ui_actions.find_any(altdriver, icon) is None:
        return False, f"event level {level} has no icon ('{icon}') on the map"
    for attempt in range(1, 4):
        logging.info(f"[Event] opening event level {level} via '{icon}'"
                     + (f" (attempt {attempt})" if attempt > 1 else ""))
        ui_actions.press_object(altdriver, icon, settle=2.0)
        if map_navigation.open_level_to_activities(altdriver, timeout=timeout):
            return True, ""
        logging.warning(f"[Event] level {level} did not reach its activity list "
                        f"(on {scenes._current_scene(altdriver)}) — pressing again")
        if not event_back_to_map(altdriver):
            break
    return False, (f"event level {level} did not reach its activity list "
                   f"(stuck on {scenes._current_scene(altdriver)})")


# A locked event level carries this countdown ("opens in ...") at its icon.
EVENT_LOCKED_MARKER = "NewLevelLockedTimer(Clone)"


def event_open_levels(altdriver, max_levels=24, tolerance=60):
    """The event levels that are OPEN right now, in order.

    A locked level keeps its icon like every other, so "the icon is there" says
    nothing — what marks it is a ``NewLevelLockedTimer(Clone)`` sitting at that
    icon. Levels open in sequence, so anything at or past the first locked one
    is locked too, which is also the honest fallback when no timer is found.
    """
    icons = {}
    for level in range(1, max_levels + 1):
        obj = ui_actions.find_any(altdriver, EVENT_LEVEL_ICON.format(level=level))
        if obj is None:
            continue
        try:
            icons[level] = (float(obj.x), float(obj.y))
        except (TypeError, ValueError):
            continue
    if not icons:
        return []

    locks = []
    try:
        for obj in altdriver.find_objects(By.NAME, EVENT_LOCKED_MARKER) or []:
            locks.append((float(obj.x), float(obj.y)))
    except Exception as e:                           # noqa: BLE001
        logging.debug(f"[Event] could not read the lock markers: {e}")

    open_levels = []
    for level in sorted(icons):
        x, y = icons[level]
        locked = any(abs(x - lx) < tolerance and abs(y - ly) < tolerance
                     for lx, ly in locks)
        if locked:
            break                                    # the rest are locked too
        open_levels.append(level)
    logging.info(f"[Event] open levels: {open_levels} "
                 f"(of {len(icons)} on the map, {len(locks)} locked marker(s))")
    return open_levels


def event_activity_scores(altdriver):
    """``[(earned, out_of)]`` from every Score tile on the activity screen.

    The activity list is the honest place to read a score: it shows EVERY
    activity in the level with what it scored, and it can be read at any time —
    unlike the finish screen, which is gone as soon as the run moves on.
    """
    found = []
    try:
        objects = altdriver.find_objects(By.NAME, EVENT_SCORE_OBJECT) or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not read the score tiles: {e}")
        return found
    for obj in objects:
        text = re.sub(r"[,  '\s]", "", ui_actions._text_of(obj) or "")
        match = re.match(r"(\d+)/(\d+)", text)
        if match:
            found.append((int(match.group(1)), int(match.group(2))))
    return found


def event_leaderboard(altdriver, timeout=20, tc_id=""):
    """Open the leaderboard and read it: ``[(player_name, score)]``.

    It opens as an OVERLAY, so this waits for the rows themselves rather than
    for a scene change that never comes.
    """
    rows = []
    if not ui_actions.press_object(altdriver, EVENT_LEADERBOARD_BUTTON, settle=2.0):
        logging.error(f"[Event] '{EVENT_LEADERBOARD_BUTTON}' did not respond")
        return rows
    if not ui_actions.wait_for_any(altdriver, EVENT_PLAYER_NAME_OBJECT, timeout=timeout):
        logging.warning("[Event] the leaderboard shows no players "
                        "(it reads 'No Results' until somebody scores)")
        return rows

    rows = _leaderboard_rows(altdriver)
    for name, score in rows:
        logging.info(f"[Event] leaderboard: {name!r} = {score}")
    # Keep the board itself: it is the other half of the comparison, and it is
    # gone as soon as the run closes it.
    evidence_screenshots.capture_evidence(altdriver, "event-leaderboard", tc_id=tc_id)
    return rows


EVENT_WINNERS_BUTTON = "WinnersButton"


EVENT_NO_RESULTS_TEXT = "no results"


def _leaderboard_rows(altdriver):
    """``[(player_name, score)]`` from a leaderboard/winners list on screen.

    A row is a name and a score on the SAME line, so they are paired by y
    rather than by list order — a re-sorted board would otherwise hand a name
    somebody else's score. Shared by the event leaderboard and the winners list
    of a closed event, which are the same widget.
    """
    names, scores = [], []
    try:
        for obj in altdriver.find_objects(By.NAME, EVENT_PLAYER_NAME_OBJECT) or []:
            text = ui_actions._text_of(obj)
            if text:
                names.append((float(obj.y), text))
        for obj in altdriver.find_objects(By.NAME, EVENT_SCORE_OBJECT) or []:
            value = ui_actions._score_int(ui_actions._text_of(obj))
            if value is not None:
                scores.append((float(obj.y), value))
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not read the board: {e}")
        return []

    rows = []
    for y, name in sorted(names):
        nearest = min(scores, key=lambda pair: abs(pair[0] - y), default=None)
        if nearest is not None and abs(nearest[0] - y) < 25:
            rows.append((name, nearest[1]))
    return rows


# How long an overlay is given to draw itself before it is read or left. The
# winners list fades in, and reading it too early sees neither a row nor the
# "No Results" notice (user, 2026-08-17).
OVERLAY_SETTLE_SECONDS = 4.0


def event_cards(altdriver):
    """What the events screen is showing: ``[(button_name, y)]`` per card.

    A card carries exactly ONE of ``StartButton`` (the event is running) or
    ``WinnersButton`` (it has closed), so the buttons are the cards for testing
    purposes. The card in front is the one whose button sits at the SMALLEST y.
    The titles ("RAMADAN") are artwork, not text objects, so there is nothing
    readable to identify a card by.
    """
    found = []
    for name in (EVENT_START_BUTTON, EVENT_WINNERS_BUTTON):
        try:
            for obj in altdriver.find_objects(By.NAME, name) or []:
                found.append((name, float(obj.y)))
        except Exception:                            # noqa: BLE001
            continue
    return sorted(found, key=lambda pair: pair[1])


def event_next_card(altdriver, settle=2.0):
    """Bring the next event card to the front. Returns True when it moved.

    A VERTICAL swipe cycles the stack — measured live: horizontal swipes and
    clicking a card behind both do nothing at all.
    """
    before = event_cards(altdriver)
    try:
        width, height = (float(v) for v in altdriver.get_application_screensize())
        altdriver.swipe({"x": width * 0.5, "y": height * 0.35},
                        {"x": width * 0.5, "y": height * 0.75}, duration=0.6)
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Event] could not swipe the card stack: {e}")
        return False
    time.sleep(settle)
    return event_cards(altdriver) != before


def event_cards_check(altdriver, username=None, password=None, tc_id="", timeout=60):
    """Browse every event card and open what it offers. Never raises.

    Start must open that event's MAP; Winners must open the winners list over
    the events screen ("No Results" is a real answer, not a failure — a closed
    event nobody scored in has none). Returns
    ``{"ok", "cards", "visited", "problems", "note"}``.
    """
    report = {"ok": False, "cards": 0, "visited": [], "problems": [], "note": ""}

    if username and not login_session.fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not map_navigation.open_feature(altdriver, "events", username, password, timeout=timeout):
        report["note"] = "the events screen did not open"
        return report

    evidence_screenshots.reset_evidence_trail(tc_id)
    trail = evidence_screenshots.evidence_trail(tc_id)
    trail.shot(altdriver, "events-screen", evidence_screenshots.EVIDENCE_KEY)           # the stack as it opens

    cards = event_cards(altdriver)
    report["cards"] = len(cards)
    if not cards:
        report["note"] = "no event cards on the events screen"
        return report
    logging.info(f"[Event] {len(cards)} card(s): {[n for n, _y in cards]}")

    seen = set()
    for _ in range(len(cards)):
        front = event_cards(altdriver)
        if not front:
            break
        kind, _y = front[0]                          # smallest y = the front card
        index = len(seen)

        if kind == EVENT_START_BUTTON:
            opened = ui_actions.press_object(altdriver, EVENT_START_BUTTON, settle=3.0) and \
                scenes.wait_for_scene(altdriver, EVENT_SCENE, timeout=timeout)
            time.sleep(OVERLAY_SETTLE_SECONDS)   # let the map finish drawing
            trail.shot(altdriver, f"card-{index}-Start-opened", evidence_screenshots.EVIDENCE_PROOF)
            if opened:
                report["visited"].append(f"card {index}: Start -> event map")
            else:
                report["problems"].append(
                    f"card {index}: Start did not open the event map "
                    f"(on {scenes._current_scene(altdriver)})")
            # Back out to the cards, whichever way it went.
            ui_actions.press_object(altdriver, "BackButton", settle=2.0)
            scenes.wait_for_scene(altdriver, EVENT_SELECTION_SCENE, timeout=timeout)
        else:
            ui_actions.press_object(altdriver, EVENT_WINNERS_BUTTON, settle=2.5)
            # The winners list is an OVERLAY: the scene does not change, so it
            # is recognised by its own content instead.
            shown = ui_actions.wait_for_any(altdriver, (EVENT_PLAYER_NAME_OBJECT,), timeout=8)
            # Let the panel finish drawing before reading OR leaving it.
            time.sleep(OVERLAY_SETTLE_SECONDS)
            if not shown:                            # a late row still counts
                shown = ui_actions.find_any(altdriver, EVENT_PLAYER_NAME_OBJECT) is not None
            text = " ".join(ui_actions.screen_texts(altdriver)).lower()
            empty = EVENT_NO_RESULTS_TEXT in text
            trail.shot(altdriver, f"card-{index}-Winners-opened", evidence_screenshots.EVIDENCE_PROOF)
            # Both outcomes are correct, and they mean different things: an
            # event nobody played shows "No Results", one that was played lists
            # its winners. So record WHICH, with the names and scores — a
            # report that only said "it opened" could not tell them apart.
            if shown:
                winners = _leaderboard_rows(altdriver)
                report.setdefault("winners", {})[index] = winners
                listed = ", ".join(f"{n} = {s}" for n, s in winners[:5]) or "unreadable rows"
                logging.info(f"[Event] card {index} winners: {listed}")
                report["visited"].append(
                    f"card {index}: Winners -> {len(winners)} winner(s): {listed}")
            elif empty:
                report.setdefault("winners", {})[index] = []
                report["visited"].append(
                    f"card {index}: Winners -> 'No Results' (nobody played this event)")
            else:
                report["problems"].append(
                    f"card {index}: Winners opened nothing readable — neither a "
                    f"winners row nor a 'No Results' notice")
            # The overlay adds its own BackButton; the topmost one closes it.
            backs = []
            try:
                backs = altdriver.find_objects(By.NAME, "BackButton") or []
            except Exception:                        # noqa: BLE001
                pass
            if len(backs) > 1:
                ui_actions._press(sorted(backs, key=lambda o: float(o.y))[0])
                time.sleep(2)
            else:
                ui_actions.press_object(altdriver, "BackButton", settle=2.0)

        seen.add(index)
        trail.shot(altdriver, f"card-{index}-back-on-events")   # it really came back
        if len(seen) < len(cards) and not event_next_card(altdriver):
            report["problems"].append("the card stack would not move to the next card")
            break

    report["screenshots"] = trail.names
    report["ok"] = bool(report["visited"]) and not report["problems"] \
        and len(report["visited"]) == report["cards"]
    if not report["ok"] and not report["note"]:
        report["note"] = (f"visited {len(report['visited'])} of {report['cards']} card(s); "
                          f"problems: {report['problems']}")
    return report


def event_score_check(altdriver, levels=(1, 2, 3), player_name="",
                      username=None, password=None, timeout=90, solve_all=True,
                      tc_id=""):
    """Solve one activity in each event level, then check the leaderboard.

    Returns ``{"ok", "levels", "earned", "leaderboard", "player", "note"}`` and
    never raises. ``earned`` is the sum of the scores the solved activities show
    on their own level screens; the leaderboard row for ``player_name`` must
    match it exactly — only activities award event score, exams award coins.
    """
    report = {"ok": False, "levels": {}, "earned": 0, "leaderboard": None,
              "player": player_name, "rows": [], "note": ""}

    # Start from a known account: log out, then log in. The leaderboard is
    # matched by player NAME, so running on somebody else's leftover session
    # would measure the wrong player and still look like a pass.
    if username and not login_session.fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report

    if not open_event(altdriver, username, password, timeout=timeout):
        report["note"] = "could not open the event"
        return report

    # No levels named? Then play the ones the event has actually OPENED — the
    # locked ones cannot be entered, and counting their (zero) score against the
    # leaderboard would fail a run for doing exactly what it was told.
    if not levels:
        levels = event_open_levels(altdriver)
        report["levels_played"] = list(levels)
        if not levels:
            report["note"] = "no open levels on the event map"
            return report

    solvers = activity_runner.get_activity_solver_map()
    for level in levels:
        if not event_back_to_map(altdriver, username, password):
            report["note"] = f"could not get back to the event map for level {level}"
            return report
        ok, note = open_event_level(altdriver, level, timeout=timeout)
        if not ok:
            report["levels"][level] = {"opened": False, "note": note, "score": 0}
            report["note"] = note
            return report

        before = sum(e for e, _t in event_activity_scores(altdriver))
        listed = activity_runner.list_level_activities(altdriver)
        offered = [e.get("title") or "" for e in listed]
        played, skipped, failed = [], [], []
        for title in offered:
            scene = activity_runner._infer_scene_from_title(title)
            if not scene or scene not in solvers:
                # Say which ones this framework cannot drive, rather than
                # quietly leaving their score out of the sum.
                skipped.append(title or "(unlabelled)")
                continue
            # Back to the list between activities: the previous one leaves the
            # app inside its own scene, and the next thumb lives on the list.
            if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is None:
                activity_runner.back_to_activity_list(altdriver)
            outcome = activity_runner.solve_activity_in_level(altdriver, scene, title_hint=title)
            if activity_runner.activity_completed(outcome):
                played.append(f"{title} ({scene})")
                if not solve_all:
                    break                            # one per level is enough
            else:
                failed.append(f"{title}: {outcome.get('done')}/{outcome.get('total')}")
        if ui_actions.find_any(altdriver, scene_names.ACTIVITY_SELECTION_SCENE_MARKER) is None:
            activity_runner.back_to_activity_list(altdriver)
        after = sum(e for e, _t in event_activity_scores(altdriver))
        # The activity list with its scores UPDATED — one frame per level, kept
        # whatever the per-run budget has spent, because this is the evidence
        # the leaderboard total is checked against.
        shot = evidence_screenshots.capture_evidence(altdriver, f"event-level-{level}-scores", tc_id=tc_id)
        if shot:
            report.setdefault("shots", []).append(shot)
        gained = after - before
        # Count the level's TOTAL, not what this run added. The leaderboard is
        # cumulative, so a level that was already solved still contributes its
        # score — comparing "earned today" against it would fail every re-run,
        # and would fail hardest on the very state the case is meant to check.
        report["levels"][level] = {"opened": True, "played": played,
                                   "offered": offered, "skipped": skipped,
                                   "failed": failed, "score": after,
                                   "gained": gained, "note": ""}
        report["earned"] += after
        logging.info(f"[Event] level {level}: solved {len(played)}/{len(offered)} "
                     f"{played} -> level total {after} ({gained:+d} this run)"
                     + (f"; no solver for {skipped}" if skipped else "")
                     + (f"; incomplete {failed}" if failed else ""))
        if not played:
            report["note"] = (f"level {level} offered {offered}, none of which "
                              f"this framework can complete")
            return report

    if not event_back_to_map(altdriver, username, password):
        report["note"] = "could not get back to the event map for the leaderboard"
        return report

    rows = event_leaderboard(altdriver, tc_id=tc_id)
    report.setdefault("shots", []).append(f"evidence-event-leaderboard.png")
    report["rows"] = rows
    wanted = (player_name or "").strip().lower()
    for name, score in rows:
        if wanted and " ".join(name.split()).lower() == " ".join(wanted.split()):
            report["leaderboard"] = score
            break
    if report["leaderboard"] is None:
        report["note"] = (f"'{player_name}' is not on the leaderboard — it lists "
                          f"{[n for n, _s in rows] or 'nobody'}")
        return report

    report["ok"] = report["leaderboard"] == report["earned"]
    if not report["ok"]:
        report["note"] = (f"the leaderboard says {report['leaderboard']} but the "
                          f"activities scored {report['earned']} "
                          f"({ {k: v.get('score') for k, v in report['levels'].items()} })")
    return report


def solve_event_levels(altdriver):
    """
    Solves all levels by clicking each LessonLevelIcon Variant(Clone) for each lesson and difficulty.
    Each lesson has 3 levels: easy, medium, hard.

    Args:
        altdriver (AltDriver): AltTester driver instance
    """
    # Loop through lessons 1 to 8
    for lesson_num in range(1, 9):  # Lessons 1 to 8
        logging.info(f"[solve_event_levels] Solving levels for lesson {lesson_num}")

        # Loop through each difficulty: easy, medium, hard
        for difficulty_num in range(1, 4):  # Difficulty 1 - easy, 2 - medium, 3 - hard
            level_index = (lesson_num - 1) * 3 + difficulty_num  # Calculate index for the level
            difficulty = ["easy", "medium", "hard"][difficulty_num - 1]  # Map difficulty_num to difficulty name

            logging.info(
                f"[solve_event_levels] Solving {difficulty} level for lesson {lesson_num} (Level Index: {level_index})")

            try:
                # Click on the respective LessonLevelIcon Variant(Clone) based on the level index
                level_icon = altdriver.wait_for_object(By.NAME, f"LessonLevelIcon Variant(Clone) {level_index}")
                level_icon.click()
                logging.info(f"[solve_event_levels] Clicked on level {level_index}")

                # Solve the level by calling solve_level with the corresponding difficulty
                lesson_modes.solve_level(altdriver, difficulty)

                # After solving the level, click 'Back' to go back
                back_button = altdriver.wait_for_object(By.NAME, 'Back')
                back_button.click()
                time.sleep(6)  # Wait for a few seconds before moving to the next level

            except Exception as e:
                logging.error(f"[solve_event_levels] Error solving level {level_index} for lesson {lesson_num}: {e}")
                continue  # Continue to the next level if one fails


def solve_specific_event_level(altdriver, level_index):
    """
    Solves a specific level based on the provided level index.
    This function will click the corresponding level icon and solve it.

    Args:
        altdriver (AltDriver): AltTester driver instance
        level_index (int): The index of the level to solve (1 to 24).
    """
    logging.info(f"[solve_specific_level] Solving specific level {level_index}...")

    try:
        # Click on the specific LessonLevelIcon Variant(Clone) based on the level index
        level_icon = altdriver.wait_for_object(By.NAME, f"LessonLevelIcon Variant(Clone) {level_index}")
        level_icon.click()
        logging.info(f"[solve_specific_level] Clicked on level {level_index}")

        # Determine the difficulty based on the level index:
        # 1 → easy, 2 → medium, 3 → hard, 4 → easy, 5 → medium, 6 → hard, etc.
        difficulty = ["easy", "medium", "hard"][(level_index - 1) % 3]
        lesson_modes.solve_level(altdriver, difficulty)

        # After solving the level, click 'Back' to go back
        back_button = altdriver.wait_for_object(By.NAME, 'Back')
        back_button.click()
        time.sleep(6)  # Wait for a few seconds before moving to the next level

    except Exception as e:
        logging.error(f"[solve_specific_level] Error solving level {level_index}: {e}")
        return False  # Return False in case of an error solving the level

    return True  # Return True when level is solved successfully
