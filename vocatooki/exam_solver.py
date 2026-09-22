"""Opening exams, recognising each exam page type, solving and submitting them.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import time
from alttester import By

from vocatooki import activity_runner, instructions_parrot, map_navigation, ui_actions


# How long to let an exam page finish appearing before reading its type.
EXAM_APPEAR_SETTLE_SECONDS = 3.0


# The results screen that proves a submit was ACCEPTED. Its "Collect" button is
# what the run presses to bank the score, so its presence is the observable
# difference between "submitted" and "the app ignored the submit because
# something was still unanswered".
EXAM_RESULT_MARKERS = ("Collect", "CollectButton", "ResultPanel", "ScorePanel")


def detect_exam_type_settled(altdriver, tries=6, pause=0.5):
    """The page's type, once the page has STOPPED changing into it.

    A page is built in pieces, and the first widget to exist decides the answer
    — that is how a page was solved with ``exam_swap_letters`` in the very
    second the exam icon was pressed. Two agreeing reads mean the page is
    really that type, not merely part-way to being it.
    """
    previous = ""
    for _ in range(tries):
        current = detect_exam_type(altdriver)
        if current and current == previous:
            return current
        previous = current
        time.sleep(pause)
    return previous


def detect_exam_type(altdriver):
    """Detect active exam type based on UI elements.

    Called per PAGE, not per exam: the pages of one exam are usually different
    types, and a given type can appear on any page.
    """
    # Rows of scrambled letters; drag one onto another to swap them.
    if altdriver.find_objects(By.NAME, "SwapLetterText(Clone)"):
        return "swap_letters"
    # Sentences with blanks; drag each word from the bank into its blank.
    if altdriver.find_objects(By.NAME, "WordInShuffledContext(Clone)"):
        return "shuffled_context"
    if altdriver.find_objects(By.NAME, "SpellingInputField"):
        return "spelling"
    if altdriver.find_objects(By.NAME, "LetterTestPanel(Clone)"):
        return "audio_letter"
    if altdriver.find_objects(By.NAME, "LetterWordText Variant(Clone)"):
        return "letter_to_word"
    if altdriver.find_objects(By.NAME, "MatchShapeImage(Clone)"):
        return "word_to_image"
    if altdriver.find_objects(By.NAME, "WordAudioShape(Clone)"):
        return "audio"
    if altdriver.find_objects(By.NAME, "WordMeaningShape(Clone)"):
        return "meaning"
    if altdriver.find_objects(By.NAME, "FillWord(Clone)"):
        return "spelling"
    if altdriver.find_objects(By.NAME, "Context"):
        return "context"
    if altdriver.find_objects(By.NAME, "QuestionTemplate(Clone)"):
        return "image_4_voices"
    if altdriver.find_objects(By.NAME, "ImageAudioShape(Clone)"):
        return "audio_to_image"

    return "unknown"


def open_exam(altdriver, timeout=60):
    """From a just-clicked exam level on the map, wait until the exam is showing.

    Same idea as ``open_level_to_activities`` but for an exam node: press
    through whatever intro the level shows and return once the exam pages are
    up (``TestNumText`` is the "1/3" counter). Never raises.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ui_actions.find_element(altdriver, "TestNumText") is not None:
            # The counter shows before the page's widgets are built. Solving
            # immediately reads the type off a half-built page and runs the
            # WRONG solver (seen live: 'swap_letters' picked in the same second
            # the exam icon was pressed), so let the page appear properly.
            time.sleep(EXAM_APPEAR_SETTLE_SECONDS)
            return True
        if ui_actions.find_element(altdriver, "nextButton") is not None:
            ui_actions.click_by_name(altdriver, "nextButton")
            time.sleep(3)
            continue
        time.sleep(2)
    try:
        now = altdriver.get_current_scene()
    except Exception:
        now = "unknown"
    logging.error(f"[Exam] exam pages not reached in {timeout}s (scene: {now})")
    return False


