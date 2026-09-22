"""Teacher tasks: answering from the real key and checking the score on the server.

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

import logging
import re
import requests
import time
from alttester import By

from vocatooki import backend_api, evidence_screenshots, exam_results_api, login_session, map_navigation, scenes, ui_actions


# --- Tasks: the teacher's tasks, and answering one -------------------------
#
# Surveyed live 2026-08-19. A task is NOT graded in the app: submitting SENDS it
# to the teacher, which is why the outcome to verify is Open -> Sent and never
# "the answers were right".
TASKS_SCENE = "TasksSelectionScene"


TASK_SCENE = "TaskScene"


TASK_CARD_OPEN = "TaskCard-Open(Clone)"      # answerable


TASK_CARD_CLOSED = "TaskCard-Closed(Clone)"  # no longer answerable


TASK_TABS = ("ALL", "Open", "Sent", "Checked", "Missed")


TASK_TITLE = "TitleText"


TASK_QUESTION_PREFIX = "Question_"


TASK_SUBMIT = "SubmitButton"


TASK_ANSWER_PREFIX = "Answer_Visual"        # Answer_Visual_<shown>_Data_<original>


TASK_MULTIPLE_CHOICE = "MultipleChoiceContent(Clone)"


# Submit only ASKS: it raises a yes/no popup, and the task is not sent
# until Yes is pressed.
TASK_CONFIRM_POPUP = "YesNoPopup(Clone)"


TASK_CONFIRM_YES = "YesButton"


# How long a submitted task is given to appear on the server. The app sits
# on the task uploading it -- measured at about 90 seconds.
TASK_RECORD_TIMEOUT = 120


# After a task is sent, how long to let the app settle back onto the Tasks
# screen before opening the next one. A ceiling, not a sleep: the run goes on
# as soon as the screen is there and has stopped changing.
TASK_NEXT_TIMEOUT = 20


# The task's own status on the server: 2 = the app has CHECKED (scored) it.
TASK_STATUS_CHECKED = 2


# How long to wait for a submitted task to be marked checked before going on
# to the next one. A ceiling, not a sleep.
TASK_CHECKED_TIMEOUT = 20


def task_tab_counts(altdriver):
    """``{"Open": "2 Open", ...}`` — each tab's own count, read off the screen."""
    counts = {}
    for tab in TASK_TABS:
        try:
            obj = altdriver.find_object(By.PATH, f"//{tab}-NavigationTab//NumTasksText")
            counts[tab] = ui_actions._text_of(obj) or ""
        except Exception:                            # noqa: BLE001
            counts[tab] = ""
    return counts


def _task_count(text):
    """"2 Open" -> 2. Unreadable -> None, which is NOT the same as zero."""
    match = re.search(r"\d+", str(text or ""))
    return int(match.group()) if match else None


def task_questions(altdriver):
    """The question chips on the strip, in order: ``["Question_1", ...]``."""
    try:
        found = [e.name for e in (altdriver.get_all_elements() or [])
                 if e.name.startswith(TASK_QUESTION_PREFIX)]
    except Exception:                                # noqa: BLE001
        return []
    def number(name):
        digits = re.findall(r"\d+", name)
        return int(digits[-1]) if digits else 0
    return sorted(set(found), key=number)


def task_answers(altdriver):
    """The answer toggles of the question on screen, in the order SHOWN.

    Named ``Answer_Visual_<shown>_Data_<original>``: the visual slot is
    shuffled per question, so the Data index says nothing about which is
    correct — measured live, Data_0 was the wrong answer on question 2.
    """
    try:
        found = [e.name for e in (altdriver.get_all_elements() or [])
                 if e.name.startswith(TASK_ANSWER_PREFIX)]
    except Exception:                                # noqa: BLE001
        return []
    def shown(name):
        digits = re.findall(r"\d+", name)
        return int(digits[0]) if digits else 0
    return sorted(set(found), key=shown)


