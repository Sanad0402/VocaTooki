"""Test Generator — Auto-convert Rally test cases to executable pytest.

Reads Rally test cases and generates fully functional pytest code with:
- Auto-discovered AltTester elements
- Proper credentials from environment
- Common patterns (login, navigation, validation)
- Zero manual page object coding
"""

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from runner import rally_naming

logger = logging.getLogger(__name__)


TASKS_TEMPLATE = '''"""
{doc}

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
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "{username}"
PASSWORD = "{password}"
# The class the task belongs to (its answer key lives there) and the player
# whose stored answers are read back to check the score.
CLASS_ID = {class_id}
USER_ID = {user_id}
# How many questions to answer WRONG on purpose, to exercise that path.
WRONG_ANSWERS = {wrong}


{guard}def {func}(altdriver):
    driver, _platform = altdriver

    result = utilsdemo.tasks_check(
        driver, username=USERNAME, password=PASSWORD, tc_id=TC_ID,
        class_id=CLASS_ID, user_id=USER_ID, wrong_answers=WRONG_ANSWERS,
        submit=True)

    # Say what this run did and did NOT cover, pass or fail.
    print(f"{{TC_ID}} RESULT: {{result['note']}}")

    assert result["questions"], (
        f"{{TC_ID}}: no task was opened to solve - {{result['note']}}")
    assert result["solved"], (
        f"{{TC_ID}}: no task was solved and submitted - {{result['note']}}")
    assert not result["unsupported"], (
        f"{{TC_ID}}: the task has questions this framework cannot answer (text "
        f"or recording), so it was not submitted: {{result['unsupported']}}")
    assert result["answered"] == result["questions"], (
        f"{{TC_ID}}: answered only {{result['answered']}} of {{result['questions']}} "
        f"question(s). {{result['note']}}")
    assert result["submitted"], (
        f"{{TC_ID}}: the task was never submitted - {{result['note']}}")

    # The server is the judge, not the screen: it holds what was really stored.
    server = result["server"]
    assert server, (
        f"{{TC_ID}}: the submitted answers could not be read back from the server, "
        f"so nothing proves what was recorded. {{result['note']}}")
    assert server["answers"] == result["questions"], (
        f"{{TC_ID}}: the server recorded {{server['answers']}} answer(s) for "
        f"{{result['questions']}} question(s). {{result['note']}}")
    # WRONG_ANSWERS is PER TASK, and a run solves every open one -- so the
    # number to match is the total EXPECTED wrong: the ones answered wrong on
    # purpose, plus any question whose own data makes it impossible to answer
    # correctly (reported separately as a content issue).
    assert server["incorrect"] == result["expected_incorrect"], (
        f"{{TC_ID}}: {{server['incorrect']}} answer(s) were scored wrong, but "
        f"{{result['expected_incorrect']}} were expected to be. "
        f"Deliberately wrong: {{result['wrong']}}. "
        f"Unanswerable in the task data: {{result['data_issues']}}")

    # Defects in the task CONTENT are reported, never failed for: they are not
    # faults in the automation, and a test should not go red for a broken
    # question somebody else owns.
    if result["data_issues"]:
        print(f"{{TC_ID}} CONTENT ISSUES: {{result['data_issues']}}")

    assert not result["problems"], (
        f"{{TC_ID}}: solving the task hit problems: {{result['problems']}}. "
        f"{{result['note']}}")
    assert result["ok"], f"{{TC_ID}}: the task run did not pass - {{result['note']}}"
'''