def solve_exam_pages(altdriver, label="", dismiss_help=False):
    """Solve the 3 pages of an exam that is ALREADY open, and submit it.

    Split out of ``solve_exam`` so a test can navigate to the exam its own way
    (e.g. a Rally case that names a map level) and still reuse the proven
    per-page detection and solvers.

    ``dismiss_help`` closes the parrot's instruction bubble once per page. It is
    OFF by default and switched on only by the guest flow: a logged-in user does
    not get that popup, and pressing 'HelpButton' where no bubble is showing
    would OPEN one right over the controls the solver needs.

    Returns ``{"parts": int, "problems": [str], "submitted": bool}`` and never
    raises: a caller that fails on ``problems`` leaves the app on the screen
    that broke, so the failure screenshot shows it.
    """
    from Activities import activitiesDemo as A  # local import breaks circulars

    def next_test():
        ui_actions.click_by_name(altdriver, "Next_Test")
        time.sleep(1)

    def page_number():
        """The page the exam is showing ('2/3' -> 2), or None."""
        try:
            return int((ui_actions.get_text_by_name(altdriver, "TestNumText") or "").split("/", 1)[0])
        except Exception:
            return None

    def submit_and_confirm(current, solver, attempts=3):
        """Submit the exam, and PROVE it was accepted.

        The app accepts a submit only when every question is answered: press it
        with anything still open and it simply stays on the page — the results
        screen never comes. So a submit with no results screen does NOT mean the
        button was missed, it means something is still unanswered. Solve what is
        left and submit again, rather than clicking Collect at a screen that is
        not there and reporting the exam as submitted.
        """
        for attempt in range(1, attempts + 1):
            ui_actions.click_by_name(altdriver, "SubmitButton")
            ui_actions.click_by_name(altdriver, "YesButton")
            time.sleep(1.5)
            if ui_actions.wait_for_any(altdriver, EXAM_RESULT_MARKERS, timeout=20):
                if attempt > 1:
                    logging.info(f"[Exam] submitted on attempt {attempt}")
                return True
            logging.warning(f"[Exam] the submit was not accepted "
                            f"(attempt {attempt}/{attempts}) — the exam still has "
                            f"unanswered questions; solving them and re-submitting")
            if not solver:
                break
            try:
                solver(altdriver)
            except Exception as e:                   # noqa: BLE001
                logging.error(f"[Exam] re-solve before re-submit failed: {e}")
                break
        return False

    def advance_from(current, solver, attempts=3):
        """Leave page ``current``, making sure it is FULLY answered first.

        The app will not advance a page with anything left unanswered, so a
        page that does not change is not a missed button press — it is a solver
        that thought it was done and was not (one tile left in the bank is
        enough). Running the solver again picks up what it missed; only when
        that stops helping is it a real failure.
        """
        for attempt in range(1, attempts + 1):
            next_test()
            time.sleep(1.5)
            if page_number() != current:
                return True
            logging.warning(f"[Exam] page {current} did not advance "
                            f"(attempt {attempt}/{attempts}) — it is not fully "
                            f"answered; running the solver again")
            if not solver:
                break
            try:
                solver(altdriver)
            except Exception as e:                   # noqa: BLE001
                logging.error(f"[Exam] re-solve of page {current} failed: {e}")
                break
        return page_number() != current

    exam_solvers = {
        "spelling": A.exam_spelling,
        "audio_letter": A.exams_3rd_audio_to_letter_matrix,
        "letter_to_word": A.exams_3rd_letter_to_word_image_match,
        "word_to_image": A.exams_word_to_image,
        "audio": A.exams_audio_to_meaning,
        "meaning":A.exams_word_to_meaning,
        "spelling":A.exam_spelling,
        'context':A.exam_multiple_choice,
        "image_4_voices":A.exams_image_for_voices,
        "audio_to_image":A.exams_image_to_audio,
        "swap_letters": A.exam_swap_letters,
        "shuffled_context": A.exam_shuffled_context,

    }

    problems = []          # parts that failed or couldn't be solved
    parts_seen = 0
    submitted = False

    # Start from the first page. The exam can be entered part-way through (a
    # previous attempt, or a human clicking ahead), and the loop only moves
    # forward — without rewinding, earlier pages would be submitted unanswered.
    for _ in range(6):
        try:
            page = (ui_actions.get_text_by_name(altdriver, "TestNumText") or "").strip()
            index = int(page.split("/", 1)[0])
        except Exception:
            break
        if index <= 1:
            break
        logging.info(f"[Exam] starting on page {page} — going back")
        ui_actions.click_by_name(altdriver, "Prev_Test")
        time.sleep(2)

    # The page count is whatever TestNumText says ("1/2", "1/3", ...) — exams
    # are not always 3 pages, and a page type can appear on any of them, so the
    # loop follows the counter instead of assuming a fixed list of labels.
    total_pages = 0
    seen = set()
    while True:
        try:
            label = (ui_actions.get_text_by_name(altdriver, "TestNumText") or "").strip()
            current, total_pages = (int(p) for p in label.split("/", 1))
        except Exception as e:      # exam not on screen, or an odd counter
            logging.error(f"[Exam] could not read the page counter: {e}")
            break
        if label in seen:           # Next_Test did not advance — don't loop forever
            logging.error(f"[Exam] still on page {label} after Next_Test; stopping")
            problems.append(f"page {label}: did not advance")
            break
        seen.add(label)
        parts_seen += 1

        logging.info(f"[Exam] Solving page {label}")
        # GUEST runs only: a guest's exam page opens behind the parrot's
        # instruction bubble. Close it FIRST — it types itself out, so waiting
        # for it wastes seconds a page, and it sits over the controls the solver
        # is about to use. Exactly ONE press per page: 'HelpButton' toggles the
        # bubble, so a second press would bring it back.
        if dismiss_help:
            instructions_parrot.dismiss_help_popup(altdriver)
        # Read the type only once the page has settled INTO that type.
        exam_type = detect_exam_type_settled(altdriver)
        solver = exam_solvers.get(exam_type)

        if solver:
            try:
                solver(altdriver)
                logging.info(f"[Exam] Solved page {label} using {solver.__name__}")
            except Exception as e:
                logging.error(f"[Exam] Failed on page {label} ({exam_type}): {e}")
                problems.append(f"page {label} ({exam_type}): {e}")
        else:
            logging.warning(f"[Exam] Unknown exam type on page {label}, skipping.")
            problems.append(f"page {label}: unknown exam type '{exam_type}'")

        if current < total_pages:
            if not advance_from(current, solver):
                logging.error(f"[Exam] page {label} stayed unanswered; stopping")
                shot = ui_actions.capture_failure_screenshot(altdriver, f"exam_page_{current}")
                problems.append(f"page {label}: could not be completed "
                                f"(the app would not advance past it)"
                                + (f" [screenshot: {shot}]" if shot else ""))
                break
        else:
            if submit_and_confirm(current, solver):
                ui_actions.click_by_name(altdriver, "Collect")
                time.sleep(5)
                ui_actions.click_by_name(altdriver, "BackButton")
                time.sleep(2)
                submitted = True
            else:
                shot = ui_actions.capture_failure_screenshot(altdriver, f"exam_submit_{current}")
                logging.error(f"[Exam] the exam would not submit from page {label}")
                problems.append(f"page {label}: the exam would not submit — "
                                f"questions are still unanswered"
                                + (f" [screenshot: {shot}]" if shot else ""))
            break

    # Pages that were never opened are a failure, not a silent pass: entering an
    # exam part-way through (Prev_Test does not go back) would otherwise submit
    # with the earlier pages unanswered and still report no problems.
    if total_pages and parts_seen < total_pages:
        problems.append(f"only {parts_seen}/{total_pages} pages were answered — "
                        f"the exam was entered part-way through")

    logging.info(f"[Exam] Finished {parts_seen}/{total_pages or '?'} page(s)"
                 + (f" for {label}" if label else "")
                 + (f"; problems: {problems}" if problems else ""))
    return {"parts": parts_seen, "total": total_pages,
            "problems": problems, "submitted": submitted}


