"""Manually flip a generated test between 'real' and 'stub' from the panel.

- **stub**  -> the test is skipped (won't run) via ``@pytest.mark.stub`` +
               ``@pytest.mark.skip``.
- **real**  -> those markers are removed so the test runs.

Either way the file is locked (``MANUAL_EDIT = True``) so a later Rally sync
won't revert the choice. Status itself is still derived from the file by
``runner.suite.impl_status`` — this module only edits the markers.
"""

import os
import re

from runner import suite as suite_mod
from runner import rally_naming


def _ensure_import_pytest(text: str) -> str:
    if re.search(r"^\s*import\s+pytest\b", text, re.MULTILINE):
        return text
    m = re.match(r"\s*(\"\"\".*?\"\"\"|'''.*?''')\s*\n", text, re.DOTALL)
    if m:  # place right after the module docstring
        idx = m.end()
        return text[:idx] + "\nimport pytest\n" + text[idx:]
    return "import pytest\n" + text


def _set_manual_edit_true(text: str) -> str:
    if re.search(r"^\s*MANUAL_EDIT\s*=", text, re.MULTILINE):
        return re.sub(r"^(\s*MANUAL_EDIT\s*=\s*).*$", r"\g<1>True", text, count=1, flags=re.MULTILINE)
    if re.search(r"^TC_ID\s*=", text, re.MULTILINE):
        return re.sub(r"^(TC_ID\s*=.*\n)", r"\1MANUAL_EDIT = True\n", text, count=1, flags=re.MULTILINE)
    return text


def _remove_stub_markers(text: str) -> str:
    text = re.sub(r"[ \t]*@pytest\.mark\.stub[ \t]*\r?\n", "", text)
    # skip decorator: reason strings in generated files never contain ')'.
    text = re.sub(r"[ \t]*@pytest\.mark\.skip\([^)]*\)[ \t]*\r?\n", "", text, flags=re.DOTALL)
    return text


def _add_stub_markers(text: str, tc_id: str, func_name: str) -> str:
    text = _ensure_import_pytest(text)
    deco = (
        "@pytest.mark.stub\n"
        f'@pytest.mark.skip(reason="{tc_id}: manually marked as stub — skipped until switched back to real.")\n'
    )
    pat = re.compile(rf"^(def\s+{re.escape(func_name)}\s*\()", re.MULTILINE)
    if not pat.search(text):
        pat = re.compile(r"^(def\s+test_\w*\s*\()", re.MULTILINE)
    return pat.sub(deco + r"\1", text, count=1)


def _has_assertion(text: str, func_name: str) -> bool:
    m = re.search(rf"def\s+{re.escape(func_name)}\s*\(.*", text, re.DOTALL)
    body = m.group(0) if m else text
    return bool(re.search(r"\bassert\b|pytest\.(raises|fail)", body))


def set_case_impl(tc_id: str, target: str) -> dict:
    """Flip case ``tc_id``'s linked test to ``target`` ('stub' | 'real').

    Returns ``{"impl", "warning", "path"}``. Raises ValueError for bad input,
    an unlinked case, or a missing file.
    """
    target = (target or "").strip().lower()
    if target not in ("stub", "real"):
        raise ValueError("Status must be 'stub' or 'real'.")

    data = suite_mod.load()
    case = next((c for c in data["test_cases"] if c.get("id") == tc_id), None)
    if not case:
        raise ValueError(f"Test case {tc_id} not found in the suite.")

    nodeid = (case.get("action") or {}).get("nodeid") or ""
    if "::" not in nodeid:
        raise ValueError("This case has no pytest test linked yet — add a nodeid first.")

    file_part, func_name = nodeid.split("::", 1)
    path = os.path.join(suite_mod._ROOT, file_part)
    if not os.path.exists(path):
        raise ValueError(f"Linked test file not found on disk: {file_part}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    warning = None
    if target == "stub":
        if not rally_naming.is_stub(text):
            text = _add_stub_markers(text, tc_id, func_name)
    else:  # real
        text = _remove_stub_markers(text)
        if not _has_assertion(text, func_name):
            warning = ("Set to 'real', but this test has no assertions yet — it will PASS "
                       "without checking anything. Implement it or use 'Generate from live app'.")

    text = _set_manual_edit_true(text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return {"impl": suite_mod.impl_status(nodeid), "warning": warning, "path": file_part}
