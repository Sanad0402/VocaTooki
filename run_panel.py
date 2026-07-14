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
import logging

logger = logging.getLogger(__name__)

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
_load_env_file(os.path.join(_ROOT, "rally.env"))

from flask import Flask, request, jsonify, render_template, Response, send_file, abort

from runner.core import manager, REPORTS_DIR
from runner.modes import mode_list, DEFAULT_MODE
from runner import suite
from data.test_users import TEST_USERS, DEFAULT_CLASS_ID

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT, "runner", "templates"),
    static_folder=os.path.join(_ROOT, "runner", "static"),
)
# Re-read templates from disk each request so UI edits show on a plain refresh
# (without this, Jinja caches the compiled template while debug=False).
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


@app.route("/")
def index():
    return render_template("index.html")


def _pick_auto_project(projects):
    """Pick the project Auto-detect would sync: first whose name contains 'dev',
    else the first project. Returns (project_id, project_name) or (None, None)."""
    for proj in projects:
        if "dev" in proj.get("Name", "").lower():
            return proj.get("_ref", "").split("/")[-1], proj.get("Name", "Unknown")
    if projects:
        return projects[0].get("_ref", "").split("/")[-1], projects[0].get("Name", "Unknown")
    return None, None


def _last_sync_info():
    """Read data/rally_suite.json metadata so the UI can show last-synced info.

    Returns None if the suite was never synced from Rally."""
    try:
        with open(os.path.join(_ROOT, "data", "rally_suite.json"), "r", encoding="utf-8") as f:
            meta = (json.load(f) or {}).get("metadata") or {}
    except (OSError, json.JSONDecodeError):
        return None
    if not meta.get("synced_at"):
        return None
    return {
        "synced_at": meta.get("synced_at"),
        "total_cases": meta.get("total_cases"),
        "project_id": meta.get("project_id"),
    }


def _get_rally_config():
    """Get Rally configuration from environment."""
    rally_token = os.getenv("RALLY_API_TOKEN", "")

    # Only needs API token (URL and project ID auto-detected)
    has_config = bool(rally_token)

    return {
        "has_config": has_config,
        "last_sync": _last_sync_info(),
    }


