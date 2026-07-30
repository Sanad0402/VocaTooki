# VocaTooki App Map — what the automation sees

The Unity client as read through AltTester: every scene, how to get between
them, and the object names that identify each screen. Everything here was
surveyed on the running app (account `vt233624`, 2026-07-30) — not inferred
from code — and is what the test generator and `Utilities/utilsdemo.py` rely on.

Use it when writing a Rally case, adding a solver, or debugging a test that
cannot find its screen.

---

## 1. Navigation graph

```
NewStartScene ──GO-Map──> MapScene ──<level icon>──┬─ lesson: WordListScene ──nextButton──> VendingMachineScene ──Toggle──> ActivitySelectionScene ──thumb──> <ACTIVITY scene>
      ^                       │                    └─ exam:   "Tests" scene (pages 1/3 → 3/3)
      └────BackButton─────────┘
```

**Back from `MapScene` lands on `NewStartScene`.** That makes the start screen
the app's reliable anchor: from anywhere, keep pressing back until you reach it,
then `GO-Map` comes down a known path. `utilsdemo.ensure_on_map()` and
`return_to_start()` do exactly this.

> **Trap:** the login screen is an *overlay* on `NewStartScene`, and the hub
> objects stay findable behind it. "`GO-Map` is findable" does **not** mean you
> are logged in — check `LoginPage.is_open()` / `UserInputField` instead.

### Scenes

`NewStartScene` (hub + login overlay) · `MapScene` · `WordListScene` (level
intro / word list) · `VendingMachineScene` (first visit to a level) ·
`ActivitySelectionScene` · `Tests` (exams) · `VTWordGuess` (Wordle) ·
`VTWORD_CONNECT` (Word Connect) · one scene per activity, named by
`AltTesterUtils.GetCurrentActivity` (`PIPES`, `BRICKOUT`, `RINGS`, `TETRIS`, …).

---

## 2. The map — icons carry their number *and* kind

Icons are named `<Prefab>(Clone) <level number>`, so click them **by name**;
counting positions in the icon list breaks the moment a map has gaps or a
different prefab. `utilsdemo._level_icon_by_number()` handles every kind, and
`level_kind(driver, 40)` tells you what a level is before opening it.

| prefab | kind | levels on the surveyed account |
|---|---|---|
| `LessonLevelIcon` | lesson (3 activities) | 1, 2, 3, 5, 6, 7, 10 … (165) |
| `TestLevelIcon` | **exam** | 4, 8, 13, 17, 22, 26, 31, 35, 40, 45 … every 4–5 |
| `DialogueLevelIcon` | dialogue | 9, 27, 46, 64, 82 … |
| `RCLevelIcon` | reading comprehension | 18, 36, 55, 73, 91 … |
| `TaskLevelIcon` | task | 41 |
| `AiDialogueLevelIcon` | AI dialogue | 132 |

Icons live under `//Levels/level_icons/*`. Other map objects: `BackButton`,
`HelpButton`, `CountersPanel`, `collect_coins`, `LessonLBCanvas` (leaderboard),
`UserProfileCanvas`. The map prefab itself varies by chapter (`5thMap(Clone)`).

---

## 3. Start-screen features

| button | opens | markers worth asserting on | how to leave |
|---|---|---|---|
| `GO-Map` | `MapScene` | `//Levels/level_icons/*` | `BackButton` |
| `GO-Tasks` | `TasksSelectionScene` | `TaskCard-Closed(Clone)`, `ALL/Open/Sent/Checked/Missed-NavigationTab` | `prev` |
| `GO-Events` | `EventSelectionScene` | `EventCard(Clone)`, `StartButton`, `WinnersButton`, `CloseDateText` | `BackButton` |
| `GO-Audiobook` | `AudiobookLibraryScene` | `BookCard(Clone)`, `PlayButton` | `BackButton` |
| `GO-Competitions` | `TournamentSelectionScene` | `Toggles` | `BackButton` |
| `GO-Treasure_Island` | `TreasureIsland` | `GO-TI-*` prefabs, `GO-TI-Progress_Bar-Tube` | **none** |
| `GO-Daily` | `DailyGamesSelection` | `WinnersCards`, `Ctrl-Card_1st` | `prev` |
| `GO-Dialogue` | `DialogueSelectionScene` | `DialogueSelectionButton(Clone)` | `BackButton` |
| `GO-Multiplayer` | `MultiplayerHub` | `Head_to_Head-Enter_Button`, `DraWin-Enter_Button` | **none** |
| `GO-Avatar_Builder` | `AvatarBuilderScene` | `Level1/2/3_ButtonGroup` | `BackButton` |
| `SettingsButton` | *popup on the start screen* | `SoundOnButton`, `MusicOnButton`, `LanguageToggleGroup` | **`Exit`** |
| `WordListButton` | `WordListScene` | `audioButton`, `upButton`, `downButton` | **`nextButton`** |
| `UserStateButton` | *popup on the start screen* | "User State Status", "Up time: …" | `Button` |

