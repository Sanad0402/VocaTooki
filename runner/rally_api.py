"""Rally API Client — Connect to Rally and fetch test cases.

Handles authentication, test case fetching, folder hierarchy, and syncing.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests

from runner import rally_naming

logger = logging.getLogger(__name__)


class RallyAPIClient:
    """Client for Rally REST API."""

    RALLY_URL = "https://rally1.rallydev.com"  # Default Rally instance
    # Rally WSAPI current version is 2.0 (there is no 3.0 — it returns HTTP 500).
    WSAPI = "/slm/webservice/v2.0"

    def __init__(self, api_token: str):
        """
        Initialize Rally client.

        Args:
            api_token: Rally API token
        """
        self.api_url = self.RALLY_URL
        self.wsapi = f"{self.RALLY_URL}{self.WSAPI}"
        self.api_token = api_token
        self.session = requests.Session()
        # Rally WSAPI authenticates API keys via the ZSESSIONID header
        # (NOT "Authorization: Bearer", which is for OAuth tokens).
        self.session.headers.update(
            {
                "ZSESSIONID": api_token,
                "Content-Type": "application/json",
            }
        )

    def test_connection(self) -> bool:
        """Test Rally API connection."""
        try:
            response = self.session.get(f"{self.wsapi}/user")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Rally connection test failed: {e}")
            return False

    def _project_ref(self, project_id: str) -> str:
        """Full project ref URL. Rally's ``project`` filter requires the ref,
        not the bare ObjectID (a bare OID silently matches nothing)."""
        pid = str(project_id)
        return pid if pid.startswith("http") else f"{self.wsapi}/project/{pid}"

    def get_projects(self) -> List[Dict[str, Any]]:
        """Fetch all projects from Rally."""
        try:
            url = f"{self.wsapi}/project"
            # fetch=Name so results carry a human-readable Name (otherwise Rally
            # returns only _refObjectName and callers see "Unknown").
            params = {"pageSize": 200, "fetch": "Name,ObjectID"}

            response = self.session.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("QueryResult", {}).get("Results", [])
            logger.info(f"Fetched {len(results)} projects from Rally")
            return results
        except Exception as e:
            logger.error(f"Failed to fetch projects: {e}")
            return []

    def _fetch_all_pages(self, url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch EVERY page of a WSAPI query, not just the first.

        A single request returns at most ``pageSize`` results; with more than
        that (e.g. many test folders), later objects silently vanished — a case
        whose TestFolder was on page 2 fell into "Ungrouped". Loops with the
        ``start`` index until TotalResultCount is exhausted.
        """
        out: List[Dict[str, Any]] = []
        start = 1
        while True:
            page_params = dict(params, start=start)
            response = self.session.get(url, params=page_params)
            response.raise_for_status()
            qr = response.json().get("QueryResult", {})
            results = qr.get("Results", [])
            out.extend(results)
            total = qr.get("TotalResultCount", len(out))
            if not results or len(out) >= total:
                return out
            start += len(results)

    def get_test_cases(
        self, project_id: str, automated_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch test cases from Rally.

        Args:
            project_id: Rally project ID
            automated_only: Only fetch test cases marked as automated

        Returns:
            List of test case dicts
        """
        try:
            url = f"{self.wsapi}/testcase"
            params = {
                "project": self._project_ref(project_id),
                "projectScopeDown": "true",
                "pageSize": 200,
                "fetch": ("FormattedID,Name,Description,Owner,Status,Method,"
                          "TestFolder,ValidationInput,ValidationExpectedResult"),
            }

            if automated_only:
                params["query"] = '(Method = "Automated")'

            results = self._fetch_all_pages(url, params)
            logger.info(f"Fetched {len(results)} test cases from Rally")
            return results
        except Exception as e:
            logger.error(f"Failed to fetch test cases: {e}")
            return []

    def get_test_folders(self, project_id: str) -> List[Dict[str, Any]]:
        """Fetch test folders from Rally.

        Note: the Rally object type is ``testfolder`` (``testcasefolder`` exists
        but is unused here and returns nothing)."""
        try:
            url = f"{self.wsapi}/testfolder"
            params = {
                "project": self._project_ref(project_id),
                "projectScopeDown": "true",
                "pageSize": 200,
                "fetch": "FormattedID,Name,Parent",
            }

            results = self._fetch_all_pages(url, params)
            logger.info(f"Fetched {len(results)} test folders from Rally")
            return results
        except Exception as e:
            logger.error(f"Failed to fetch test folders: {e}")
            return []

    # ---- posting results back to Rally -----------------------------------

    def find_test_case(self, formatted_id: str) -> Optional[Dict[str, Any]]:
        """Look up a TestCase by its FormattedID (e.g. "TC1150").

        Returns the raw object (with _ref, Project, WorkProduct) or None.
        """
        try:
            url = f"{self.wsapi}/testcase"
            params = {
                "query": f'(FormattedID = "{formatted_id}")',
                "fetch": "FormattedID,Name,Project",
                "pageSize": 1,
            }
            r = self.session.get(url, params=params)
            r.raise_for_status()
            results = r.json().get("QueryResult", {}).get("Results", [])
            return results[0] if results else None
        except Exception as e:
            logger.error(f"find_test_case({formatted_id}) failed: {e}")
            return None

    def create_test_case_result(self, tc_ref: str, verdict: str, build: str,
                                notes: str = "", project_ref: Optional[str] = None,
                                date_iso: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a TestCaseResult under a TestCase.

        Rally requires Build, Date, TestCase and Verdict. Returns the created
        object (with _ref) or None. ``verdict`` should be one of Rally's exact
        values: "Pass", "Fail", "Blocked", "Inconclusive", "Error".
        """
        try:
            payload = {
                "TestCaseResult": {
                    "TestCase": tc_ref,
                    "Verdict": verdict,
                    "Build": build or "n/a",
                    "Date": date_iso or datetime.now(timezone.utc).isoformat(),
                    "Notes": notes or "",
                }
            }
            if project_ref:
                payload["TestCaseResult"]["Project"] = project_ref
            r = self.session.post(f"{self.wsapi}/testcaseresult/create",
                                  data=json.dumps(payload))
            r.raise_for_status()
            body = r.json().get("CreateResult", {})
            errs = body.get("Errors") or []
            if errs:
                logger.error(f"Rally rejected result: {errs}")
                return {"_errors": errs}
            obj = body.get("Object", {})
            logger.info(f"Posted TestCaseResult {obj.get('_ref')} verdict={verdict}")
            return obj
        except Exception as e:
            logger.error(f"create_test_case_result failed: {e}")
            return None

    def attach_screenshot(self, artifact_ref: str, image_path: str,
                          name: Optional[str] = None) -> bool:
        """Attach a PNG to an ARTIFACT (e.g. a TestCase).

        Rally attachments are two objects: an AttachmentContent (base64) and an
        Attachment that links it to the artifact. NOTE: the target must be a
        true Artifact — a TestCaseResult is NOT one and Rally rejects it, so
        result screenshots are attached to the parent TestCase instead.
        Best-effort — a failed attachment must not fail the result post.
        """
        try:
            import base64
            with open(image_path, "rb") as f:
                raw = f.read()
            b64 = base64.b64encode(raw).decode("ascii")
            cr = self.session.post(
                f"{self.wsapi}/attachmentcontent/create",
                data=json.dumps({"AttachmentContent": {"Content": b64}}))
            cr.raise_for_status()
            content = cr.json().get("CreateResult", {}).get("Object", {})
            content_ref = content.get("_ref")
            if not content_ref:
                logger.error("attachment content not created")
                return False
            att = {
                "Attachment": {
                    "Artifact": artifact_ref,
                    "Content": content_ref,
                    "ContentType": "image/png",
                    "Name": name or os.path.basename(image_path),
                    "Size": len(raw),
                }
            }
            ar = self.session.post(f"{self.wsapi}/attachment/create",
                                   data=json.dumps(att))
            ar.raise_for_status()
            errs = ar.json().get("CreateResult", {}).get("Errors") or []
            if errs:
                logger.error(f"attachment link failed: {errs}")
                return False
            logger.info("Attached screenshot to Rally result")
            return True
        except Exception as e:
            logger.error(f"attach_screenshot failed: {e}")
            return False

    def get_test_steps(self, test_case_id: str) -> List[Dict[str, Any]]:
        """Fetch test steps for a test case."""
        try:
            url = f"{self.wsapi}/testcase/{test_case_id}/steps"
            params = {"pageSize": 200, "fetch": "StepIndex,Input,ExpectedResult"}

            response = self.session.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("QueryResult", {}).get("Results", [])
            return results
        except Exception as e:
            logger.debug(f"Failed to fetch test steps for {test_case_id}: {e}")
            return []

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Rally rich-text -> readable plain text with real line breaks."""
        import re
        if not html:
            return ""
        t = re.sub(r'<br\s*/?>', '\n', str(html), flags=re.IGNORECASE)
        t = re.sub(r'</(p|div|li)>', '\n', t, flags=re.IGNORECASE)
        t = re.sub(r'<[^>]+>', '', t)
        for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                     ("&gt;", ">"), ("&#39;", "'"), ("&quot;", '"')):
            t = t.replace(a, b)
        # collapse runs of blank lines / trailing spaces but KEEP the newlines
        t = re.sub(r'[ \t]+\n', '\n', t)
        t = re.sub(r'\n{3,}', '\n\n', t)
        return t.strip()

    def _extract_credentials(self, description: str) -> Dict[str, str]:
        """Extract username and password from test case description.

        Looks for patterns like:
        - "Username: user1, Password: pass1"
        - "username=user1 password=pass1"
        - "user: user1" / "pwd: pass1"

        Returns dict with 'username' and 'password' keys (empty if not found).
        """
        import re
        user_data = {}

        if not description:
            return user_data

        # <br> is a line break: turn it into a real newline BEFORE stripping
        # tags, otherwise "vt233624<br>- Password" collapses to "vt233624-"
        # and the trailing dash ends up inside the captured username.
        text = re.sub(r'<br\s*/?>', '\n', description, flags=re.IGNORECASE)
        # Strip remaining HTML tags to get plain text
        clean_text = re.sub(r'<[^>]+>', '', text)

        # Try common patterns (stop at: whitespace, comma, newline, or capital letter P/U)
        # Pattern 1: Username: xxx
        match = re.search(r'[Uu]sername\s*[:=]\s*([^\s,\n]+?)(?=\s|,|$|[Pp]assword|[Pp])', clean_text)
        if match:
            user_data['username'] = match.group(1).strip('"\'')

        # Pattern 2: Password: yyy
        match = re.search(r'[Pp]assword\s*[:=]\s*([^\s,\n]+?)(?=\s|,|$)', clean_text)
        if match:
            user_data['password'] = match.group(1).strip('"\'')

        # Pattern 3: user=xxx (fallback if username not found)
        if 'username' not in user_data:
            match = re.search(r'user\s*=\s*([^\s,\n]+)', clean_text)
            if match:
                user_data['username'] = match.group(1).strip('"\'')

        # Pattern 4: pass=yyy or pwd=yyy (fallback if password not found)
        if 'password' not in user_data:
            match = re.search(r'(?:pass|pwd)\s*=\s*([^\s,\n]+)', clean_text)
            if match:
                user_data['password'] = match.group(1).strip('"\'')

        return user_data

    def sync_to_json(
        self,
        project_id: str,
        output_file: str,
        automated_only: bool = True,
    ) -> bool:
        """
        Sync Rally test cases to local JSON file.

        Args:
            project_id: Rally project ID
            output_file: Path to save JSON
            automated_only: Only sync test cases marked as automated

        Returns:
            True if successful
        """
        try:
            logger.info(f"Syncing Rally project {project_id} to {output_file}")

            # Fetch folders and test cases
            folders = self.get_test_folders(project_id)
            test_cases = self.get_test_cases(project_id, automated_only)

            # Build folder hierarchy using FormattedID (short ID) for clean names
            folder_map = {}
            for folder in folders:
                folder_id = folder.get("FormattedID") or folder.get("_ref", "").split("/")[-1]
                folder_map[folder["_ref"]] = {
                    "id": folder_id,
                    "name": folder.get("Name", "Unknown"),
                    "parent": None,
                }

            # Link parents
            for folder in folders:
                folder_ref = folder["_ref"]
                parent_ref = (folder.get("Parent") or {}).get("_ref")
                if parent_ref and parent_ref in folder_map:
                    folder_map[folder_ref]["parent"] = (
                        folder_map[parent_ref]["id"]
                    )

            # Build test case list (Rally links test cases via TestFolder, not Folder)
            test_list = []
            used_folder_ids = set()
            for tc in test_cases:
                tc_id = tc.get("FormattedID") or tc.get("_ref", "").split("/")[-1]
                tc_name = tc.get("Name", "Unknown")
                # Store descriptions as readable text, not raw Rally HTML —
                # <br> becomes a real newline so the panel and generated
                # docstrings show the original line structure.
                tc_description = self._html_to_text(tc.get("Description", ""))
                folder_ref = (tc.get("TestFolder") or {}).get("_ref")
                folder_id = folder_map.get(folder_ref, {}).get("id") if folder_ref else None
                if folder_id:
                    used_folder_ids.add(folder_id)

                # Extract credentials from description if provided
                user_data = self._extract_credentials(tc_description)

                # Fetch the Rally test steps so generated files carry the real
                # procedure (not an empty stub). ObjectID is the last _ref segment.
                tc_oid = tc.get("_ref", "").split("/")[-1]
                raw_steps = self.get_test_steps(tc_oid)
                steps_out = [
                    {
                        "index": s.get("StepIndex"),
                        "input": s.get("Input", ""),
                        "expected": s.get("ExpectedResult", ""),
                    }
                    for s in sorted(raw_steps, key=lambda x: (x.get("StepIndex") or 0))
                ]

                # Canonical identifier shared with test_generator (file stem == function name).
                ident = rally_naming.test_identifier(tc_id, tc_name)

                # Build the folder path to match test_generator._determine_output_path output
                # This mirrors the logic in test_generator._determine_output_path (line 279-305)
                folder_path = ""
                if folder_id:
                    # Find the folder by id
                    for f_ref, f_data in folder_map.items():
                        if f_data["id"] == folder_id:
                            name = f_data["name"].replace(" ", "_").replace("–", "").replace("—", "").strip()
                            parent_id = f_data.get("parent")

                            if parent_id:
                                # Find parent folder
                                for p_ref, p_data in folder_map.items():
                                    if p_data["id"] == parent_id:
                                        parent_name = (
                                            p_data["name"].replace(" ", "_").replace("–", "").replace("—", "").strip()
                                        )
                                        folder_path = f"{parent_id}_{parent_name}/{folder_id}_{name}/"
                                        break
                            else:
                                folder_path = f"{folder_id}_{name}/"
                            break

                nodeid = f"Tests/rally/{folder_path}{ident}.py::{ident}"

                test_list.append(
                    {
                        "id": tc_id,
                        "name": tc_name,
                        "folder": folder_id,
                        "description": tc_description,
                        "owner": (tc.get("Owner") or {}).get("_refObjectName", ""),
                        "status": tc.get("Status", ""),
                        "user": user_data,
                        "steps": steps_out,
                        "validation": {
                            "input": self._html_to_text(tc.get("ValidationInput", "") or ""),
                            "expected": self._html_to_text(tc.get("ValidationExpectedResult", "") or ""),
                        },
                        "action": {
                            "kind": "pytest",
                            "nodeid": nodeid,
                        },
                    }
                )

            # Keep ALL test folders so the UI shows the complete Rally folder hierarchy.
            # Test cases (automated only) will be nested under their folders.
            # Empty folders are visible to show the full structure.
            folders_out = list(folder_map.values())

            # Cases with no Rally TestFolder go into a synthetic "Ungrouped" folder.
            if any(t["folder"] is None for t in test_list):
                ungrouped_id = "RALLY_UNGROUPED"
                for t in test_list:
                    if t["folder"] is None:
                        t["folder"] = ungrouped_id
                folders_out.append({"id": ungrouped_id, "name": "Ungrouped", "parent": None})

            # Create output structure
            output = {
                "folders": folders_out,
                "test_cases": test_list,
                "metadata": {
                    "project_id": project_id,
                    "total_cases": len(test_list),
                    "automated_only": automated_only,
                    "synced_from": "Rally API",
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            # Write JSON file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)

            logger.info(f"✅ Synced {len(test_list)} test cases to {output_file}")
            return True

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            return False


def create_client_from_env(
    env_file: Optional[str] = None,
) -> Optional[RallyAPIClient]:
    """Create Rally client from environment variables (API token only)."""
    if env_file:
        # Load env file
        env_path = Path(env_file)
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key not in os.environ:
                            os.environ[key] = value

    # Get API token from environment
    rally_token = os.getenv("RALLY_API_TOKEN")

    if not rally_token:
        logger.error(
            "Rally API token not found. "
            "Set RALLY_API_TOKEN in rally.env"
        )
        return None

    return RallyAPIClient(rally_token)


if __name__ == "__main__":
    # Example usage
    client = create_client_from_env("rally.env")
    if client:
        if client.test_connection():
            logger.info("✅ Connected to Rally!")
        else:
            logger.error("❌ Failed to connect to Rally")
