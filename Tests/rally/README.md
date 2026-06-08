# Rally Test Folders & Test Cases — how to add them

This folder holds the **pytest** test cases that the HTML runner (Test Folder / Test Case modes)
executes. Rally is the source of truth: keep the **TF/TC IDs and names identical to Rally**.

- Each **test case** is a normal pytest test in a file under its Test Folder.
- **Credentials are written inside the test** (not taken from `data/test_users.py`, fixtures, or
  config). The runner only injects the AltDriver (via the `altdriver` fixture) + host/port/platform.
- The runner finds and runs tests through a small registry: **`data/rally_suite.json`**.

## Folder layout

```
Tests/rally/                                   # package (has __init__.py)
└─ TF194_Login/                                # a Test Folder  -> __init__.py + a row in rally_suite.json
   ├─ TF195_Positive_Flow/                     # a sub Test Folder
   │   ├─ __init__.py
   │   └─ test_tc128_standard_login.py         # one test case = one pytest test
   └─ TF196_Negative_Flow/
       ├─ __init__.py
       └─ test_tc132_invalid_credentials.py
```

Directory names are code-safe slugs (e.g. `TF196_Negative_Flow`). The **exact Rally name**
(e.g. `Login – Negative Flow`) is stored in `data/rally_suite.json`, which is what the UI/reports show.

---

## Add a TEST FOLDER

Two equal ways:

### A) From the UI (recommended)
1. Open the runner (`http://localhost:5000`), set **Run Type → Test Folder** (or Test Case(s)).
2. Click **+ Add folder** → enter **ID** (e.g. `TF196`), **Name** (exact Rally name,
   e.g. `Login – Negative Flow`), **Parent** (e.g. `TF194`, or top level). Save.
   → This writes a row into `data/rally_suite.json`.

### B) By hand (JSON)
Add an entry to the `folders` array in **`data/rally_suite.json`**:
```json
{ "id": "TF196", "name": "Login – Negative Flow", "parent": "TF194" }
```

### Then (only if the folder will hold test files)
Create a matching directory with an empty `__init__.py`:
```
Tests/rally/TF194_Login/TF196_Negative_Flow/__init__.py
```

**Files touched:** `data/rally_suite.json` (always) + the new `Tests/rally/<TF…>/__init__.py` (if it holds tests).

---

## Add a TEST CASE  (the important one)

### Step 1 — write the pytest test file
Create `Tests/rally/<TF folder>/test_tcNNN_short_name.py`. Put the **credentials in the test**
and assert the Rally "Expected Result". Use `LoginPage` / `StartScreen` / `utilsdemo` for the steps.

Template (copy `test_tc132_invalid_credentials.py`):
```python
import time
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen
from Utilities import utilsdemo

USERNAME = "vt01229400001"     # <-- provided manually here
PASSWORD = "0000"

def test_invalid_credentials(altdriver):
    driver, _platform = altdriver          # the only thing injected: the AltDriver
    login_page = LoginPage(driver)

    if not login_page.is_open():           # navigate to the login screen
        try:
            utilsdemo.call_method(driver, "AltTesterUtils", "Logout"); time.sleep(2)
        except Exception:
            pass
    login_page.wait_until_open(timeout=20)

    login_page.set_username(USERNAME)      # Rally "Validation Input"
    login_page.set_password(PASSWORD)
    login_page.click_login()
    time.sleep(3)

    # Rally "Validation Expected Result"
    assert not StartScreen(driver).is_present("GO-Map"), "Login should have failed."
    assert login_page.get_notif_text(timeout=5), "Expected an error message."
```

Rules:
- Function name starts with `test_`, signature is `def test_x(altdriver):`.
- `altdriver` yields `(driver, platform)` — unpack it.
- Return / pass = **PASS**; a failed `assert` or any exception = **FAIL** (shown in the live log + report).

### Step 2 — get the test's pytest **nodeid**
`<path-from-project-root>::<function>` with forward slashes, e.g.:
```
Tests/rally/TF194_Login/TF196_Negative_Flow/test_tc132_invalid_credentials.py::test_invalid_credentials
```
Confirm it collects:
```
.venv\Scripts\python -m pytest "<nodeid>" --collect-only -q -o addopts=
```

### Step 3 — register the case (link it to the nodeid)
Two equal ways:

**A) From the UI:** Run Type → Test Case(s) → **+ Add test case** → fill **ID** (`TC132`),
**Name** (exact Rally name), **Folder** (`TF196`), **Pytest nodeid** (from Step 2). Save.

**B) By hand (JSON):** add/replace the entry in the `test_cases` array of **`data/rally_suite.json`**:
```json
{
  "id": "TC132",
  "name": "TC06 – Invalid Credentials",
  "folder": "TF196",
  "action": {
    "kind": "pytest",
    "nodeid": "Tests/rally/TF194_Login/TF196_Negative_Flow/test_tc132_invalid_credentials.py::test_invalid_credentials"
  }
}
```

**Files touched:** the new `Tests/rally/<TF…>/test_*.py` + `data/rally_suite.json`.
(A test case with no `nodeid` shows in the tree but runs as **SKIPPED — "no test linked"**.)

---

## Run it
1. Open the runner, **Run Type → Test Case(s)** (or **Test Folder**).
2. Tick the case (or folder) checkbox — every test case has its own checkbox, so you can run just one.
3. **Dry-run** lists what will run (no app needed). **Run** executes via pytest against the app on
   the Connection host/port (default `127.0.0.1:13000`). Results show per case as
   `TC132 – … PASS/FAIL`, with the live log and downloadable report.

## Sequential / continuation test cases (no re-login)

Test cases selected for one run execute in **one pytest process**, in order, sharing **one app
session** (the `altdriver` fixture is session-scoped — the app is never restarted between cases).
So a later test can **continue from where the previous one stopped** instead of logging in again.

How to write a continuation flow:
- The **first** test in the flow logs in and sets up state.
- **Following** tests **omit the login** and just do the next steps, asserting the carried-over state.

Worked example in `TF195_Positive_Flow` (run the folder, or select both, in order):
- `test_tc128_standard_login.py::test_standard_login` — logs in, lands on the Start Scene.
- `test_tc131_ux_ui_validation.py::test_ux_ui_validation` — **no login**; reuses TC128's session
  and validates the Home-page controls.

Rules / caveats:
- **Run them together, in order.** A continuation test run on its own fails (nobody logged in).
  Use Test Folder (runs the folder in order) or multi-select the cases.
- Order follows the suite order of cases within the folder — author them in sequence.
- Chained tests are coupled: if an earlier test fails or leaves a bad state, later continuation
  tests may fail too.
- Persistence is **within a single run**; a fresh run starts a new session, so the first case
  should always log in.

## Which files matter (summary)

| You're adding…        | Edit / create                                                            |
|-----------------------|--------------------------------------------------------------------------|
| A Test Folder         | `data/rally_suite.json` (folders[]) + `Tests/rally/<TF…>/__init__.py`     |
| A Test Case           | `Tests/rally/<TF…>/test_*.py` (the test) + `data/rally_suite.json` (test_cases[]) |
| Nothing else          | `conftest.py` / `pytest.ini` do **not** need per-case changes            |

The `altdriver` fixture and `--host/--port/--platform` plumbing already live in `conftest.py`;
the runner passes them automatically.
