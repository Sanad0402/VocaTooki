import pytest
from alttester import AltDriver

def pytest_addoption(parser):
    parser.addoption("--platform", action="store", required=True)
    parser.addoption("--device_instance_id", action="store", default=None)
    parser.addoption("--app_id", action="store", default=None)

@pytest.fixture
def altdriver(request):
    platform = request.config.getoption("--platform")
    device_instance_id = request.config.getoption("--device_instance_id")
    app_id = request.config.getoption("--app_id")

    return AltDriver(
        host="127.0.0.1",
        port=13000,
        platform=platform,
        device_instance_id=device_instance_id,  # ✅ correct name
        app_id=app_id,
        enable_logging=True
    )
