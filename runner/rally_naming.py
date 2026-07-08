"""Shared naming rules for Rally → pytest sync.

Single source of truth so the nodeid written into ``data/rally_suite.json``
(by ``runner.rally_api``) always matches the file name and function name that
``runner.test_generator`` writes to disk. Keeping this in one place is what
prevents the drift that used to produce un-runnable, duplicated tests.
"""

import re

# Marker embedded in every generated test file: ``TC_ID = "TC128"``.
# Used to recognise a generator-produced file and read the Rally id back out
# for dedup / prune. Files without this marker are treated as hand-written and
# are never deleted.
TC_ID_RE = re.compile(r"""TC_ID\s*=\s*["']([^"']+)["']""")

# When a generated file contains ``MANUAL_EDIT = True`` it is treated as
# hand-maintained: re-sync will neither overwrite nor delete it. This lets you
# fix a generated test and keep the fix across syncs while the nodeid mapping
# stays intact.
# Anchored to line start (MULTILINE) so it matches the real ``MANUAL_EDIT = True``
# assignment but NOT the instructional ``# Set MANUAL_EDIT = True ...`` comment.
MANUAL_RE = re.compile(r"""^\s*MANUAL_EDIT\s*=\s*True\b""", re.MULTILINE)

# A generated file carrying ``@pytest.mark.stub`` is an unimplemented stub: it
# skips at runtime (never a false-green ``assert True``). Line-anchored so a
# mention inside a comment/string does not count.
STUB_RE = re.compile(r"""^\s*@pytest\.mark\.stub\b""", re.MULTILINE)


def slugify(name: str) -> str:
    """Turn a Rally test-case name into a lowercase identifier fragment.

    Normalises dashes/slashes to spaces, collapses every other non-alphanumeric
    run to a single underscore, and trims leading/trailing underscores. No
    length truncation — the full name is preserved so it reads like Rally.
    """
    s = (name or "").lower()
    s = re.sub(r"[–—/]", " ", s)  # en dash, em dash, slash → space
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def test_identifier(tc_id: str, name: str) -> str:
    """Canonical pytest identifier used for BOTH the file stem and function.

    Example: ``("TC128", "TC01 – Standard Login")`` → ``test_tc128_tc01_standard_login``.
    Includes the Rally id so identifiers stay unique even if two cases share a
    name, and always carries the ``test_`` prefix pytest requires.
    """
    return f"test_{tc_id.lower()}_{slugify(name)}"


def read_tc_id(text: str):
    """Return the Rally id declared in a generated file's text, or None."""
    m = TC_ID_RE.search(text or "")
    return m.group(1) if m else None


def is_manual(text: str) -> bool:
    """True if the file has been locked against re-sync (``MANUAL_EDIT = True``)."""
    return bool(MANUAL_RE.search(text or ""))


def is_stub(text: str) -> bool:
    """True if the file is an auto-generated, not-yet-implemented stub
    (``@pytest.mark.stub`` → skipped at runtime, never a false pass)."""
    return bool(STUB_RE.search(text or ""))
