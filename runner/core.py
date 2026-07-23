"""RunManager: orchestrates automation runs for the HTML runner.

Single active run at a time. Reuses the existing solver functions, Page objects,
and report writer. Captures `print()` + `logging` output so the browser can show a
live log, tracks progress, and builds a text + HTML report at the end.
"""

import os
import io
import sys
import html
import json
import time
import logging
import tempfile
import threading
import subprocess

from data.test_users import TEST_USERS, DEFAULT_CLASS_ID

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from Utilities import utilsdemo
from Pages.StartScreen import StartScreen
from Pages.map_page import MapPage
from .modes import MODES, DEFAULT_MODE
from . import suite
from . import emailer


REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.expanduser("~/Downloads/reports"))

# ---- run history (the panel's "Last runs" tab) ----------------------------
HISTORY_PATH = os.path.join(_ROOT, "data", "run_history.json")
MAX_HISTORY = 30


def load_run_history():
    """Newest-first list of recorded runs (empty when none/corrupt)."""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def clear_run_history():
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    except OSError:
        pass

_USERS_BY_NAME = {u["username"]: u for u in TEST_USERS}


def _fmt_dur(seconds):
    seconds = int(round(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _import_ref(ref):
    """Resolve a 'package.module:function' reference to the callable test-case function."""
    import importlib
    if not ref or ":" not in ref:
        raise RuntimeError(f"'code' test case needs a ref like 'module:function', got: {ref!r}")
    mod_name, fn_name = ref.split(":", 1)
    fn = getattr(importlib.import_module(mod_name), fn_name, None)
    if not callable(fn):
        raise RuntimeError(f"{ref} is not a callable function.")
    return fn


class _StopRun(Exception):
    """Raised internally to unwind the run loop when the user clicks Stop."""


def _silence_alttester_logging():
    """Mirror conftest.py: keep AltTester/websocket noise out of the live log."""
    for name in ("alttester", "alttester.altdriver", "alttester._websocket",
                 "alttester._command", "alttester._base_alt_object", "websocket", "urllib3"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False
    try:
        from loguru import logger as loguru_logger
        for name in ("alttester", "alttester.altdriver", "alttester._websocket",
                     "alttester._command", "alttester._base_alt_object"):
            loguru_logger.disable(name)
    except Exception:
        pass


class _StreamTee:
    """File-like object that mirrors writes to the original stream and to a sink.

    Buffers partial output and emits one log line per newline.
    """

    def __init__(self, original, sink):
        self._original = original
        self._sink = sink
        self._buf = ""

    def write(self, text):
        try:
            self._original.write(text)
        except Exception:
            pass
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._sink(line)
        return len(text)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self):
        return False


class _QueueLogHandler(logging.Handler):
    def __init__(self, sink):
        super().__init__()
        self._sink = sink

    def emit(self, record):
        try:
            self._sink(self.format(record))
        except Exception:
            pass


class RunManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    # ---- lifecycle -------------------------------------------------------
    # Cap on retained events. A run that logs more than this only loses the
    # OLDEST live-log lines from the browser view (the full log still goes to
    # the report); without a cap a chatty run grows this list unbounded and
    # every SSE poll copies it, which is what froze the panel page.
    MAX_EVENTS = 4000

    def reset(self):
        with self._lock:
            self.state = "idle"          # idle | running | done | error | stopped
            self.events = []             # bounded list of {seq, type, ...}
            self._next_seq = 0           # seq keeps growing even after trimming
            self.error = None
            self.progress = {}
            self.groups = []             # [{username, class_id, lesson_from, lesson_to, start}]
            self.cases = []              # per-test-case result rows (test_folder/test_case runs)
            self.report_txt = None
            self.report_html_path = None
            self.report_html = None
            self._stop_event = threading.Event()
            self._thread = None
            self._started_at = None
            self._driver = None
            self._driver_closed = False
            self._proc = None            # pytest subprocess (suite runs)
            self._email_after = False    # email the report when the run finishes?

    def is_running(self):
        return self.state == "running"

    # ---- event plumbing --------------------------------------------------
    def _emit(self, etype, **data):
        with self._lock:
            evt = {"seq": self._next_seq, "type": etype, "t": time.strftime("%H:%M:%S"), **data}
            self._next_seq += 1
            self.events.append(evt)
            if len(self.events) > self.MAX_EVENTS:
                # Trim oldest; only "log" lines are ever numerous enough to be
                # trimmed, and state/progress events are re-sent by polling.
                del self.events[: len(self.events) - self.MAX_EVENTS]

    def _log(self, line):
        self._emit("log", line=line)

    def events_since(self, cursor):
        with self._lock:
            if not self.events:
                return []
            base = self.events[0]["seq"]
            idx = max(0, cursor - base)
            return self.events[idx:]

    def snapshot(self):
        with self._lock:
            results = []
            report = utilsdemo.activity_report
            for i, g in enumerate(self.groups):
                end = self.groups[i + 1]["start"] if i + 1 < len(self.groups) else len(report)
                results.append({
                    "username": g["username"],
                    "class_id": g["class_id"],
                    "lesson_from": g["lesson_from"],
                    "lesson_to": g["lesson_to"],
                    "entries": [dict(e) for e in report[g["start"]:end]],
                })
            return {
                "state": self.state,
                "error": self.error,
                "progress": dict(self.progress),
                "results": results,
                "cases": [dict(c) for c in self.cases],
                "report_txt": bool(self.report_txt),
                "report_html": bool(self.report_html),
                "event_count": len(self.events),
            }

    # ---- planning --------------------------------------------------------
    @staticmethod
    def resolve_users(cfg):
        """Normalize the `users` list into [{username, password, class_id}], + errors.

        Each item may be a predefined username (string, resolved from TEST_USERS)
        or a typed user object {username, password, class_id?}.
        """
        out, errors = [], []
        for item in (cfg.get("users") or []):
            if isinstance(item, str):
                u = _USERS_BY_NAME.get(item)
                if not u:
                    errors.append(f"Unknown user '{item}'.")
                    continue
                out.append({
                    "username": u["username"],
                    "password": u.get("password", ""),
                    "class_id": u.get("class_id", DEFAULT_CLASS_ID),
                })
            elif isinstance(item, dict):
                un = (item.get("username") or "").strip()
                pw = item.get("password")
                if not un:
                    errors.append("A custom user is missing a username.")
                    continue
                if not pw:
                    errors.append(f"User '{un}' is missing a password.")
                    continue
                out.append({
                    "username": un,
                    "password": pw,
                    "class_id": (item.get("class_id") or "").strip() or DEFAULT_CLASS_ID,
                })
            else:
                errors.append("Invalid user entry.")
        if not out and not errors:
            errors.append("Select or add at least one user.")
        return out, errors

    def build_plan(self, cfg):
        users, _ = self.resolve_users(cfg)
        lf, lt = int(cfg["lesson_from"]), int(cfg["lesson_to"])
        mode = cfg.get("mode", DEFAULT_MODE)
        override = cfg.get("class_id_override")
        steps = []
        for u in users:
            cid = override or u["class_id"]
            for lesson in range(lf, lt + 1):
                steps.append(f"[{u['username']}] class {cid} - lesson {lesson} ({mode})")
        return steps

    @classmethod
    def validate(cls, cfg):
        errors = []
        _, user_errors = cls.resolve_users(cfg)
        errors.extend(user_errors)
        try:
            lf, lt = int(cfg["lesson_from"]), int(cfg["lesson_to"])
            if lf < 0 or lt < 0:
                errors.append("Lesson numbers must be >= 0.")
            if lf > lt:
                errors.append("'From' lesson must be <= 'To' lesson.")
        except (KeyError, TypeError, ValueError):
            errors.append("Lesson From/To must be integers.")
        if cfg.get("mode", DEFAULT_MODE) not in MODES:
            errors.append(f"Unknown mode '{cfg.get('mode')}'.")
        return errors

    # ---- run -------------------------------------------------------------
    def start(self, cfg):
        """Validate + start. Returns (ok, payload)."""
        if self.is_running():
            return False, {"error": "A run is already in progress."}

        if cfg.get("run_type") in ("test_folder", "test_case"):
            return self._start_suite(cfg)

        errors = self.validate(cfg)
        if errors:
            return False, {"error": " ".join(errors)}

        self.reset()
        self._email_after = bool(cfg.get("email_report"))
        plan = self.build_plan(cfg)

        if cfg.get("dry_run"):
            with self._lock:
                self.state = "done"
            self._emit("plan", steps=plan, dry_run=True)
            for s in plan:
                self._log("DRY-RUN " + s)
            self._log(f"DRY-RUN complete: {len(plan)} step(s) would execute.")
            self._emit("state", state="done")
            return True, {"steps": plan, "dry_run": True}

        with self._lock:
            self.state = "running"
            self._started_at = time.time()
        self._emit("state", state="running")
        self._emit("plan", steps=plan, dry_run=False)

        self._thread = threading.Thread(target=self._run, args=(cfg,), daemon=True)
        self._thread.start()
        return True, {"steps": plan, "dry_run": False}

    # ---- suite (Test Folder / Test Case) runs ---------------------------
    def _start_suite(self, cfg):
        rt = cfg.get("run_type")
        selection = cfg.get("test_folders") if rt == "test_folder" else cfg.get("test_cases")
        if not (selection or []):
            what = "test folder" if rt == "test_folder" else "test case"
            return False, {"error": f"Select at least one {what}."}
        cases, warnings = suite.resolve(rt, selection)
        if not cases:
            msg = warnings[0] if warnings else "Nothing to run for the current selection."
            return False, {"error": msg}

        self.reset()
        self._email_after = bool(cfg.get("email_report"))
        with self._lock:
            self.cases = [self._case_row(i, c) for i, c in enumerate(cases)]
        plan_text = self._suite_plan_text(cfg, cases, warnings)

        if cfg.get("dry_run"):
            with self._lock:
                self.state = "done"
            self._emit("plan", text=plan_text, warnings=warnings, dry_run=True)
            self._emit("cases", cases=[dict(c) for c in self.cases])
            for line in plan_text.splitlines():
                self._log("DRY-RUN " + line if line.strip() else line)
            self._emit("state", state="done")
            return True, {"dry_run": True, "cases": len(cases), "plan": plan_text}

        with self._lock:
            self.state = "running"
            self._started_at = time.time()
        self._emit("state", state="running")
        self._emit("plan", text=plan_text, warnings=warnings, dry_run=False)
        self._emit("cases", cases=[dict(c) for c in self.cases])
        for w in warnings:
            self._log(f"[WARN] {w}")

        self._thread = threading.Thread(target=self._run_suite, args=(cfg, cases), daemon=True)
        self._thread.start()
        return True, {"dry_run": False, "cases": len(cases)}

    def _case_row(self, idx, c):
        action = c.get("action") or {}
        return {
            "index": idx, "tc_id": c["id"], "tc_name": c.get("name", c["id"]),
            "folder": c.get("folder", ""), "username": (c.get("user") or {}).get("username", ""),
            "action": action.get("kind", "pytest"), "nodeid": action.get("nodeid", ""),
            "status": "PENDING", "duration": "", "error": "",
        }

    def _suite_plan_text(self, cfg, cases, warnings):
        rt = cfg.get("run_type")
        sel = ", ".join(cfg.get("test_folders") if rt == "test_folder" else cfg.get("test_cases") or [])
        lines = ["Execution plan:", "",
                 "Run Type:", "Test Folder" if rt == "test_folder" else "Test Case(s)", "",
                 f"Selected: {sel or '—'}", "", f"Test cases ({len(cases)}):"]
        for i, c in enumerate(cases, 1):
            u = c.get("user") or {}
            lines.append(f"  {i}. {c['id']} - {c.get('name', '')}  [user: {u.get('username', '-')}]")
        if warnings:
            lines += ["", "Warnings:"] + [f"  ! {w}" for w in warnings]
        return "\n".join(lines)

    def _update_case(self, idx, **changes):
        with self._lock:
            if 0 <= idx < len(self.cases):
                self.cases[idx].update(changes)
                row = dict(self.cases[idx])
            else:
                return
        self._emit("case", index=idx, case=row)

    def _set_case_progress(self, done, total, label, username=""):
        prog = {"done": done, "total": total, "label": label, "username": username,
                "fraction": round(done / total, 3) if total else 0}
        with self._lock:
            self.progress = prog
        self._emit("progress", **prog)

    def _run_suite(self, cfg, cases):
        """Run the selected test cases via a pytest subprocess (creds live in each test)."""
        total = len(cases)
        platform = cfg.get("platform") or "WindowsEditor"
        host = cfg.get("host") or "127.0.0.1"
        port = int(cfg.get("port") or 13000)

        # Map nodeid -> case row index; cases without a linked test are skipped up front.
        nodeid_index, nodeids = {}, []
        for idx, c in enumerate(cases):
            nodeid = (c.get("action") or {}).get("nodeid")
            if nodeid:
                nodeid_index[nodeid] = idx
                nodeids.append(nodeid)
            else:
                self._update_case(idx, status="SKIPPED", error="No pytest test linked (set a nodeid).")
        results = os.path.join(REPORTS_DIR, f"_suite_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")

        try:
            os.makedirs(REPORTS_DIR, exist_ok=True)
            self._log(f"[INFO] Checking AltTester at {host}:{port} (platform={platform})...")
            if not self._preflight(host, port):
                raise RuntimeError(
                    f"Could not connect to AltTester server at {host}:{port}. "
                    f"Is the app running and instrumented?")
            if not nodeids:
                self._log("[INFO] No linked test cases to run.")
                self._set_case_progress(total, total, "Finished")
                self._build_suite_reports(platform)
                with self._lock:
                    self.state = "done"
                self._emit("state", state="done")
                return

            cmd = [sys.executable, "-u", "-m", "pytest", "-v", *nodeids, "-s",
                   "-p", "runner.pytest_runner_plugin", "--rally-results", results,
                   "--host", host, "--port", str(port), "--platform", platform,
                   "--maxfail=0", "-p", "no:cacheprovider", "-o", "addopts="]
            app_id = (cfg.get("app_id") or "").strip()
            device = (cfg.get("device_instance_id") or "").strip()
            if app_id:
                cmd += ["--app_id", app_id]
            if device:
                cmd += ["--device_instance_id", device]

            env = dict(os.environ, REPORTS_DIR=REPORTS_DIR, PYTHONIOENCODING="utf-8")
            self._log(f"[INFO] Running {len(nodeids)} test case(s) via pytest...")
            proc = subprocess.Popen(cmd, cwd=_ROOT, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            with self._lock:
                self._proc = proc
            offset = 0
            for line in proc.stdout:
                if line.strip():
                    self._log(line.rstrip())
                offset = self._drain_case_results(results, offset, nodeid_index)
                if self._stopped():
                    self._terminate_proc()
                    break
            proc.wait()
            self._drain_case_results(results, offset, nodeid_index)

            if self._stopped():
                self._cancel_remaining_cases()
                final = "stopped"
            else:
                final = "done"
            self._set_case_progress(total, total, "Finished")
            self._build_suite_reports(platform)
            with self._lock:
                self.state = final
            self._log("[STOPPED] Execution stopped by user" if final == "stopped" else "[INFO] Run done.")
            self._emit("state", state=final)
        except Exception as e:
            if self._stopped():
                self._cancel_remaining_cases()
                self._build_suite_reports(platform)
                with self._lock:
                    self.state = "stopped"
                self._log("[STOPPED] Execution stopped by user")
                self._emit("state", state="stopped")
            else:
                self._fail_remaining_cases(f"Automation failed: {e}")
                with self._lock:
                    self.state = "error"
                    self.error = str(e)
                self._log(f"[FATAL] Automation failed: {e}")
                self._build_suite_reports(platform)
                self._emit("state", state="error", error=str(e))
        finally:
            with self._lock:
                self._proc = None
            try:
                os.remove(results)
            except OSError:
                pass
            self._record_run_history("suite")

    def _drain_case_results(self, path, offset, nodeid_index):
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    idx = nodeid_index.get(rec.get("nodeid"))
                    if idx is None:
                        continue
                    status = {"passed": "PASSED", "failed": "FAILED", "skipped": "SKIPPED"}.get(
                        rec.get("outcome"), str(rec.get("outcome", "")).upper())
                    done = sum(1 for c in self.cases if c["status"] not in ("PENDING", "RUNNING"))
                    self._update_case(idx, status=status, duration=_fmt_dur(rec.get("duration", 0)),
                                      error=rec.get("error", ""))
                    self._set_case_progress(done + 1, len(self.cases), self.cases[idx]["tc_name"])
                offset = f.tell()
        except FileNotFoundError:
            pass
        return offset

    def _cancel_remaining_cases(self):
        for idx in range(len(self.cases)):
            if self.cases[idx]["status"] in ("PENDING", "RUNNING"):
                self._update_case(idx, status="CANCELLED", error="Cancelled — run stopped by user.")

    def _fail_remaining_cases(self, error):
        for idx in range(len(self.cases)):
            if self.cases[idx]["status"] in ("PENDING", "RUNNING"):
                self._update_case(idx, status="FAILED", error=error)

    def _build_suite_reports(self, platform):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(REPORTS_DIR, f"suite_report_{platform}_{ts}")
        totals = {"PASSED": 0, "FAILED": 0, "SKIPPED": 0, "CANCELLED": 0}
        for c in self.cases:
            totals[c["status"]] = totals.get(c["status"], 0) + 1
        try:
            with open(base + ".txt", "w", encoding="utf-8") as f:
                f.write("TEST CASE EXECUTION REPORT\n" + "=" * 40 + "\n\n")
                f.write(f"Platform: {platform}   {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Passed {totals['PASSED']}  Failed {totals['FAILED']}  "
                        f"Cancelled {totals['CANCELLED']}\n" + "-" * 40 + "\n")
                for c in self.cases:
                    f.write(f"{c['tc_id']} - {c['tc_name']}\n")
                    f.write(f"  User    : {c['username']}\n")
                    f.write(f"  Status  : {c['status']}   Duration: {c['duration']}\n")
                    if c["error"]:
                        f.write(f"  Error   : {c['error']}\n")
                    f.write("-" * 40 + "\n")
            self.report_txt = base + ".txt"
            self._log(f"[REPORT] Text report: {self.report_txt}")
        except Exception as e:
            self._log(f"[WARN] Failed to write text report: {e}")
        try:
            self.report_html = self._render_suite_html(platform, totals)
            with open(base + ".html", "w", encoding="utf-8") as f:
                f.write(self.report_html)
            self.report_html_path = base + ".html"
            self._log(f"[REPORT] HTML report: {self.report_html_path}")
        except Exception as e:
            self._log(f"[WARN] Failed to build HTML report: {e}")
        self._email_report(platform, ts)

    def _render_suite_html(self, platform, totals):
        rows = []
        for c in self.cases:
            st = c["status"]
            err = html.escape(c.get("error", "") or "")
            err_html = f'<details><summary>error</summary><pre>{err}</pre></details>' if err else ""
            rows.append(
                f'<tr class="s-{html.escape(st.lower())}">'
                f'<td>{html.escape(c["tc_id"])}</td><td>{html.escape(c["tc_name"])}</td>'
                f'<td>{html.escape(c["username"])}</td><td>{html.escape(st)}</td>'
                f'<td>{html.escape(c["duration"])}</td><td>{err_html}</td></tr>')
        summary = (f'Passed: {totals["PASSED"]} &nbsp; Failed: {totals["FAILED"]} &nbsp; '
                   f'Cancelled: {totals["CANCELLED"]}')
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Test Case Report</title>
<style>
  body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2933; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #d2d6dc; padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f5f7fa; }}
  .summary {{ margin: 8px 0 16px; font-weight: 600; }}
  tr.s-passed td:nth-child(4) {{ color: #057a55; font-weight: 600; }}
  tr.s-failed td:nth-child(4) {{ color: #c81e1e; font-weight: 600; }}
  tr.s-cancelled td:nth-child(4) {{ color: #6b7280; font-weight: 600; }}
  pre {{ white-space: pre-wrap; margin: 4px 0; font-size: 12px; }}
</style></head><body>
  <h1>Test Case Execution Report</h1>
  <div>Platform: {html.escape(platform)} &nbsp;|&nbsp; {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
  <div class="summary">{summary}</div>
  <table><thead><tr><th>TC ID</th><th>Test Case Name</th><th>User</th>
  <th>Status</th><th>Duration</th><th>Error</th></tr></thead>
  <tbody>{''.join(rows) or '<tr><td colspan=6>No test cases.</td></tr>'}</tbody></table>
</body></html>"""

    def stop(self):
        if not self.is_running():
            return False
        self._stop_event.set()
        self._log("[STOP] Stopping now — ending the current run...")
        # Sever the lesson-range driver and/or kill the pytest subprocess so the
        # run unwinds immediately instead of finishing the current item.
        self._close_driver()
        self._terminate_proc()
        return True

    def _terminate_proc(self):
        proc = self._proc
        if proc is None:
            return
        try:
            proc.terminate()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _close_driver(self):
        """Close the active AltDriver once (safe to call from any thread / twice)."""
        with self._lock:
            drv = self._driver
            if drv is None or self._driver_closed:
                return
            self._driver_closed = True
        try:
            drv.stop()
        except Exception:
            try:
                drv.close()
            except Exception:
                pass

    def _stopped(self):
        return self._stop_event.is_set()

    def _run(self, cfg):
        _silence_alttester_logging()

        # Wire up log capture (process-global; safe because only one run at a time).
        handler = _QueueLogHandler(self._log)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        prev_level = root.level
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = _StreamTee(old_stdout, self._log)
        sys.stderr = _StreamTee(old_stderr, self._log)

        # Make the solvers' own time.sleep(...) calls interruptible: when Stop is
        # pressed they return early instead of waiting out long delays. Scoped to
        # the run and restored in finally. (Returns early, never raises.)
        import time as _timemod
        _orig_sleep = _timemod.sleep

        def _interruptible_sleep(secs):
            rem = float(secs)
            while rem > 0 and not self._stopped():
                _orig_sleep(0.2 if rem > 0.2 else rem)
                rem -= 0.2
        _timemod.sleep = _interruptible_sleep

        driver = None
        try:
            host = cfg.get("host") or "127.0.0.1"
            port = int(cfg.get("port") or 13000)
            platform = cfg.get("platform") or "WindowsEditor"
            users, _ = self.resolve_users(cfg)
            override = cfg.get("class_id_override")
            lf, lt = int(cfg["lesson_from"]), int(cfg["lesson_to"])
            mode = cfg.get("mode", DEFAULT_MODE)
            mode_run = MODES[mode]["run"]
            lessons = list(range(lf, lt + 1))

            self._log(f"[INFO] Connecting to AltTester at {host}:{port} (platform={platform})...")
            if not self._preflight(host, port):
                raise RuntimeError(
                    f"Could not reach AltTester at {host}:{port}. "
                    f"Is the app running and instrumented (AltTester listening on that port)?"
                )
            driver = self._connect(host, port, platform, cfg)
            with self._lock:
                self._driver = driver       # so stop() can sever the connection
            if self._stopped():
                raise _StopRun()
            setattr(utilsdemo, "RUN_PLATFORM", platform)
            try:
                setattr(driver, "platform", platform)  # so reports show the platform
            except Exception:
                pass
            self._log("[INFO] Connected.")

            utilsdemo.activity_report.clear()

            for ui, user in enumerate(users):
                if self._stopped():
                    break
                username = user["username"]
                cid = override or user["class_id"]

                with self._lock:
                    self.groups.append({
                        "username": username, "class_id": cid,
                        "lesson_from": lf, "lesson_to": lt,
                        "start": len(utilsdemo.activity_report),
                    })

                self._set_progress(ui, len(users), username, None, lessons)
                self._log(f"=== User {ui + 1}/{len(users)}: {username} (class {cid}) ===")

                try:
                    start_screen = StartScreen(driver, utilsdemo=utilsdemo)
                    map_page = MapPage(driver)
                    start_screen.login(username, user["password"])
                    start_screen.go_to_map()
                    self._sleep(6)
                except Exception as e:
                    if self._stopped():
                        break
                    self._log(f"[ERROR] Login/navigation failed for {username}: {e}")
                    continue

                for li, lesson in enumerate(lessons):
                    if self._stopped():
                        break
                    self._set_progress(ui, len(users), username, lesson, lessons, li)
                    self._log(f"--- {username}: lesson {lesson} ({mode}) ---")
                    try:
                        mode_run(map_page, driver, cid, lesson)
                    except Exception as e:
                        if self._stopped():
                            break
                        self._log(f"[ERROR] Lesson {lesson} for {username} failed: {e}")
                    self._sleep(1)
                if self._stopped():
                    break

            final = "stopped" if self._stopped() else "done"
            self._build_reports(platform)
            with self._lock:
                self.state = final
            self._log(f"[INFO] Run {final}.")
            self._emit("state", state=final)

        except _StopRun:
            self._build_reports(cfg.get("platform") or "WindowsEditor")
            with self._lock:
                self.state = "stopped"
            self._log("[INFO] Run stopped.")
            self._emit("state", state="stopped")
        except Exception as e:
            if self._stopped():
                self._build_reports(cfg.get("platform") or "WindowsEditor")
                with self._lock:
                    self.state = "stopped"
                self._log("[INFO] Run stopped.")
                self._emit("state", state="stopped")
            else:
                with self._lock:
                    self.state = "error"
                    self.error = str(e)
                self._log(f"[FATAL] Run failed: {e}")
                self._emit("state", state="error", error=str(e))
        finally:
            self._close_driver()
            _timemod.sleep = _orig_sleep
            sys.stdout, sys.stderr = old_stdout, old_stderr
            root.removeHandler(handler)
            root.setLevel(prev_level)
            self._record_run_history("lessons")

    def _record_run_history(self, kind):
        """Append this run's outcome to the persisted history (best-effort).

        Called from the run threads' ``finally`` blocks, after the final state
        is set, so every real run (done / stopped / error) is recorded. Dry
        runs never reach these threads and are not recorded.
        """
        try:
            with self._lock:
                state = self.state
                cases = [dict(c) for c in self.cases]
                error = self.error
                started = self._started_at
            totals = {}
            for c in cases:
                totals[c.get("status", "?")] = totals.get(c.get("status", "?"), 0) + 1
            for c in cases:                      # keep the file small
                if c.get("error"):
                    c["error"] = str(c["error"])[:300]
            entry = {
                "id": time.strftime("%Y%m%d_%H%M%S"),
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                            time.localtime(started)) if started else "",
                "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "kind": kind,                    # suite | lessons
                "state": state,
                "error": (error or "")[:300],
                "totals": totals,
                "cases": cases,
                "report_txt": self.report_txt,
                "report_html": self.report_html_path,
            }
            history = load_run_history()
            history.insert(0, entry)
            os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history[:MAX_HISTORY], f, indent=1)
        except Exception as e:          # history must never break a run
            logging.getLogger(__name__).warning(f"run history not recorded: {e}")

    def _sleep(self, seconds):
        """Interruptible sleep: wakes immediately when stop is requested."""
        self._stop_event.wait(timeout=seconds)

    def _preflight(self, host, port, timeout=3.0):
        """Quick TCP check so a missing app fails in seconds, not after AltDriver's 60s retry."""
        import socket
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def _connect(self, host, port, platform, cfg):
        from alttester import AltDriver
        # enable_logging=False: AltTester's per-command "Received: {...}" debug
        # output would otherwise flood the live log and starve the server.
        kwargs = dict(host=host, port=port, platform=platform, enable_logging=False)
        app_id = (cfg.get("app_id") or "").strip()
        device = (cfg.get("device_instance_id") or "").strip()
        if app_id:
            kwargs["app_id"] = app_id
        if device:
            kwargs["device_instance_id"] = device
        return AltDriver(**kwargs)

    def _set_progress(self, ui, total_users, username, lesson, lessons, lesson_idx=None):
        prog = {
            "user_index": ui + 1,
            "user_total": total_users,
            "username": username,
            "lesson": lesson,
            "lessons_total": len(lessons),
            "lessons_done": (lesson_idx if lesson_idx is not None else 0),
        }
        # Overall fraction across users * lessons.
        per_user = len(lessons) or 1
        done = ui * per_user + (lesson_idx if lesson_idx is not None else 0)
        prog["fraction"] = round(done / (total_users * per_user), 3) if total_users else 0
        with self._lock:
            self.progress = prog
        self._emit("progress", **prog)

    # ---- reports ---------------------------------------------------------
    def _build_reports(self, platform):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        txt_path = os.path.join(REPORTS_DIR, f"runner_report_{platform}_{ts}.txt")
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                utilsdemo.write_activity_report(f)
            self.report_txt = txt_path
            self._log(f"[REPORT] Text report: {txt_path}")
        except Exception as e:
            self._log(f"[WARN] Failed to write text report: {e}")

        try:
            html_content = self._render_html_report(platform)
            html_path = os.path.join(REPORTS_DIR, f"runner_report_{platform}_{ts}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.report_html = html_content
            self.report_html_path = html_path
            self._log(f"[REPORT] HTML report: {html_path}")
        except Exception as e:
            self._log(f"[WARN] Failed to build HTML report: {e}")

        self._email_report(platform, ts)

    def _email_report(self, platform, ts):
        """Email the report files when a run finishes (only if requested). Never raises."""
        try:
            if not self._email_after:
                self._log("[EMAIL] Skipped — email report not requested for this run.")
                return
            if not emailer.email_configured():
                self._log("[EMAIL] Skipped — SMTP not configured (automation_email.env).")
                return
            to = [emailer.default_recipient()]
            state = "stopped" if self._stopped() else "completed"
            subject = f"Voca Tooki run report ({state}) — {ts}"
            body = self._email_body(platform, state)
            attachments = [p for p in (self.report_txt, self.report_html_path) if p]
            ok, detail = emailer.send_report_email(to, subject, body, attachments)
            self._log(("[EMAIL] " if ok else "[EMAIL][WARN] ") + detail)
        except Exception as e:
            self._log(f"[EMAIL][WARN] Email step failed: {e}")

    def _email_body(self, platform, state):
        report = utilsdemo.activity_report
        totals = {"PASSED": 0, "FAILED": 0, "SKIPPED": 0}
        for e in report:
            totals[e.get("status", "")] = totals.get(e.get("status", ""), 0) + 1
        lines = [
            f"Voca Tooki automation run {state}.",
            f"Platform: {platform}",
            f"Activities: {len(report)}  |  Passed: {totals.get('PASSED', 0)}  "
            f"Failed: {totals.get('FAILED', 0)}  Skipped: {totals.get('SKIPPED', 0)}",
            "",
            "Users / lessons in this run:",
        ]
        for g in self.groups:
            lines.append(f"  - {g['username']} (class {g['class_id']}), lessons {g['lesson_from']}-{g['lesson_to']}")
        lines += ["", "Full report attached (.txt and .html)."]
        return "\n".join(lines)

    def _render_html_report(self, platform):
        report = utilsdemo.activity_report
        rows = []
        totals = {"PASSED": 0, "FAILED": 0, "SKIPPED": 0}
        for i, g in enumerate(self.groups):
            end = self.groups[i + 1]["start"] if i + 1 < len(self.groups) else len(report)
            entries = report[g["start"]:end]
            rows.append(
                f'<tr class="group"><td colspan="4">User: {html.escape(g["username"])}'
                f' &nbsp;|&nbsp; class {html.escape(str(g["class_id"]))}'
                f' &nbsp;|&nbsp; lessons {g["lesson_from"]}-{g["lesson_to"]}</td></tr>'
            )
            for e in entries:
                status = e.get("status", "")
                totals[status] = totals.get(status, 0) + 1
                err = html.escape(e.get("error", "") or "")
                err_html = f'<details><summary>error</summary><pre>{err}</pre></details>' if err else ""
                rows.append(
                    f'<tr class="s-{html.escape(status.lower())}">'
                    f'<td>{html.escape(str(e.get("activity", "")))}</td>'
                    f'<td>{html.escape(status)}</td>'
                    f'<td>{html.escape(str(e.get("duration", "")))}</td>'
                    f'<td>{err_html}</td></tr>'
                )
        summary = (f'Passed: {totals.get("PASSED", 0)} &nbsp; '
                   f'Failed: {totals.get("FAILED", 0)} &nbsp; '
                   f'Skipped: {totals.get("SKIPPED", 0)}')
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Activity Report</title>
<style>
  body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2933; }}
  h1 {{ font-size: 20px; }}
  .summary {{ margin: 8px 0 16px; font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #d2d6dc; padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f5f7fa; }}
  tr.group td {{ background: #eef2ff; font-weight: 600; }}
  tr.s-passed  td:nth-child(2) {{ color: #057a55; font-weight: 600; }}
  tr.s-failed  td:nth-child(2) {{ color: #c81e1e; font-weight: 600; }}
  tr.s-skipped td:nth-child(2) {{ color: #c27803; font-weight: 600; }}
  pre {{ white-space: pre-wrap; margin: 4px 0; font-size: 12px; }}
</style></head>
<body>
  <h1>Activity Execution Report</h1>
  <div>Platform: {html.escape(platform)} &nbsp;|&nbsp; {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
  <div class="summary">{summary}</div>
  <table>
    <thead><tr><th>Activity</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan=4>No activities recorded.</td></tr>'}</tbody>
  </table>
</body></html>"""


# Module-level singleton used by the Flask app.
manager = RunManager()
