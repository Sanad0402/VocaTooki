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


# ---- release status: the one thing the team may see -----------------------
# The panel drives runs, holds Rally credentials and can delete generated code,
# so it stays on localhost. The release status is read-only and safe to share,
# so remote callers are allowed exactly that and nothing else.
_PUBLIC_PATHS = ("/status", "/api/status/release", "/static/")
_LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost")


def _is_local(addr):
    return (addr or "").split("%")[0] in _LOCAL_HOSTS


@app.before_request
def _guard_remote_access():
    if _is_local(request.remote_addr):
        return None
    path = request.path or "/"
    if any(path == p or path.startswith(p) for p in _PUBLIC_PATHS):
        if request.method != "GET":
            return jsonify({"error": "read-only"}), 403
        return None
    return jsonify({"error": "This panel is local-only. Release status: /status"}), 403


@app.route("/status")
def status_page():
    """Read-only release progress — the page to share with the team."""
    return render_template("status.html")


@app.route("/api/status/release")
def api_status_release():
    from runner import release_status
    return jsonify(release_status.summary(suite.tree()))


@app.route("/api/status/config", methods=["POST"])
def api_status_config():
    """Set the release name, the platform the runner is testing, and the scope."""
    from runner import release_status
    d = request.get_json(force=True, silent=True) or {}
    release_status.configure(release=d.get("release"), platform=d.get("platform"))
    return jsonify(release_status.summary(suite.tree()))


@app.route("/api/status/scope", methods=["POST"])
def api_status_scope():
    """Add or remove a folder / case from what the release percentage counts."""
    from runner import release_status
    d = request.get_json(force=True, silent=True) or {}
    release_status.set_scope(d.get("kind", "folder"), d.get("id", ""),
                             add=bool(d.get("add", True)))
    return jsonify(release_status.summary(suite.tree()))


@app.route("/api/status/case", methods=["POST"])
def api_status_case():
    """Record one case on one platform by hand (the cases AltTester cannot run)."""
    from runner import release_status
    d = request.get_json(force=True, silent=True) or {}
    tc_id = (d.get("id") or "").strip()
    if not tc_id:
        return jsonify({"error": "Missing test case id."}), 400
    release_status.record(tc_id, d.get("verdict"), platform=d.get("platform"),
                          source="manual", note=d.get("note", ""))
    return jsonify(release_status.summary(suite.tree()))


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


def _prune_generated_tests():
    """Reconcile the whole project with the suite after cases disappear.

    Deleting a case (or a whole folder) in the panel, or dropping it in Rally
    and re-syncing, used to leave its generated test file in ``Tests/rally``,
    where it kept on running and no longer belonged to any Rally case. Every
    removal path now sweeps the whole tree instead of tracking single ids.

    Returns response fields for the UI: ``removed_tests`` (paths deleted),
    ``kept_tests`` (hand-locked files left in place) and a ``prune_message``,
    all omitted when there was nothing to do.
    """
    from runner.test_generator import RallyTestGenerator
    try:
        result = RallyTestGenerator(_ROOT).prune_to_suite()
    except Exception:
        logger.exception("pruning generated tests failed")
        return {}

    deleted = [os.path.relpath(p, _ROOT) for p in result.get("deleted", [])]
    kept = [os.path.relpath(p, _ROOT) for p in result.get("kept", [])]
    if not deleted and not kept:
        return {}

    parts = []
    if deleted:
        parts.append(f"removed {len(deleted)} generated test(s): " + ", ".join(deleted))
    if kept:
        parts.append(f"kept {len(kept)} hand-edited file(s) (MANUAL_EDIT = True): "
                     + ", ".join(kept) + " — delete manually if no longer needed")
    logger.info("Prune: " + "; ".join(parts))
    return {"removed_tests": deleted, "kept_tests": kept,
            "prune_message": "; ".join(parts)}


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