def task_answer_selected(altdriver, answer):
    """Is this answer chosen? Reads the Toggle, which is the real state.

    The `selectedAnswer` child exists on every answer whether chosen or not, so
    its presence proves nothing — and its active flag cannot be read.
    """
    try:
        obj = altdriver.find_object(By.NAME, answer)
        return bool(obj.get_component_property("UnityEngine.UI.Toggle", "isOn",
                                               "UnityEngine.UI"))
    except Exception:                                # noqa: BLE001
        return False


def task_answer_question(altdriver, settle=1.2):
    """Answer the question on screen. Returns ``(answered, note)``.

    Only multiple choice is automated. A task can also ask for TEXT or a
    RECORDING; those are reported, never silently passed over.
    """
    if ui_actions.find_any(altdriver, TASK_MULTIPLE_CHOICE) is None:
        return False, "not a multiple-choice question (text or recording?)"

    answers = task_answers(altdriver)
    if not answers:
        return False, "a multiple-choice question with no answers on screen"
    if any(task_answer_selected(altdriver, a) for a in answers):
        return True, ""                              # already answered

    for answer in answers:
        if not ui_actions.press_object(altdriver, answer, settle=settle):
            continue
        if task_answer_selected(altdriver, answer):
            return True, ""
    return False, f"none of {len(answers)} answers would select"


# The task API. The answer key is NOT in the game: the app never marks an option
# as correct, and no component exposes it (measured -- the driver cannot even
# enumerate fields). It comes from the backend, where a sub-task carries its
# options and a `correct_answer` naming the right one BY ID.
#
# The id is the link that makes this usable: `parameters[].id` is exactly the
# Data index in `Answer_Visual_<shown>_Data_<id>`, so "correct_answer: 1" means
# press the answer whose name ends `_Data_1`, wherever it happens to be shown.
# The tasks API base (VT_TASKS_API) lives in Utilities/vt/backend.py.


# The login the APP itself uses. It answers with everything a task run needs to
# know about the player -- their id, their class, and which backend their data
# lives on -- so none of it has to be written into a Rally case, where it goes
# stale the moment the case is pointed at another account. (That mismatch once
# looked exactly like the app losing a student's answers.)
VT_PLAYER_LOGIN_URL = "https://login.vocatooki.com/access/login"


VT_PLAYER_EMAIL_DOMAIN = "@vocatooki.com"


_PLAYER_CACHE = {}


def vt_player(username, password):
    """``{"user_id", "class_id", "backend"}`` for a player, or ``{}``.

    The login wants the EMAIL form of the username: "vt233640" alone is refused,
    "vt233640@vocatooki.com" is accepted.
    """
    if not username or not password:
        return {}
    cached = _PLAYER_CACHE.get((username, password))
    if cached is not None:
        return cached

    email = username if "@" in str(username) else f"{username}{VT_PLAYER_EMAIL_DOMAIN}"
    try:
        # The payload the app itself sends: username AND email (both the email
        # form -- the bare "vt233640" is refused), the password, and the game.
        r = requests.post(VT_PLAYER_LOGIN_URL,
                          json={"username": email, "email": email,
                                "password": str(password), "game": exam_results_api.VT_GAME},
                          headers={"Content-Type": "application/json",
                                   "Accept": "application/json"}, timeout=25)
        r.raise_for_status()
        data = r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not look up '{username}': {e}")
        _PLAYER_CACHE[(username, password)] = {}
        return {}

    who = {"user_id": data.get("id"), "class_id": data.get("class_id"),
           "backend": (data.get("backend") or "").rstrip("/")}
    if who["user_id"]:
        logging.info(f"[Tasks] '{username}' is player {who['user_id']} "
                     f"in class {who['class_id']} on {who['backend'] or 'the default backend'}")
    _PLAYER_CACHE[(username, password)] = who
    return who


def task_api_headers(token=None):
    """Bearer headers for the task API, logging in once if needed."""
    return exam_results_api.get_auth_headers(token=token)


def class_tasks(class_id, token=None):
    """``[{"id", "name", ...}]`` — the tasks set for a class."""
    try:
        r = requests.get(f"{backend_api.VT_TASKS_API}/get-class-tasks/{class_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not list the class's tasks: {e}")
        return []


