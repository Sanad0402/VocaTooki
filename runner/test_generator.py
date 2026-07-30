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
        for tc in suite.get("test_cases", []):
            try:
                nodeid = (tc.get("action") or {}).get("nodeid") or ""
                file_part = nodeid.split("::", 1)[0] if "::" in nodeid else ""
                path = self.project_root / file_part if file_part else None
                if path is None or not path.exists():
                    continue                      # new case -> wait for explicit generate
                refreshed.append(str(self.generate_test(tc)))
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
        test_type = self._infer_test_type(tc_name, description, nodeid)
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
        test_type = self._infer_test_type(tc_name, description, nodeid)
        scope_note = self.out_of_scope(tc_name, description, nodeid)
        if scope_note:
            # Not a Unity-client case (CRM/web/API). Discovering elements would
            # only wire it to whatever is on screen, which is worse than saying
            # plainly that AltTester cannot test it.
            code = self._gen_stub(tc_id, tc_name, func_name, description,
                                  test_case.get("steps", []), reason=scope_note)
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

    def _infer_test_type(self, tc_name: str, description: str = "",
                         nodeid: str = "") -> str:
        """Infer test type from the test case name (and its folder/description)."""
        lower = tc_name.lower()
        negative_words = ("invalid", "incorrect", "wrong", "empty", "locked",
                          "disabled", "negative", "failure")
        is_login = any(k in lower for k in ("login", "log in", "sign in", "credential"))
        is_negative = any(w in lower for w in negative_words)
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
        """Why this case cannot be automated against the game, or None."""
        hay = cls._haystack(tc_name, description, nodeid)
        for keyword, reason in cls.OUT_OF_SCOPE:
            if keyword in hay:
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
        elif test_type == "exam":
            return self._gen_exam(tc_id, tc_name, user_data, func_name,
                                  description, steps, validation)
        elif test_type == "page":
            return self._gen_page(tc_id, tc_name, user_data, func_name,
                                  description, steps, nodeid=nodeid)
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
        return "\n".join(lines)

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
            guard = f'@pytest.mark.stub\n@pytest.mark.skip(reason="{reason}")\n'

        expected_note = v_exp or f"{scene} activity completed successfully"

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
            guard = f'@pytest.mark.stub\n@pytest.mark.skip(reason="{reason}")\n'

        expected_note = v_exp or "all 3 exam pages solved and submitted"

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
    assert result["parts"] == 3, (
        f"{{TC_ID}}: only {{result['parts']}}/3 exam pages were reached. "
        f"Expected: {expected_note}")
    assert not result["problems"], (
        f"{{TC_ID}}: exam pages failed — " + " | ".join(result["problems"]))
    assert result["submitted"], \\
        f"{{TC_ID}}: the exam was solved but never submitted/collected"

    # 5. Clean state for the next test case: back to the level map
    utilsdemo.return_to_map(driver)
'''

    def _gen_page(self, tc_id, tc_name, user_data, test_func_name,
                  description="", steps=None, nodeid="") -> str:
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
            guard = f'@pytest.mark.stub\n@pytest.mark.skip(reason="{reason}")\n'

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
            guard = f'@pytest.mark.stub\n@pytest.mark.skip(reason="{reason}")\n'

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
@pytest.mark.skip(reason="{skip_reason}")
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
