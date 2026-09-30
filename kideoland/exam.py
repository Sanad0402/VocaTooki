"""A Kideo Land lesson's exam, solved by the shared exam-page solvers.

Opening: the exam map icon's own ``TestMapIcon.IconClicked()`` loads
``KideoLandTests``. From there the page loop, the per-page solvers and the
submit are Voca Tooki's ``exam_solver.solve_exam_pages`` -- the exam pages are
the same scripts in both games, and exam-page detection accepts Kideo Land's
``KL_`` prefab names.

What "passed" means here comes from the game: submitting with every question
answered marks the exam completed, and that is what unlocks the next lesson.
There is no score threshold (TestsManager.SubmitAllTests). So the proof asked
for is the submit being accepted -- and, where there is a next lesson on the
same island, that lesson unlocking.
"""

import logging
import time
from datetime import datetime

from kideoland import names, navigation
from kideoland.login import current_scene, wait_for_scene
from vocatooki import activity_runner, exam_solver, ui_actions


# How long an exam page may take to build before it counts as an unknown type.
PAGE_PATIENCE = 30.0

# An exam submitted earlier reopens as a REVIEW: every answer already placed
# with its check mark, a score stamp (a MarkPanel, "10/10") on the page and
# the submit button greyed out. Solving it again cannot work -- nothing is left
# to answer and submit never comes -- so it is recognised and left.
# TestsManager.GenerateResultOfTest builds that stamp and sets TestsSubmitted.
TESTS_MANAGER = "com.kideo.learn.english.TestsManager"
MARK_PANEL_COMPONENTS = ("com.kideo.learn.english.MarkPanel", "MarkPanel")


def already_solved(driver, timeout=8.0, poll=0.5):
    """True when the open exam is a submitted one being reviewed."""
    from alttester import By
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for manager in driver.find_objects(By.COMPONENT, TESTS_MANAGER):
                if manager.get_component_property(TESTS_MANAGER, "TestsSubmitted",
                                                  names.ASSEMBLY) is True:
                    return True
        except Exception:
            pass
        for component in MARK_PANEL_COMPONENTS:
            try:
                if driver.find_objects(By.COMPONENT, component):
                    return True
            except Exception:
                continue
        time.sleep(poll)
    return False


def leave_exam(driver):
    """Out of the exam and back on the island map, answering 'leave?' if asked."""
    for _ in range(4):
        if current_scene(driver) == names.MAP_SCENE:
            return True
        ui_actions.click_by_name(driver, "BackButton")
        time.sleep(2)
        if ui_actions.find_any(driver, "AreYouSurePanel") is not None and \
                ui_actions.find_any(driver, "YesButton") is not None:
            ui_actions.click_by_name(driver, "YesButton")
            time.sleep(2)
    return navigation.back_to_map(driver)


def solve_exam(driver, lesson_row, label):
    """Open and solve the lesson's exam; append its report row. Returns bool (submitted)."""
    started = datetime.now()
    exam_icon = lesson_row.get("exam")
    if exam_icon is None:
        raise AssertionError(f"{label}: no exam icon on the map")
    navigation.open_icon(driver, exam_icon)
    if not wait_for_scene(driver, names.TESTS_SCENE, timeout=60) or \
            not exam_solver.open_exam(driver, timeout=60):
        shot = ui_actions.capture_failure_screenshot(driver, "kl_exam_open")
        raise AssertionError(f"{label}: the exam did not open (on {current_scene(driver)})"
                             + (f" [screenshot: {shot}]" if shot else ""))

    if already_solved(driver):
        logging.info(f"[KL Exam] {label}: already solved earlier (score stamp on the page) "
                     f"-- entered, leaving it as it is")
        activity_runner.activity_frame(driver, f"exam-{label}", "already-solved")
        left = leave_exam(driver)
        activity_runner.activity_report.append({
            "activity": f"Exam · {label} (already solved)",
            "status": "PASSED" if left else "FAILED",
            "error": "" if left else f"could not leave the solved exam (on {current_scene(driver)})",
            "duration": f"{int((datetime.now() - started).total_seconds())}s",
            "platform": "Kideo Land",
            "difficulty": "Exam",
        })
        return "already_solved" if left else False

    # Kideo Land builds an exam page slowly: wait up to PAGE_PATIENCE seconds
    # for it to become a type the solvers know before calling it unknown.
    result = exam_solver.solve_exam_pages(driver, label=label, page_patience=PAGE_PATIENCE)
    duration = f"{int((datetime.now() - started).total_seconds())}s"
    ok = result["submitted"] and not result["problems"]
    activity_runner.activity_report.append({
        "activity": f"Exam · {label}",
        "status": "PASSED" if ok else "FAILED",
        "error": "" if ok else " | ".join(result["problems"]) or "the exam was not submitted",
        "duration": duration,
        "platform": "Kideo Land",
        "difficulty": "Exam",
    })
    logging.info(f"[KL Exam] {label}: {result['parts']}/{result.get('total') or '?'} pages, "
                 f"submitted={result['submitted']}")
    navigation.back_to_map(driver)
    time.sleep(2)
    return ok
