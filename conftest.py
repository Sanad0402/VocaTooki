# conftest.py
import os
import logging
from datetime import datetime

import pytest
from alttester import AltDriver
from loguru import logger as loguru_logger

from Utilities import utilsdemo
from data.test_users import TEST_USERS, DEFAULT_CLASS_ID

test_results = []  # Store test status info


# -----------------------------
# Logging: hide AltTester noise
# -----------------------------
def pytest_configure(config):
    # Standard python logging (your logs)
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,  # Python 3.8+
        )
    except TypeError:
        # Older Python fallback (no "force")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    # Silence python-logging noisy libs (if any)
    for libname in (
        "alttester",
        "alttester.altdriver",
        "alttester._websocket",
        "websocket",
        "urllib3",
    ):
        py_logger = logging.getLogger(libname)
        py_logger.setLevel(logging.ERROR)
        py_logger.propagate = False

    # Silence Loguru logs from AltTester modules (this is what prints the DEBUG "Received:" line)
    # AltTester uses loguru inside its own modules, so disable those names explicitly.
    for loguru_name in (
        "alttester",
        "alttester.altdriver",
        "alttester._websocket",
        "alttester._command",
        "alttester._base_alt_object",
    ):
        loguru_logger.disable(loguru_name)


# -----------------------------
# Activity report reset
# -----------------------------
@pytest.fixture(scope="session", autouse=True)
def _reset_activity_report():
    try:
        from Utilities.utilsdemo import activity_report
        activity_report.clear()
    except Exception:
        pass
    yield


# -----------------------------
# CLI options
# -----------------------------
def pytest_addoption(parser):
    parser.addoption("--platform", action="store", default="WindowsEditor", help="Platform name")
    parser.addoption("--host", action="store", default="127.0.0.1", help="AltTester host")
    parser.addoption("--port", action="store", type=int, default=13000, help="AltTester port")

    # These are optional. Empty string means "not provided".
    parser.addoption("--app_id", action="store", default="", help="App ID (optional)")
    parser.addoption("--device_instance_id", action="store", default="", help="Device ID (optional)")

    parser.addoption(
        "--reports_dir",
        action="store",
        default=os.getenv("REPORTS_DIR", r"C:\Users\sanad\Downloads\reports"),
        help="Directory to save reports",
    )
    parser.addoption("--user-mode", choices=["single", "all"], default="single")
    parser.addoption("--user-index", type=int, default=0)

    parser.addoption(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="easy",
        help="Difficulty to run for single-level execution.",
    )
    parser.addoption("--level", type=int, default=None, help="Map node index to run (0/1/2 are lessons; 4 is exam).")

    parser.addoption(
        "--lessons",
        action="store",
        default=None,
        help='Lessons as CSV or JSON-like list, e.g. "1,2,3" or "[1,2,3]"',
    )
    parser.addoption("--lesson", action="store", default=None, help="Single lesson number")
    parser.addoption("--levels-only", action="store_true", default=False, help="Run level solver only")
    parser.addoption("--class-id", action="store", default=None, help="Override class ID for this test (optional)")


# -----------------------------
# AltDriver fixture (FIXED)
# -----------------------------
@pytest.fixture(scope="session")
def altdriver(request):
    platform = request.config.getoption("--platform")

    # Optional values: if empty -> do not pass to AltDriver
    app_id = (request.config.getoption("--app_id") or "").strip()
    device_instance_id = (request.config.getoption("--device_instance_id") or "").strip()

    driver_kwargs = dict(
        host=request.config.getoption("--host"),
        port=request.config.getoption("--port"),
        platform=platform,
        enable_logging=True,  # keep True if you still want your own logs; AltTester logs are disabled above
    )

    # ✅ only include if provided
    if app_id:
        driver_kwargs["app_id"] = app_id
    if device_instance_id:
        driver_kwargs["device_instance_id"] = device_instance_id

    driver = AltDriver(**driver_kwargs)

    setattr(utilsdemo, "RUN_PLATFORM", platform)

    yield driver, platform

    # Graceful shutdown
    try:
        driver.close()
    except Exception:
        try:
            driver.stop()
        except Exception:
            pass


# -----------------------------
# Collect per-test results
# -----------------------------
def pytest_runtest_logreport(report):
    if report.when == "call":
        test_results.append(
            {
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "longrepr": str(report.longrepr) if report.failed else "",
                "duration": report.duration,
            }
        )


# -----------------------------
# Write a report at end
# -----------------------------
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    reports_dir = session.config.getoption("--reports_dir")
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(reports_dir, f"activity_report_{timestamp}.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("🧪 TEST CASE EXECUTION REPORT\n")
        f.write("=" * 40 + "\n\n")
        for entry in test_results:
            f.write(f"Test    : {entry['nodeid']}\n")
            f.write(f"Outcome : {entry['outcome'].upper()}\n")
            f.write(f"Duration: {entry['duration']:.2f}s\n")
            if entry["outcome"] == "failed":
                f.write(f"Error   :\n{entry['longrepr']}\n")
            f.write("-" * 40 + "\n")

        f.write("\n\n")

        try:
            utilsdemo.write_activity_report(f)
        except Exception as e:
            f.write("[WARN] write_activity_report failed: " + str(e) + "\n")

    print(f"[REPORT] Full report saved to: {report_path}")


# -----------------------------
# Parametrize users
# -----------------------------
def pytest_generate_tests(metafunc):
    if "user" in metafunc.fixturenames:
        mode = metafunc.config.getoption("--user-mode")
        idx = metafunc.config.getoption("--user-index")

        if mode == "single":
            if idx < 0 or idx >= len(TEST_USERS):
                print(f"[WARN] --user-index {idx} out of range. Using 0.")
                idx = 0
            users = [TEST_USERS[idx]]
        else:
            users = TEST_USERS

        metafunc.parametrize("user", users, ids=[u["username"] for u in users], scope="class")


# -----------------------------
# Helpers / fixtures
# -----------------------------
@pytest.fixture
def single_lesson_num(request):
    try:
        return int(request.config.getoption("--lesson"))
    except Exception:
        return 0


@pytest.fixture
def single_class_id(request):
    cid = request.config.getoption("--class-id")
    return cid if cid else DEFAULT_CLASS_ID


def _parse_lessons(val):
    # Accept list/tuple, CSV string, or JSON-ish string with brackets/spaces
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return [int(x) for x in val if str(x).strip().isdigit()]

    s = str(val).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    s = s.replace(" ", "")
    out = []
    for part in s.split(","):
        if part == "":
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out or None


@pytest.fixture
def lesson_numbers(request):
    lessons_arg = request.config.getoption("--lessons")
    parsed = _parse_lessons(lessons_arg)
    if parsed:
        return parsed

    single = request.config.getoption("--lesson")
    parsed_single = _parse_lessons(single)
    if parsed_single:
        return parsed_single

    return [0]
