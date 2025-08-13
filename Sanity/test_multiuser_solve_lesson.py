import os
import time
import pathlib
import pytest

from data.test_users import *
from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))
LESSON_RANGE = range(0, 6)

def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")

@pytest.mark.sanity1
def test_multiuser_full_lessons(altdriver, user):
    driver, platform_name = altdriver
    username = user["username"]
    password = user["password"]
    class_id = user.get("class_id", DEFAULT_CLASS_ID)

    start_page = StartScreen(driver)
    map_page = MapPage(driver)

    # 1) Login
    start_page.login(username, password)

    # 2) Click the GO-Map object
    start_page.go_to_map()

    time.sleep(6)

    # 3) Solve lessons 0..5
    for lesson_num in LESSON_RANGE:
        map_page.solve_lesson_express(class_id, lesson_num)
        time.sleep(1)

    # 4) Write report
    _ensure_reports_dir()
    report_path = _report_filename(platform_name, username)
    with open(report_path, "w", encoding="utf-8") as f:
        map_page.write_activity_report(f)

    print(f"[INFO] Activity report written: {report_path}")
