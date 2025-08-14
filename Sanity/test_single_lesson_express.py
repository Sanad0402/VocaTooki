import os
import time
import pathlib
import pytest

from data.test_users import DEFAULT_CLASS_ID
from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))

def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")

@pytest.mark.sanity1
def test_single_lesson_express(altdriver, user, lesson_numbers):
    """Runs one or more lessons from --lesson or --lessons."""
    driver, platform_name = altdriver
    username = user["username"]
    password = user["password"]
    class_id = user.get("class_id", DEFAULT_CLASS_ID)

    start_page = StartScreen(driver)
    map_page = MapPage(driver)

    # Login and navigate to map
    start_page.login(username, password)
    start_page.go_to_map()
    time.sleep(6)

    for lesson_number in lesson_numbers:
        map_page.solve_lesson_express(class_id, lesson_number)
        time.sleep(1)

    # Save activity report
    _ensure_reports_dir()
    report_path = _report_filename(platform_name, username)
    with open(report_path, "w", encoding="utf-8") as f:
        map_page.write_activity_report(f)

    print(f"[INFO] Activity report written: {report_path}")