@app.route("/api/config")
def api_config():
    rally_config = _get_rally_config()

    return jsonify({
        "users": [
            {"username": u["username"], "class_id": u.get("class_id", DEFAULT_CLASS_ID)}
            for u in TEST_USERS
        ],
        "modes": mode_list(),
        "run_types": [
            {"key": "lesson_range", "label": "Lesson Range (users)"},
            {"key": "test_folder", "label": "Test Folder"},
            {"key": "test_case", "label": "Test Case(s)"},
        ],
        "suite": suite.tree(),
        "rally": rally_config,
        "defaults": {
            "run_type": "lesson_range",
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


@app.route("/api/suite")
def api_suite():
    return jsonify(suite.tree())


@app.route("/api/rally/projects")
def api_rally_projects():
    """List Rally projects for the UI picker (readable names, no IDs to type).

    Returns {configured, projects: [{id, name}], auto_detected} so the UI can
    offer an 'Auto-detect' default plus a dropdown of real project names."""
    from runner.rally_api import create_client_from_env

    client = create_client_from_env("rally.env")
    if not client:
        return jsonify({"configured": False, "projects": [], "auto_detected": ""})

    try:
        projects = client.get_projects()
    except Exception:
        logger.exception("Failed to list Rally projects")
        return jsonify({"configured": True, "projects": [], "auto_detected": ""})

    auto_id, _ = _pick_auto_project(projects)
    return jsonify({
        "configured": True,
        "projects": [
            {"id": p.get("_ref", "").split("/")[-1], "name": p.get("Name", "Unknown")}
            for p in projects
        ],
        "auto_detected": auto_id or "",
    })


@app.route("/api/rally/test", methods=["POST"])
def api_rally_test():
    """Quick connectivity check — verifies the API key without running a sync."""
    from runner.rally_api import create_client_from_env

    client = create_client_from_env("rally.env")
    if not client:
        return jsonify({"ok": False, "message": "No API token — add RALLY_API_TOKEN to rally.env"}), 200

    if not client.test_connection():
        return jsonify({"ok": False, "message": "Rally rejected the API key (check rally.env)"}), 200

    try:
        n = len(client.get_projects())
    except Exception:
        n = None
    msg = "Connected to Rally" + (f" · {n} project{'' if n == 1 else 's'}" if n is not None else "")
    return jsonify({"ok": True, "message": msg}), 200


@app.route("/api/rally/sync", methods=["POST"])
def api_rally_sync():
    """Sync test cases from Rally and reload suite.

    Accepts an optional ``project_id`` in the POST body. When omitted (empty),
    the project is auto-detected (first named '…dev…', else the first project)."""
    from runner.rally_api import create_client_from_env
    from runner.test_generator import RallyTestGenerator

    body = request.get_json(force=True, silent=True) or {}
    requested_id = (body.get("project_id") or "").strip()

    try:
        # Create Rally client
        client = create_client_from_env("rally.env")
        if not client:
            return jsonify({
                "error": "Rally not configured. Set RALLY_API_TOKEN in rally.env"
            }), 400

        # Test connection
        if not client.test_connection():
            return jsonify({
                "error": "Failed to connect to Rally. Check RALLY_API_TOKEN in rally.env"
            }), 400

        if requested_id:
            # Explicit choice from the UI dropdown — use it directly.
            project_id = requested_id
            project_name = next(
                (p.get("Name", "Unknown") for p in client.get_projects()
                 if p.get("_ref", "").split("/")[-1] == requested_id),
                requested_id,
            )
            logger.info(f"Using selected project: {project_name} ({project_id})")
        else:
            # Auto-detect a project.
            project_id, project_name = _pick_auto_project(client.get_projects())
            if not project_id:
                return jsonify({"error": "No projects found in Rally"}), 400
            logger.info(f"Auto-detected project: {project_name} ({project_id})")

        # Sync to JSON
        output_file = os.path.join(_ROOT, "data", "rally_suite.json")
        success = client.sync_to_json(project_id, output_file, automated_only=True)

        if not success:
            return jsonify({"error": "Failed to sync from Rally"}), 500

        # Generate tests
        generator = RallyTestGenerator(_ROOT)
        generated = generator.generate_all_tests()

        # Reload suite tree
        new_suite = suite.tree()

        logger.info(f"Synced {len(generated)} test cases from {project_name}")

        return jsonify({
            "success": True,
            "message": f"Synced {len(generated)} test cases from {project_name}",
            "suite": new_suite,
            "project_name": project_name,
            "count": len(generated),
            "synced_at": (_last_sync_info() or {}).get("synced_at"),
        })

    except Exception as e:
        logger.exception("Rally sync error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/suite/folder", methods=["POST"])
def api_suite_folder():
    d = request.get_json(force=True, silent=True) or {}
    try:
        if d.get("_action") == "update":
            tree = suite.update_folder(d.get("id"), name=d.get("name"), parent=d.get("parent"))
        else:
            tree = suite.add_folder(d.get("id"), d.get("name"), d.get("parent"))
    except suite.SuiteError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(tree)


@app.route("/api/suite/folder/<folder_id>", methods=["DELETE"])
def api_suite_folder_delete(folder_id):
    cascade = request.args.get("cascade") in ("1", "true", "yes")
    try:
        tree = suite.delete_folder(folder_id, cascade=cascade)
    except suite.SuiteError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(tree)


@app.route("/api/suite/skeleton", methods=["POST"])
def api_suite_skeleton():
    """Generate real test skeletons for selected cases by discovering elements
    on the LIVE app (AltTester). Requires the game running and reachable at the
    given host/port. Upgrades honest stubs into real/pre-wired skeletons."""
    from runner.live_skeleton import generate_skeletons_live

    d = request.get_json(force=True, silent=True) or {}
    tc_ids = [str(t).strip() for t in (d.get("test_cases") or []) if str(t).strip()]
    if not tc_ids:
        return jsonify({"error": "Select at least one test case first."}), 400

    try:
        results, elements = generate_skeletons_live(
            tc_ids,
            host=d.get("host") or "127.0.0.1",
            port=int(d.get("port") or 13000),
            platform=d.get("platform") or "WindowsEditor",
            app_id=d.get("app_id") or "",
            device_instance_id=d.get("device_instance_id") or "",
        )
    except Exception as e:
        # Almost always: the app/AltTester isn't running or is unreachable.
        logger.exception("Live skeleton generation failed")
        return jsonify({
            "error": f"Could not connect to the app for element discovery: {e}. "
                     f"Is the game running and AltTester reachable?"
        }), 502

    ok = sum(1 for r in results if r.get("ok"))
    return jsonify({
        "results": results,
        "scene": elements.get("scene"),
        "inputs": elements.get("inputs", []),
        "buttons": elements.get("buttons", []),
        "message": f"Generated {ok}/{len(results)} skeleton(s) from scene "
                   f"'{elements.get('scene')}' ({len(elements.get('inputs', []))} inputs, "
                   f"{len(elements.get('buttons', []))} buttons).",
        "suite": suite.tree(),
    })


@app.route("/api/suite/case", methods=["POST"])
def api_suite_case():
    d = request.get_json(force=True, silent=True) or {}
    try:
        if d.get("_action") == "update":
            tree = suite.update_case(d.get("id"), d)
        else:
            tree = suite.add_case(d)
    except suite.SuiteError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(tree)


@app.route("/api/suite/case/impl", methods=["POST"])
def api_suite_case_impl():
    """Manually flip a case's linked test between 'real' and 'stub'.

    Edits the test file's markers (and locks MANUAL_EDIT=True so a re-sync keeps
    the choice). Body: {"id": "TC452", "impl": "real"|"stub"}."""
    from runner.impl_toggle import set_case_impl

    d = request.get_json(force=True, silent=True) or {}
    tc_id = (d.get("id") or "").strip()
    target = (d.get("impl") or "").strip().lower()
    if not tc_id:
        return jsonify({"error": "Missing test case id."}), 400
    try:
        res = set_case_impl(tc_id, target)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Impl toggle failed")
        return jsonify({"error": str(e)}), 500
    res["suite"] = suite.tree()
    return jsonify(res)


@app.route("/api/suite/case/<tc_id>", methods=["DELETE"])
def api_suite_case_delete(tc_id):
    try:
        tree = suite.delete_case(tc_id)
    except suite.SuiteError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(tree)


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
    print("Runner panel: http://127.0.0.1:5000")
    # threaded=True so SSE streaming + background run thread coexist with requests.
    app.run(host="127.0.0.1", port=5000, threaded=True, debug=False)
