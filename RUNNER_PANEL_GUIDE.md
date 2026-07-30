# VocaTooki Test Runner — Panel & Framework Guide

How the Flask control panel works, the two ways to add test cases (manual or
synced from Rally), and the recommended day-to-day workflow.

- **Panel:** `python run_panel.py` → http://localhost:5000
- **Requires** the game running with AltTester instrumentation, reachable on the
  configured host/port (default `127.0.0.1:13000`) for real runs.

---

## 1. The panel at a glance

**Left = Configuration · Right = Progress / Results / Live log.**

Top control — **Run Type**:

| Run Type | What it runs | Driven by |
|----------|--------------|-----------|
| **Lesson Range (users)** | Drives the game directly: logs in each user and solves a lesson range | Users + lesson range + mode |
| **Test Folder** | Every pytest case inside the selected folder(s) | Rally suite tree |
| **Test Case(s)** | Only the cases you tick | Rally suite tree |

Other blocks:
- **Rally card** — `Sync from Rally`, `Test connection`, `Change project`.
- **Suite tree** — folders + cases with checkboxes, status badges, and per-row `edit` / `delete` / `make real` / `make stub`.
- **Toolbar** — `+ Add folder`, `+ Add test case`, `🔎 Generate from live app`.
- **Connection (advanced)** — platform / host / port / app_id / device_instance_id.
- **Actions** — `Run`, `Dry-run`, `Stop`, `Email report`, report links.

---

## 2. How a run maps to the framework

When you tick case(s) and click **Run**:

```
select case → its action.nodeid → preflight AltTester (host:port)
   → pytest <nodeid> → live log streams → PASS / FAIL / SKIPPED per case → report
```

- The **game must be running** (preflight), or the run stops with
  "Could not connect to AltTester…".
- Each case runs its **real linked pytest file** under `Tests/rally/`.
- File/function/nodeid names are kept aligned by `runner/rally_naming.py`, so a
  case always maps to exactly one test.

---

## 3. Status badges & per-case controls

| Badge | Meaning | Runs as |
|-------|---------|---------|
| 🟢 **real** | Implemented, has assertions | PASS / FAIL |
| 🟠 **stub** | Auto-generated, not finished (`@pytest.mark.stub` → skips) | SKIPPED |
| ⚪ **no test** | No pytest nodeid linked yet | SKIPPED |

Per case: **make real / make stub** (flips the file's markers and locks
`MANUAL_EDIT = True`), **edit**, **delete**.

> A **stub never shows a false green** — it skips. That's intentional: a synced
> case with no real steps yet must not look "passing".

---

## 4. Two ways to add test cases

### Way 1 — Synced from Rally (main path)

1. In **Rally**, set the test case's **Method = `Automated`**.
2. Panel → **Sync from Rally**. The case appears as a 🟠 **stub**; its file is
   generated under `Tests/rally/…` carrying the Rally **description + steps**.
3. Make it real (pick one):
   - Put the app on the case's screen → tick it → **🔎 Generate from live app**
     (writes real interactions/assertions from the steps/description + the live
     elements), **or**
   - Edit the generated file by hand.
4. **Run** it.

> Sync also **prunes** generated files whose case left Rally — *unless* the file
> has `MANUAL_EDIT = True`, which locks it against overwrite and prune.

### Way 2 — Manually (no Rally)

**From the panel:** **+ Add test case** → fill **ID** (e.g. `TC900`), **Name**,
**Folder**, and **Pytest nodeid** (`Tests/rally/…/test_x.py::test_x`).
- If that file exists → shows 🟢 real / 🟠 stub from its content.
- If not → ⚪ *no test* (runs as SKIPPED until you create it).

**In code:** create `Tests/rally/<folder>/test_tc900_x.py`:

```python
TC_ID = "TC900"
MANUAL_EDIT = True   # protect from Rally sync

def test_tc900_x(altdriver):
    driver, _platform = altdriver
    # ... drive the app, then assert ...
    assert SomePage(driver).is_present("SomeElement")
```

Then point a case's nodeid at it (via **+ Add test case**), or it appears
automatically on the next sync if it also exists in Rally.

---

## 5. 🔎 Generate from live app — what it produces (per selected case)

Connects once, reads the **current scene's** elements, then for each ticked case:

| Source of steps | Result |
|-----------------|--------|
| Positive login **with credentials** | Complete login test (asserts `GO-Map`) |
| Structured Rally steps (Input / Expected) | Real interactions + assertions |
| Steps / expected written in the **Description** | Real presence assertions |
| Nothing matches confidently | Honest **stub** (skips) — no fake assertion |

- Derived tests are written with `MANUAL_EDIT = True` and a **REVIEW** header.
- It reads the **current scene only** — navigate the app to the target screen
  before generating.

CLI equivalent (one case):
```
python -m runner.live_skeleton TC452 --host 127.0.0.1 --port 13000
```

---

## 6. Recommended workflow (the full loop)

```
1. Rally: mark cases Method = Automated
2. Panel: Sync from Rally            → cases appear as stubs (with steps)
3. Run the game (AltTester on 13000), navigate to the case's screen
4. Tick case → 🔎 Generate from live app   → real interactions/assertions
5. Review the file; keep MANUAL_EDIT = True to lock it
6. Tick case(s) → Run                → live log + PASS/FAIL + downloadable report
7. Re-sync anytime — locked (MANUAL_EDIT) files are preserved
```

**Two rules to remember**
- **`MANUAL_EDIT = True`** = "this file is mine — don't overwrite or prune on sync."
- **Generate from live app reads the current scene** — be on the right screen first.

---

## 7. Running from the command line (no panel)

```bash
# one case / nodeid
pytest "Tests/rally/TF194_Login/TF195_Login__Positive_Flow/test_tc128_tc01_standard_login_with_valid_credentials.py::test_tc128_tc01_standard_login_with_valid_credentials" \
  --platform WindowsEditor --host 127.0.0.1 --port 13000

# everything except unfinished stubs
pytest -m "not stub" --platform WindowsEditor --host 127.0.0.1 --port 13000
```

Reports are written to `REPORTS_DIR` (default `~/Downloads/reports`).

---

## The app itself

[APP_MAP.md](APP_MAP.md) documents what the automation sees inside the game —
every scene and how to get between them, the start-screen features and what
identifies each one, how activities/exams/daily games are recognised and solved,
and the practical traps (2-driver licence limit, the changing app-id, UTF-8).
Read it before writing a Rally case or adding a solver.