def user_class_id(user_id, token=None):
    """The class this player's tasks belong to, or None.

    Saves the Rally case from carrying a class id that is only ever right for
    one account: `get-user-tasks` answers with `taskid_classid` ("651_2336"),
    so the class falls out of the player id on its own.
    """
    try:
        r = requests.get(f"{backend_api.VT_TASKS_API}/get-user-tasks/{user_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        for entry in (r.json() or []):
            pair = str(entry.get("taskid_classid") or "")
            if "_" in pair:
                return int(pair.split("_", 1)[1])
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not work out the class for user {user_id}: {e}")
    return None


def task_answer_key(task_id, token=None):
    """``[{"index", "type", "question", "correct", "options"}]`` for a task.

    ``correct`` is the id to press (the `Data_` index), and ``options`` maps
    every id to its text, so a WRONG answer can be chosen deliberately too.
    """
    try:
        r = requests.get(f"{backend_api.VT_TASKS_API}/get-task/{task_id}",
                         headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        task = r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not read task {task_id}: {e}")
        return []

    key = []
    for index, sub in enumerate(task.get("sub_tasks") or [], start=1):
        data = sub.get("data") or {}
        options = {int(p.get("id")): p.get("freetext")
                   for p in (data.get("parameters") or [])
                   if p.get("id") is not None}
        key.append({
            "index": index,
            "type": sub.get("type") or "",
            "question": data.get("task_question") or "",
            "correct": data.get("correct_answer"),
            "options": options,
        })
    return key


def task_submitted_answers(user_id, task_id, token=None, attempt=0):
    """What the SERVER recorded for this user's attempt, or {}.

    The honest proof a run worked: `choosenAnswer` against `correctAnswer` per
    question, and the `result` the task scored -- read back from the backend
    rather than inferred from a tab count.
    """
    try:
        r = requests.get(
            f"{backend_api.VT_TASKS_API}/get-task-answer/{user_id}/{task_id}/{attempt}",
            headers=task_api_headers(token), timeout=25)
        r.raise_for_status()
        return r.json() or {}
    except Exception as e:                           # noqa: BLE001
        logging.error(f"[Tasks] could not read the submitted answers: {e}")
        return {}


def wait_for_task_recorded(user_id, task_id, timeout=90, poll=5):
    """Wait until the SERVER has stored this submission. Returns the record.

    Submitting is not instant: the app sits on the task while it uploads, and
    reading the answers straight afterwards comes back empty -- which reads
    exactly like a submit that never happened. Waiting for the record is also
    what makes it safe to go on to the NEXT task: the run only moves once the
    server agrees the last one landed.
    """
    end = time.time() + timeout
    while True:
        stored = task_submitted_answers(user_id, task_id)
        if stored.get("answer"):
            logging.info(f"[Tasks] the server recorded task {task_id} "
                         f"({len(stored['answer'])} answer(s), "
                         f"result={stored.get('result')})")
            return stored
        if time.time() >= end:
            logging.error(f"[Tasks] the server never recorded task {task_id} "
                          f"within {timeout}s")
            return stored
        time.sleep(poll)


def task_answer_by_data_id(altdriver, data_id, settle=1.2):
    """Press the answer whose name ends ``_Data_<data_id>``. Returns bool.

    The visual slot is shuffled per question, so the answer is chosen by its
    DATA id -- the one thing that means the same on every render.
    """
    wanted = f"_Data_{int(data_id)}"
    for name in task_answers(altdriver):
        if not name.endswith(wanted):
            continue
        # Already chosen (a re-opened task keeps its answers): pressing again
        # would toggle it back OFF and read as a failure.
        if task_answer_selected(altdriver, name):
            return True
        if ui_actions.press_object(altdriver, name, settle=settle):
            return task_answer_selected(altdriver, name)
        return False
    logging.error(f"[Tasks] no answer ending '{wanted}' on this question")
    return False


def _tasks_answer_key_for(title, class_id, user_id):
    """``(key, task_id)`` for the task with this title, or ``([], None)``."""
    if not class_id and user_id:
        class_id = user_class_id(user_id)
        if class_id:
            logging.info(f"[Tasks] class {class_id} discovered from user {user_id}")
    if not class_id:
        return [], None
    wanted = (title or "").strip().lower()
    for entry in class_tasks(class_id):
        if str(entry.get("name", "")).strip().lower() == wanted:
            return task_answer_key(entry.get("id")), entry.get("id")
    return [], None


def wait_for_task_checked(user_id, task_id, timeout=TASK_CHECKED_TIMEOUT, poll=3):
    """Wait until the server marks this task CHECKED. Returns the record.

    Recorded and checked are two different moments: the answers land first, and
    the app scores them a beat later. Waiting for the score means the next task
    starts from a settled account, and that the `result` read back is the real
    one rather than whatever was there mid-scoring.

    A ceiling, not a sleep -- and NOT a failure on its own if the status never
    arrives: the answers are already stored, so the run says so and goes on.
    """
    end = time.time() + timeout
    stored = {}
    while True:
        stored = task_submitted_answers(user_id, task_id)
        if stored.get("status") == TASK_STATUS_CHECKED:
            logging.info(f"[Tasks] task {task_id} is CHECKED "
                         f"(result={stored.get('result')})")
            return stored
        if time.time() >= end:
            logging.warning(f"[Tasks] task {task_id} was not marked checked within "
                            f"{timeout}s (status={stored.get('status')})")
            return stored
        time.sleep(poll)


def _tasks_settle_for_next(altdriver, timeout=TASK_NEXT_TIMEOUT):
    """Wait for the Tasks screen to come back and stop changing. Returns bool.

    Between two tasks the app has to put the finished one away -- the tab
    counts re-count and the card list rebuilds -- and a card pressed mid-rebuild
    is a press that lands on nothing. A ceiling rather than a sleep: as soon as
    the screen is there and settled, the run goes on.
    """
    end = time.time() + timeout
    while time.time() < end:
        if scenes._current_scene(altdriver) == TASKS_SCENE:
            left = max(1.0, end - time.time())
            scenes.wait_for_scene_ready(altdriver, timeout=left, stable_for=1.0,
                                 label="tasks list")
            logging.info("[Tasks] the Tasks screen is settled; on to the next task")
            return True
        time.sleep(1.0)
    logging.info(f"[Tasks] still on {scenes._current_scene(altdriver)} after {timeout}s; "
                 f"carrying on to the next task anyway")
    return False


def _tasks_solve_one(altdriver, trail, class_id=None, user_id=None,
                     wrong_answers=0, submit=True, timeout=90):
    """Open the first OPEN task, answer it, submit it. One task, never raises.

    Returns a record of that task alone; ``tasks_check`` stitches the records
    together. Split out so the run can go on to the NEXT task without the
    login, the tab counts and the final verdict being redone each time.
    """
    out = {"title": "", "task_id": None, "questions": 0, "answered": 0,
           "wrong": [], "unsupported": [], "submitted": False, "checked": False,
           "server": {}, "problems": [], "data_issues": [], "note": ""}

    try:
        card = altdriver.find_object(By.PATH, f"//{TASK_CARD_OPEN}[0]")
        out["title"] = ui_actions._text_of(altdriver.find_object(
            By.PATH, f"//{TASK_CARD_OPEN}[0]//TaskText")) or ""
        ui_actions._press(card)
    except Exception as e:                           # noqa: BLE001
        out["note"] = f"the open task card could not be opened: {e}"
        return out
    if not scenes.wait_for_scene(altdriver, TASK_SCENE, timeout=timeout):
        out["note"] = f"'{out['title']}' did not open into the task"
        return out
    trail.shot(altdriver, f"task-{ui_actions._slugish(out['title'])}-opened", evidence_screenshots.EVIDENCE_PROOF)

    questions = task_questions(altdriver)
    out["questions"] = len(questions)
    if not questions:
        out["note"] = f"'{out['title']}' shows no questions"
        return out
    logging.info(f"[Tasks] '{out['title']}': {len(questions)} question(s)")

    key, out["task_id"] = _tasks_answer_key_for(out["title"], class_id, user_id)
    if key:
        logging.info(f"[Tasks] answer key for '{out['title']}': {len(key)} question(s)")
    else:
        # Without the key the answers would be arbitrary, and the task is
        # SCORED -- a run must not post a bad score to a real teacher's task and
        # call it a pass. Said out loud, and nothing is sent.
        out["problems"].append(
            f"no answer key for '{out['title']}': without it the answers would "
            'be arbitrary on a task that is scored. Add "Class ID: <n>" to the '
            "Rally case.")
        submit = False

    # Which questions to get WRONG on purpose: the last ones, so a correct
    # answer is still exercised first.
    deliberately_wrong = set()
    if wrong_answers and key:
        deliberately_wrong = {e["index"] for e in key[-int(wrong_answers):]}

    for index, question in enumerate(questions, start=1):
        if not ui_actions.press_object(altdriver, question, settle=1.5):
            out["problems"].append(f"question {index} could not be opened")
            continue
        scenes.wait_for_scene_ready(altdriver, timeout=6, stable_for=0.8, label=question)

        entry = next((e for e in key if e["index"] == index), None)
        if entry is not None and entry.get("correct") is not None:
            correct = int(entry["correct"])
            if entry["options"] and correct not in entry["options"]:
                # The task's own data is wrong -- measured: 'a/an' Q5 and Q8 say
                # correct_answer 3 while the options are only 0 and 1. Leaving
                # the question blank would block the whole task, so an option is
                # chosen and the bad data is reported.
                fallback = sorted(entry["options"])[0]
                # Reported, but NOT a problem with the run: the task's content
                # is wrong, which the test should surface without failing for a
                # defect outside its own subject.
                out["data_issues"].append(
                    f"'{out['title']}' Q{index}: the task data says the correct "
                    f"answer is {correct}, which is not one of its options "
                    f"{sorted(entry['options'])} - answered "
                    f"{entry['options'][fallback]!r} instead")
                correct = fallback
            if index in deliberately_wrong:
                choice = next((i for i in entry["options"] if i != correct), correct)
                out["wrong"].append(
                    f"{out['title']} Q{index}: chose "
                    f"{entry['options'].get(choice)!r} instead of "
                    f"{entry['options'].get(correct)!r}")
            else:
                choice = correct
            if task_answer_by_data_id(altdriver, choice):
                out["answered"] += 1
                continue
            out["problems"].append(
                f"question {index}: could not press the answer Data_{choice}")
            continue

        answered, why = task_answer_question(altdriver)
        if answered:
            out["answered"] += 1
        else:
            # A task can also ask for TEXT or a RECORDING, and neither is
            # automated here. Never passed over quietly.
            out["unsupported"].append(f"{out['title']} Q{index}: {why}")
            logging.warning(f"[Tasks] question {index} not answered - {why}")

    trail.shot(altdriver, f"{ui_actions._slugish(out['title'])}-answered-"
                          f"{out['answered']}-of-{out['questions']}", evidence_screenshots.EVIDENCE_PROOF)

    if out["unsupported"]:
        out["note"] = (f"{len(out['unsupported'])} of {out['questions']} question(s) "
                       f"are not automatable, so '{out['title']}' was NOT submitted")
        return out                                   # never send a half-done task
    if out["answered"] != out["questions"]:
        # The app refuses a part-answered task and records NOTHING, leaving it
        # Open -- measured: submitting 18 of 20 stored 0 answers, and the run
        # then met the same task again. Better to stop and say which questions
        # were missed.
        out["problems"].append(
            f"'{out['title']}': only {out['answered']} of {out['questions']} "
            f"question(s) could be answered, so it was NOT submitted")
        out["note"] = out["problems"][-1]
        return out

    if not submit:
        out["note"] = (f"answered {out['answered']}/{out['questions']}; "
                       f"'{out['title']}' was not submitted")
        return out

    if not ui_actions.press_object(altdriver, TASK_SUBMIT, settle=2.0):
        out["problems"].append("Submit could not be pressed")
        return out

    # Submit only ASKS. It opens a YesNoPopup(Clone), and until Yes is pressed
    # nothing is sent -- measured live: a run sat on TaskScene with the tab
    # counts unmoved, having "submitted" a task that never left.
    if ui_actions.wait_for_any(altdriver, (TASK_CONFIRM_POPUP, TASK_CONFIRM_YES), timeout=10):
        trail.shot(altdriver, f"{ui_actions._slugish(out['title'])}-submit-confirm", evidence_screenshots.EVIDENCE_STEP)
        if not ui_actions.press_object(altdriver, TASK_CONFIRM_YES, settle=3.0):
            out["problems"].append(
                "the submit confirmation appeared but Yes could not be pressed")
            return out
        logging.info("[Tasks] confirmed the submit")
    else:
        logging.warning("[Tasks] no submit confirmation appeared")
    out["submitted"] = True

    # LEAVE the task before waiting for the server. The app shows its own
    # checked screen straight after the confirm, but the answers do not reach
    # the server until the task is exited -- measured: a run that sat on that
    # screen polling for 120s never saw the record appear, while the same task
    # submitted by code that navigated away first was stored within seconds.
    if not scenes.wait_for_scene(altdriver, TASKS_SCENE, timeout=20):
        login_session.return_to_start(altdriver)
        map_navigation.open_feature(altdriver, "tasks", timeout=timeout)

    # Only now is it worth asking the server. Waiting here is also what makes
    # going on to the NEXT task safe.
    if user_id and out["task_id"]:
        stored = wait_for_task_recorded(user_id, out["task_id"],
                                        timeout=TASK_RECORD_TIMEOUT)
        # Then wait for it to be CHECKED, so the score read back is the settled
        # one and the next task starts from a quiet account.
        checked = wait_for_task_checked(user_id, out["task_id"],
                                        timeout=TASK_CHECKED_TIMEOUT)
        if checked.get("answer"):
            stored = checked
        out["checked"] = stored.get("status") == TASK_STATUS_CHECKED
        answers = stored.get("answer") or []
        right = sum(1 for a in answers
                    if a.get("choosenAnswer") == a.get("correctAnswer"))
        out["server"] = {"result": stored.get("result"),
                         "status": stored.get("status"),
                         "answers": len(answers), "correct": right,
                         "incorrect": len(answers) - right}
        if not answers:
            # Cost a whole investigation once: the id in the Rally case belonged
            # to a DIFFERENT player, so the answers were looked for under
            # somebody else and the run read as data loss.
            out["problems"].append(
                f"the server has no answers for '{out['title']}' under user "
                f"{user_id}. The task WAS submitted, so check that the User ID "
                f"in the Rally case is this account's — an id belonging to "
                f"another player looks exactly like a submit that vanished.")
        elif len(answers) != out["questions"]:
            out["problems"].append(
                f"the server recorded {len(answers)} answer(s) for "
                f"{out['questions']} question(s) of '{out['title']}'")
        expected_wrong = len(out["wrong"]) + len(out["data_issues"])
        if key and (len(answers) - right) != expected_wrong:
            out["problems"].append(
                f"'{out['title']}': {len(answers) - right} answer(s) came back "
                f"wrong, but {expected_wrong} were expected to "
                f"({len(out['wrong'])} answered wrong on purpose, "
                f"{len(out['data_issues'])} unanswerable in the task data)")
    out["note"] = (f"'{out['title']}': answered {out['answered']}/{out['questions']}, "
                   f"submitted, {'checked' if out['checked'] else 'NOT yet checked'}, "
                   f"server result {out['server'].get('result')}")
    logging.info(f"[Tasks] {out['note']}")
    return out


def tasks_check(altdriver, username=None, password=None, tc_id="",
                submit=True, timeout=90, class_id=None, user_id=None,
                wrong_answers=0, max_tasks=None):
    """Solve the account's OPEN tasks and prove the server recorded them.

    Works through EVERY open task by default, going back to the Tasks screen
    between them; ``max_tasks`` caps how many. A task is answered from the
    backend ANSWER KEY, so it is answered CORRECTLY -- except for
    ``wrong_answers`` questions per task chosen on purpose, which exercise the
    wrong-answer path and show up in the score. Those are reported by name,
    because a run that quietly answered badly and one that deliberately
    answered badly must not look the same.

    A task is scored by the app and lands in CHECKED; only what a teacher must
    read waits in Sent. Never raises.
    """
    report = {"ok": False, "tasks": [], "solved": 0, "checked": 0, "title": "",
              "player": {}, "data_issues": [], "questions": 0,
              "answered": 0, "unsupported": [], "wrong": [], "counts_before": {},
              "counts_after": {}, "submitted": False, "server": {},
              "expected_incorrect": 0, "problems": [], "note": ""}

    evidence_screenshots.reset_evidence_trail(tc_id)
    trail = evidence_screenshots.evidence_trail(tc_id)

    # Who is this player? Asked of the login the app itself uses, so the id, the
    # class and the backend all come from the ACCOUNT rather than from numbers
    # typed into a Rally case -- where they go stale the moment the case is
    # pointed at somebody else, and a stale id looks exactly like the app losing
    # a student's answers. Anything passed in explicitly still wins.
    if username and password:
        who = vt_player(username, password)
        if who.get("user_id"):
            user_id = user_id or who["user_id"]
            class_id = class_id or who.get("class_id")
            report["player"] = who
            # The account's own backend wins — unless the run NAMED one, which
            # is a stated choice and must not be switched behind its back.
            if who.get("backend") and not backend_api.backend_pinned():
                backend_api.VT_TASKS_API = f"{who['backend']}/data"
        elif not user_id:
            report["note"] = (f"could not look up '{username}' - without the "
                              f"player id the answers cannot be checked")
            return report

    if username and not login_session.fresh_login(altdriver, username, password):
        report["note"] = f"could not log in as {username}"
        return report
    if not map_navigation.open_feature(altdriver, "tasks", username, password, timeout=timeout):
        report["note"] = "the Tasks screen did not open"
        return report

    report["counts_before"] = task_tab_counts(altdriver)
    trail.shot(altdriver, "tasks-BEFORE", evidence_screenshots.EVIDENCE_KEY)
    open_before = _task_count(report["counts_before"].get("Open"))
    logging.info(f"[Tasks] tabs before: {report['counts_before']}")

    if ui_actions.find_any(altdriver, TASK_CARD_OPEN) is None:
        report["note"] = ("there is no OPEN task on this account to solve "
                          f"(tabs: {report['counts_before']})")
        return report

    limit = int(max_tasks) if max_tasks else 0        # 0 = every open task
    seen_titles = []
    while True:
        if limit and len(report["tasks"]) >= limit:
            break
        # Back on the Tasks screen, is there still something to answer?
        if scenes._current_scene(altdriver) != TASKS_SCENE:
            login_session.return_to_start(altdriver)
            if not map_navigation.open_feature(altdriver, "tasks", timeout=timeout):
                report["problems"].append(
                    "could not get back to the Tasks screen for the next task")
                break
        if ui_actions.find_any(altdriver, TASK_CARD_OPEN) is None:
            break                                    # nothing open left

        one = _tasks_solve_one(altdriver, trail, class_id=class_id, user_id=user_id,
                               wrong_answers=wrong_answers, submit=submit,
                               timeout=timeout)
        report["tasks"].append(one)

        if one["submitted"]:
            # Let the app finish putting the task away before the next one is
            # opened: the tabs re-count and the card list rebuilds, and opening
            # a card mid-rebuild is how a press lands on nothing.
            _tasks_settle_for_next(altdriver, timeout=TASK_NEXT_TIMEOUT)

        # A task that could not be submitted would still be sitting in Open, so
        # trying again would open the SAME card forever.
        if not one["submitted"]:
            report["problems"].extend(one["problems"] or [])
            if one["note"]:
                report["problems"].append(one["note"])
            break
        if one["title"] and one["title"] in seen_titles:
            report["problems"].append(
                f"'{one['title']}' came round a second time - stopping rather "
                f"than solving the same task twice")
            break
        seen_titles.append(one["title"])

    # Stitch the per-task records into one picture.
    for one in report["tasks"]:
        report["questions"] += one["questions"]
        report["answered"] += one["answered"]
        report["wrong"].extend(one["wrong"])
        report["unsupported"].extend(one["unsupported"])
        report["problems"].extend(p for p in one["problems"]
                                  if p not in report["problems"])
        report["data_issues"].extend(one.get("data_issues") or [])
    report["solved"] = sum(1 for o in report["tasks"] if o["submitted"])
    report["checked"] = sum(1 for o in report["tasks"] if o.get("checked"))
    report["title"] = ", ".join(o["title"] for o in report["tasks"] if o["title"])
    report["submitted"] = bool(report["tasks"]) and all(
        o["submitted"] for o in report["tasks"])
    # What SHOULD come back wrong: the ones answered wrong on purpose, plus the
    # ones that cannot be answered correctly at all. A question whose
    # correct_answer is not among its options is guaranteed to score wrong
    # however it is answered -- counting only the deliberate ones failed a run
    # that had done everything right ('a/an' Q5 and Q8).
    report["expected_incorrect"] = len(report["wrong"]) + len(report["data_issues"])
    served = [o["server"] for o in report["tasks"] if o["server"]]
    if served:
        report["server"] = {
            "answers": sum(s.get("answers", 0) for s in served),
            "correct": sum(s.get("correct", 0) for s in served),
            "incorrect": sum(s.get("incorrect", 0) for s in served),
            "results": [s.get("result") for s in served],
        }

    if scenes._current_scene(altdriver) != TASKS_SCENE:
        login_session.return_to_start(altdriver)
        map_navigation.open_feature(altdriver, "tasks", timeout=timeout)
    report["counts_after"] = task_tab_counts(altdriver)
    trail.shot(altdriver, "tasks-AFTER", evidence_screenshots.EVIDENCE_KEY)
    open_after = _task_count(report["counts_after"].get("Open"))
    logging.info(f"[Tasks] tabs after: {report['counts_after']}")

    if report["solved"]:
        if None in (open_before, open_after):
            report["problems"].append(
                f"the tab counts could not be read ({report['counts_before']} -> "
                f"{report['counts_after']})")
        elif open_after >= open_before:
            # A drop, not a drop of exactly one per task: submitting one task
            # was measured moving TWO out of Open (3 -> 1, Checked 0 -> 2),
            # because the app settles whatever else it had already scored.
            report["problems"].append(
                f"Open went {open_before} -> {open_after}: submitting a task "
                f"should take it out of Open")

    report["ok"] = (bool(report["solved"]) and report["submitted"]
                    and not report["problems"]
                    and report["answered"] == report["questions"])
    report["note"] = report["note"] or (
        f"Solved {report['solved']} task(s), {report['checked']} checked "
        f"({report['title'] or 'none'}): "
        f"answered {report['answered']} of {report['questions']} question(s), "
        f"{report['expected_incorrect']} expected wrong "
        f"({len(report['wrong'])} on purpose, "
        f"{len(report['data_issues'])} unanswerable in the task data). "
        f"Open {open_before} -> {open_after}, "
        f"Checked {report['counts_before'].get('Checked')} -> "
        f"{report['counts_after'].get('Checked')}. "
        f"Server: {report['server'] or 'not read'}."
        + (f" CONTENT ISSUES in the task data (not an automation fault): "
           f"{report['data_issues']}." if report["data_issues"] else "")
        + (f" Problems: {report['problems']}." if report["problems"] else ""))
    logging.info(f"[Tasks] {report['note']}")
    return report
