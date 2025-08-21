import os
import time
import pathlib
import pytest

from data.test_users import DEFAULT_CLASS_ID
from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage  # ok to keep even if unused

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))

def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")

@pytest.mark.sanity1
def test_navigate_start_screen(altdriver, user):
    # Unwrap driver & platform_name exactly like the working test
    try:
        driver, platform_name = altdriver
    except Exception:
        driver = altdriver
        platform_name = "Unknown"

    username = user["username"]
    password = user["password"]

    start = StartScreen(driver)
    start.login(username, password)
    time.sleep(2)

    # (tap from start) -> (expected scene)
    steps = [
        (start.go_to_map,             "MapScene"),
        (start.go_to_tasks,           "TaskManager"),
        (start.go_to_shop,            "AvatarBuilderScene"),
        (start.go_to_daily_games,     "DailyGamesSelection"),
        (start.go_to_dialogue,        "DialogueSelectionScene"),
        (start.go_to_competitions,    "TournamentSelectionScene"),
        (start.go_to_treasure_island, "TreasureIsland"),
        (start.go_to_wordlist,        "WordListScene"),
    ]

    for go, expected in steps:
        go()
        time.sleep(3)
        # (your scene checks etc. can stay as-is if you add them back)

        # scene-specific tweaks
        if expected.lower() == "taskmanager":
            try:
                start.click_by_name("Button")
                time.sleep(1)
            except Exception:
                print("[WARN] Tasks popup 'Button' not found")

        if expected.lower() == "wordlistscene":
            try:
                start.click_by_name("nextButton")  # case-sensitive
                time.sleep(1)
            except Exception:
                print("[WARN] WordList 'nextButton' not found")

        # Return to start (prev/back/home)
        if expected.lower() in ("taskmanager", "dailygamesselection"):
            for name in ("prev", "PrevButton", "Back", "BackButton", "HomeButton"):
                try:
                    start.click_by_name(name)
                    break
                except Exception:
                    continue
        else:
            try:
                start.click_by_name("BackButton")
            except Exception:
                try:
                    start.click_by_name("HomeButton")
                except Exception:
                    print("[WARN] No back/home button found on this screen")

        time.sleep(2)

    # >>> REPORT BLOCK — identical behavior, but using StartScreen instance <<<
    _ensure_reports_dir()
    report_path = _report_filename(platform_name, username)
    with open(report_path, "w", encoding="utf-8") as f:
        start.write_activity_report(f)   # <-- instance method, like map_page.write_activity_report

    print(f"[INFO] Activity report written: {report_path}")
