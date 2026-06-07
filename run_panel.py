"""Local HTML runner control panel.

Usage:
    pip install -r requirements.txt   # first time (installs Flask)
    python run_panel.py               # then open http://localhost:5000

It drives the existing AltTester automation: pick users, a lesson range and a run
mode, then Run / Stop / Dry-run with a live log, progress and a results report.

The app must be running and AltTester reachable on the configured host/port
(default 127.0.0.1:13000) for real runs to do anything.
"""

import os
import sys
import json
import time

# Make sure the project root is importable when launched directly.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _load_env_file(path):
    """Minimal .env loader (no dependency) so AUTO_EMAIL_* are available."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass


_load_env_file(os.path.join(_ROOT, "automation_email.env"))

from flask import Flask, request, jsonify, render_template, Response, send_file, abort

from runner.core import manager, REPORTS_DIR
from runner.modes import mode_list, DEFAULT_MODE
from data.test_users import TEST_USERS, DEFAULT_CLASS_ID

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT, "runner", "templates"),
    static_folder=os.path.join(_ROOT, "runner", "static"),
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "users": [
            {"username": u["username"], "class_id": u.get("class_id", DEFAULT_CLASS_ID)}
            for u in TEST_USERS
        ],
        "modes": mode_list(),
        "defaults": {
            "mode": DEFAULT_MODE,
            "lesson_from": 0,
            "lesson_to": 6,
            "platform": "WindowsEditor",
            "host": "127.0.0.1",
            "port": 13000,
            "app_id": "",
            "device_instance_id": "",
        },
        "reports_dir": REPORTS_DIR,
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    cfg = request.get_json(force=True, silent=True) or {}
    ok, payload = manager.start(cfg)
    if not ok:
        # 409 when a run is active, 400 for validation problems.
        code = 409 if "in progress" in (payload.get("error", "")) else 400
        return jsonify(payload), code
    return jsonify(payload)


@app.route("/api/stop", methods=["POST"])
def api_stop():
    return jsonify({"stopped": manager.stop()})


@app.route("/api/status")
def api_status():
    return jsonify(manager.snapshot())


@app.route("/api/stream")
def api_stream():
    def gen():
        cursor = 0
        # Seed any events already recorded (e.g. dry-run or late connect).
        while True:
            events = manager.events_since(cursor)
            if events:
                cursor += len(events)
                for evt in events:
                    yield f"data: {json.dumps(evt)}\n\n"
            else:
                # Heartbeat keeps proxies/clients from timing out.
                yield ": keep-alive\n\n"
            snap_state = manager.state
            if snap_state in ("done", "error", "stopped") and not manager.events_since(cursor):
                yield f"data: {json.dumps({'type': 'end', 'state': snap_state})}\n\n"
                break
            time.sleep(0.3)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/report.txt")
def api_report_txt():
    if not manager.report_txt or not os.path.exists(manager.report_txt):
        abort(404)
    return send_file(manager.report_txt, as_attachment=True,
                     download_name=os.path.basename(manager.report_txt))


@app.route("/api/report.html")
def api_report_html():
    if not manager.report_html:
        abort(404)
    return Response(manager.report_html, mimetype="text/html")


if __name__ == "__main__":
    print("Runner panel: http://localhost:5000")
    # threaded=True so SSE streaming + background run thread coexist with requests.
    app.run(host="127.0.0.1", port=5000, threaded=True, debug=False)