class RallyTestGenerator:
    """Generates pytest from Rally test case definitions."""

    def __init__(self, project_root: str):
        """Initialize generator."""
        self.project_root = Path(project_root)
        self.rally_suite_path = self.project_root / "data" / "rally_suite.json"
        self.tests_base_dir = self.project_root / "Tests" / "rally"

    def load_rally_suite(self) -> Dict[str, Any]:
        """Load Rally test suite from JSON."""
        if not self.rally_suite_path.exists():
            raise FileNotFoundError(f"Rally suite not found: {self.rally_suite_path}")
        # encoding is explicit: Rally descriptions carry em dashes and smart
        # quotes, and Windows' default cp1252 fails to decode them.
        with open(self.rally_suite_path, encoding="utf-8") as f:
            return json.load(f)

    def generate_all_tests(self, prune: bool = True) -> List[str]:
        """Generate pytest files for all Rally test cases.

        When ``prune`` is True (default), any previously generated file whose
        embedded ``TC_ID`` is no longer in the current suite is deleted. This
        removes leftovers from older sync schemes (numeric ObjectIDs, the
        ``General/`` fallback, truncated names). Hand-written files (no
        ``TC_ID`` marker) are never touched.
        """
        suite = self.load_rally_suite()
        generated = []
        current_ids = set()
        for tc in suite.get("test_cases", []):
            try:
                path = self.generate_test(tc)
                generated.append(str(path))
                current_ids.add(tc.get("id"))
            except Exception as e:
                logger.error(f"Failed to generate test {tc.get('id')}: {e}")

        if prune:
            self._prune_orphans(current_ids)

        return generated

    def refresh_generated_tests(self, prune: bool = True) -> List[str]:
        """Re-render ONLY the tests that were already generated.

        Sync-time behaviour: a case whose file exists is refreshed from the
        latest Rally data (unless locked with MANUAL_EDIT = True), but a NEW
        case gets no file — it shows as "not generated" in the panel until the
        user explicitly clicks generate. Orphans of deleted Rally cases are
        still pruned.
        """
        suite = self.load_rally_suite()
        refreshed = []
        # Which cases' CODE actually changed, as opposed to being rewritten
        # identically. That is the honest answer to "what did this sync do to
        # my tests?" — credentials edited in Rally show up here, and nothing
        # else does.
        self.changed_case_ids = []
        for tc in suite.get("test_cases", []):
            try:
                nodeid = (tc.get("action") or {}).get("nodeid") or ""
                file_part = nodeid.split("::", 1)[0] if "::" in nodeid else ""
                path = self.project_root / file_part if file_part else None
                if path is None or not path.exists():
                    continue                      # new case -> wait for explicit generate
                try:
                    before = path.read_text(encoding="utf-8")
                except OSError:
                    before = ""
                written = self.generate_test(tc)
                refreshed.append(str(written))
                try:
                    if Path(written).read_text(encoding="utf-8") != before:
                        self.changed_case_ids.append(tc.get("id"))
                except OSError:
                    pass
            except Exception as e:
                logger.error(f"Failed to refresh test {tc.get('id')}: {e}")
        if prune:
            current = {t.get("id") for t in suite.get("test_cases", [])}
            self._prune_orphans(current)
        return refreshed

    def generate_test(self, test_case: Dict[str, Any]) -> Path:
        """Generate pytest for a single Rally test case.

        The file path and function name are taken from the recorded
        ``action.nodeid`` when present, so what gets written on disk always
        matches exactly what the runner executes (``pytest <nodeid>``). If no
        nodeid is recorded, they are computed from the shared naming rules.
        """
        tc_id = test_case["id"]
        tc_name = test_case["name"]
        folder_id = test_case.get("folder")
        user_data = test_case.get("user", {})

        # Prefer the recorded nodeid — it is the exact string the runner runs,
        # so deriving file + function from it guarantees a match.
        nodeid = (test_case.get("action") or {}).get("nodeid") or ""
        if "::" in nodeid:
            file_part, func_name = nodeid.split("::", 1)
            output_path = self.project_root / file_part
        else:
            func_name = self._get_test_func_name(tc_id, tc_name)
            output_path = self._determine_output_path(tc_id, tc_name, folder_id)

        # A file locked with MANUAL_EDIT = True is hand-maintained: never
        # overwrite it. The mapping still holds because the recorded nodeid keeps
        # pointing at this same file/function.
        if output_path.exists():
            try:
                if rally_naming.is_manual(output_path.read_text(encoding="utf-8")):
                    logger.info(f"Preserved manual edit (MANUAL_EDIT=True): {output_path}")
                    return output_path
            except Exception:
                pass

        description = test_case.get("description", "")
        steps = test_case.get("steps", [])
        test_type = self._infer_test_type(tc_name, description, nodeid,
                                          test_case.get("validation"))
        test_code = self._generate_test_code(
            tc_id, tc_name, test_type, user_data, func_name, description, steps,
            validation=test_case.get("validation"), nodeid=nodeid,
        )
        test_code = self._inject_manual_marker(test_code)

        # Remove any older file for this same Rally case before writing.
        self._remove_stale_for_tc(tc_id, output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        return output_path

    def generate_skeleton(self, test_case: Dict[str, Any],
                          elements: Dict[str, Any]) -> Path:
        """#4 — build a test from elements discovered on the LIVE app (via
        ``ElementInspector``) instead of an empty stub.

        ``elements`` = ``{"scene": str, "inputs": [names], "buttons": [names]}``.
        A fully-inferable case (positive login with the login controls present
        and credentials on the Rally case) is written as a COMPLETE real test
        (``MANUAL_EDIT = True``). Everything else is written as a *populated*
        stub — the real discovered element calls are pre-wired in the body, but
        it still skips until a human finishes and unlocks it. Never a false pass.

        A file already locked with ``MANUAL_EDIT = True`` is left untouched.
        Returns the written Path.
        """
        tc_id = test_case["id"]
        tc_name = test_case["name"]
        nodeid = (test_case.get("action") or {}).get("nodeid") or ""
        if "::" in nodeid:
            file_part, func_name = nodeid.split("::", 1)
            output_path = self.project_root / file_part
        else:
            func_name = self._get_test_func_name(tc_id, tc_name)
            output_path = self._determine_output_path(tc_id, tc_name, test_case.get("folder"))

        if output_path.exists():
            try:
                if rally_naming.is_manual(output_path.read_text(encoding="utf-8")):
                    logger.info(f"Preserved manual edit (MANUAL_EDIT=True): {output_path}")
                    return output_path
            except Exception:
                pass

        description = test_case.get("description", "")
        test_type = self._infer_test_type(tc_name, description, nodeid,
                                          test_case.get("validation"))
        scope_note = self.out_of_scope(tc_name, description, nodeid)
        if scope_note:
            # Not a Unity-client case (CRM/web/API). Discovering elements would
            # only wire it to whatever is on screen, which is worse than saying
            # plainly that AltTester cannot test it.
            code = self._gen_stub(tc_id, tc_name, func_name, description,
                                  test_case.get("steps", []), reason=scope_note)
        elif test_type == "guest":
            # Before exam/activity/page/daily: those templates all start with
            # ensure_logged_in, and a guest case describes itself in their words
            # ("...solve the first exam..."). Discovery is passed through so the
            # parsed route can be confirmed against the objects really on screen.
            code = self._gen_guest(
                tc_id, tc_name, func_name, description,
                test_case.get("steps", []), test_case.get("validation"),
                elements=elements or {},
            )
        elif test_type == "tasks":
            code = self._gen_tasks(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []),
                test_case.get("validation"),
            )
        elif test_type == "treasure_island":
            # Missions -> an island -> a building -> the activity it starts.
            # Every step is an object lookup in proven utils, so live discovery
            # adds nothing.
            code = self._gen_treasure_island(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []), test_case.get("validation"),
            )
        elif test_type == "event":
            # The event flow is proven utils end to end, so live discovery adds
            # nothing here either.
            code = self._gen_event(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []), test_case.get("validation"),
            )
        elif test_type == "exam":
            # Like activities: the whole flow comes from proven utils, so live
            # discovery adds nothing — this is always a REAL test.
            code = self._gen_exam(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []), test_case.get("validation"),
            )
        elif test_type == "activity":
            # Activity playthroughs are composed from the proven utils (login ->
            # map level -> the right activity -> solve), so this always writes a
            # REAL test. Discovery still helps: when the app was sitting on the
            # level's activity selection, ``elements['activity']['title']`` is
            # the label actually printed on the thumb.
            code = self._gen_activity(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []),
                test_case.get("validation"), nodeid=nodeid,
                title_hint=((elements or {}).get("activity") or {}).get("title", ""),
            )
        elif test_type == "page":
            # The feature's route was surveyed on the live app, so this is a
            # real test too — no element guessing needed.
            code = self._gen_page(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []), nodeid=nodeid,
                validation=test_case.get("validation"),
            )
        elif test_type == "daily":
            code = self._gen_daily(
                tc_id, tc_name, test_case.get("user", {}), func_name,
                description, test_case.get("steps", []), nodeid=nodeid,
            )
        else:
            code = self._gen_skeleton_from_elements(
                tc_id, tc_name, test_type, func_name,
                test_case.get("description", ""), test_case.get("steps", []),
                test_case.get("user", {}), elements or {},
            )
        # Complete skeletons declare MANUAL_EDIT = True themselves; populated
        # stubs get MANUAL_EDIT = False injected here.
        code = self._inject_manual_marker(code)
        self._remove_stale_for_tc(tc_id, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        return output_path

    @staticmethod
    def _inject_manual_marker(test_code: str) -> str:
        """Add the ``MANUAL_EDIT`` lock flag right after the ``TC_ID`` line.

        Kept here (not in each template) so all generated files get it uniformly.
        Set the flag to True in a file to protect it from the next Rally sync.
        """
        # Only skip if a real MANUAL_EDIT assignment already exists (line-anchored),
        # not merely an instructional comment mentioning it (stubs reference it in a
        # comment, and must still get the actual MANUAL_EDIT = False line injected).
        if re.search(r"^\s*MANUAL_EDIT\s*=", test_code, re.MULTILINE):
            return test_code
        return re.sub(
            r'(TC_ID\s*=\s*"[^"]*"\n)',
            r"\1# Set MANUAL_EDIT = True to keep your changes when re-syncing from Rally.\n"
            r"MANUAL_EDIT = False\n",
            test_code,
            count=1,
        )

    def _remove_stale_for_tc(self, tc_id: str, canonical_path: Path) -> None:
        """Delete any generator-produced file for ``tc_id`` other than the
        canonical target (prevents a rename from leaving a duplicate behind)."""
        if not self.tests_base_dir.exists():
            return
        canonical = Path(canonical_path).resolve()
        for path in self.tests_base_dir.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            marker = rally_naming.read_tc_id(text)
            if marker == tc_id and path.resolve() != canonical:
                if rally_naming.is_manual(text):
                    logger.info(f"Kept manually-locked file for {tc_id}: {path}")
                    continue
                try:
                    path.unlink()
                    logger.info(f"Removed stale duplicate for {tc_id}: {path}")
                except Exception as e:
                    logger.error(f"Could not remove {path}: {e}")

    def _prune_orphans(self, current_ids: set) -> List[str]:
        """Delete generator-produced files whose Rally id is no longer in the
        suite. Only files carrying the ``TC_ID`` marker are eligible.

        Returns the paths removed (also recorded on ``self.last_pruned`` so a
        caller that only wants the refreshed list can still report deletions).
        """
        self.last_pruned = []
        self.last_kept_locked = []
        if not self.tests_base_dir.exists():
            return self.last_pruned
        for path in self.tests_base_dir.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            marker = rally_naming.read_tc_id(text)
            if marker and marker not in current_ids:
                if rally_naming.is_manual(text):
                    logger.info(
                        f"Kept manually-locked orphan (Rally {marker} not in suite): {path}"
                    )
                    self.last_kept_locked.append(str(path))
                    continue
                try:
                    path.unlink()
                    self.last_pruned.append(str(path))
                    logger.info(
                        f"Pruned orphan (Rally {marker} not in current suite): {path}"
                    )
                except Exception as e:
                    logger.error(f"Could not prune {path}: {e}")
        self.prune_empty_dirs()
        return self.last_pruned

    def prune_to_suite(self) -> Dict[str, List[str]]:
        """Reconcile the WHOLE project with the suite: any generated test whose
        Rally case is gone is removed.

        This is deliberately not per-case. Whether one case was deleted in the
        panel, a Test Folder was deleted with all its cases, or a batch of cases
        disappeared from Rally between syncs, the same sweep covers it — every
        file under ``Tests/rally`` carrying a ``TC_ID`` that the suite no longer
        contains is deleted, and folders left empty are removed.

        Files locked with ``MANUAL_EDIT = True`` are hand-written, so they are
        reported under ``kept`` rather than deleted.

        Returns ``{"deleted": [paths], "kept": [paths]}``.
        """
        suite = self.load_rally_suite()
        current = {t.get("id") for t in suite.get("test_cases", [])}
        deleted = self._prune_orphans(current)
        return {"deleted": deleted, "kept": list(self.last_kept_locked)}

    def prune_empty_dirs(self) -> List[str]:
        """Drop folders left behind with nothing in them.

        Removing the last case of a Rally Test Folder used to leave its
        directory (e.g. ``TF291_Tetris/``) sitting in the tree, which reads as
        "there are tests here". Only completely empty directories go — one that
        still holds an ``__init__.py`` or any other file is left alone.
        """
        removed = []
        if not self.tests_base_dir.exists():
            return removed
        # Deepest first, so emptying a child can empty its parent too.
        for path in sorted((p for p in self.tests_base_dir.rglob("*") if p.is_dir()),
                           key=lambda p: len(p.parts), reverse=True):
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    removed.append(str(path))
                    logger.info(f"Removed empty test folder: {path}")
            except OSError:
                pass
        return removed

    # Keyword -> Unity activity scene (as reported by
    # AltTesterUtils.GetCurrentActivity and mapped in utilsdemo's solvers).
    # Keywords cover what Rally cases call the activity AND what the game
    # prints on its thumb — "Break Out" on screen is Rally's "Brickout".
    # Longest keywords first so "brick out" wins over a bare "brick".
    ACTIVITY_SCENES = {
        "pipes": "PIPES",
        "rings": "RINGS",
        "brickout": "BRICKOUT",
        "brick out": "BRICKOUT",
        "breakout": "BRICKOUT",
        "break out": "BRICKOUT",
        "turtle island": "TURTLE_ISLAND",
        "parashoot": "PARASHOOT",
        "parachute": "PARASHOOT",
        "puzzle": "PUZZLES",
        "crossword": "CROSSWORD",
        "missing bubble": "MISSING_BUBBLE",
        "gap guru": "GAP_GURU",
        "type it right": "TYPE_IT_RIGHT",
        "frogger": "FROGGER",
        "radar": "RADAR",
        "tetris": "TETRIS",
        "memory cards": "MEMMORY_CARDS",
        "hangwords": "HANGWORDS",
        "hang words": "HANGWORDS",
        "bee careful": "BEE_CAREFUL",
        "echo order": "ECHO_ORDER",
        "translation wiz": "TRANSLATION_WIZ",
        "lexi match": "UNSCRAMBLE_QUIZ",
        "unscramble": "UNSCRAMBLE_QUIZ",
        "i spy": "ISPY",
        "ispy": "ISPY",
    }

    def _infer_activity_scene(self, tc_name: str, description: str = "",
                              nodeid: str = ""):
        """Scene name if the Rally case is about completing a game activity.

        The activity is named in different places depending on who wrote the
        case: the title ("Pipes Activity - ..."), the Rally Test Folder (the
        nodeid path carries it, e.g. ``TF289_Brickout``), or only the body
        ("Component: Brickout Activity"). All three are searched, longest
        keyword first, so "break out" is not shadowed by a shorter match.
        """
        title = (tc_name or "").lower()
        folder = (nodeid or "").replace("_", " ").replace("/", " ").lower()
        body = self._clean_html(description).lower()

        for haystack in (title, folder, body):
            best = None
            for kw, scene in self.ACTIVITY_SCENES.items():
                if kw in haystack and (best is None or len(kw) > len(best[0])):
                    best = (kw, scene)
            if best:
                return best[1]
        return None

    def activity_aliases(self, scene: str):
        """Every keyword that maps to ``scene`` — what the thumb might say."""
        return [kw for kw, s in self.ACTIVITY_SCENES.items() if s == scene]

    # A guest case is one where the app is used WITHOUT an account. It is
    # recognised first, before every other type, because guest cases describe
    # themselves in the words of the flows they exercise: "Guest opens the
    # Events page" is a page case by keyword, "Guest solves Tetris" an activity
    # case, "Guest mode - no login" a login case. All of those templates start
    # by typing credentials the case does not have, so losing the guest signal
    # produces a test that exercises the wrong thing.
    GUEST_PHRASES = (
        "guest", "free trial", "without logging in", "without login",
        "without an account", "without account", "no account", "not logged in",
        "no login", "skip login", "anonymous", "visitor", "trial mode",
    )

    @classmethod
    def _is_guest_case(cls, tc_name: str, description: str = "", nodeid: str = "",
                       validation: Optional[Dict[str, str]] = None) -> bool:
        """True when the case is about using the app without logging in.

        Searches the title, the Rally Test Folder (carried in the nodeid path),
        the description AND the validation text, because the route into guest
        mode is prose and may only be spelled out in Validation Input.
        """
        hay = cls._haystack(tc_name, description, nodeid)
        v = validation or {}
        hay += " " + cls._clean_html(
            f"{v.get('input', '')} {v.get('expected', '')}").lower()
        # Whole phrases only, and never as the head of a hyphenated compound:
        # a login case reading "no account-specific login errors occur" is not a
        # guest case, and "guest" must not be found inside "guestAr".
        return any(re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9-])", hay)
                   for p in cls.GUEST_PHRASES)

    def _infer_test_type(self, tc_name: str, description: str = "",
                         nodeid: str = "", validation: Optional[Dict[str, str]] = None) -> str:
        """Infer test type from the test case name (and its folder/description)."""
        lower = tc_name.lower()
        negative_words = ("invalid", "incorrect", "wrong", "empty", "locked",
                          "disabled", "negative", "failure")
        is_login = any(k in lower for k in ("login", "log in", "sign in", "credential"))
        is_negative = any(w in lower for w in negative_words)
        # FIRST: a guest case never logs in, whatever else it mentions.
        if self._is_guest_case(tc_name, description, nodeid, validation):
            return "guest"
        if is_login and is_negative:
            return "login_negative"
        if is_login:
            return "login_positive"
        # Negative flows whose name omits "login" but clearly concern auth
        # (e.g. "Empty Fields", "Locked/Disabled Account", "Invalid Credentials").
        if is_negative and any(k in lower for k in ("account", "field", "password", "credential", "user")):
            return "login_negative"
        if any(k in lower for k in ("logout", "log out", "sign out")):
            return "logout"
        # A TASKS case is about SOLVING a task -- opening it, answering its
        # questions, submitting -- as opposed to merely opening the Tasks
        # screen. Checked before the page rule, which would otherwise claim
        # it and generate a test that opens a screen and passes.
        if not is_negative and self._is_tasks_case(tc_name, description,
                                                   nodeid, validation):
            return "tasks"
        # Treasure Island is its own flow (missions -> an island -> a building).
        # Checked BEFORE the activity and page rules because a Treasure Island
        # case both names activities ("complete the activity it opens") and is a
        # hub FEATURE — either rule would otherwise claim it and generate a test
        # that plays a map level, or one that only opens the screen.
        if not is_negative and self._is_treasure_island_case(
                tc_name, description, nodeid, validation):
            return "treasure_island"
        # An EVENT case is about PLAYING an event — its levels, its score, its
        # leaderboard — as opposed to merely opening the Events page. Checked
        # BEFORE the exam and activity rules for a reason: an event case has to
        # say what does NOT award score ("exams award coins only"), and that one
        # word made TC1188 generate an exam test.
        if not is_negative and self._is_event_case(tc_name, description, nodeid, validation):
            return "event"
        # Positive "finish the <game> activity" cases -> full playthrough test.
        if self._infer_activity_scene(tc_name, description, nodeid) and not is_negative:
            return "activity"
        # Exam cases ("Solve exam pages successfully", folder TF187_Exams).
        if not is_negative and self._is_exam_case(tc_name, description, nodeid):
            return "exam"
        # "Solve the Wordle daily game" -> play it. Checked BEFORE "page",
        # because Daily Games is also a hub feature: opening the page and
        # winning the game are different tests.
        if not is_negative and self._infer_daily_game(tc_name, description, nodeid):
            return "daily"
        # "Open the Events page" and friends -> click the hub button, check it opened.
        if not is_negative and self._infer_feature(tc_name, description, nodeid):
            return "page"
        return "generic"

    # Doing something INSIDE a task, rather than looking at the Tasks screen.
    _TASK_DO_WORDS = ("solve", "answer", "submit", "send", "score", "checked",
                      "question")

    @classmethod
    def _is_tasks_case(cls, tc_name: str, description: str = "", nodeid: str = "",
                       validation: Optional[Dict[str, str]] = None) -> bool:
        """Is this case about solving a TASK?

        The Tasks test folders (TF212 and its children) are the strongest
        signal; otherwise the case has to mention tasks AND doing something
        with one, so "Open the Tasks page" stays an ordinary page case.
        """
        v = validation or {}
        hay = " ".join([tc_name or "", description or "", nodeid or "",
                        str(v.get("input", "")), str(v.get("expected", ""))]).lower()
        if re.search(r"tf21[2-7]", (nodeid or "").lower()):
            return True
        if not re.search(r"(?<![a-z])tasks?(?![a-z])", hay):
            return False
        return any(word in hay for word in cls._TASK_DO_WORDS)

    @classmethod
    def _is_treasure_island_case(cls, tc_name: str, description: str = "",
                                 nodeid: str = "",
                                 validation: Optional[Dict[str, str]] = None) -> bool:
        """Is this case about Treasure Island?

        The feature names itself in every case that concerns it (the folder is
        called "Treasure Island" too), so the name is the whole test — no
        keyword guessing needed.
        """
        v = validation or {}
        hay = " ".join([tc_name or "", description or "", nodeid or "",
                        str(v.get("input", "")), str(v.get("expected", ""))]).lower()
        return "treasure island" in hay or "treasure_island" in hay

    # Playing an event, as opposed to merely opening the Events page: the case
    # talks about the event AND about doing something inside it.
    _EVENT_PLAY_WORDS = ("leaderboard", "score", "solve", "play", "complete",
                         "winner", "level")

    @classmethod
    def _is_event_case(cls, tc_name: str, description: str = "", nodeid: str = "",
                       validation: Optional[Dict[str, str]] = None) -> bool:
        """Is this case about playing an EVENT?"""
        hay = cls._haystack(tc_name, description, nodeid)
        if validation:
            hay += " " + cls._clean_html(
                f"{validation.get('input', '')} {validation.get('expected', '')}").lower()
        # "event" as a whole word — not "EventSystem", not "prevent".
        if not re.search(r"(?<![a-z])events?(?![a-z])", hay):
            return False
        return any(word in hay for word in cls._EVENT_PLAY_WORDS)

    # Playing a daily game, as opposed to merely opening the Daily Games page.
    _SOLVE_VERBS = ("solve", "play", "complete", "finish", "win", "guess")

    @classmethod
    def _infer_daily_game(cls, tc_name: str, description: str = "", nodeid: str = ""):
        """Which daily game the case is about ("wordle" / "word connect"), or None."""
        from Utilities.utilsdemo import DAILY_GAMES

        hay = cls._haystack(tc_name, description, nodeid)
        if not any(v in hay for v in cls._SOLVE_VERBS):
            return None
        for key in DAILY_GAMES:
            if key in hay:
                return key
        # "solve the daily game" with no game named is ambiguous — not a match.
        return None

    # Cases that are not about the Unity client at all. AltTester cannot drive
    # these, so they must stay honest stubs instead of being wired to whatever
    # buttons happened to be on screen.
    OUT_OF_SCOPE = (
        ("vt-crm", "the VT-CRM admin system (web), not the Unity client"),
        ("crm", "the CRM (web), not the Unity client"),
        ("admin panel", "an admin panel (web), not the Unity client"),
        ("dashboard", "a web dashboard, not the Unity client"),
        ("website", "a website, not the Unity client"),
        ("web app", "a web app, not the Unity client"),
        ("browser", "a browser, not the Unity client"),
        ("endpoint", "a backend API, not the Unity client"),
    )

    @classmethod
    def _haystack(cls, tc_name: str, description: str = "", nodeid: str = "") -> str:
        """Title + Rally folder (carried in the nodeid path) + body, lowercased."""
        return " ".join((
            (tc_name or "").lower(),
            (nodeid or "").replace("_", " ").replace("/", " ").replace("-", "-").lower(),
            cls._clean_html(description).lower(),
        ))

    @classmethod
    def out_of_scope(cls, tc_name: str, description: str = "", nodeid: str = ""):
        """Why this case cannot be automated against the game, or None.

        Matched on whole words: as bare substrings these keywords fire on
        ordinary client prose ("no account is needed, unlike the dashboard" is
        not a CRM case), and because this check runs BEFORE type dispatch a
        false hit refuses a perfectly automatable case with a wrong reason.
        """
        hay = cls._haystack(tc_name, description, nodeid)
        for keyword, reason in cls.OUT_OF_SCOPE:
            if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", hay):
                return reason
        return None

    # Verbs that make a case "open this screen and check it is there".
    _PAGE_VERBS = ("open", "navigat", "access", "display", "view", "show",
                   "enter", "load", "launch", "reach")

    @classmethod
    def _infer_feature(cls, tc_name: str, description: str = "", nodeid: str = ""):
        """Which start-screen feature the case is about ("events", ...), or None.

        Needs BOTH a feature name and an open/navigate verb, so a case that
        merely mentions the map in passing is not mistaken for a page test.
        """
        from Utilities.utilsdemo import APP_FEATURES

        hay = cls._haystack(tc_name, description, nodeid)
        if not any(v in hay for v in cls._PAGE_VERBS):
            return None
        best = None
        for key in APP_FEATURES:
            if key in hay and (best is None or len(key) > len(best)):
                best = key
        return best

    @classmethod
    def _is_exam_case(cls, tc_name: str, description: str = "", nodeid: str = "") -> bool:
        """True when the case is about taking an exam.

        Checked in the title, the Rally Test Folder (carried in the nodeid path)
        and the body, the same places the activity is looked for. Word-bounded
        so "examine"/"example" don't count.
        """
        haystack = " ".join((
            (tc_name or "").lower(),
            (nodeid or "").replace("_", " ").replace("/", " ").lower(),
            cls._clean_html(description).lower(),
        ))
        return bool(re.search(r"\bexams?\b", haystack))

    def _generate_test_code(
        self,
        tc_id: str,
        tc_name: str,
        test_type: str,
        user_data: Dict[str, str],
        func_name: str,
        description: str = "",
        steps: Optional[List[Dict[str, Any]]] = None,
        validation: Optional[Dict[str, str]] = None,
        nodeid: str = "",
        title_hint: str = "",
    ) -> str:
        """Generate pytest code based on test type."""
        steps = steps or []
        # Scope beats type: a CRM/web case can read exactly like a client case
        # ("Open the Events page"), and wiring it to the game would be a test
        # that passes while checking the wrong product.
        scope_note = self.out_of_scope(tc_name, description, nodeid)
        if scope_note:
            return self._gen_stub(tc_id, tc_name, func_name, description, steps,
                                  reason=scope_note)
        if test_type == "guest":
            # Guest first, and with no user_data at all: the credential scraper
            # picks up things like "Username: N/A" from a description, and any
            # template that sees a username emits a login.
            return self._gen_guest(tc_id, tc_name, func_name, description, steps,
                                   validation=validation)
        if test_type == "login_positive":
            return self._gen_login_positive(tc_id, tc_name, user_data, func_name, description, steps)
        elif test_type == "login_negative":
            return self._gen_login_negative(tc_id, tc_name, user_data, func_name, description, steps)
        elif test_type == "logout":
            return self._gen_logout(tc_id, tc_name, func_name, description, steps)
        elif test_type == "activity":
            return self._gen_activity(tc_id, tc_name, user_data, func_name,
                                      description, steps, validation,
                                      nodeid=nodeid, title_hint=title_hint)
        elif test_type == "tasks":
            return self._gen_tasks(tc_id, tc_name, user_data, func_name,
                                   description, steps, validation)
        elif test_type == "treasure_island":
            return self._gen_treasure_island(tc_id, tc_name, user_data, func_name,
                                             description, steps, validation)
        elif test_type == "event":
            return self._gen_event(tc_id, tc_name, user_data, func_name,
                                   description, steps, validation)
        elif test_type == "exam":
            return self._gen_exam(tc_id, tc_name, user_data, func_name,
                                  description, steps, validation)
        elif test_type == "page":
            return self._gen_page(tc_id, tc_name, user_data, func_name,
                                  description, steps, nodeid=nodeid,
                                  validation=validation)
        elif test_type == "daily":
            return self._gen_daily(tc_id, tc_name, user_data, func_name,
                                   description, steps, nodeid=nodeid)
        else:
            return self._gen_stub(tc_id, tc_name, func_name, description, steps,
                                  reason=self.out_of_scope(tc_name, description, nodeid))

    # -----------------------------------------------------------------
    # Shared content helpers — turn the Rally case into readable content
    # so generated files are never "empty".
    # -----------------------------------------------------------------
    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML/entities from a Rally rich-text field to plain text."""
        if not text:
            return ""
        t = re.sub(r"<[^>]+>", " ", str(text))
        for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                     ("&gt;", ">"), ("&#39;", "'"), ("&quot;", '"')):
            t = t.replace(a, b)
        return re.sub(r"\s+", " ", t).strip()

    @staticmethod
    def _py_str(text: str, limit: int = 300) -> str:
        """Rally text made safe to embed in a double-quoted Python literal.

        Rally prose routinely contains quotes ('the exam level ("Level: N")'),
        backslashes and braces. Dropped straight into a template they produce a
        file that will not even parse — the generated test then fails at
        COLLECTION, which looks like "generate is broken" rather than like a
        test that needs work. So: one line, no double quotes, no backslashes,
        no braces (the templates interpolate into f-strings), and bounded length.
        """
        t = re.sub(r"\s+", " ", str(text or "")).strip()
        t = t.replace("\\", "/").replace('"', "'")
        t = t.replace("{", "(").replace("}", ")")
        if len(t) > limit:
            t = t[:limit].rstrip() + "..."
        return t

    @staticmethod
    def _doc_safe(text: str) -> str:
        """Text that cannot break out of the triple-quoted docstring it lands in."""
        t = str(text or "").replace('"""', "'''")
        # A docstring may not end on a backslash — it would escape the closing quotes.
        return t.rstrip("\\")

    @classmethod
    def _doc_block(cls, tc_id: str, tc_name: str, description: str,
                   steps: List[Dict[str, Any]]) -> str:
        """Docstring body: Rally description + numbered steps."""
        lines = [f"{tc_id} — {tc_name}", "",
                 "Auto-generated from Rally (Method = Automated)."]
        desc = cls._clean_html(description)
        if desc:
            lines += ["", "Description:", f"    {desc}"]
        step_lines = []
        for i, s in enumerate(steps or [], 1):
            inp = cls._clean_html(s.get("input", ""))
            exp = cls._clean_html(s.get("expected", ""))
            if not inp and not exp:
                continue
            step_lines.append(f"    {i}. {inp}" if inp else f"    {i}.")
            if exp:
                step_lines.append(f"       Expected: {exp}")
        if step_lines:
            lines += ["", "Steps (from Rally):"] + step_lines
        else:
            lines += ["", "(No test steps recorded in Rally — add them to the case, then re-sync.)"]
        return cls._doc_safe("\n".join(lines))

    @classmethod
    def _body_scaffold(cls, steps: List[Dict[str, Any]]) -> str:
        """Body comments listing the real Rally steps for the implementer."""
        out = []
        for i, s in enumerate(steps or [], 1):
            inp = cls._clean_html(s.get("input", ""))
            exp = cls._clean_html(s.get("expected", ""))
            out.append(f"    # Step {i}: {inp}" if inp else f"    # Step {i}:")
            if exp:
                out.append(f"    #   Expected: {exp}")
        if not out:
            out = ["    # (No steps recorded in Rally — add them to the case and re-sync.)"]
        return "\n".join(out)

    def _get_test_func_name(self, tc_id: str, tc_name: str) -> str:
        """Canonical test function name (matches the file stem and nodeid).

        Delegates to the shared naming rules so the function name can never
        drift from what ``rally_api`` writes into the nodeid.
        """
        return rally_naming.test_identifier(tc_id, tc_name)

    def _gen_login_positive(self, tc_id, tc_name, user_data, test_func_name,
                            description="", steps=None) -> str:
        """Generate positive login test. Skips honestly if the Rally case has
        no credentials (rather than running with a 'CHANGE_ME' placeholder)."""
        username = user_data.get("username") or "CHANGE_ME"
        password = user_data.get("password") or ""
        creds_missing = username == "CHANGE_ME"
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        # Guard rather than run a meaningless login when no credentials exist.
        guard = "@pytest.mark.stub\n" if creds_missing else ""
        guard += (
            f'@pytest.mark.skip(reason="{tc_id}: no credentials on the Rally case. '
            f'Add Username/Password to the case, then re-sync.")\n'
            if creds_missing else ""
        )

        return f'''"""
{doc}
"""

import time
import pytest
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver
    login_page = LoginPage(driver)

    if not login_page.is_open():
        try:
            from Utilities import utilsdemo
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
            time.sleep(2)
        except Exception:
            pass

    login_page.wait_until_open(timeout=20)

    username = "{username}"
    password = "{password}"

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(5)

    assert StartScreen(driver).is_present("GO-Map"), \\
        f"Login failed: GO-Map not found after login ({{TC_ID}})"
'''

    def _gen_login_negative(self, tc_id, tc_name, user_data, test_func_name,
                            description="", steps=None) -> str:
        """Generate negative login test — a real check that login is rejected."""
        if "empty" in tc_name.lower():
            username, password = "", ""
        else:
            username = user_data.get("username") or "invalid_user"
            password = user_data.get("password") or "invalid_pass"
        doc = self._doc_block(tc_id, tc_name, description, steps or [])

        return f'''"""
{doc}
"""

import time
from Pages.LoginPage import LoginPage

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


def {test_func_name}(altdriver):
    driver, _platform = altdriver
    login_page = LoginPage(driver)

    if not login_page.is_open():
        try:
            from Utilities import utilsdemo
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
            time.sleep(2)
        except Exception:
            pass

    login_page.wait_until_open(timeout=20)

    username = "{username}"
    password = "{password}"

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(3)

    # Negative expectation: login must be rejected. Either we stay on the login
    # screen, or an error/notification is shown. (LoginPage exposes get_notif_text()
    # and is_open(); there is no error_visible().)
    still_on_login = login_page.is_open()
    notif = login_page.get_notif_text()
    assert still_on_login or notif, \\
        f"Expected login to be rejected but it was accepted ({{TC_ID}})"
'''

    def _gen_logout(self, tc_id, tc_name, test_func_name,
                    description="", steps=None) -> str:
        """Generate logout test."""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        return f'''"""
{doc}
"""

import time
from Pages.LoginPage import LoginPage
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


def {test_func_name}(altdriver):
    driver, _platform = altdriver

    utilsdemo.call_method(driver, "AltTesterUtils", "Logout")
    time.sleep(2)

    assert LoginPage(driver).is_open(), \\
        f"Logout failed: not on login screen ({{TC_ID}})"
'''

    def _gen_activity(self, tc_id, tc_name, user_data, test_func_name,
                      description="", steps=None, validation=None,
                      nodeid="", title_hint="") -> str:
        """Full playthrough test for a game activity, composed from the proven
        utils (login -> map level -> find the activity in it -> solve -> logout).

        Everything case-specific is read from the Rally case itself:
        credentials and the map level number come from the description, the
        target scene from the case name/folder/description, and the validation
        fields become the docstring/assert context. Missing pieces produce an
        honest skip, never a false pass.

        ``title_hint`` is the label the activity actually shows on its thumb,
        confirmed on the live app at generation time (MCP). With it the test
        clicks the right activity straight away instead of opening each one to
        see what it is.
        """
        scene = self._infer_activity_scene(tc_name, description, nodeid) or "UNKNOWN"
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        clean_desc = self._clean_html(description)
        # The map level to click. Prefer an explicit marker ("Map level: 49" /
        # "click level 49") over incidental level mentions like "Account is at
        # level 44", which describes progress, not the target level.
        m = (re.search(r"(?:map|click(?:\s*on)?)\s*level\s*[:#]?\s*(\d+)",
                       clean_desc, re.IGNORECASE)
             or re.search(r"level\s*[:#]?\s*(\d+)", clean_desc, re.IGNORECASE))
        level = int(m.group(1)) if m else -1

        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        validation = validation or {}
        v_in = self._clean_html(validation.get("input", ""))
        v_exp = self._clean_html(validation.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        missing = []
        if not username:
            missing.append("credentials (Username/Password)")
        if level < 0:
            missing.append('the map level ("level N")')
        guard = ""
        if missing:
            reason = (f"{tc_id}: description is missing " + " and ".join(missing)
                      + ". Add it to the Rally case, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        expected_note = self._py_str(v_exp or f"{scene} activity completed successfully")

        # The thumb label. Confirmed on the live app when generation could read
        # it (MCP); otherwise left empty on purpose, so utilsdemo falls back to
        # its own aliases instead of hunting for a label we only guessed.
        title = (title_hint or "").strip()
        title_src = ("read from the live app at generation time" if title
                     else "not confirmed live — utilsdemo matches its known aliases")

        return f'''"""
{doc}
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

ACTIVITY_SCENE = "{scene}"
# Label printed on the activity's thumb in the level ({title_src}). The test
# clicks that thumb directly instead of opening activities until it finds the
# right one.
ACTIVITY_TITLE = "{title}"
MAP_LEVEL = {level}          # from the Rally description
USERNAME = "{username}"
PASSWORD = "{password}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description. When several
    #    cases run in one session with the same user, the login is skipped and
    #    the test continues from the map the previous case returned to.
    utilsdemo.ensure_logged_in(driver, USERNAME, PASSWORD)
    time.sleep(2)

    # 2. Open the map level named in the description. Self-recovering: whatever
    #    screen the app is on, it backs out to the map (and logs in again if the
    #    session dropped) before clicking the level.
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL,
                                        username=USERNAME, password=PASSWORD), \\
        f"{{TC_ID}}: could not open level {{MAP_LEVEL}} on the map"

    # 3. Get into the level's activity selection (handles intro/vending flow)
    assert utilsdemo.open_level_to_activities(driver), \\
        f"{{TC_ID}}: activity selection screen was not reached"

    # 4. Find the {scene} activity in this level and play it to completion.
    #    The thumb is chosen by its printed title (ACTIVITY_TITLE), so the test
    #    never plays a different activity by mistake.
    #    On any failed assert below the test stays on the failing screen, so
    #    the failure screenshot (conftest hook) shows the actual state.
    result = utilsdemo.solve_activity_in_level(driver, ACTIVITY_SCENE,
                                               title_hint=ACTIVITY_TITLE)
    assert result["found"], \\
        f"{{TC_ID}}: {scene} activity was not found in level {{MAP_LEVEL}}"
    assert result["total"] > 0 and result["done"] >= result["total"], (
        f"{{TC_ID}}: {scene} did not complete — progress "
        f"{{result['done']}}/{{result['total']}}. Expected: {expected_note}")
    assert result["feedback"], \\
        f"{{TC_ID}}: {scene} reached {{result['done']}}/{{result['total']}} but the final feedback screen never appeared"

    # 5. Clean state for the next test case: back to the level map (no logout —
    #    the next case in this run reuses the session and just clicks its level)
    utilsdemo.return_to_map(driver)
'''

    def _gen_exam(self, tc_id, tc_name, user_data, test_func_name,
                  description="", steps=None, validation=None) -> str:
        """Exam playthrough, composed from the proven utils.

        An exam is a node on the map like any other level, so navigation is the
        activity route (login -> click the level number from the description).
        From there ``solve_exam_pages`` runs the same per-page type detection
        and solvers the runner's ``exam_only`` mode uses, then submits.

        As with activities, a missing credential or level produces an honest
        skip rather than a test that passes without checking anything.
        """
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        clean_desc = self._clean_html(description)
        # "Level: 40 (Exam)" / "map level 40" — same rule as activity cases.
        m = (re.search(r"(?:map|click(?:\s*on)?)\s*level\s*[:#]?\s*(\d+)",
                       clean_desc, re.IGNORECASE)
             or re.search(r"level\s*[:#]?\s*(\d+)", clean_desc, re.IGNORECASE))
        level = int(m.group(1)) if m else -1

        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        validation = validation or {}
        v_in = self._clean_html(validation.get("input", ""))
        v_exp = self._clean_html(validation.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        missing = []
        if not username:
            missing.append("credentials (Username/Password)")
        if level < 0:
            missing.append('the exam level ("Level: N")')
        guard = ""
        if missing:
            reason = (f"{tc_id}: description is missing " + " and ".join(missing)
                      + ". Add it to the Rally case, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        expected_note = self._py_str(v_exp or "all 3 exam pages solved and submitted")

        return f'''"""
{doc}
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync so the level/credentials stay
# current with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

MAP_LEVEL = {level}          # the exam node, from the Rally description
USERNAME = "{username}"
PASSWORD = "{password}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # 1. Login with the credentials from the Rally description (skipped when a
    #    previous case in this run already logged this user in).
    utilsdemo.ensure_logged_in(driver, USERNAME, PASSWORD)
    time.sleep(2)

    # 2. Open the exam level named in the description. An exam sits on the map
    #    like any other level, so this is the same self-recovering navigation as
    #    an activity: back out to the map from wherever the app is, re-login if
    #    the session dropped, then click the level.
    assert utilsdemo.enter_level_number(driver, MAP_LEVEL,
                                        username=USERNAME, password=PASSWORD), \\
        f"{{TC_ID}}: could not open level {{MAP_LEVEL}} on the map"

    # 3. Get past the intro to the exam pages themselves
    assert utilsdemo.open_exam(driver), \\
        f"{{TC_ID}}: the exam did not open at level {{MAP_LEVEL}}"

    # 4. Solve every page (type is detected per page) and submit. On a failed
    #    assert the test stays on the failing screen, so the failure screenshot
    #    (conftest hook) shows the actual state.
    result = utilsdemo.solve_exam_pages(driver, label=f"{{TC_ID}} level {{MAP_LEVEL}}")
    # Exams are not always 3 pages — check every page the exam actually has.
    assert result["total"] and result["parts"] == result["total"], (
        f"{{TC_ID}}: answered {{result['parts']}}/{{result['total']}} exam pages. "
        f"Expected: {expected_note}")
    assert not result["problems"], (
        f"{{TC_ID}}: exam pages failed — " + " | ".join(result["problems"]))
    assert result["submitted"], \\
        f"{{TC_ID}}: the exam was solved but never submitted/collected"

    # 5. Clean state for the next test case: back to the level map
    utilsdemo.return_to_map(driver)
'''

    # Phrases that mean the case wants something DONE inside the feature, not
    # merely the feature opened. Deliberately narrow: an ordinary page case
    # ("Open the Events page successfully") matches none of them.
    # Verbs that mean something is DONE inside the feature, not merely looked
    # at. A page case is "open X and check it is there"; the moment a case asks
    # to answer, submit, play or finish anything, the page template cannot
    # honour it. Kept broad on purpose -- a phrase list tuned to one feature is
    # what let TC1192 ("answer every question ... submit ... moves to Sent")
    # through as a passing page test.
    # Verbs that mean something is DONE inside the feature, not merely looked
    # at. A page case is "open X and check it is there"; the moment a case asks
    # to answer, submit, play or finish anything, the page template cannot
    # honour it. Kept broad on purpose -- a list tuned to one feature is what
    # let TC1192 ("answer every question ... submit ... moves to Sent") through
    # as a passing page test.
    #
    # Matched on WORD BOUNDARIES: "played" as a substring also matches
    # "dis-played", which flagged "Verify the Events page is displayed" and
    # would have skipped a perfectly good page case.
    _BEYOND_A_PAGE = (
        "answer", "answers", "answered", "submit", "submitted", "solve",
        "solved", "complete", "completed", "completing", "finish", "finished",
        "play", "plays", "played", "playing", "record", "recorded", "upload",
        "send", "sent", "score", "scored", "progress", "reaches", "reach",
        "increases", "decreases", "correct", "until", "100%",
    )
    _BEYOND_A_PAGE_PHRASES = ("goes up", "raises the", "moves to", "each question",
                              "every question", "must go up")
    # A pure "open the page" case is a handful of steps: launch, log in, tap the
    # button, check it opened. A case with a long script is describing a FLOW,
    # whatever words it happens to use.
    _PAGE_STEP_LIMIT = 5

    @classmethod
    def _asks_for_more_than_a_page(cls, tc_name: str, description: str = "",
                                   validation: Optional[Dict[str, str]] = None) -> bool:
        """Does this case ask for more than opening the screen?

        The page template can only prove a screen appeared. When the case is
        really about doing something in there, generating a passing page test
        hides the gap behind a green tick, so callers turn this into a loud
        skip.

        Judged two ways, because either alone has been fooled: the WORDS used,
        and the SHAPE of the case -- a ten-step script is a flow no matter how
        it is worded.
        """
        v = validation or {}
        hay = " ".join([tc_name or "", description or "",
                        str(v.get("input", "")), str(v.get("expected", ""))]).lower()
        words = set(re.findall(r"[a-z0-9%]+", hay))
        if words & set(cls._BEYOND_A_PAGE):
            return True
        if any(phrase in hay for phrase in cls._BEYOND_A_PAGE_PHRASES):
            return True
        steps = len(re.findall(r"(?:^|[\s>])\d{1,2}\s*[.)]\s", str(v.get("input", ""))))
        return steps >= cls._PAGE_STEP_LIMIT

    def _gen_page(self, tc_id, tc_name, user_data, test_func_name,
                  description="", steps=None, nodeid="", validation=None) -> str:
        """"Open <feature> and check it is there" test.

        Every start-screen feature was surveyed on the live app, so the button,
        the scene it loads and the objects that prove it opened are known
        (``utilsdemo.APP_FEATURES``). The test goes back to the start screen
        from wherever the app is, clicks the button, and fails if the feature
        does not actually come up — a click that lands nowhere is not a pass.
        """
        feature = self._infer_feature(tc_name, description, nodeid) or ""
        from Utilities.utilsdemo import APP_FEATURES
        spec = APP_FEATURES.get(feature, {})
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])

        # Without credentials the test cannot guarantee a logged-in app, and
        # every feature lives behind the login. Skip honestly instead.
        guard = ""
        if not username:
            reason = (f"{tc_id}: no credentials on the Rally case — add "
                      f"Username/Password so the test can reach the start screen, "
                      f"then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')
        elif self._asks_for_more_than_a_page(tc_name, description, validation):
            # This template only proves the screen APPEARED. A case that asks
            # for work INSIDE the feature ("until its progress reaches 100%",
            # "the level goes up") would pass here having done none of it — a
            # green result that verified nothing, which is worse than no test.
            # Skip loudly and name what is missing.
            reason = (f"{tc_id}: this Rally case asks for work inside the feature, "
                      f"but no flow is implemented for it — only 'open the page' is. "
                      f"A pass here would prove nothing. Implement the flow, or "
                      f"reword the case to be about opening the page.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        markers = spec.get("markers") or []
        marker_note = ", ".join(markers) if markers else "its scene"

        return f'''"""
{doc}

Opens "{feature}" from the start screen ({spec.get("button", "?")}) and verifies it
loaded — scene '{spec.get("scene") or "(popup on the start screen)"}',
identified by: {marker_note}.
Feature route surveyed on the live app; see utilsdemo.APP_FEATURES.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

FEATURE = "{feature}"
USERNAME = "{username}"
PASSWORD = "{password}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # Logs in if needed, returns to the start screen from wherever the app is,
    # clicks the feature's button and waits for its scene/markers.
    assert utilsdemo.open_feature(driver, FEATURE,
                                  username=USERNAME, password=PASSWORD), \\
        f"{{TC_ID}}: the {feature} page did not open"

    # Leave the app on the start screen for whatever runs next.
    utilsdemo.return_to_start(driver)
'''

    # The leaderboard lists players by NAME, so a case has to say which name
    # belongs to its account — the username never appears there.
    @classmethod
    def _player_name(cls, description: str = "", validation=None) -> str:
        """The player name a case expects on the leaderboard, or ""."""
        hay = cls._clean_html(description)
        if validation:
            hay += " " + cls._clean_html(
                f"{validation.get('input', '')} {validation.get('expected', '')}")
        m = re.search(r"player\s*name\s*[:\-]\s*([^:]+?)(?=\s{2,}|\s*(?:<|$)|"
                      r"\s+(?:Test Type|Priority|Severity|Username|password|Objective)\b)",
                      hay, re.I)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    def _gen_tasks(self, tc_id, tc_name, user_data, test_func_name,
                   description="", steps=None, validation=None) -> str:
        """Solve a task set by the teacher, and check the score on the server.

        The whole flow lives in ``utilsdemo.tasks_check``: open the Tasks
        screen, open an OPEN task, answer every question from the backend
        ANSWER KEY -- correctly, except for however many the case wants wrong
        on purpose -- submit, confirm, then read back from the server what was
        actually stored and what it scored.
        """
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        v = validation or {}
        v_in = self._clean_html(v.get("input", ""))
        v_exp = self._clean_html(v.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        hay = (self._clean_html(description) + " " + v_in).lower()
        # "answer 2 of them incorrectly" -> 2. No number named -> all correct.
        m = re.search(r"(\d+)\s+(?:questions?\s+)?(?:in)?correct", hay)
        wrong = int(m.group(1)) if m else 0
        # The answer key and the score check need the class and the player id.
        cm = re.search(r"class\s*id\s*:?\s*(\d+)", hay)
        um = re.search(r"user\s*id\s*:?\s*(\d+)", hay)
        class_id = cm.group(1) if cm else "None"
        user_id = um.group(1) if um else "None"

        guard = ""
        missing = []
        if not username:
            missing.append("Username/password")
        # Neither the player id nor the class is asked for any more: both come
        # from the account itself, via the same login the app uses. A number
        # typed into a case goes stale the moment the case is pointed at another
        # account, and a stale id looks exactly like a submit that vanished.
        if missing:
            reason = (f"{tc_id}: the Rally case is missing " + " and ".join(missing) +
                      ". Without it the task cannot be answered from the answer key "
                      "nor its score checked, so a run would prove nothing. Add it to "
                      "the description, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        return TASKS_TEMPLATE.format(
            doc=doc, tc_id=tc_id, username=self._py_str(username),
            password=self._py_str(password), class_id=class_id, user_id=user_id,
            wrong=wrong, guard=guard, func=test_func_name)

    def _gen_treasure_island(self, tc_id, tc_name, user_data, test_func_name,
                             description="", steps=None, validation=None) -> str:
        """Play Treasure Island's missions and check that its LEVEL goes up.

        The flow lives in ``utilsdemo.treasure_island_check``: open the mission
        list from the clipboard, and for each required skill press its Play,
        tap a building on that skill's island and complete the activity it
        starts, until the skill reads 100%.

        SPEAKING has no solver in this framework. The test does not fail for
        it — it asserts that the run SAID it was skipped, because silently
        ignoring a required skill is what would make this case lie.
        """
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        v = validation or {}
        v_in = self._clean_html(v.get("input", ""))
        v_exp = self._clean_html(v.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        guard = ""
        if not username:
            reason = (f"{tc_id}: the Rally case is missing Username/password. "
                      f"Add it to the description, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        return f'''"""
{doc}

Treasure Island, surveyed on the live app (2026-08-17):
    GO-Treasure_Island -> scene TreasureIsland (a first entry plays an intro; "Skip" leaves it)
    TaskSummary (the clipboard) opens the mission list: LevelText, PercentText,
    and one CategorySummaryRow(Clone) per required skill
    a row's PlayButton ZOOMS to that skill's island - it does NOT change scene
    the islands are objects: Category_1-Speaking .. Category_5-Listening
    ("Sentences" is Category_3-Context - the row and the island disagree)
    a building (GO-TI-<Activity> Variant(Clone)) opens a panel whose PlayButton
    loads the real activity scene, which the framework's solvers then play
SPEAKING has no solver here, so it is skipped and the result says so.
"""

import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "{self._py_str(username)}"
PASSWORD = "{self._py_str(password)}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # Open the missions, play each automatable skill's island until that skill
    # reads 100%, then read the Treasure Island level again. Never raises: the
    # whole picture comes back in the report, so a failure says which skill
    # stopped where.
    result = utilsdemo.treasure_island_check(
        driver, username=USERNAME, password=PASSWORD, tc_id=TC_ID)

    # Say what this run did and did NOT cover, pass or fail. An assertion
    # message is only ever seen on a failure, and a green result that never
    # mentions the skills with no automation reads as though every required
    # skill was verified.
    print(f"{{TC_ID}} RESULT: {{result['note']}}")

    assert result["level_before"], (
        f"{{TC_ID}}: the mission list never showed a level - {{result['note']}}")

    # The user's rule, asserted rather than assumed: Speaking has no automation,
    # so the run must SAY it skipped it instead of passing over it quietly.
    assert "Speaking" in result["skipped"] or not any(
        s.lower() == "speaking" for s in result["skills"]), (
        f"{{TC_ID}}: Speaking is a required skill with no automation, but the run "
        f"did not report it as skipped (skipped: {{result['skipped']}})")

    assert not result["problems"], (
        f"{{TC_ID}}: playing the missions hit problems: {{result['problems']}}. "
        f"Played: {{result['plays']}}")

    # The point of the case: every skill this framework CAN play reaches 100%.
    unfinished = {{k: v.get("after") for k, v in result["skills"].items()
                  if k not in result["skipped"] and (v.get("after") or 0) < 0.999}}
    assert not unfinished, (
        f"{{TC_ID}}: these skills did not reach 100%: {{unfinished}}. "
        f"Played: {{result['plays']}}. {{result['note']}}")

    # ... and the island's overall never goes backwards. NOT "the level went
    # up": measured live, the overall is the MEAN of all required skills, so
    # while Speaking has no solver the ceiling is 75% and the level cannot move
    # however well the run goes. result["level_rose"] carries that fact, ready
    # to be asserted the day Speaking becomes automatable.
    assert result["percent_after"] >= result["percent_before"], (
        f"{{TC_ID}}: Treasure Island went BACKWARDS, "
        f"{{result['percent_before']}}% -> {{result['percent_after']}}%. {{result['note']}}")

    assert result["ok"], (
        f"{{TC_ID}}: the Treasure Island run did not pass - {{result['note']}}")
'''

    def _gen_event(self, tc_id, tc_name, user_data, test_func_name,
                   description="", steps=None, validation=None) -> str:
        """Play an event's levels and check its leaderboard.

        The whole flow lives in ``utilsdemo.event_score_check``: log out and
        back in (a leaderboard row is matched by NAME, so a leftover session
        would measure the wrong player), open the running event, solve one
        activity per level, then compare the sum of what those activities
        scored with the row on the leaderboard.

        Scores are read from the ACTIVITY LIST ("80/240" per activity), not
        from the finish screen — the list can be read at any time and shows
        every activity in the level, while the finish screen is gone as soon as
        the run moves on.
        """
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        player = self._player_name(description, validation)
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        v = validation or {}
        v_in = self._clean_html(v.get("input", ""))
        v_exp = self._clean_html(v.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        # How many event levels the case plays. "3 event levels" in the prose
        # decides it; the default matches the case this template was written for.
        hay = (self._clean_html(description) + " " + v_in).lower()
        # "solve EVERY activity" vs "solve one activity" — the case decides.
        solve_all = ("every activit" in hay or "all activit" in hay or "all the activit" in hay)
        # Browsing the events SCREEN (cards, Start, Winners) is a different
        # test from playing an event. Solving activities in a case that only
        # asks to look at the cards would exercise the wrong thing entirely.
        cards_only = (("card" in hay or "browse" in hay or "navigate" in hay)
                      and "winners" in hay and "leaderboard score" not in hay)
        # A case that says "the opened levels" plays whatever the event has
        # unlocked; otherwise the number it names ("3 event levels").
        if re.search(r"open(?:ed)?\s+levels?", hay):
            levels = ()                              # discovered at runtime
        else:
            m = re.search(r"(\d+)\s+event\s+levels?", hay)
            count = max(1, min(int(m.group(1)), 24)) if m else 3
            levels = tuple(range(1, count + 1))

        guard = ""
        missing = []
        if not username:
            missing.append("Username/password")
        if not player:
            missing.append("the player's leaderboard name (\"Player name: ...\")")
        if missing:
            reason = (f"{tc_id}: the Rally case is missing " + " and ".join(missing) +
                      ". Add it to the description, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        cards_body = "" if not cards_only else f'''
    # Browse the event cards ONLY: bring each card to the front, and open what
    # it offers — Start must open that event's map, Winners must open its
    # winners list. Nothing is played here; this case is about the events
    # screen itself.
    result = utilsdemo.event_cards_check(
        driver, username=USERNAME, password=PASSWORD, tc_id=TC_ID)

    assert result["cards"], f"{{TC_ID}}: no event cards on the events screen — {{result['note']}}"
    assert not result["problems"], (
        f"{{TC_ID}}: browsing the event cards hit problems: {{result['problems']}}. "
        f"Visited: {{result['visited']}}")
    assert len(result["visited"]) == result["cards"], (
        f"{{TC_ID}}: only {{len(result['visited'])}} of {{result['cards']}} card(s) "
        f"could be opened — {{result['visited']}}")
    return
'''

        return f'''"""
{doc}

Event flow, surveyed on the live app (2026-08-16):
    GO-Events -> EventSelectionScene -> StartButton -> EventScene (the map)
    level icon "LessonLevelIcon Variant(Clone) N" -> the level's activity list
    each activity shows its score there as "earned/max" (e.g. "80/240")
    LeaderboardButton opens the leaderboard AS AN OVERLAY on the event map
    a leaderboard row is a PlayerName next to a Score
Only ACTIVITY levels award event score; exams award coins and must not change it.
"""

import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

USERNAME = "{username}"
PASSWORD = "{password}"
# The leaderboard lists players by NAME, never by username.
PLAYER_NAME = "{self._py_str(player, 80)}"
# () = whatever the event has OPENED when the test runs.
EVENT_LEVELS = {levels}
# Solve every activity in a level, or just one?
SOLVE_ALL_ACTIVITIES = {solve_all}


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver
{cards_body}
    # Log out and back in first, open the running event, solve one activity in
    # each level, then read the leaderboard. Never raises: the whole picture
    # comes back in the report so a failure says which level scored what.
    result = utilsdemo.event_score_check(
        driver, levels=EVENT_LEVELS, player_name=PLAYER_NAME,
        username=USERNAME, password=PASSWORD, solve_all=SOLVE_ALL_ACTIVITIES,
        tc_id=TC_ID)

    # With no levels named the test plays what the event opened, so the report
    # says which ones those were.
    played_levels = result.get("levels_played") or list(EVENT_LEVELS)
    assert played_levels, f"{{TC_ID}}: the event had no open levels to play — {{result['note']}}"

    # Every level had to open and be played, or the sum below means nothing.
    for level in played_levels:
        detail = result["levels"].get(level, {{}})
        assert detail.get("opened"), (
            f"{{TC_ID}}: event level {{level}} did not open — {{detail.get('note') or result['note']}}")
        assert detail.get("played"), (
            f"{{TC_ID}}: nothing was completed in event level {{level}} — {{result['note']}}")
        assert detail.get("score"), (
            f"{{TC_ID}}: event level {{level}} awarded no score for "
            f"'{{detail.get('played')}}' — an activity level must award score")

    # The player has to BE on the leaderboard before its score can be compared.
    assert result["leaderboard"] is not None, (
        f"{{TC_ID}}: {{PLAYER_NAME!r}} is not on the event leaderboard — {{result['note']}}")

    # The point of the case: what the activities scored is what the leaderboard
    # shows. Exams award coins only, so nothing else may move this number.
    assert result["ok"], (
        f"{{TC_ID}}: the leaderboard shows {{result['leaderboard']}} for {{PLAYER_NAME!r}} "
        f"but the activities scored {{result['earned']}} "
        f"({{ {{lvl: d.get('score') for lvl, d in result['levels'].items()}} }}). "
        f"{{result['note']}}")
'''

    def _gen_daily(self, tc_id, tc_name, user_data, test_func_name,
                   description="", steps=None, nodeid="") -> str:
        """Play a Daily Game (Wordle / Word Connect) to a win.

        Both solvers read the answer out of the game rather than hardcoding it —
        Wordle from ``GameplayManager.word``, Word Connect from the puzzle bank
        on ``GameCanvas`` matched against the letters on the board — so the test
        keeps working as the daily puzzle changes.

        Daily Games are once per day per account: if it has already been played
        the test FAILS with that reason rather than passing on a game it never
        got to play.
        """
        game = self._infer_daily_game(tc_name, description, nodeid) or ""
        username = user_data.get("username") or ""
        password = user_data.get("password") or ""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])

        guard = ""
        if not username:
            reason = (f"{tc_id}: no credentials on the Rally case. Add "
                      f"Username/Password, then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        return f'''"""
{doc}

Plays the "{game}" daily game from the start screen (Daily Games -> Play) and
checks the game reports a win. The answer is read from the game at runtime, so
this keeps working as the daily puzzle changes.

NOTE: daily games are once per day per account. Re-running this on the same day
with {username or "the same user"} fails with "already played today" — that is
deliberate, not a flaky test.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync. Hand-editing? Set MANUAL_EDIT = True.
MANUAL_EDIT = False

DAILY_GAME = "{game}"
USERNAME = "{username}"
PASSWORD = "{password}"


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    result = utilsdemo.solve_daily_game(driver, DAILY_GAME,
                                        username=USERNAME, password=PASSWORD)

    assert result["opened"], \\
        f"{{TC_ID}}: could not start {game} — {{result['note']}}"
    assert result["solved"], \\
        f"{{TC_ID}}: {game} did not report a win — {{result['note']}}"
'''

    # ------------------------------------------------------------------
    # Guest flow (no login)
    # ------------------------------------------------------------------
    # The route into guest mode is written in prose on the Rally case (the user
    # owns it, not this code), so it is PARSED rather than assumed: each step
    # becomes an ordered action, and each action's label becomes a list of
    # candidate Unity object names. The generated test carries that route as
    # data and walks it through utilsdemo, so a wording change in Rally is a
    # data change here — not a new template.

    _GUEST_TYPE_VERBS = ("enter", "type", "input", "fill in", "fill", "write")
    _GUEST_CLICK_VERBS = ("tap", "click", "press", "select", "choose", "hit")
    _GUEST_WAIT_VERBS = ("wait for", "wait until", "wait")
    _GUEST_CHECK_VERBS = ("verify", "confirm", "validate", "check", "ensure", "assert")

    # Object names for the guest entry, read off the live app's own snapshots.
    # The build ships BOTH spellings ("Free Trial" and the misspelled
    # "FreeTrail") plus a "PlayAsGuest" object, so a parsed label is tried
    # against every one of them instead of trusting the Rally wording.
    GUEST_ALIASES = {
        "free trial": ("Free Trial", "FreeTrial", "FreeTrail", "StartFreeTrial",
                       "PlayAsGuest"),
        "guest": ("PlayAsGuest", "GuestButton", "Free Trial", "FreeTrail"),
        "start": ("StartButton", "Start"),
        "next": ("NextButton", "nextButton", "Next"),
        "back": ("BackButton", "backButton", "Back"),
        "map": ("GO-Map",),
    }

    # Labels that name no control at all ("tap anywhere to dismiss").
    _GUEST_VAGUE = ("anywhere", "any where", "screen", "somewhere", "the screen",
                    "anything", "it", "them")

    @classmethod
    def _numbered_steps(cls, text: str) -> List[str]:
        """Split a Rally procedure into ordered step sentences.

        Rally hands this over as one blob whose numbering is the only reliable
        structure — ``_clean_html`` collapses the newlines — so the case's own
        "1." / "2)" numbering is used first, and plain lines are the fallback.
        """
        t = str(text or "").replace("\r", "")
        if not t.strip():
            return []
        parts = [p.strip() for p in re.split(r"(?:^|\s)\d{1,2}[.)]\s+", t) if p.strip()]
        if len(parts) > 1:
            return parts
        return [ln.strip("-•* \t") for ln in t.splitlines() if ln.strip()]

    @classmethod
    def _name_candidates(cls, label: str) -> List[str]:
        """Unity object names a human-written label might refer to.

        "Start Free Trial" -> StartFreeTrial, Start Free Trial, ...,
        FreeTrial, Free Trial (dropping the leading verb), plus the aliases
        actually seen on the app. Order is preference order: the walker clicks
        the first one that is really on screen.
        """
        # "Let's Start" -> also LetsStart, not just the Let/s split.
        tight = re.sub(r"['’]", "", str(label or ""))
        words = re.findall(r"[A-Za-z0-9]+", tight)
        if not words:
            return []
        camel = "".join(w[:1].upper() + w[1:].lower() for w in words)
        spaced = " ".join(words)
        out = [camel, spaced, f"{camel}Button", f"{spaced} Button",
               "_".join(words), camel[:1].lower() + camel[1:]]
        raw_words = re.findall(r"[A-Za-z0-9]+", str(label or ""))
        if raw_words != words:
            out.append("".join(w[:1].upper() + w[1:].lower() for w in raw_words))
        if len(words) > 1:                     # drop a leading verb: "Start Free Trial"
            tail = words[1:]
            out += ["".join(w[:1].upper() + w[1:].lower() for w in tail),
                    " ".join(tail)]
        low = spaced.lower()
        for key, extra in cls.GUEST_ALIASES.items():
            if key in low:
                out += list(extra)
        seen, uniq = set(), []
        for n in out:
            if n and n not in seen:
                seen.add(n)
                uniq.append(n)
        return uniq

    @classmethod
    def _clean_label(cls, raw: str) -> str:
        """Trim a parsed label down to what is likely the control's text."""
        t = re.split(r"[.,;:!?]|\bthen\b|\band\b|\bto\b|\bso\b", str(raw or ""),
                     maxsplit=1)[0]
        t = t.strip().strip("\"'“”‘’()[]")
        # Drop trailing UI nouns — the object is named for the label, not the noun.
        t = re.sub(r"\s+(button|icon|option|tab|toggle|field|input|box|textbox|"
                   r"screen|page|checkbox)$", "", t, flags=re.IGNORECASE).strip()
        return re.sub(r"^(?:the|a|an|on|in)\s+", "", t, flags=re.IGNORECASE).strip()

    @classmethod
    def _guest_action(cls, step: str) -> Dict[str, Any]:
        """One Rally step -> one action for the guest route walker.

        Only the FIRST actionable verb in a step is turned into an action; a
        step that packs several ("wait for X, then select Male") keeps its full
        text so the reader can see what was not automated.
        """
        s = " ".join(str(step or "").split())
        low = s.lower()
        base = {"text": s, "label": "", "value": "", "candidates": []}

        # "Enter guestAr in the Last Name field" -> type into a named field.
        m = re.search(
            r"\b(?:%s)\b\s+[\"'“]?(.+?)[\"'”]?\s+(?:in|into|to)\s+(?:the\s+)?"
            r"[\"'“]?(.+?)[\"'”]?\s*(?:field|input|box|textbox)\b"
            % "|".join(cls._GUEST_TYPE_VERBS), low)
        if m:
            value = s[m.start(1):m.end(1)].strip().strip("\"'“”")
            field = cls._clean_label(s[m.start(2):m.end(2)])
            return {**base, "do": "type", "label": field, "value": value,
                    "candidates": cls._name_candidates(field)}

        # A step that asks for a verification is an ASSERTION, not a press, even
        # when it also contains a press verb ("tap any level greater than 5 —
        # verify it is locked"): the check is the point and it cannot be derived
        # from prose, so it must not become a click on an invented object name.
        if any(v in low for v in cls._GUEST_CHECK_VERBS) or s.startswith(("✅", "✓")):
            return {**base, "do": "check", "label": cls._clean_label(s)}

        # "tap Start Free Trial button" / "select Arabic" -> press a named control.
        # The LAST press verb wins: a step often names a screen with a verb of its
        # own first ("In the 'Choose Your Native Language' screen, select Arabic").
        # Match the VERBS only: a pattern that also captured the tail would
        # consume the rest of the sentence and hide every later verb.
        matches = list(re.finditer(r"\b(?:%s)\b" % "|".join(cls._GUEST_CLICK_VERBS), low))
        if matches:
            tail = re.sub(r"^\s*(?:on\s+|the\s+)*", "", s[matches[-1].end():])
            label = cls._clean_label(tail)
            first_word = label.split()[0].lower() if label.split() else ""
            if label and first_word not in cls._GUEST_VAGUE:
                return {**base, "do": "click", "label": label,
                        "candidates": cls._name_candidates(label)}
            # "tap anywhere on screen to dismiss the parrot" — a real action, but
            # it names no control, so it cannot be automated by name.
            return {**base, "do": "tap_anywhere", "label": label or "anywhere"}

        # "Wait for the 'You Are' screen to appear" -> wait for a marker.
        m = re.search(r"\b(?:%s)\b\s+(?:for\s+|until\s+)?(.+)$" % "|".join(cls._GUEST_WAIT_VERBS), low)
        if m:
            label = cls._clean_label(s[m.start(1):])
            return {**base, "do": "wait", "label": label,
                    "candidates": cls._name_candidates(label)}

        if any(v in low for v in cls._GUEST_CHECK_VERBS) or s.startswith(("✅", "✓")):
            return {**base, "do": "check", "label": cls._clean_label(s)}

        return {**base, "do": "manual"}

    @classmethod
    def _parse_guest_route(cls, description: str = "",
                           validation: Optional[Dict[str, str]] = None,
                           steps: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Everything the guest template needs, parsed out of the Rally case.

        Reads structured steps AND ``validation.input`` AND the description,
        because in this project the procedure lives in Validation Input (the
        synced cases carry no structured steps at all).

        Returns ``{"route": [actions], "entry": int, "todo": [actions],
        "source": str}`` where ``entry`` counts the leading actions that are
        real, resolvable UI interactions — the guest ENTRY. A route with fewer
        than two of those is not a route, and the caller degrades honestly.
        """
        v = validation or {}
        step_texts = []
        source = ""
        for s in steps or []:
            txt = " ".join(x for x in (s.get("input", ""), s.get("expected", "")) if x)
            if txt.strip():
                step_texts.append(txt.strip())
        if step_texts:
            source = "Rally steps"
        if not step_texts and v.get("input"):
            step_texts = cls._numbered_steps(v["input"])
            source = "Rally Validation Input"
        if not step_texts:
            step_texts = cls._numbered_steps(cls._clean_html(description))
            source = "Rally description"

        route = [cls._guest_action(t) for t in step_texts]
        # The entry is the leading run of actions we can actually drive.
        entry = 0
        for a in route:
            if a["do"] in ("click", "type", "wait", "tap_anywhere"):
                entry += 1
            else:
                break
        todo = [a for a in route if a["do"] in ("check", "manual")]
        return {"route": route, "entry": entry, "todo": todo, "source": source}

    # Labels that only navigate the wizard — never a value the case is choosing.
    _GUEST_NAV_LABELS = (
        "free trial", "start free trial", "let's start", "lets start", "start",
        "next", "prev", "previous", "back", "continue", "ok", "yes", "no",
        "done", "finish", "submit", "close", "map", "the map", "skip",
    )

    @classmethod
    def _guest_values(cls, route: List[Dict[str, Any]]) -> Dict[str, Any]:
        """The case's own DATA, pulled out of the parsed route.

        The shape of the onboarding is app knowledge and lives in
        ``utilsdemo.GUEST_ENTRY``; what varies per case is the child's name and
        which option each screen should get. Only those are baked into the test.
        """
        first = last = ""
        options: List[str] = []
        for a in route:
            if a["do"] == "type":
                label = (a["label"] or "").lower()
                if "first" in label:
                    first = a["value"]
                elif "last" in label:
                    last = a["value"]
                elif not first:
                    first = a["value"]
            elif a["do"] == "click":
                label = (a["label"] or "").strip()
                if not label or label.lower() in cls._GUEST_NAV_LABELS:
                    continue
                if label not in options:
                    options.append(label)
        return {"first": first, "last": last, "options": options}

    # Option labels that are not the language: the app asks gender as a label
    # too, and the English level always ends in "Literacy"/"Proficiency".
    _GUEST_GENDER_LABELS = ("male", "female")
    _GUEST_DIFFICULTY_SUFFIXES = ("literacy", "proficiency")

    # The English level a case picks maps to the school GRADE it stands for
    # (user, 2026-08-14), and the grade is what the guest's name carries.
    _GUEST_GRADES = {
        "beginning literacy": "3rd",
        "elementary proficiency": "4th",
        "intermediate proficiency": "5th",
        "advanced proficiency": "6th",
    }

    @classmethod
    def _guest_last_name(cls, options: List[str]) -> str:
        """The guest's last name, carrying the two choices that define the run.

        ``guest`` + the level's GRADE + the language's first two letters —
        "Arabic" + "Beginning Literacy" -> ``guest3rdAr``. A guest has no email
        or id, so this name is the only way to tell one registration from
        another afterwards; deriving it means a case cannot silently register
        under a name that does not match what it selected.

        A level with no grade mapped falls back to its initials, so an unknown
        level still produces a distinct name instead of a colliding one.
        """
        language = difficulty = ""
        for option in options:
            low = (option or "").strip().lower()
            if not low or low in cls._GUEST_GENDER_LABELS:
                continue
            if low.endswith(cls._GUEST_DIFFICULTY_SUFFIXES):
                difficulty = difficulty or option
            elif not language:
                language = option
        if not (language or difficulty):
            return ""
        short = re.sub(r"[^A-Za-z]", "", language)[:2].capitalize()
        key = re.sub(r"\s+", " ", (difficulty or "").strip().lower())
        grade = cls._GUEST_GRADES.get(key) or "".join(
            w[0].upper() for w in re.findall(r"[A-Za-z]+", difficulty))
        return f"guest{grade}{short}"

    def _gen_guest(self, tc_id, tc_name, test_func_name, description="",
                   steps=None, validation=None, elements=None) -> str:
        """Guest-flow test: register through "Start FREE trial", never log in.

        The onboarding route was walked on the live app, so the object names live
        in ``utilsdemo.GUEST_ENTRY`` and the flow in ``utilsdemo.enter_guest_mode``
        — this template only supplies what the Rally case decides: the child's
        name and the option labels (language, English level, gender). No
        USERNAME/PASSWORD is emitted at all; their absence is the reviewable
        proof the test cannot fall back to a login.

        Steps that prose cannot describe (solve an activity in every accessible
        level, take the exam, verify a locked level, clear data) are emitted as
        explicit TODOs rather than guessed at.
        """
        parsed = self._parse_guest_route(description, validation, steps)
        vals = self._guest_values(parsed["route"])
        first = vals["first"]
        options = vals["options"]
        # The last name is DERIVED from the selections (guest + language +
        # difficulty initials), so it always describes the run it registered.
        last = self._guest_last_name(options) or vals["last"]
        todo = parsed["todo"]

        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        v = validation or {}
        v_in = self._clean_html(v.get("input", ""))
        v_exp = self._clean_html(v.get("expected", ""))
        if v_in or v_exp:
            doc += "\n\nValidation (from Rally):"
            if v_in:
                doc += f"\n    Input:    {v_in}"
            if v_exp:
                doc += f"\n    Expected: {v_exp}"

        options_literal = "[" + ", ".join(f'"{self._py_str(o, 60)}"' for o in options) + "]"
        # The guest band is levels 1-5 on the live map (5 is the first exam), so
        # the lesson levels a guest case plays through are 1-3.
        levels_literal = "(1, 2, 3)"

        # The three PROFICIENCY cases also sit the first exam on the map
        # (Rally: "Navigate to the first exam on the map and complete it").
        # A Beginning Literacy case is the one that proves the activities, so it
        # is left to walk the levels only.
        level_label = next((o for o in options
                            if o.strip().lower().endswith(("literacy", "proficiency"))), "")
        solves_exam = level_label.strip().lower().endswith("proficiency")
        # Do not list a step as an unimplemented TODO once the body does it.
        if solves_exam:
            todo = [a for a in todo
                    if "exam" not in (a.get("text", "") or "").lower()]

        n_exam = 6
        n_lock = 7 if solves_exam else 6
        n_todo, n_reset = n_lock + 1, n_lock + 2
        exam_block = "" if not solves_exam else f'''
    # {n_exam}. The first exam on the map (Rally: "Navigate to the first exam on
    #    the map and complete it"). This case is a '{self._py_str(level_label, 40)}'
    #    one, so the exam is the point of it — the Beginning Literacy case is
    #    what proves the activities. WHICH level carries the exam was read off
    #    the live map above (it moves with the language and level the guest
    #    picked), and its icon is pressed BY NAME, never by coordinates.
    exam = utilsdemo.guest_take_exam(driver, level=first_exam)
    assert exam["ok"], (
        f"{{TC_ID}}: the first exam (level {{first_exam}}) was not completed — "
        f"{{exam.get('note')}}. Answered {{exam.get('parts')}}/{{exam.get('total')}} "
        f"page(s), submitted={{exam.get('submitted')}}, "
        f"problems={{exam.get('problems')}}")
'''

        todo_block = "\n".join(
            f"    #   {i}. {self._py_str(a['text'], 150)}"
            for i, a in enumerate(todo, 1)
        ) or "    #   (none — every Rally step is covered above)"

        # Honest degradation: without a name or an option there is nothing
        # case-specific to drive, so say what is missing instead of running a
        # generic walk and calling it a pass.
        guard = ""
        if not (first or options):
            reason = (f"{tc_id}: could not read the guest details from the Rally case. "
                      f"Spell them out in the Description or Validation Input "
                      f"(e.g. 'enter X in the First Name field', 'select Arabic'), "
                      f"then re-sync.")
            guard = ('@pytest.mark.stub\n'
                     f'@pytest.mark.skip(reason="{self._py_str(reason)}")\n')

        expected_note = self._py_str(
            v_exp or "the guest registers and reaches the map", 200)

        return f'''"""
{doc}

Guest flow — this test NEVER logs in.

Route walked on the live app (2026-08-13) and encoded in utilsdemo.GUEST_ENTRY:
    log out (AltTesterUtils.Logout; UI only as fallback)  ->  "Free Trial"
    ->  "Let's Start"
    ->  child's name  ->  gender toggles  ->  native language  ->  English level
    ->  GenderSelectPopup(Clone) on the hub  ->  GO-Map
The app asks these in a different ORDER from the Rally steps, so the option
labels below are matched per screen rather than in sequence.

Parsed from {parsed["source"] or "(nothing)"}. Steps this generator could not
derive from prose are listed as TODO in the body.
"""

import time
import pytest
from Utilities import utilsdemo

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
# Regenerated from the Rally case on every sync so the guest details stay current
# with the description. Hand-editing? Set MANUAL_EDIT = True to lock.
MANUAL_EDIT = False

# The child this case registers. No USERNAME/PASSWORD: a guest has no account.
# LAST_NAME is derived from the two choices below — "guest" + the language's
# first two letters + the difficulty's initials — so the registered guest can be
# identified afterwards by what it selected (Rally said "{self._py_str(vals["last"], 40)}").
FIRST_NAME = "{self._py_str(first, 60)}"
LAST_NAME = "{self._py_str(last, 60)}"
# What this case picks on the onboarding option screens, in any order.
OPTIONS = {options_literal}
# Rally: "tap on any level greater than 5 — verify it is locked". Checked at
# level 9 (user, 2026-08-16): the level is pressed AFTER the exam has been
# submitted, so the check has to sit well clear of anything finishing the exam
# could have opened up — otherwise a level that legitimately unlocked would
# read as a broken guest restriction.
GUEST_LOCKED_LEVEL = 9
# What the app must say when that level is pressed:
#   "You've completed all free levels. Please subscribe to open more levels."
# Kept as fragments so a typographic apostrophe or a re-wrap does not fail the
# case, while a missing or different gate does.
LOCKED_MESSAGE_FRAGMENTS = ["completed all free levels", "subscribe"]


{guard}def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # 1. Register as a guest. Logs the current user out first — the trial entry
    #    only EXISTS while nobody is logged in — and never types credentials.
    result = utilsdemo.enter_guest_mode(driver, FIRST_NAME, LAST_NAME,
                                        options=OPTIONS)
    assert result["ok"], (
        f"{{TC_ID}}: guest onboarding failed at '{{result['failed_at']}}' — "
        f"{{result['note']}}. Got as far as: {{result['trace']}}. "
        f"Expected: {expected_note}")

    # 2. Prove we are really inside the app. The login overlay sits ON the start
    #    screen with the hub live behind it, so a findable GO-Map is not evidence.
    state = utilsdemo.app_state(driver)
    assert utilsdemo.in_app(driver), \\
        f"{{TC_ID}}: onboarding ended on the {{state}} screen, not in the app"

    # 3. Enter the map (Rally: "Enter the map").
    assert utilsdemo.press_object(driver, "GO-Map", settle=12.0), \\
        f"{{TC_ID}}: GO-Map did not respond on the hub"
    assert utilsdemo.wait_for_scene(driver, utilsdemo.MAP_SCENE, timeout=60), \\
        f"{{TC_ID}}: the map did not load for the guest"

    # 4. The guest's map: icons are there and an exam node exists. WHICH level
    #    carries the first exam moves with the language and level the guest
    #    picked (Turkish/Advanced does not have it at 5), so it is read off the
    #    live map instead of hardcoded.
    icons = utilsdemo._find_level_icons(driver)
    assert icons, f"{{TC_ID}}: no level icons on the guest's map"
    first_exam = utilsdemo.guest_first_exam_level(driver)
    assert first_exam, f"{{TC_ID}}: no exam node on the guest's map"

    # 5. Levels {levels_literal}: open each one, open EVERY activity in it and
    #    prove it really starts, check the app never goes to an error state, and
    #    play one activity through to completion.
    walk = utilsdemo.guest_walk_levels(driver, levels={levels_literal},
                                       complete_one=True)
    # Report the WALK's own problems first. A crash or an offline popup ends the
    # walk where it stands, so the levels after it were never attempted — and a
    # per-level assertion would then blame the level that never ran ("no
    # activity opened in level 2") instead of naming what actually stopped it.
    assert not walk["problems"], \\
        f"{{TC_ID}}: the guest level walk hit problems: {{walk['problems']}}"
    for level in {levels_literal}:
        detail = walk["levels"].get(level, {{}})
        assert detail.get("opened"), (
            f"{{TC_ID}}: no activity opened in level {{level}} — it offered "
            f"{{detail.get('activities')}}, problems: {{detail.get('problems')}}")
    assert walk["completed"], \\
        f"{{TC_ID}}: no activity was completed as a guest (opened: {{walk['opened']}})"

{exam_block}
    # {n_lock}. The guest restriction: a level past the accessible band must not
    #    open. Locked levels keep their icon, so the check is behavioural: press
    #    it and require the app stays on the map (a paywall/sign-up prompt counts
    #    as positive evidence and is reported).
    # The subscribe gate the app raises once the exam is done and it is back on
    # the map. Its message is read from 'originalText' rather than the rendered
    # label — the label types itself out, so reading it returns whatever had
    # been typed so far. Matched as FRAGMENTS: the apostrophe is typographic in
    # some builds and the sentence wraps, while a gate that goes quiet, or
    # offers something else, still fails. This is the proof that finishing the
    # exam unlocked nothing.
    gate = utilsdemo.guest_subscribe_gate(driver, expect=LOCKED_MESSAGE_FRAGMENTS,
                                          tc_id=TC_ID)
    assert gate["shown"], (
        f"{{TC_ID}}: no subscribe gate after the exam — {{gate['note']}}")
    missing = [f for f in LOCKED_MESSAGE_FRAGMENTS
               if f.lower() not in (gate["text"] or "").lower()]
    assert not missing, (
        f"{{TC_ID}}: the subscribe gate did not say what it should "
        f"(missing {{missing}}) — it said {{gate['text']!r}}")
    assert gate["closed"], (
        f"{{TC_ID}}: the subscribe gate would not close — {{gate['note']}}")
    # The gate hands over to a "Web Purchase Unavailable" notice. If it showed
    # and did not close, the locked-level press below would land on the POPUP
    # and the app would stay on the map — which reads exactly like a locked
    # level. Fail here instead of passing that check for the wrong reason.
    assert not gate["followup_shown"] or gate["followup_closed"], (
        f"{{TC_ID}}: the follow-up notice stayed on screen — {{gate['note']}}. "
        f"It said {{gate['followup']!r}}")

    lock = utilsdemo.guest_level_locked(driver, level=GUEST_LOCKED_LEVEL)
    assert lock["locked"],         f"{{TC_ID}}: a level past the guest band was not locked — {{lock['note']}}"

    # {n_todo}. Rally steps that cannot be derived from the description — implement
    #    against the live app, then set MANUAL_EDIT = True to keep the code:
{todo_block}

    # {n_reset}. STOP HERE — deliberately no logout. Rally says "Perform Clear
    #    Data", and that is a device-level reset a test cannot do: logging out
    #    would leave this guest REGISTERED, so the next case would resume it
    #    instead of registering its own. The run ends on the map, as this guest,
    #    and says so in the log.
    utilsdemo.guest_clear_data_notice(TC_ID)
'''

    def _gen_stub(self, tc_id, tc_name, test_func_name,
                  description="", steps=None, reason="") -> str:
        """Generate an HONEST stub: carries the real Rally description + steps,
        and SKIPS (never 'assert True') so it can't masquerade as passing.
        The @pytest.mark.skip also prevents the altdriver fixture from starting,
        so unimplemented stubs don't try to connect to the game."""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        scaffold = self._body_scaffold(steps or [])
        # An out-of-scope case gets the real explanation instead of the generic
        # "not implemented yet" — nobody should waste time trying to wire a CRM
        # case to the Unity client.
        if reason:
            skip_reason = (f"{tc_id}: targets {reason}. AltTester drives the Unity "
                           f"client only — automate this with a web/API driver instead.")
            note = f"    # OUT OF SCOPE for AltTester: this case targets {reason}.\n"
        else:
            skip_reason = (f"{tc_id}: auto-generated from Rally, not implemented yet. "
                           f"Implement the steps below, remove this skip, then set "
                           f"MANUAL_EDIT = True.")
            note = "    # TODO: implement the Rally steps below against the live app (AltTester):\n"
        return f'''"""
{doc}
"""

import pytest

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


@pytest.mark.stub
@pytest.mark.skip(reason="{self._py_str(skip_reason)}")
def {test_func_name}(altdriver):
    driver, _platform = altdriver

{note}{scaffold}

    # When implemented: delete the @pytest.mark.skip above and set MANUAL_EDIT = True
    # so the next Rally sync keeps your code.
'''

    def _gen_skeleton_from_elements(self, tc_id, tc_name, test_type, func_name,
                                    description, steps, user_data, elements) -> str:
        """Render a test using elements discovered on the live app (see #4)."""
        scene = elements.get("scene") or "?"
        inputs = [n for n in (elements.get("inputs") or []) if n]
        buttons = [n for n in (elements.get("buttons") or []) if n]
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        disc = (f"Generated from the LIVE app via AltTester element discovery.\n"
                f"Scene: {scene} | inputs: {inputs or 'none'} | buttons: {buttons or 'none'}")

        # Can we produce a COMPLETE positive-login test? Needs the login
        # controls on screen and real credentials from the Rally case.
        username = (user_data or {}).get("username") or ""
        password = (user_data or {}).get("password") or ""
        user_field = next((i for i in inputs if "user" in i.lower()), None)
        pass_field = next((i for i in inputs if "pass" in i.lower()), None)
        login_btn = next((b for b in buttons if "login" in b.lower()), buttons[0] if buttons else None)
        login_ready = (test_type == "login_positive" and username and username != "CHANGE_ME"
                       and user_field and pass_field and login_btn)

        if login_ready:
            return f'''"""
{doc}

{disc}
"""

import time
from alttester import By
from Pages.StartScreen import StartScreen

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
MANUAL_EDIT = True


def {func_name}(altdriver):
    driver, _platform = altdriver

    driver.wait_for_object(By.NAME, "{user_field}", enabled=True).set_text("{username}")
    driver.wait_for_object(By.NAME, "{pass_field}", enabled=True).set_text("{password}")
    driver.wait_for_object(By.NAME, "{login_btn}").click()
    time.sleep(5)

    assert StartScreen(driver).is_present("GO-Map"), \\
        f"Login failed: GO-Map not found after login ({{TC_ID}})"
'''

        # Next best: derive real interactions + assertions from the Rally steps
        # matched against the discovered elements. If we can produce at least one
        # assertion, this becomes a real (runnable, checked) test.
        all_names = [n for n in (elements.get("all") or (inputs + buttons)) if n]
        derived_body, has_assert = self._derive_body(steps or [], description, all_names, inputs)
        if has_assert:
            return f'''"""
{doc}

{disc}

Interactions/assertions auto-derived from the Rally steps + live elements.
REVIEW: matched elements come from the scene shown at generation time — adjust
navigation/waits as needed.
"""

import time
from alttester import By

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"
MANUAL_EDIT = True


def {func_name}(altdriver):
    driver, _platform = altdriver

{derived_body}
'''

        # Otherwise: a populated but still-skipped stub. Real element calls are
        # pre-wired (commented) so a human just fills values + asserts.
        set_lines = "\n".join(
            f'    # driver.wait_for_object(By.NAME, "{n}", enabled=True).set_text("<value>")'
            for n in inputs
        ) or "    # (no input fields discovered on this scene)"
        click_lines = "\n".join(
            f'    # driver.wait_for_object(By.NAME, "{n}").click()' for n in buttons
        ) or "    # (no buttons discovered on this scene)"
        scaffold = self._body_scaffold(steps or [])
        return f'''"""
{doc}

{disc}
"""

import time
import pytest
from alttester import By

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


@pytest.mark.stub
@pytest.mark.skip(reason="{tc_id}: skeleton pre-wired from live elements, not finished. "
                         "Complete the interactions/asserts, remove this skip, then set MANUAL_EDIT = True.")
def {func_name}(altdriver):
    driver, _platform = altdriver

    # --- Elements discovered on the live app (uncomment + set real values) ---
{set_lines}
{click_lines}

    # --- Rally steps to assert ---
{scaffold}
'''

    @staticmethod
    def _best_element(text, candidates):
        """Best-matching object name for a Rally step phrase, or None if the
        match is too weak (keeps auto-derivation honest — no confident match,
        no fabricated assertion)."""
        words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2]
        if not words or not candidates:
            return None
        best, best_score = None, 0.0
        for name in candidates:
            nl = name.lower()
            nwords = set(re.findall(r"[a-z0-9]+", nl))
            overlap = sum(1 for w in words if w in nwords or w in nl)
            score = overlap + SequenceMatcher(None, (text or "").lower(), nl).ratio()
            if score > best_score:
                best_score, best = score, name
        return best if best_score >= 1.6 else None

    @classmethod
    def _description_checks(cls, description):
        """Pull likely 'expected UI component' phrases out of a free-text Rally
        description (many cases put steps/expected in the Description instead of
        the structured Input/ExpectedResult fields). Returns a list of phrases."""
        text = cls._clean_html(description)
        if not text:
            return []
        # Prefer the region after a cue like "Components Validated:" / "Verify".
        m = re.search(r"(?:components?\s+validated|verif\w*|expected|checks?|ensures?|displays?)\s*[:\-]?\s*(.*)",
                      text, re.IGNORECASE)
        region = m.group(1) if m else text
        frags = re.split(r"[•▪◦·\n;:]|\s\-\s|\s\*\s|,| and | & ", region)
        ui_words = ("button", "page", "title", "link", "field", "dropdown", "grid", "icon",
                    "menu", "tab", "panel", "label", "text", "screen", "scene", "list",
                    "checkbox", "toggle", "image", "popup", "dialog", "banner", "navigation", "header")
        out = []
        for f in frags:
            f = f.strip(" .:\t")
            if 3 <= len(f) <= 60 and f not in out and any(
                re.search(rf"\b{u}\b", f.lower()) for u in ui_words):
                out.append(f)
        return out[:12]

    def _derive_body(self, steps, description, all_names, inputs):
        """Build a test body from BOTH structured Rally steps and check phrases
        pulled from the Description. Input -> click; Expected/component -> assert
        (wait_for_object fails if absent). Unmatched parts stay TODO comments.

        Returns (body_text, has_assertion)."""
        lines, has_assert = [], False

        for i, s in enumerate(steps or [], 1):
            inp = self._clean_html(s.get("input", ""))
            exp = self._clean_html(s.get("expected", ""))
            lines.append(f"    # Step {i}: {inp}" if inp else f"    # Step {i}:")

            el = self._best_element(inp, all_names) if inp else None
            if el and el in inputs:
                lines.append(f'    driver.wait_for_object(By.NAME, "{el}", enabled=True)'
                             f'  # TODO: .set_text(<value>) if this step types')
            elif el:
                lines.append(f'    driver.wait_for_object(By.NAME, "{el}").click()')
                lines.append("    time.sleep(1)")
            elif inp:
                lines.append("    # TODO: perform this action (no matching element discovered)")

            if exp:
                ael = self._best_element(exp, all_names)
                if ael:
                    lines.append(f'    assert driver.wait_for_object(By.NAME, "{ael}", timeout=10), '
                                 f'"Expected: {exp.replace(chr(34), chr(39))[:100]}"')
                    has_assert = True
                else:
                    lines.append(f"    #   Expected (add assertion): {exp}")
            lines.append("")

        # Description-derived presence checks (for cases whose steps/expected
        # live in the Description rather than the structured step fields).
        checks = self._description_checks(description)
        if checks:
            lines.append("    # --- Checks derived from the Rally description ---")
            for phrase in checks:
                el = self._best_element(phrase, all_names)
                if el:
                    lines.append(f'    assert driver.wait_for_object(By.NAME, "{el}", timeout=10), '
                                 f'"Expected: {phrase.replace(chr(34), chr(39))[:100]}"')
                    has_assert = True
                else:
                    lines.append(f"    # TODO: assert present -> {phrase}")

        return "\n".join(lines).rstrip() or "    pass", has_assert

    def _determine_output_path(
        self, tc_id: str, tc_name: str, folder_id: Optional[str]
    ) -> Path:
        """Determine output file path from folder hierarchy."""
        suite = self.load_rally_suite()
        folder_path = "General"

        if folder_id:
            for folder in suite.get("folders", []):
                if folder["id"] == folder_id:
                    name = folder["name"].replace(" ", "_").replace("–", "").strip()
                    parent_id = folder.get("parent")
                    if parent_id:
                        for parent in suite.get("folders", []):
                            if parent["id"] == parent_id:
                                parent_name = (
                                    parent["name"].replace(" ", "_").replace("–", "").strip()
                                )
                                folder_path = f"{parent_id}_{parent_name}/{folder_id}_{name}"
                                break
                    else:
                        folder_path = f"{folder_id}_{name}"
                    break

        filename = f"{rally_naming.test_identifier(tc_id, tc_name)}.py"
        return self.tests_base_dir / folder_path / filename
