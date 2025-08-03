import pytest
from alttester import AltDriver
from Utilities import utilsdemo
import os

# Global platform configurations
PLATFORMS = [
    {
        "name": "WindowsEditor",
        "platform": "WindowsEditor",
        "app_id": "13C50000",
        "device_id": "73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48"
    },
    {
        "name": "Android",
        "platform": "Android",
        "app_id": "com.vocatooki.app",
        "device_id": "YOUR_ANDROID_DEVICE_ID"
    },
    {
        "name": "WebGL",
        "platform": "WebGL",
        "app_id": "WebGLAppId",
        "device_id": "YOUR_WEBGL_DEVICE_ID"
    },
    {
        "name": "WindowsBuild",
        "platform": "WindowsBuild",
        "app_id": "com.vocatooki.build",
        "device_id": "YOUR_WINDOWS_BUILD_DEVICE_ID"
    }
]

# Global user credentials
utilsdemo.USERNAME = "vt01274560008"
utilsdemo.PASSWORD = "3453"

@pytest.fixture(params=PLATFORMS)
def altdriver(request):
    config = request.param
    print(f"\n[FIXTURE] Connecting to platform: {config['name']}")
    driver = AltDriver(
        host="127.0.0.1",
        port=13000,
        platform=config["platform"],
        app_id=config["app_id"],
        device_instance_id=config["device_id"],
        enable_logging=True
    )
    yield driver, config['name']
    print(f"[FIXTURE] Closing connection for platform: {config['name']}")
    driver.stop()  # <-- This happens after test completes
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    os.makedirs(r"C:\\Users\\sanad\\Downloads\\reports", exist_ok=True)
    utilsdemo.write_activity_report(r"C:\\Users\\sanad\\Downloads\\reports\\final_activity_report.txt")
    print("[REPORT] Activity report saved after test session.")
