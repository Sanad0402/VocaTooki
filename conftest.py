import pytest
import os
from alttester import AltDriver
from Utilities.utilsdemo import write_activity_report  # ✅ Add this

def pytest_addoption(parser):
    parser.addoption("--platform", action="store", required=True)
    parser.addoption("--app_id", action="store", required=True)
    parser.addoption("--device_instance_id", action="store", required=False)

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

    yield driver
    driver.stop()

# ✅ Auto-generate report after test session
def pytest_sessionfinish(session, exitstatus):
    os.makedirs("reports", exist_ok=True)
    write_activity_report("reports/final_activity_report.txt")
