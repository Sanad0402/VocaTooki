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
        with open(self.rally_suite_path) as f:
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

        test_type = self._infer_test_type(tc_name)
        description = test_case.get("description", "")
        steps = test_case.get("steps", [])
        test_code = self._generate_test_code(
            tc_id, tc_name, test_type, user_data, func_name, description, steps
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

        test_type = self._infer_test_type(tc_name)
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

    def _prune_orphans(self, current_ids: set) -> None:
        """Delete generator-produced files whose Rally id is no longer in the
        suite. Only files carrying the ``TC_ID`` marker are eligible."""
        if not self.tests_base_dir.exists():
            return
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
                    continue
                try:
                    path.unlink()
                    logger.info(
                        f"Pruned orphan (Rally {marker} not in current suite): {path}"
                    )
                except Exception as e:
                    logger.error(f"Could not prune {path}: {e}")

    def _infer_test_type(self, tc_name: str) -> str:
        """Infer test type from test case name."""
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
        return "generic"

    def _generate_test_code(
        self,
        tc_id: str,
        tc_name: str,
        test_type: str,
        user_data: Dict[str, str],
        func_name: str,
        description: str = "",
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate pytest code based on test type."""
        steps = steps or []
        if test_type == "login_positive":
            return self._gen_login_positive(tc_id, tc_name, user_data, func_name, description, steps)
        elif test_type == "login_negative":
            return self._gen_login_negative(tc_id, tc_name, user_data, func_name, description, steps)
        elif test_type == "logout":
            return self._gen_logout(tc_id, tc_name, func_name, description, steps)
        else:
            return self._gen_stub(tc_id, tc_name, func_name, description, steps)

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

    def _gen_stub(self, tc_id, tc_name, test_func_name,
                  description="", steps=None) -> str:
        """Generate an HONEST stub: carries the real Rally description + steps,
        and SKIPS (never 'assert True') so it can't masquerade as passing.
        The @pytest.mark.skip also prevents the altdriver fixture from starting,
        so unimplemented stubs don't try to connect to the game."""
        doc = self._doc_block(tc_id, tc_name, description, steps or [])
        scaffold = self._body_scaffold(steps or [])
        return f'''"""
{doc}
"""

import pytest

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


@pytest.mark.stub
@pytest.mark.skip(reason="{tc_id}: auto-generated from Rally, not implemented yet. "
                         "Implement the steps below, remove this skip, then set MANUAL_EDIT = True.")
def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # TODO: implement the Rally steps below against the live app (AltTester):
{scaffold}

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
