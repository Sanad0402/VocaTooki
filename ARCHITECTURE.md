# Architecture

## The layers

Everything the tests do goes through the `vocatooki` package. Modules are layered:
a module only needs **lower** layers while it loads; calling **up** is allowed
inside a function, never at import time. Every module must import on its own
(a unit test imports each one in a fresh interpreter).

```
  scene_names          Unity scene names — plain constants, imports nothing
  ui_actions           find / press / read UI objects BY NAME (never coordinates)
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

- **Click by object name, never by screen coordinates** — resolutions change.
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
