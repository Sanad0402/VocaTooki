# Sanity/test_single_lesson_express.py
import os
import time
import pathlib
import pytest

from data.test_users import DEFAULT_CLASS_ID
from Pages.StartScreen import StartScreen            # match file casing
from Pages.map_page import MapPage                   # file is map_page.py

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))

def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")

@pytest.mark.sanity1
def test_single_lesson_express(altdriver, user, request):
    """
    Runs ONE lesson from the map for the given user.
    Uses the same flow as solve_lesson_express: levels -> exam.
    CLI:
      --lesson <idx>       map node index (e.g., 0/1/2; exam often at 4)
      --levels-only        run only Easy/Medium/Hard (skip exam)
    """
    # Read CLI args (conftest.py adds these)
    lesson_num = request.config.getoption("--lesson")
    levels_only = request.config.getoption("--levels-only")

    driver, platform_name = altdriver
    username = user["username"]
    password = user["password"]
    class_id = user.get("class_id", DEFAULT_CLASS_ID)

    start_page = StartScreen(driver)
    map_page = MapPage(driver)

    # 1) Login and go to map
    start_page.login(username, password)
    start_page.go_to_map()
    time.sleep(6)  # replace with a robust wait if you expose a map root

    # 2) Run only the requested lesson
    if levels_only:
        map_page.solve_lesson_levels_express(class_id, lesson_num)   # levels only
    else:
        map_page.solve_lesson_express(class_id, lesson_num)          # levels + exam

    # 3) Write the activity report (file-handle API)
    _ensure_reports_dir()
    report_path = _report_filename(platform_name, username)
    with open(report_path, "w", encoding="utf-8") as f:
        map_page.write_activity_report(f)

    print(f"[INFO] Activity report written: {report_path}")
# Sanity/test_single_lesson_express.py
import os
import time
import pathlib
import pytest

from data.test_users import DEFAULT_CLASS_ID
from Pages.StartScreen import StartScreen            # match file casing
from Pages.map_page import MapPage                   # file is map_page.py

REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))

def _ensure_reports_dir():
    pathlib.Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def _report_filename(platform_name: str, username: str) -> str:
    safe_user = "".join(c for c in username if c.isalnum() or c in ("@", "_", "-", ".")).replace("@", "_at_")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORTS_DIR, f"ActivityReport_{platform_name}_{safe_user}_{ts}.txt")

@pytest.mark.sanity1
def test_single_lesson_express(altdriver, user, request):
    """
    Runs ONE lesson from the map for the given user.
    Uses the same flow as solve_lesson_express: levels -> exam.
    CLI:
      --lesson <idx>       map node index (e.g., 0/1/2; exam often at 4)
      --levels-only        run only Easy/Medium/Hard (skip exam)
    """
    # Read CLI args (conftest.py adds these)
    lesson_num = request.config.getoption("--lesson")

    driver, platform_name = altdriver
    username = user["username"]
    password = user["password"]
    class_id = user.get("class_id", DEFAULT_CLASS_ID)

    start_page = StartScreen(driver)
    map_page = MapPage(driver)

    # 1) Login and go to map
    start_page.login(username, password)
    start_page.go_to_map()
    time.sleep(6)  # replace with a robust wait if you expose a map root

    # 2) Run only the requested lesson

    map_page.solve_lesson_express(class_id, lesson_num)          # levels + exam

    # 3) Write the activity report (file-handle API)
    _ensure_reports_dir()
    report_path = _report_filename(platform_name, username)
    with open(report_path, "w", encoding="utf-8") as f:
        map_page.write_activity_report(f)

    print(f"[INFO] Activity report written: {report_path}")