def solve_exam(altdriver, class_id, lesson_num):
    """Navigate to a lesson's exam through the class map and solve it.

    Unchanged behaviour for the runner's lesson flows: raises on failure so the
    run records a FAILED row with the stuck-screen screenshot, and appends a
    PASSED row on success so the exam shows up in the report.
    """
    from datetime import datetime as _dt
    _start = _dt.now()

    map_navigation.enter_to_level(altdriver, class_id, lesson_num, type="exam")
    time.sleep(4)
    result = solve_exam_pages(altdriver, label=f"lesson {lesson_num}")

    dur = f"{int((_dt.now() - _start).total_seconds())}s"
    if result["parts"] == 0:
        raise RuntimeError(
            f"Exam lesson {lesson_num} never opened — no exam parts were found "
            f"(navigation/level issue).")
    if result["problems"]:
        raise RuntimeError(f"Exam lesson {lesson_num} failed: "
                           + " | ".join(result["problems"]))
    activity_runner.activity_report.append({
        "activity": f"Exam · lesson {lesson_num}",
        "status": "PASSED",
        "error": "",
        "duration": dur,
        "platform": getattr(altdriver, "platform", "Unknown"),
    })


def run_all_exams(altdriver, class_id):
    """
    Runs solve_exam for all lessons (0–18) in sequence.
    """
    for lesson_number in range(10, 40):  # lessons 0 to 18 inclusive
        try:
            logging.info(f"[Exam Runner] Starting exam for lesson {lesson_number}")
            solve_exam(altdriver, class_id, lesson_number)
            logging.info(f"[Exam Runner] Completed exam for lesson {lesson_number}")
            time.sleep(3)  # short pause between lessons
        except Exception as e:
            logging.error(f"[Exam Runner] Error at lesson {lesson_number}: {e}")
            continue
