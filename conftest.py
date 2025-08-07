import pytest
import os
from Utilities import utilsdemo

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    os.makedirs(r"C:\\Users\\sanad\\Downloads\\reports", exist_ok=True)
    utilsdemo.write_activity_report(r"C:\\Users\\sanad\\Downloads\\reports\\final_activity_report.txt")
    print("[REPORT] Activity report saved after test session.")