Also on the start screen: `LogoutButton`, `ExitButton_1` (**quits the app** —
never click it in a test), `HelpButton`, `GO-Main_Screen`.

> **Two screens have no back/close button at all** — the word list (leave with
> `nextButton`) and Treasure Island. A naive "press back until home" loop
> strands there, which is why `utilsdemo` includes `Exit` and `nextButton` in
> its exit chain (`Exit` matched exactly, so it can never hit `ExitButton_1`)
> and falls back to logout+login.

`utilsdemo.APP_FEATURES` holds this table in code; `open_feature(driver,
"events")` returns to the start screen from anywhere, clicks through, and fails
if the feature does not actually appear.

---

## 4. Inside a level

### Activity selection — which thumb is which activity

All three thumbs are named `ActivityThumb`. The activity title is a separate
`Text - RTLTMP` object **sharing the thumb's x coordinate** (a fourth one,
higher up, is the lesson title). `utilsdemo.list_level_activities()` pairs them
by proximity, so the right activity is clicked directly instead of opening each
one to see what it is.

Example — level 43 "What is Made in Japan": `['Pipes', 'Break Out', 'Rings']`.

> **The UI title is not the Rally name.** "Break Out" on screen is Rally's
> "Brickout" (scene `BRICKOUT`). Aliases live in `utilsdemo.ACTIVITY_UI_TITLES`.

### First visit to a level

`WordListScene` (press `nextButton`, possibly several pages) →
`VendingMachineScene` (press `Toggle`) → `ActivitySelectionScene`. Both loads
take several seconds, so `open_level_to_activities()` drives it as a loop rather
than one shot per step.

### Exams (`Tests` scene)

`TestNumText` holds the page counter (`"1/3"`, `"2/3"`, `"3/3"`) — its presence
is how `open_exam()` knows the exam is up. Finish flow: `SubmitButton` →
`YesButton` → `Collect` → `BackButton`.

Page type is detected per page from marker objects
(`utilsdemo.detect_exam_type`): `SpellingInputField`, `Context`,
`WordAudioShape(Clone)`, `MatchShapeImage(Clone)`, `QuestionTemplate(Clone)`, …
**The three pages of one exam are usually different types**, so detection has to
run per page. A verified run (level 40) solved
`exams_audio_to_meaning` → `exam_spelling` → `exam_multiple_choice`.

---

## 5. Daily Games

`GO-Daily` → `DailyGamesSelection` → `//Wordle/GameIcon` or
`//Word Connect/GameIcon` → leaderboard panel → **`PlayNowButton`**.

The two entries named `Wordle` / `Word Connect` are containers — `GameIcon`
inside them is the control. `Exit` closes the panel.

| game | scene | how it is solved |
|---|---|---|
| Wordle | `VTWordGuess` | answer read from `Gameplay Manager` → `KaelmixStudioGameAssets.TemplateWordGuess.GameplayManager.word`, then `Key (<letter>)` taps + `Enter` |
| Word Connect | `VTWORD_CONNECT` | puzzle bank read from `GameCanvas` → `WordConnect.WordsConnect.levels` (`{letters, words}`) with `currentLevel`, matched against the letters on the board, then swiped |

`GetCurrentActivity` returns `"Undefined"` for daily games — identify them by
**scene**, not activity.

> **Once per day, per account.** After playing, the Daily Games page stops
> opening for that user (there is a `LevelLockedTimer` countdown). A daily test
> re-run on the same day fails with "already played today" — that is deliberate,
> not flakiness. Schedule it once a day, or rotate accounts.

---

## 6. AltTesterUtils

A component on `AltTesterPrefab` (`Assembly-CSharp`), called through
`utilsdemo.call_method`. Only three methods are used anywhere in the project:

| method | returns / does |
|---|---|
| `Logout` | logs the user out (back to the login overlay) |
| `GetCurrentActivity` | the current activity's scene name (`"Undefined"` outside activities) |
| `LoadPreviousScene` | goes back one scene |

---

## 7. Practical notes

- **The AltTester licence allows 2 connected drivers at once.** The MCP session,
  a standalone `alttester` CLI daemon, the panel's discovery connection and the
  pytest fixture each take one. Free them (`alttester disconnect`, or
  `runner.mcp_discovery.disconnect()`) before a run, or the third connection
  fails with a bare `ConnectionError`.
- **The app-id changes when the game restarts.** `runner/mcp_discovery.py`
  handles this by looking the game up in `apps` and reconnecting.
- **App text is multilingual** (English + Hebrew). Read and write files with an
  explicit `encoding="utf-8"`; Windows' default cp1252 raises on the em dashes
  and Hebrew in Rally descriptions and on screen.

See also: [RUNNER_PANEL_GUIDE.md](RUNNER_PANEL_GUIDE.md) for the panel and the
Rally → generate → run workflow.
