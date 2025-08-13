# conftest.py
import os
import json
import logging
import pathlib
from datetime import datetime
import pytest

# --- AltTester imports (safe fallback if not installed) ---
try:
    from alttester import AltDriver  # AltTester® Python client
    try:
        from alttester import By  # optional
    except Exception:
        By = None
except Exception:  # pragma: no cover
    AltDriver = None
    By = None


# ----------------------------- CLI OPTIONS ------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    """CLI options for flexible runs & CI matrices."""
    parser.addoption("--platform", action="store", default="Unknown",
                     help="Platform name (Android/Editor/Windows/etc.)")
    parser.addoption("--app_id", action="store", default=None,
                     help="Application ID / package name / bundle id")
    parser.addoption("--device_instance_id", action="store", default=None,
                     help="Cloud/local device instance id or tag")
    parser.addoption("--app-host", action="store", default="127.0.0.1",
                     help="AltTester host")
    parser.addoption("--app-port", action="store", default="13000",
                     help="AltTester port")
    parser.addoption("--users-file", action="store", default=None,
                     help="Path to users JSON (array of user cases)")
    parser.addoption("--report-dir", action="store", default="Reports",
                     help="Base directory for run artifacts (logs, screenshots)")


# ------------------------- ARTIFACTS & LOGGING --------------------------
def _make_run_dir(config: pytest.Config) -> pathlib.Path:
    """Create an isolated artifacts directory per run/worker."""
    platform = config.getoption("--platform") if hasattr(config, "getoption") else "Unknown"
    worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")  # xdist-friendly
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = pathlib.Path(config.getoption("--report-dir") if hasattr(config, "getoption") else "Reports")
    run_dir = base / f"{platform}_{worker}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def pytest_configure(config: pytest.Config):
    """Set up per-run artifacts root and (optional) pytest-html metadata."""
    run_dir = _make_run_dir(config)
    config._artifact_root = run_dir  # used by hooks below

    # Configure root logging once per session (file + console)
    log_file = run_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.info("Artifacts directory: %s", run_dir)

    if config.pluginmanager.hasplugin("html"):
        # enrich pytest-html report metadata if plugin is installed
        meta = getattr(config, "_metadata", {})
        meta.update({
            "Platform": config.getoption("--platform"),
            "Worker": os.environ.get("PYTEST_XDIST_WORKER", "gw0"),
            "Run Started": datetime.now().isoformat(timespec="seconds"),
        })
        config._metadata = meta


@pytest.fixture(scope="session")
def artifact_root(request: pytest.FixtureRequest) -> pathlib.Path:
    """Expose the per-run artifacts directory as a fixture."""
    return getattr(request.config, "_artifact_root")


# ----------------------------- DATA FIXTURES ----------------------------
@pytest.fixture(scope="session")
def users(request: pytest.FixtureRequest):
    """
    Load users from JSON if provided via --users-file.
    Example entry:
      {"username":"vt000...", "password":"***", "class_id":1234, "lesson_nums":[0,1], "target_language":"EN"}
    """
    path = request.config.getoption("--users-file")
    if not path:
        return []
    p = pathlib.Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--users-file must contain a JSON array")
    return data


# ------------------------------ DRIVER FIXTURE --------------------------
@pytest.fixture
def altdriver(request: pytest.FixtureRequest, artifact_root: pathlib.Path):
    """
    Provides a connected AltDriver and guarantees clean teardown.
    Yields: (driver, platform_name)
    Matches tests that do: driver, platform_name = altdriver
    """
    if AltDriver is None:
        pytest.skip("AltTester AltDriver not available in this environment")

    platform = request.config.getoption("--platform")
    app_id = request.config.getoption("--app_id")
    device_instance_id = request.config.getoption("--device_instance_id")
    host = request.config.getoption("--app-host")
    port = int(request.config.getoption("--app-port"))

    logging.info("[SETUP] AltDriver connect host=%s port=%s platform=%s device=%s app_id=%s",
                 host, port, platform, device_instance_id or "-", app_id or "-")

    # Use your exact constructor/signature
    driver = AltDriver(
        host=host,
        port=port,
        platform=platform,
        device_instance_id=device_instance_id,  # as you had it ✅
        app_id=app_id,
        enable_logging=True,
    )

    try:
        yield driver, platform  # ✅ tuple so your tests can unpack
    finally:
        # Always attempt to stop/close to avoid dangling connections
        try:
            logging.info("[TEARDOWN] Stopping AltDriver")
            stop = getattr(driver, "stop", None) or getattr(driver, "close", None) or getattr(driver, "disconnect", None)
            if callable(stop):
                stop()
        except Exception as e:  # pragma: no cover
            logging.warning("Error stopping AltDriver: %s", e)


# ----------------------- FAILURE ARTIFACTS (BEST-EFFORT) ----------------
def _capture_artifacts_on_failure(item: pytest.Item, report: pytest.TestReport, driver, artifact_dir: pathlib.Path):
    """Try to capture a screenshot from the app when a test fails."""
    if not (report.failed and driver):
        return
    try:
        for attr in ("getPNGScreenshot", "get_screenshot", "screenshot"):
            if hasattr(driver, attr):
                png = getattr(driver, attr)()
                out = artifact_dir / f"{item.name}.png"
                if isinstance(png, (bytes, bytearray)):
                    out.write_bytes(png)
                    logging.info("Saved screenshot: %s", out)
                break
    except Exception as e:
        logging.warning("Failed to capture screenshot: %s", e)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """
    After each test phase, we can act on the result.
    On test failure (call phase), save a screenshot into a per-test folder.
    """
    outcome = yield
    rep = outcome.get_result()

    # retrieve driver if this test used the 'altdriver' fixture
    driver = None
    try:
        if "altdriver" in item.fixturenames:
            driver, _ = item.funcargs.get("altdriver", (None, None))
    except Exception:
        pass

    # make a per-test artifacts folder
    session_root = getattr(item.config, "_artifact_root", pathlib.Path("Reports") / "default")
    test_dir = session_root / item.name
    test_dir.mkdir(parents=True, exist_ok=True)

    if rep.when == "call":
        _capture_artifacts_on_failure(item, rep, driver, test_dir)


# ------------------------- OPTIONAL FINAL SUMMARY -----------------------
def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    """
    If you have a function like Utilities.utilsdemo.write_activity_report(artifact_root),
    call it here once at the end. Safe no-op if not present.
    """
    try:
        from Utilities.utilsdemo import write_activity_report  # adjust if your path/name differs
    except Exception:
        return  # nothing to do

    artifacts = getattr(session.config, "_artifact_root", pathlib.Path("Reports") / "default")
    try:
        write_activity_report(str(artifacts))  # pass path or whatever your function expects
        logging.info("Final activity report written to: %s", artifacts)
    except Exception as e:
        logging.warning("write_activity_report failed: %s", e)
