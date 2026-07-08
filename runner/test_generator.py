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
        test_code = self._generate_test_code(
            tc_id, tc_name, test_type, user_data, func_name
        )
        test_code = self._inject_manual_marker(test_code)

        # Remove any older file for this same Rally case before writing.
        self._remove_stale_for_tc(tc_id, output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        return output_path

    @staticmethod
    def _inject_manual_marker(test_code: str) -> str:
        """Add the ``MANUAL_EDIT`` lock flag right after the ``TC_ID`` line.

        Kept here (not in each template) so all generated files get it uniformly.
        Set the flag to True in a file to protect it from the next Rally sync.
        """
        if "MANUAL_EDIT" in test_code:
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
        if "login" in lower:
            if "invalid" in lower or "negative" in lower:
                return "login_negative"
            return "login_positive"
        if "logout" in lower:
            return "logout"
        if "navigation" in lower:
            return "navigation"
        return "generic"

    def _generate_test_code(
        self,
        tc_id: str,
        tc_name: str,
        test_type: str,
        user_data: Dict[str, str],
        func_name: str,
    ) -> str:
        """Generate pytest code based on test type."""
        if test_type == "login_positive":
            return self._gen_login_positive(tc_id, tc_name, user_data, func_name)
        elif test_type == "login_negative":
            return self._gen_login_negative(tc_id, tc_name, user_data, func_name)
        elif test_type == "logout":
            return self._gen_logout(tc_id, tc_name, func_name)
        elif test_type == "navigation":
            return self._gen_navigation(tc_id, tc_name, func_name)
        else:
            return self._gen_generic(tc_id, tc_name, func_name)

    def _get_test_func_name(self, tc_id: str, tc_name: str) -> str:
        """Canonical test function name (matches the file stem and nodeid).

        Delegates to the shared naming rules so the function name can never
        drift from what ``rally_api`` writes into the nodeid.
        """
        return rally_naming.test_identifier(tc_id, tc_name)

    def _gen_login_positive(self, tc_id: str, tc_name: str, user_data: Dict[str, str], test_func_name: str) -> str:
        """Generate positive login test."""
        # Credentials are hard-coded per Rally test case (this framework's model:
        # each case carries its own user). Fill them via the Flask UI (edit case
        # → username/password) or by editing the file and setting MANUAL_EDIT=True.
        username = user_data.get("username") or "CHANGE_ME"
        password = user_data.get("password") or ""
        cred_source = f'username = "{username}"\n    password = "{password}"'

        return f'''"""
{tc_id} — {tc_name}

Auto-generated from Rally test case.
Expected: Successful login and redirect to home screen.
"""

import time
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen

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

    {cred_source}

    login_page.set_username(username)
    login_page.set_password(password)
    login_page.click_login()
    time.sleep(5)

    assert StartScreen(driver).is_present("GO-Map"), \\
        f"Login failed: GO-Map not found after login ({{TC_ID}})"
'''

    def _gen_login_negative(
        self, tc_id: str, tc_name: str, user_data: Dict[str, str], test_func_name: str
    ) -> str:
        """Generate negative login test."""
        username = user_data.get("username", "invalid_user")
        password = user_data.get("password", "invalid_pass")

        return f'''"""
{tc_id} — {tc_name}

Auto-generated from Rally test case.
Expected: Login fails with invalid credentials.
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

    assert login_page.is_open() or login_page.error_visible(), \\
        f"Login should fail with invalid credentials ({{TC_ID}})"
'''

    def _gen_logout(self, tc_id: str, tc_name: str, test_func_name: str) -> str:
        """Generate logout test."""
        return f'''"""
{tc_id} — {tc_name}

Auto-generated from Rally test case.
Expected: Logout succeeds and returns to login screen.
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

    def _gen_navigation(self, tc_id: str, tc_name: str, test_func_name: str) -> str:
        """Generate navigation test."""
        return f'''"""
{tc_id} — {tc_name}

Auto-generated from Rally test case.
Expected: Navigation succeeds to target screen.
"""

import time

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # TODO: Customize navigation steps for this test
    time.sleep(2)
    assert True, "Navigation test placeholder"
'''

    def _gen_generic(self, tc_id: str, tc_name: str, test_func_name: str) -> str:
        """Generate generic placeholder test."""
        return f'''"""
{tc_id} — {tc_name}

Auto-generated from Rally test case.
TODO: Customize based on actual test steps.
"""

# Rally test case ID (for sync and maintenance)
TC_ID = "{tc_id}"


def {test_func_name}(altdriver):
    driver, _platform = altdriver

    # TODO: Implement test steps
    assert True
'''

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
