import pytest
import os
from datetime import datetime
from Utilities import utilsdemo
from alttester import AltDriver

test_results = []  # Store test status info

def pytest_addoption(parser):
    parser.addoption("--platform", action="store", help="Platform name")
    parser.addoption("--app_id", action="store", help="App ID")
    parser.addoption("--device_instance_id", action="store", help="Device ID")


@pytest.fixture
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
    yield driver, platform
    driver.stop()


# Hook: Collect each test result
def pytest_runtest_logreport(report):
    if report.when == "call":
        test_results.append({
            "nodeid": report.nodeid,
            "outcome": report.outcome,
            "longrepr": str(report.longrepr) if report.failed else "",
            "duration": report.duration
        })


# Hook: Generate report after session ends
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"activity_report_{timestamp}.txt"
    reports_dir = r"C:\Users\sanad\Downloads\reports"
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, filename)

    with open(report_path, "w", encoding="utf-8") as f:
        # 1. Write test case results
        f.write("🧪 TEST CASE EXECUTION REPORT\n")
        f.write("=" * 40 + "\n\n")
        for entry in test_results:
            f.write(f"Test    : {entry['nodeid']}\n")
            f.write(f"Outcome : {entry['outcome'].upper()}\n")
            f.write(f"Duration: {entry['duration']:.2f}s\n")
            if entry['outcome'] == "failed":
                f.write(f"Error   :\n{entry['longrepr']}\n")
            f.write("-" * 40 + "\n")

        f.write("\n\n")  # Separator between sections

        # 2. Write activity gameplay results
        utilsdemo.write_activity_report(f)

    print(f"[REPORT] Full report saved to: {report_path}")
