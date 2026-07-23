"""Pytest plugin that reports per-test results back to the HTML runner.

Loaded with ``-p runner.pytest_runner_plugin``. For each test it prints
``[START]/[PASS]/[FAIL]/[SKIPPED] <nodeid>`` (so the runner's live log shows progress
when pytest runs with ``-s``) and appends one JSON line per result to the file given by
``--rally-results``. The runner maps each nodeid back to its Rally test case.
"""

import os
import json

_CONFIG = None
_STARTED = set()
_EMITTED = set()


def pytest_addoption(parser):
    parser.addoption("--rally-results", action="store", default="",
                     help="JSONL file the runner tails for per-test results.")


def pytest_configure(config):
    global _CONFIG
    _CONFIG = config


def _write(rec):
    path = _CONFIG.getoption("--rally-results") if _CONFIG else ""
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def pytest_runtest_logreport(report):
    if report.when == "setup":
        if report.nodeid not in _STARTED:
            _STARTED.add(report.nodeid)
            print(f"[START] {report.nodeid}")
        if report.failed:                       # error during setup -> the test errored
            _emit(report, "failed")
        elif report.skipped:
            _emit(report, "skipped")
    elif report.when == "call":
        _emit(report, report.outcome)


def _emit(report, outcome):
    if report.nodeid in _EMITTED:
        return
    _EMITTED.add(report.nodeid)
    tag = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIPPED"}.get(outcome, outcome.upper())
    print(f"[{tag}] {report.nodeid}  ({getattr(report, 'duration', 0) or 0:.1f}s)")
    props = dict(getattr(report, "user_properties", []) or [])
    _write({
        "nodeid": report.nodeid, "outcome": outcome,
        "duration": round(getattr(report, "duration", 0) or 0, 2),
        "error": str(report.longrepr) if report.failed else "",
        "screenshot": props.get("screenshot", ""),
    })
