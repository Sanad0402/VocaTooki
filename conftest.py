# conftest.py
import os
import logging
import shutil
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
        # MUST stay False: True makes AltDriver re-enable the loguru
        # "alttester.*" namespaces disabled above, and every websocket command
        # is then logged as a multi-KB DEBUG line. A solver run emits hundreds
        # of thousands of them - enough to freeze the panel's live log page.
        # Our own print()/logging output is unaffected by this flag.
        enable_logging=False,
    )

    # ✅ only include if provided
    if app_id:
        driver_kwargs["app_id"] = app_id
    if device_instance_id:
        driver_kwargs["device_instance_id"] = device_instance_id

    driver = AltDriver(**driver_kwargs)

    setattr(utilsdemo, "RUN_PLATFORM", platform)

    yield driver, platform

    # Graceful shutdown — always sever the AltTester connection when the test
    # session ends. NOTE: this driver version has no close(); stop() is the
    # real API (the old close()-first code only ever worked via its fallback).
    try:
        driver.stop()
        logging.info("[AltDriver] connection closed after the test run.")
        print("[INFO] AltDriver connection closed.")
    except Exception as e:
        logging.warning(f"[AltDriver] failed to close connection: {e}")


# -----------------------------
# Screenshot on failure
# -----------------------------
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    if call.when == "call" and call.excinfo is not None:
        driver = None
        try:
            # Try to get altdriver from fixtures
            if hasattr(item, "funcargs") and "altdriver" in item.funcargs:
                altdriver = item.funcargs["altdriver"]
                driver, platform = altdriver

                # Get or create screenshots directory
                reports_dir = item.config.getoption("--reports_dir")
                screenshots_dir = os.path.join(reports_dir, "screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)

                # Generate screenshot filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                test_name = item.name.replace("::", "_")
                screenshot_path = os.path.join(
                    screenshots_dir, f"{test_name}_{timestamp}.png"
                )

                # Capture the screen AS FAILED — tests deliberately stay on the
                # failing screen so this shows where they got stuck.
                # NOTE: the python driver's API is get_png_screenshot(path) —
                # there is no get_screenshot(), which is why failure screenshots
                # silently never appeared before.
                #
                # Shoot it into the run folder first (mandatory: a spent budget
                # must never suppress the frame that shows the failure), then
                # COPY it to the flat path the report/Rally pipeline expects.
                # One capture, both homes. If the case is excluded from run
                # screenshots the shooter returns None and we capture directly —
                # the failure frame is never optional.
                run_shot = _shoot_milestone(item, "failure", mandatory=True, driver=driver)
                if run_shot is not None:
                    shutil.copyfile(str(run_shot), screenshot_path)
                else:
                    driver.get_png_screenshot(screenshot_path)
                logging.info(f"Screenshot saved: {screenshot_path}")
                # This hook runs before the default makereport (tryfirst), so
                # entries added here are copied onto the TestReport and reach
                # the runner plugin, which attaches them to the panel/report.
                item.user_properties.append(("screenshot", screenshot_path))
        except Exception as e:
            logging.warning(f"Failed to capture screenshot on failure: {e}")
        # Recovery: the failed test intentionally left the app on the broken
        # screen. Walk back to the START SCREEN so the NEXT chained test starts
        # clean (a stuck TC otherwise cascades).
        #
        # The start screen, not the map: it is the hub every flow begins from --
        # open_feature, the tasks walk, the events walk and Treasure Island all
        # return there first -- and a test that needs the map opens it from
        # there anyway. Walking to the map instead cost a pointless GO-Map /
        # BackButton dance at the end of every failed run, which on a Tasks
        # failure looped eight steps and then gave up.
        if driver is not None:
            try:
                from Utilities import utilsdemo
                utilsdemo.return_to_start(driver)
            except Exception as e:
                logging.warning(f"Post-failure recovery to the start screen failed: {e}")


# -----------------------------
# Run screenshots (capped)
# -----------------------------
# Up to 3 frames per test case, captured at milestones without any test having to
# ask: one once the app is up (setup) and one at the end of the test body. The
# FAILURE frame is taken by the hook above and is deliberately not counted
# against this budget — a spent allowance must never suppress the one screenshot
# that shows why a test failed.
#
# Each frame is attached to item.user_properties("screenshot"), the same channel
# the failure screenshot already uses, so the panel and the report pick them up
# with no extra plumbing.

_SHOOTERS = {}


def _tc_id_of(item):
    return getattr(getattr(item, "module", None), "TC_ID", None) or item.name


def _shooter_for(item):
    """The Shooter for this test, or None when the panel excluded the case."""
    from runner import screenshots

    key = item.nodeid
    if key not in _SHOOTERS:
        tc = _tc_id_of(item)
        _SHOOTERS[key] = screenshots.Shooter.for_test(tc) if screenshots.wants(tc) else None
    return _SHOOTERS[key]


def _driver_of(item):
    altdriver = (getattr(item, "funcargs", None) or {}).get("altdriver")
    if not altdriver:
        return None
    return altdriver[0] if isinstance(altdriver, (tuple, list)) else altdriver


def _shoot_milestone(item, label, mandatory=False, driver=None):
    """Capture one budgeted frame for ``item``. Returns the Path or None.

    Milestone frames are deliberately NOT put on item.user_properties: that
    channel carries the single failure screenshot the report and the Rally
    upload use, it is read as a dict (last value wins) and everything
    downstream expects a bare filename in reports/screenshots/. Run frames live
    in their own per-run folder and the panel lists them from there.
    """
    try:
        shooter = _shooter_for(item)
        if shooter is None:
            return None
        return shooter.shoot(driver or _driver_of(item), label, mandatory=mandatory)
    except Exception as e:  # noqa: BLE001 - a screenshot must never fail a run
        logging.debug(f"[shots] milestone '{label}' skipped: {e}")
        return None


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_call(item):
    """One frame as soon as the app is up (fixtures done), then run the test."""
    _shoot_milestone(item, "start")
    yield


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    """Last frame of the test body, before the fixtures tear the app down.

    tryfirst is REQUIRED: pytest's own teardown hook runs the fixture
    finalizers, and on the last test of a session that closes the AltDriver —
    a trylast hook here would find a dead driver and silently lose the frame.
    """
    _shoot_milestone(item, "end")
    _SHOOTERS.pop(item.nodeid, None)


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

        if not TEST_USERS:
            # No users configured (credentials now come from Rally). Parametrize
            # with an empty set so these legacy user-driven tests are cleanly
            # skipped instead of crashing collection with an IndexError.
            users = []
        elif mode == "single":
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
