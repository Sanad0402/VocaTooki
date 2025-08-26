# conftest.py
import os
import pytest
from datetime import datetime
from alttester import AltDriver
from Utilities import utilsdemo
from data.test_users import TEST_USERS, DEFAULT_CLASS_ID  # Added missing import for clarity

test_results = []  # Store test status info


@pytest.fixture(scope="session", autouse=True)
def _reset_activity_report():
    try:
        from Utilities.utilsdemo import activity_report
        activity_report.clear()
    except Exception:
        pass
    yield


def pytest_addoption(parser):
    parser.addoption("--platform", action="store", default="WindowsEditor", help="Platform name")
    parser.addoption("--app_id", action="store", default="", help="App ID")
    parser.addoption("--device_instance_id", action="store", default="", help="Device ID")
    parser.addoption("--reports_dir", action="store",
                     default=os.getenv("REPORTS_DIR", r"C:\Users\sanad\Downloads\reports"),
                     help="Directory to save reports")
    parser.addoption("--user-mode", choices=["single", "all"], default="single")
    parser.addoption("--user-index", type=int, default=0)
    parser.addoption("--difficulty", choices=["easy", "medium", "hard"], default="easy",
                     help="Difficulty to run for single-level execution.")
    parser.addoption("--level", type=int, default=None,
                     help="Map node index to run (0/1/2 are lessons; 4 is exam).")
    parser.addoption("--lesson", type=int, default=None,  # backward-compat alias
                     help="[Alias of --level] Map node index to run.")
    parser.addoption("--class-id", action="store", default=None,
                     help="Override class ID for this test (optional)")
    parser.addoption("--lessons", action="store", default="0", help="Comma-separated lesson indexes to run")
    parser.addoption("--levels-only", action="store_true", default=False, help="Run levels only, skip exam")


@pytest.fixture(scope="session")
def altdriver(request):
    platform = request.config.getoption("--platform")
    app_id = request.config.getoption("--app_id")
    device_instance_id = request.config.getoption("--device_instance_id")

    driver = AltDriver(
        host="127.0.0.1",
        port=13000,
        platform=platform,
        app_id=app_id,
        device_instance_id=device_instance_id,
        enable_logging=True
    )

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


def pytest_runtest_logreport(report):
    if report.when == "call":
        test_results.append({
            "nodeid": report.nodeid,
            "outcome": report.outcome,
            "longrepr": str(report.longrepr) if report.failed else "",
            "duration": report.duration
        })


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
            if entry['outcome'] == "failed":
                f.write(f"Error   :\n{entry['longrepr']}\n")
            f.write("-" * 40 + "\n")

        f.write("\n\n")

        try:
            utilsdemo.write_activity_report(f)
        except Exception as e:
            f.write("[WARN] write_activity_report failed: " + str(e) + "\n")

    print(f"[REPORT] Full report saved to: {report_path}")


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

        # This is the corrected line:
        metafunc.parametrize("user", users, ids=[u["username"] for u in users], scope="class")


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


@pytest.fixture
def lesson_numbers(request):
    lessons_arg = request.config.getoption("--lessons")
    if lessons_arg and lessons_arg.strip() != "0":
        try:
            return [int(x) for x in lessons_arg.split(",") if x.strip().isdigit()]
        except ValueError:
            return [0]

    single = request.config.getoption("--lesson")
    if single is not None:
        try:
            return [int(single)]
        except ValueError:
            return [0]

    return [0]