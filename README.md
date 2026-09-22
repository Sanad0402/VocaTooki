# VocaTooki Test Automation

Automated tests for the VocaTooki game (Unity), driven through **AltTester**:
logs in, walks the lesson map, plays every activity to the end with a solver,
sits exams, runs guest / events / tasks / Treasure Island flows, and reports
results back to **Rally** — from a web **runner panel** or from pytest.

## Folder map

| Folder / file | What it is |
|---|---|
| `vocatooki/` | **The framework** — one module per domain (navigation, activities, exams, guest, …). See [ARCHITECTURE.md](ARCHITECTURE.md). |
| `vocatooki/solvers/` | One solver per activity, named after it (`frogger.py`, `missing_bubble.py`, …); 3rd grade in `solvers/third_grade/`. Index in `solvers/__init__.py`. |
| `Pages/` | Page objects (`login_page.py`, `start_screen.py`, `map_page.py`, `page_template.py`). |
| `runner/` + `run_panel.py` | The runner panel (Flask): pick a run type and an API, run, see results, post to Rally. |
| `Tests/rally/` | Test cases **generated** from Rally in the panel (do not hand-edit — regenerate). |
| `Tests/unit/` | Offline safety net: the framework contract + behaviour pins (no app needed). |
| `Scripts/` | Utilities: `safety_check.py`, Rally sync scripts, guest-data tools. |
| `data/` | Users, the synced Rally suite, run history. |
| `Utilities/utilsdemo.py`, `Activities/activitiesDemo.py` | **Compatibility front doors** — re-export the framework so older code and generated tests keep working. New code imports from `vocatooki`. |

## Run it

- **Runner panel:** `python run_panel.py` → http://127.0.0.1:5000 — the Run dialog asks
  which API (auto / green / vtbe / vtbetest / vtbe2027) before every run.
  See [RUNNER_PANEL_GUIDE.md](RUNNER_PANEL_GUIDE.md).
- **Tests from the command line:** see [How_to_Run_Tests_VocaTooki_Automation.md](How_to_Run_Tests_VocaTooki_Automation.md).
- **Before committing any framework change:** `python Scripts/safety_check.py`
  (compiles everything, runs the offline contract/behaviour tests, checks the whole
  suite still collects). A change is done only when it passes.

The app has to be running in the Unity Editor with AltTester on port 13000.
The AltTester licence allows **two** connected drivers — close MCP/CLI sessions
before a run.

More: [APP_MAP.md](APP_MAP.md) (the app's scenes and navigation).