@app.route("/api/rally/post-result", methods=["POST"])
def api_rally_post_result():
    """Post a run result back to Rally as a TestCaseResult.

    Body: {tc_id, verdict("Pass"|"Fail"|...), build, notes, screenshot(filename)}.
    Attaches the failure screenshot (if any) to the result. Build defaults to
    the app version reported by AltTester, else a caller-supplied value.
    """
    from runner.rally_api import create_client_from_env
    from runner.core import REPORTS_DIR

    body = request.get_json(force=True, silent=True) or {}
    tc_id = (body.get("tc_id") or "").strip()
    verdict = (body.get("verdict") or "").strip() or "Pass"
    build = (body.get("build") or "").strip() or "n/a"
    notes = body.get("notes") or ""
    shot = os.path.basename(body.get("screenshot") or "")

    if not tc_id:
        return jsonify({"error": "Missing test case id."}), 400

    client = create_client_from_env("rally.env")
    if not client or not client.test_connection():
        return jsonify({"error": "Rally not connected (check rally.env)."}), 400

    tc = client.find_test_case(tc_id)
    if not tc:
        return jsonify({"error": f"{tc_id} not found in Rally."}), 404

    project_ref = (tc.get("Project") or {}).get("_ref")
    result = client.create_test_case_result(
        tc.get("_ref"), verdict, build, notes, project_ref=project_ref)
    if not result or result.get("_errors"):
        return jsonify({"error": "Rally rejected the result: "
                        + "; ".join(result.get("_errors", ["unknown"]) if result else ["no response"])}), 502

    # Attach the screenshot to the TestCase (an Artifact). Rally's Attachment
    # only accepts Artifacts, and a TestCaseResult is not one — so it can't be
    # attached to the result directly; the TestCase is the closest home and its
    # attachments are visible right next to the result.
    attached = False
    if shot:
        path = os.path.join(REPORTS_DIR, "screenshots", shot)
        if os.path.exists(path):
            import time as _t
            attached = client.attach_screenshot(
                tc.get("_ref"), path,
                name=f"{tc_id}_{verdict}_{_t.strftime('%Y%m%d_%H%M%S')}.png")
    return jsonify({
        "ok": True,
        "message": f"{tc_id}: posted {verdict} to Rally"
                   + (" · screenshot attached to the test case" if attached
                      else (" · screenshot NOT attached" if shot else "")),
        "verdict": verdict,
    })


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

        # Refresh ONLY already-generated tests; new cases stay "not generated"
        # until the user explicitly clicks generate on them. Cases that no
        # longer exist in Rally have their code removed from the project.
        generator = RallyTestGenerator(_ROOT)
        # prune=False: _prune_generated_tests does the sweep, so the deletions
        # are reported to the UI instead of happening silently.
        refreshed = generator.refresh_generated_tests(prune=False)
        # Mark the cases whose generated CODE this sync actually changed (a
        # username edited in Rally, say). The mark is stored on the case, so it
        # is still there when the user comes back to the panel later.
        changed_ids = list(getattr(generator, "changed_case_ids", []) or [])
        if changed_ids:
            suite.mark_updated(changed_ids)
        pruned = _prune_generated_tests()

        # Reload suite tree
        new_suite = suite.tree()

        total = sum(len(f.get("cases", [])) for f in new_suite.get("folders", []))
        logger.info(f"Synced {total} case(s) from {project_name}; refreshed {len(refreshed)} generated test(s)")

        removed = len(pruned.get("removed_tests", []))
        return jsonify({
            "success": True,
            "message": (f"Synced {total} case(s) from {project_name} "
                        f"({len(refreshed)} generated test(s) refreshed"
                        + (f", {removed} removed" if removed else "") + ")"),
            **pruned,
            "suite": new_suite,
            "project_name": project_name,
            "count": total,
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
    pruned = _prune_generated_tests()
    return jsonify({**tree, **pruned})


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
    # The case is gone from the suite; its generated code must not stay behind.
    pruned = _prune_generated_tests()
    return jsonify({**tree, **pruned})


@app.route("/api/run", methods=["POST"])
def api_run():
    cfg = request.get_json(force=True, silent=True) or {}
    ok, payload = manager.start(cfg)
    if not ok:
        # 409 when a run is active, 400 for validation problems.
        code = 409 if "in progress" in (payload.get("error", "")) else 400
        return jsonify(payload), code
    return jsonify(payload)


@app.route("/api/run/preview", methods=["POST"])
def api_run_preview():
    """The cases a run WOULD execute, for the screenshot dialog.

    Resolved server-side with the very same suite.resolve() the run uses, so
    the dialog can never offer a case the run will not touch (or miss one a
    folder selection pulls in).
    """
    cfg = request.get_json(force=True, silent=True) or {}
    rt = cfg.get("run_type")
    if rt not in ("test_folder", "test_case"):
        return jsonify({"run_type": rt, "cases": []})
    selection = cfg.get("test_folders") if rt == "test_folder" else cfg.get("test_cases")
    cases, warnings = suite.resolve(rt, selection or [])
    return jsonify({
        "run_type": rt,
        "warnings": warnings,
        # suite.resolve() yields the raw case dicts (id/name); the tc_id/tc_name
        # shape only appears later, in RunManager._case_row.
        "cases": [{"tc_id": c.get("id", ""), "tc_name": c.get("name", ""),
                   "linked": bool((c.get("action") or {}).get("nodeid"))}
                  for c in cases],
    })


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
                # Advance by seq, not count: the manager trims old log events,
                # so counting would replay or re-skip after a trim.
                cursor = events[-1]["seq"] + 1
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


@app.route("/api/suite/case/<tc_id>/generate", methods=["POST"])
def api_case_generate(tc_id):
    """Explicitly generate the pytest file for one Rally case.

    LIVE-FIRST: when the game + AltTester are reachable on the configured
    host/port, the code is generated *from the running app* — the current
    scene's real element names are discovered and wired into the test (same
    engine as the batch "Generate from live app" button). Only when the app is
    unreachable (or the caller passes ``live: false``) does this fall back to
    the offline template generator, and the response says which path was used.
    """
    from runner.test_generator import RallyTestGenerator
    import json as _json
    try:
        with open(os.path.join(_ROOT, "data", "rally_suite.json"), encoding="utf-8") as f:
            cases = _json.load(f).get("test_cases", [])
    except (OSError, ValueError):
        cases = []
    tc = next((t for t in cases if t.get("id") == tc_id), None)
    if not tc:
        return jsonify({"error": f"{tc_id} not found in the synced Rally suite. Sync first."}), 404

    d = request.get_json(force=True, silent=True) or {}
    host = d.get("host") or "127.0.0.1"
    try:
        port = int(d.get("port") or 13000)
    except (TypeError, ValueError):
        port = 13000
    want_live = d.get("live", True)

    path, elements, source, live_error = None, {}, "offline", None
    if want_live:
        # Cheap TCP check first so an unreachable app fails fast instead of
        # blocking the request on the connect timeout.
        if manager._preflight(host, port, timeout=1.5):
            from runner.live_skeleton import generate_from_live_app
            try:
                path, elements, source = generate_from_live_app(
                    tc_id, host=host, port=port,
                    platform=d.get("platform") or "WindowsEditor",
                    app_id=d.get("app_id") or "",
                    device_instance_id=d.get("device_instance_id") or "",
                )
            except Exception as e:  # noqa: BLE001 - fall back, never lose the click
                logger.exception("live generation failed for %s; falling back offline", tc_id)
                live_error = str(e)
        else:
            live_error = f"AltTester not reachable at {host}:{port}"

    if path is None:
        try:
            path = RallyTestGenerator(_ROOT).generate_test(tc)
        except Exception as e:
            logger.exception("generate failed for %s", tc_id)
            return jsonify({"error": f"Generation failed: {e}"}), 500

    rel = os.path.relpath(str(path), _ROOT)
    # The code now matches the synced case, so the "updated" mark has served
    # its purpose — clear it before the tree is rebuilt below.
    suite.clear_updated(tc_id)
    impl = suite.impl_status((tc.get("action") or {}).get("nodeid") or "")

    if source in ("mcp", "altdriver"):
        via = "the MCP CLI" if source == "mcp" else "AltDriver (MCP CLI unavailable)"
        msg = (f"{tc_id}: generated {rel} from the LIVE app via {via} — scene "
               f"'{elements.get('scene')}' ({len(elements.get('inputs', []))} inputs, "
               f"{len(elements.get('buttons', []))} buttons).")
        activity = (elements.get("activity") or {}).get("title")
        if activity:
            msg += f" Activity thumb confirmed on screen: “{activity}”."
        if impl != "real":
            msg += (" Still a stub: the current scene didn't cover this case — "
                    "navigate the app to the screen it tests and generate again, "
                    "or finish the pre-wired TODOs.")
    else:
        msg = f"{tc_id}: generated {rel} offline (templates only, app not read)."
        if live_error:
            msg += f" Live generation skipped: {live_error}."
        if impl != "real":
            msg += (" Wrote a stub — add credentials/level to the Rally description "
                    "and re-sync, or start the game and generate again.")

    return jsonify({"ok": True, "impl": impl, "path": rel, "message": msg,
                    "source": source, "live_error": live_error,
                    "scene": elements.get("scene"),
                    "inputs": elements.get("inputs", []),
                    "buttons": elements.get("buttons", []),
                    "suite": suite.tree()})


@app.route("/api/preflight")
def api_preflight():
    """Quick TCP reachability check of the AltTester server (topbar dot)."""
    host = request.args.get("host", "127.0.0.1")
    try:
        port = int(request.args.get("port", "13000"))
    except ValueError:
        return jsonify({"ok": False})
    return jsonify({"ok": manager._preflight(host, port, timeout=1.5)})


# ---- run screenshots (per-run folders, capped) ----------------------------
# Distinct from /api/screenshots/<name>, which serves the FLAT failure frames.
# These are the milestone frames a run captures into reports/screenshots/<run>/.

@app.route("/api/shots")
def api_shots():
    from runner import screenshots
    return jsonify({"runs": screenshots.list_runs()})


@app.route("/api/shots/<run_id>/<name>")
def api_shot_file(run_id, name):
    from runner import screenshots
    path = screenshots.resolve_file(run_id, name)
    if path is None:
        abort(404)
    # Read the bytes instead of send_file(): on Windows a file handle that
    # outlives the response keeps a LOCK on the frame, and deleting the run
    # then silently leaves the viewed thumbnail behind. These frames are small.
    return Response(path.read_bytes(), mimetype="image/png")


@app.route("/api/shots", methods=["DELETE"])
def api_shots_delete():
    """Delete one run's frames (?run_id=...) or every run's."""
    from runner import screenshots
    run_id = (request.args.get("run_id") or "").strip()
    removed = screenshots.delete_screenshots(run_id or None)
    return jsonify({"ok": True, "removed": removed,
                    "message": f"Deleted {removed} screenshot(s)"
                               + (f" from {run_id}." if run_id else " from all runs.")})


@app.route("/api/screenshots/<name>")
def api_screenshot(name):
    """Serve a failure screenshot. Only bare filenames from the screenshots
    directory are accepted — no paths."""
    from runner.core import REPORTS_DIR
    if os.path.basename(name) != name:
        abort(404)
    path = os.path.join(REPORTS_DIR, "screenshots", name)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="image/png")


# ---- run history ("Last runs" tab) ----------------------------------------

@app.route("/api/runs")
def api_runs():
    from runner import core as core_mod
    return jsonify({"runs": core_mod.load_run_history()})


@app.route("/api/runs/clear", methods=["POST"])
def api_runs_clear():
    from runner import core as core_mod
    core_mod.clear_run_history()
    return jsonify({"ok": True})


@app.route("/api/runs/<run_id>/report.<kind>")
def api_run_report(run_id, kind):
    """Serve an archived run's report. Paths come only from the recorded
    history entry (never from the request), so this cannot read arbitrary files."""
    from runner import core as core_mod
    entry = next((r for r in core_mod.load_run_history() if r.get("id") == run_id), None)
    if not entry:
        abort(404)
    path = entry.get("report_html") if kind == "html" else entry.get("report_txt")
    if not path or not os.path.exists(path):
        abort(404)
    if kind == "html":
        return send_file(path, mimetype="text/html")
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


if __name__ == "__main__":
    # Single-instance guard: a second panel next to a live one is how stale
    # code kept serving port 5000 (the old process owned the port while the
    # fresh one silently failed to bind). Refuse loudly instead.
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 5000))
        probe.close()
    except OSError:
        print("Another runner panel is ALREADY serving http://127.0.0.1:5000 — "
              "not starting a second one.\n"
              "Close the other window (or kill the old python process) and retry.")
        raise SystemExit(1)
    print("Runner panel: http://127.0.0.1:5000")
    # threaded=True so SSE streaming + background run thread coexist with requests.
    # Localhost by default. Set PANEL_HOST=0.0.0.0 to let the team reach
    # http://<this machine>:5000/status — every other route stays refused for
    # remote callers (see _guard_remote_access).
    host = os.environ.get("PANEL_HOST", "127.0.0.1")
    if host != "127.0.0.1":
        print(f"Release status shared on http://{host}:5000/status "
              f"(control panel remains local-only)")
    app.run(host=host, port=5000, threaded=True, debug=False)
