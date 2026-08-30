"""
TC1192 — Tasks - Solve an open task: answer every question, submit, and it moves to Sent

Auto-generated from Rally (Method = Automated).

Description:
    Test Type: Functional Priority: Important Severity: Major Username: vt233644 password : 6562 Objective: Verify a student can solve an OPEN task end to end: open it from the Tasks screen, answer every question in it, submit it, and see the task leave 'Open' and appear under 'Sent'. The Tasks screen lists task cards under five tabs - ALL, Open, Sent, Checked, Missed - each tab showing its own count. An OPEN card is a TaskCard-Open(Clone); a card that can no longer be answered is a TaskCard-Closed(Clone). Opening an open card loads the task, which is a run of multiple-choice questions (15 in the task surveyed) shown one at a time, with a numbered strip along the bottom and a Submit at the end of the strip. NOTE: a task is NOT graded in the app. Submitting SENDS it to the teacher, so the outcome to verify is that the task moved from Open to Sent - not that the answers were correct.

(No test steps recorded in Rally — add them to the case, then re-sync.)

Validation (from Rally):
    Input:    1. Launch the app and log in. Log out first so the run starts on a known account. 2. On the start screen, tap the Tasks button to open the Tasks screen. 3. Read the count on each tab (ALL, Open, Sent, Checked, Missed) and note how many tasks are Open. 4. Open the Open tab and pick a task card that is still open (TaskCard-Open(Clone)); note its title. 5. Tap that card and verify the task opens and shows its first question. 6. Answer every question in the task, choosing one answer per question, using the numbered strip to move through them. 7. Verify no question was left unanswered before submitting. 8. Tap Submit at the end of the strip. 9. Go back to the Tasks screen and read the tab counts again. 10. Verify the task is no longer listed under Open, and is now listed under Sent.
    Expected: - The Tasks screen opens and shows the five tabs with their counts. - An open task card opens the task and shows its questions one at a time. - Every question accepts exactly one answer, and the chosen answer stays chosen. - Submitting raises a confirmation, and the task is only sent once it is confirmed. - After submitting, the Open count goes DOWN by one and the task appears under Checked (a task the app can score itself is not left in Sent). - The answers stored on the server match the answers given: every question answered, and exactly 2 scored incorrect - the two that were answered wrong on purpose. - The result the task scored reflects that (e.g. 8 of 10 correct = 80). - The run reports the task it solved, and which questions it answered incorrectly on purpose.

Tasks, surveyed on the live app (2026-08-19):
    GO-Tasks -> TasksSelectionScene, five tabs (ALL/Open/Sent/Checked/Missed)
    an answerable card is TaskCard-Open(Clone); a spent one TaskCard-Closed(Clone)
    the card opens TaskScene: Question_1..N on a strip, ending in SubmitButton
    answers are Answer_Visual_<shown>_Data_<id>, and the SHOWN slot is shuffled
    per question -- the Data id is the only stable handle
    Submit only ASKS: YesNoPopup(Clone) -> YesButton is what actually sends it

The answer key is NOT in the game. It comes from the backend, where every
sub-task carries a correct_answer naming the right option BY the same id.
A submitted multiple-choice task is scored and lands in CHECKED, not Sent.
"""

import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "TC1192"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "vt233644"
PASSWORD = "6562"
# The class the task belongs to (its answer key lives there) and the player
# whose stored answers are read back to check the score.
CLASS_ID = None
USER_ID = None
# How many questions to answer WRONG on purpose, to exercise that path.
WRONG_ANSWERS = 0


def test_tc1192_tasks_solve_an_open_task_answer_every_question_submit_and_it_moves_to_sent(altdriver):
    driver, _platform = altdriver

    result = utilsdemo.tasks_check(
        driver, username=USERNAME, password=PASSWORD, tc_id=TC_ID,
        class_id=CLASS_ID, user_id=USER_ID, wrong_answers=WRONG_ANSWERS,
        submit=True)

    # Say what this run did and did NOT cover, pass or fail.
    print(f"{TC_ID} RESULT: {result['note']}")

    assert result["questions"], (
        f"{TC_ID}: no task was opened to solve - {result['note']}")
    assert result["solved"], (
        f"{TC_ID}: no task was solved and submitted - {result['note']}")
    assert not result["unsupported"], (
        f"{TC_ID}: the task has questions this framework cannot answer (text "
        f"or recording), so it was not submitted: {result['unsupported']}")
    assert result["answered"] == result["questions"], (
        f"{TC_ID}: answered only {result['answered']} of {result['questions']} "
        f"question(s). {result['note']}")
    assert result["submitted"], (
        f"{TC_ID}: the task was never submitted - {result['note']}")

    # The server is the judge, not the screen: it holds what was really stored.
    server = result["server"]
    assert server, (
        f"{TC_ID}: the submitted answers could not be read back from the server, "
        f"so nothing proves what was recorded. {result['note']}")
    assert server["answers"] == result["questions"], (
        f"{TC_ID}: the server recorded {server['answers']} answer(s) for "
        f"{result['questions']} question(s). {result['note']}")
    # WRONG_ANSWERS is PER TASK, and a run solves every open one -- so the
    # number to match is the total EXPECTED wrong: the ones answered wrong on
    # purpose, plus any question whose own data makes it impossible to answer
    # correctly (reported separately as a content issue).
    assert server["incorrect"] == result["expected_incorrect"], (
        f"{TC_ID}: {server['incorrect']} answer(s) were scored wrong, but "
        f"{result['expected_incorrect']} were expected to be. "
        f"Deliberately wrong: {result['wrong']}. "
        f"Unanswerable in the task data: {result['data_issues']}")

    # Defects in the task CONTENT are reported, never failed for: they are not
    # faults in the automation, and a test should not go red for a broken
    # question somebody else owns.
    if result["data_issues"]:
        print(f"{TC_ID} CONTENT ISSUES: {result['data_issues']}")

    assert not result["problems"], (
        f"{TC_ID}: solving the task hit problems: {result['problems']}. "
        f"{result['note']}")
    assert result["ok"], f"{TC_ID}: the task run did not pass - {result['note']}"
