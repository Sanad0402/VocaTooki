# Architecture

## The layers

Everything the tests do goes through the `vocatooki` package. Modules are layered:
a module only needs **lower** layers while it loads; calling **up** is allowed
inside a function, never at import time. Every module must import on its own
(a unit test imports each one in a fresh interpreter).

```
  scene_names          Unity scene names — plain constants, imports nothing
  ui_actions           find UI objects BY NAME; press them THROUGH THE SCREEN at their live position
  scenes               "is this screen ready" waits, login/hub/onboarding checks
  instructions_parrot  the instructions parrot: blocker, bubble, closing them
  parrot_guard         clears the parrot before EVERY click/tap/swipe, and on every new scene
  evidence_screenshots EvidenceTrail — ordered picture walkthrough (max 7 frames)
  backend_api          which API host every call goes to (set_backend, class map, user state)
  login_session        log in / out, first-entry gender popup, the logged-in user
  map_navigation       the lesson map: level icons, entering levels, app features
  activity_runner      open + play an activity, PASS only when finished, 3 evidence frames
  lesson_modes         full / express / express-hard lesson runs
  exam_solver          open exams, recognise each page type, solve, submit
  exam_results_api     exam results from the backend
  guest_flow, events, daily_games, tasks, treasure_island, pretest_gate   feature flows
  text_to_speech       Google TTS for the speaking activities
  solvers/             one module per activity + solvers/registry.py (THE scene -> solver table)
```

## Rules that keep it working

- **Locate by object name, press through the screen.** Never a hardcoded pixel —
  resolutions change — but every press is a real tap at the object's LIVE position
  (`ui_actions.press_on_screen`; `parrot_guard.install` routes every `AltObject.click()`
  / `.tap()` through it). AltTester's object click fires the object's handlers directly,
  skipping the raycast and the EventSystem; that is how the hard-level gift that locks
  the map shipped (2026-10-06). What the touch hits instead of the object, and every
  bypass, is recorded in `ui_actions.INPUT_FINDINGS`. `VT_PRESS=object` restores the old
  behaviour for a comparison run.
- **A level ends with the completion contract** (`level_completion.finish_level`): leave
  with Back like a user, record and dismiss whatever popup is up (the gift), the map is
  back, a touch reaches its icons, and tapping a level still opens it. One
  `LEVEL COMPLETION` row per level, PASSED or FAILED, saying what it could not cover.
- **No size is a pixel count.** A distance, tolerance or clamp comes from the objects on
  screen (`ui_actions.typical_gap` / `cluster_tolerance` / `band_of` read the spacing of the
  rows, columns or thumbs being grouped) or from the live window (`ui_actions.scaled` turns a
  value measured on a window of a known height into the live window's; `screen_size` for
  fractions). The app has run at 1255x720 up to 2560x1440 (2026-10-06).
- **Leave an activity through its own popup, and wait for the list.** The result popup covers
  the toolbar; `when_finish_activity` presses the popup's ExitButton first and returns only
  when the activity selection is back and settled. Never the map between activities.
- **Let the parrot finish.** The blocker is clicked at once; the bubble is left to hide by
  itself, and the icon is pressed only after `BUBBLE_PATIENCE` (8s).
- **A level icon is "entered" only when the map scene is gone** after the tap
  (`map_navigation._open_level_icon`); a map that stays is a recorded `no-effect`.
- **Never pass without verifying.** A lesson-run activity is PASSED only when the
  game shows it finished (counter N/N or the success screen); otherwise it is
  retried, then FAILED with the reason. An unimplemented flow is a loud skip.
- **Every run names its API.** `backend_api.set_backend()` points every call
  (class map, user state, exams, tasks) at one host; "auto" asks each in turn.
  Values a run reassigns (`VT_DATA_API`, `VT_TASKS_API`, the logged-in user) are
  read as `module.NAME`, never copied with `from … import`.
- **The parrot is handled centrally** (`parrot_guard`): icon (`HelpButton`) first,
  an empty point only as the fallback, never a blind press.
- **Evidence:** start → mid (first time the counter reaches half) → final feedback.

## Adding a solver for a new activity

1. Create `vocatooki/solvers/<activity_name>.py` (3rd-grade letter activities go in
   `solvers/third_grade/`). Import what you need from `vocatooki` modules explicitly.
2. Drive it by the **progress counter** (`read_activity_progress`), not a fixed
   number of rounds; read the answer from the game's own component properties.
3. Pass it **live on easy, medium and hard** before mapping it.
4. Add the scene to `vocatooki/solvers/registry.py` — the one table every path uses.
5. Re-export it in `Activities/activitiesDemo.py` if older code should reach it there.
6. Run `python Scripts/safety_check.py`, then update the contract snapshot
   (`Tests/unit/contract_snapshot.json`) in the same commit if you added names on purpose.

## Compatibility front doors

`Utilities/utilsdemo.py` and `Activities/activitiesDemo.py` re-export every name
the framework had before the reorganisation (frozen in
`Tests/unit/contract_snapshot.json`). The generated Rally tests, the runner and
the page objects still use them. Renamed files keep their old name as a
`sys.modules` alias (`Pages/LoginPage.py` → `Pages/login_page.py`, …), so both names
are the same module. New code should import from `vocatooki` directly.

## The safety net

`python Scripts/safety_check.py` — compile everything, run `Tests/unit` (contract:
every frozen name still resolves, every scene still reaches the same solver,
every name the generator writes exists, every module imports on its own, renamed
modules are aliases; behaviour: finish-to-pass, mid frame, backend switching,
parrot guard, Frogger, guest labels), and check the full suite still collects.
