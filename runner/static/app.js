"use strict";

const $ = (id) => document.getElementById(id);
const LS_KEY = "vt_runner_cfg";
const LS_USERS = "vt_runner_custom_users";
const LS_RALLY_PROJECT = "vt_runner_rally_project";

let CONFIG = null;
let MODES = [];
let SUITE = { folders: [] };
let SEL_FOLDERS = new Set();
let SEL_CASES = new Set();
let EXPANDED = new Set();   // folder ids currently expanded (default: all collapsed)
let evtSource = null;
let statusTimer = null;

// ---------------------------------------------------------------- init
async function init() {
  CONFIG = await (await fetch("/api/config")).json();
  MODES = CONFIG.modes;
  SUITE = CONFIG.suite || { folders: [] };

  // Run types
  const rtEl = $("run_type");
  rtEl.innerHTML = "";
  (CONFIG.run_types || []).forEach((r) => {
    const o = document.createElement("option");
    o.value = r.key; o.textContent = r.label;
    rtEl.appendChild(o);
  });
  rtEl.value = (CONFIG.defaults && CONFIG.defaults.run_type) || "lesson_range";
  rtEl.addEventListener("change", () => { onRunTypeChange(); saveCfg(); });

  // Modes
  const modeEl = $("mode");
  modeEl.innerHTML = "";
  MODES.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.key; o.textContent = m.label;
    modeEl.appendChild(o);
  });
  modeEl.value = CONFIG.defaults.mode;
  modeEl.addEventListener("change", updateModeDesc);

  $("lesson_from").value = CONFIG.defaults.lesson_from;
  $("lesson_to").value = CONFIG.defaults.lesson_to;
  $("platform").value = CONFIG.defaults.platform;
  $("host").value = CONFIG.defaults.host;
  $("port").value = CONFIG.defaults.port;

  $("btn-add-user").addEventListener("click", () => { addCustomUserRow(); saveCustomRows(); });
  $("custom-users").addEventListener("input", saveCustomRows);
  $("custom-users").addEventListener("change", saveCustomRows);
  $("custom-users").addEventListener("click", (e) => {
    if (e.target.classList && e.target.classList.contains("cu-remove")) saveCustomRows();
  });

  $("btn-add-folder").addEventListener("click", () => showFolderForm(null));
  $("btn-add-case").addEventListener("click", () => showCaseForm(null));

  // Rally event listeners (safe — only attach if elements exist)
  const syncBtn = $("btn-sync-rally");
  const testBtn = $("btn-rally-test");
  const projectBtn = $("btn-rally-project");
  const projectSel = $("rally-project");
  if (syncBtn) syncBtn.addEventListener("click", syncRally);
  if (testBtn) testBtn.addEventListener("click", testRally);
  if (projectBtn) projectBtn.addEventListener("click", toggleProjectPicker);
  if (projectSel) projectSel.addEventListener("change", () => {
    try { localStorage.setItem(LS_RALLY_PROJECT, projectSel.value); } catch (e) {}
  });

  restoreConfig();
  restoreCustomUsers();
  updateModeDesc();
  renderSuiteTree();
  onRunTypeChange();

  initRallyCard();

  $("btn-run").addEventListener("click", () => startRun(false));
  $("btn-dry").addEventListener("click", () => startRun(true));
  $("btn-stop").addEventListener("click", stopRun);

  const snap = await (await fetch("/api/status")).json();
  applyState(snap.state);
  if (snap.state === "running") openStream();
  renderFromSnapshot(snap);
  if (snap.report_html || snap.report_txt) showReports();
}

function updateModeDesc() {
  const m = MODES.find((x) => x.key === $("mode").value);
  $("mode-desc").textContent = m ? m.description : "";
}

function currentRunType() { return $("run_type").value; }

function onRunTypeChange() {
  const rt = currentRunType();
  const suiteMode = rt === "test_folder" || rt === "test_case";
  $("lesson-config").classList.toggle("hidden", suiteMode);
  $("suite-config").classList.toggle("hidden", !suiteMode);
  if (suiteMode) {
    $("suite-label").textContent = rt === "test_folder" ? "Test Folders" : "Test Cases";
    $("suite-hint").textContent = rt === "test_folder"
      ? "Select folder(s) to run every test case inside. The user is hard-coded per test case."
      : "Select test case(s) to run. The user is hard-coded per test case.";
    $("suite-tree").classList.toggle("sel-folder", rt === "test_folder");
    $("suite-tree").classList.toggle("sel-case", rt === "test_case");
  }
}

// ---------------------------------------------------------------- custom users
function addCustomUserRow(prefill) {
  prefill = prefill || {};
  const enabled = prefill.enabled === undefined ? true : !!prefill.enabled;
  const row = document.createElement("div");
  row.className = "custom-user";
  row.innerHTML = `
    <input type="checkbox" class="cu-enabled" title="Include in run" ${enabled ? "checked" : ""}>
    <input type="text" class="cu-username" placeholder="username" value="${escapeAttr(prefill.username || "")}">
    <input type="password" class="cu-password" placeholder="password" value="${escapeAttr(prefill.password || "")}">
    <input type="text" class="cu-class" placeholder="class id (optional)" value="${escapeAttr(prefill.class_id || "")}">
    <button type="button" class="small danger cu-remove" title="Remove this user">✕</button>`;
  row.querySelector(".cu-remove").addEventListener("click", () => row.remove());
  $("custom-users").appendChild(row);
}
function getCustomRows() {
  return [...document.querySelectorAll("#custom-users .custom-user")].map((r) => ({
    enabled: r.querySelector(".cu-enabled").checked,
    username: r.querySelector(".cu-username").value.trim(),
    password: r.querySelector(".cu-password").value,
    class_id: r.querySelector(".cu-class").value.trim(),
  }));
}
function getCustomUsersForRun() {
  return getCustomRows().filter((r) => r.enabled && (r.username || r.password))
    .map((r) => ({ username: r.username, password: r.password, class_id: r.class_id }));
}
function saveCustomRows() { try { localStorage.setItem(LS_USERS, JSON.stringify(getCustomRows())); } catch (e) {} }
function restoreCustomUsers() {
  let rows;
  try { rows = JSON.parse(localStorage.getItem(LS_USERS)); } catch (e) {}
  $("custom-users").innerHTML = "";
  if (Array.isArray(rows) && rows.length) rows.forEach((r) => addCustomUserRow(r));
  else addCustomUserRow();
}

// ---------------------------------------------------------------- suite manager
function setSuite(tree) { SUITE = tree || { folders: [] }; renderSuiteTree(); }

function toggleFolder(id) {
  EXPANDED.has(id) ? EXPANDED.delete(id) : EXPANDED.add(id);
  renderSuiteTree();
}

function renderSuiteTree() {
  const el = $("suite-tree");
  if (!el) return;
  el.innerHTML = "";
  const folders = SUITE.folders || [];
  if (!folders.length) {
    el.innerHTML = '<span class="muted">No test folders yet. Use “+ Add folder”.</span>';
    return;
  }

  // Build hierarchy (folders arrive in tree order with depth + nested cases).
  const byId = {};
  folders.forEach((f) => (byId[f.id] = f));
  const children = {};
  const roots = [];
  folders.forEach((f) => {
    if (f.parent && byId[f.parent]) (children[f.parent] = children[f.parent] || []).push(f);
    else roots.push(f);
  });

  const renderCase = (c, depth) => {
    const row = document.createElement("div");
    row.className = "suite-row case";
    row.style.paddingLeft = (depth * 20) + "px";
    row.innerHTML = `
      <span class="twisty"></span>
      <input type="checkbox" class="sel-c" value="${escapeAttr(c.id)}" ${SEL_CASES.has(c.id) ? "checked" : ""}>
      <span class="ico">🧪</span><b>${escapeHtml(c.id)}</b> <span class="nm">${escapeHtml(c.name)}</span>
      <span class="muted">· ${c.nodeid ? "pytest" : "⚠ no test linked"}</span>
      <span class="row-actions">
        <button type="button" class="link c-edit">edit</button>
        <button type="button" class="link danger c-del">delete</button>
      </span>`;
    row.querySelector(".sel-c").addEventListener("change", (e) => {
      e.target.checked ? SEL_CASES.add(c.id) : SEL_CASES.delete(c.id); saveCfg();
    });
    row.querySelector(".c-edit").addEventListener("click", () => showCaseForm(c));
    row.querySelector(".c-del").addEventListener("click", () => deleteCase(c));
    el.appendChild(row);
  };

  const renderFolder = (f, depth) => {
    const kids = children[f.id] || [];
    const cases = f.cases || [];
    const hasChildren = kids.length > 0 || cases.length > 0;
    const expanded = EXPANDED.has(f.id);
    const row = document.createElement("div");
    row.className = "suite-row folder";
    row.style.paddingLeft = (depth * 20) + "px";
    row.innerHTML = `
      <span class="twisty">${hasChildren ? (expanded ? "▾" : "▸") : ""}</span>
      <input type="checkbox" class="sel-f" value="${escapeAttr(f.id)}" ${SEL_FOLDERS.has(f.id) ? "checked" : ""}>
      <span class="ico">📁</span><b>${escapeHtml(f.id)}</b> <span class="nm">${escapeHtml(f.name)}</span>
      <span class="count">${cases.length ? "· " + cases.length : ""}</span>
      <span class="row-actions">
        <button type="button" class="link f-edit">edit</button>
        <button type="button" class="link danger f-del">delete</button>
      </span>`;
    row.addEventListener("click", (e) => {
      if (e.target.closest("input, button")) return;   // checkbox / edit / delete don't toggle
      if (hasChildren) toggleFolder(f.id);
    });
    row.querySelector(".sel-f").addEventListener("change", (e) => {
      e.target.checked ? SEL_FOLDERS.add(f.id) : SEL_FOLDERS.delete(f.id); saveCfg();
    });
    row.querySelector(".f-edit").addEventListener("click", () => showFolderForm(f));
    row.querySelector(".f-del").addEventListener("click", () => deleteFolder(f));
    el.appendChild(row);

    if (expanded) {
      kids.forEach((k) => renderFolder(k, depth + 1));
      cases.forEach((c) => renderCase(c, depth + 1));
    }
  };

  roots.forEach((r) => renderFolder(r, 0));
}

function folderOptions(selected) {
  return ['<option value="">(top level)</option>'].concat(
    SUITE.folders.map((f) => `<option value="${escapeAttr(f.id)}" ${f.id === selected ? "selected" : ""}>${escapeHtml(f.id)} — ${escapeHtml(f.name)}</option>`)
  ).join("");
}

function showFolderForm(folder) {
  const editing = !!folder;
  $("suite-form").classList.remove("hidden");
  $("suite-form").innerHTML = `
    <h3>${editing ? "Edit" : "Add"} folder</h3>
    <div class="row">
      <div class="field"><label>ID</label><input id="sf_id" value="${escapeAttr(editing ? folder.id : "")}" ${editing ? "disabled" : ""} placeholder="TF200"></div>
      <div class="field grow"><label>Name</label><input id="sf_name" value="${escapeAttr(editing ? folder.name : "")}" placeholder="Login – Lockout"></div>
    </div>
    <div class="field"><label>Parent</label><select id="sf_parent">${folderOptions(editing ? folder.parent : "")}</select></div>
    <div class="suite-toolbar">
      <button type="button" class="small primary" id="sf_save">Save</button>
      <button type="button" class="small" id="sf_cancel">Cancel</button>
      <span id="sf_msg" class="error hidden"></span>
    </div>`;
  $("sf_cancel").addEventListener("click", () => $("suite-form").classList.add("hidden"));
  $("sf_save").addEventListener("click", async () => {
    const body = { id: $("sf_id").value.trim(), name: $("sf_name").value.trim(), parent: $("sf_parent").value };
    if (editing) body._action = "update";
    await suitePost("/api/suite/folder", body, "sf_msg");
  });
}

function showCaseForm(c) {
  const editing = !!c;
  $("suite-form").classList.remove("hidden");
  $("suite-form").innerHTML = `
    <h3>${editing ? "Edit" : "Add"} test case</h3>
    <div class="row">
      <div class="field"><label>ID</label><input id="sc_id" value="${escapeAttr(editing ? c.id : "")}" ${editing ? "disabled" : ""} placeholder="TC129"></div>
      <div class="field grow"><label>Name (exact Rally)</label><input id="sc_name" value="${escapeAttr(editing ? c.name : "")}" placeholder="TC02 – ..."></div>
    </div>
    <div class="field"><label>Folder</label><select id="sc_folder">${folderOptions(c ? c.folder : "")}</select></div>
    <div class="field"><label>Pytest nodeid <span class="hint">(path::test_function — creds live inside the test)</span></label>
      <input id="sc_nodeid" value="${escapeAttr(c && c.nodeid ? c.nodeid : "")}"
        placeholder="Tests/rally/TF194_Login/TF195_Positive_Flow/test_tc129_xxx.py::test_xxx"></div>
    <div class="suite-toolbar">
      <button type="button" class="small primary" id="sc_save">Save</button>
      <button type="button" class="small" id="sc_cancel">Cancel</button>
      <span id="sc_msg" class="error hidden"></span>
    </div>`;
  $("sc_cancel").addEventListener("click", () => $("suite-form").classList.add("hidden"));
  $("sc_save").addEventListener("click", async () => {
    const body = {
      id: $("sc_id").value.trim(), name: $("sc_name").value.trim(), folder: $("sc_folder").value,
      action_kind: "pytest", nodeid: $("sc_nodeid").value.trim(),
    };
    if (editing) body._action = "update";
    await suitePost("/api/suite/case", body, "sc_msg");
  });
}

async function suitePost(url, body, msgId) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) { const m = $(msgId); m.textContent = data.error || "Failed."; m.classList.remove("hidden"); return; }
  setSuite(data);
  $("suite-form").classList.add("hidden");
}

async function deleteFolder(f) {
  if (!confirm(`Delete folder ${f.id} – ${f.name}? (subfolders and test cases inside it will also be deleted)`)) return;
  const res = await fetch(`/api/suite/folder/${encodeURIComponent(f.id)}?cascade=1`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) { showError(data.error || "Delete failed."); return; }
  SEL_FOLDERS.delete(f.id); setSuite(data);
}

async function deleteCase(c) {
  if (!confirm(`Delete test case ${c.id} – ${c.name}?`)) return;
  const res = await fetch(`/api/suite/case/${encodeURIComponent(c.id)}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) { showError(data.error || "Delete failed."); return; }
  SEL_CASES.delete(c.id); setSuite(data);
}

// ---------------------------------------------------------------- config
function gatherConfig(dryRun) {
  const rt = currentRunType();
  const base = {
    run_type: rt, dry_run: dryRun, email_report: $("email_report").checked,
    platform: $("platform").value.trim(), host: $("host").value.trim(),
    port: parseInt($("port").value, 10),
    app_id: $("app_id").value.trim(), device_instance_id: $("device_instance_id").value.trim(),
  };
  if (rt === "test_folder") return { ...base, test_folders: [...SEL_FOLDERS] };
  if (rt === "test_case") return { ...base, test_cases: [...SEL_CASES] };
  return {
    ...base, users: getCustomUsersForRun(),
    lesson_from: parseInt($("lesson_from").value, 10),
    lesson_to: parseInt($("lesson_to").value, 10),
    mode: $("mode").value,
  };
}

function saveCfg() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      ...gatherConfig(false), sel_folders: [...SEL_FOLDERS], sel_cases: [...SEL_CASES],
    }));
  } catch (e) {}
}

function restoreConfig() {
  let s;
  try { s = JSON.parse(localStorage.getItem(LS_KEY)); } catch (e) { return; }
  if (!s) return;
  const set = (id, v) => { if (v !== undefined && v !== null && $(id)) $(id).value = v; };
  if (s.run_type && CONFIG.run_types.some((r) => r.key === s.run_type)) $("run_type").value = s.run_type;
  set("lesson_from", s.lesson_from); set("lesson_to", s.lesson_to);
  set("platform", s.platform); set("host", s.host); set("port", s.port);
  set("app_id", s.app_id); set("device_instance_id", s.device_instance_id);
  if (typeof s.email_report === "boolean") $("email_report").checked = s.email_report;
  if (s.mode && MODES.some((m) => m.key === s.mode)) $("mode").value = s.mode;
  if (Array.isArray(s.sel_folders)) SEL_FOLDERS = new Set(s.sel_folders);
  if (Array.isArray(s.sel_cases)) SEL_CASES = new Set(s.sel_cases);
}

// ---------------------------------------------------------------- run
function clientValidate(cfg) {
  if (cfg.run_type === "test_folder" && !(cfg.test_folders || []).length) return "Select at least one test folder.";
  if (cfg.run_type === "test_case" && !(cfg.test_cases || []).length) return "Select at least one test case.";
  if (cfg.run_type === "lesson_range" && !(cfg.users || []).length) return "Add at least one user.";
  return null;
}

async function startRun(dryRun) {
  hideError();
  const cfg = gatherConfig(dryRun);
  saveCfg();
  const err = clientValidate(cfg);
  if (err) { showError(err); return; }

  if (evtSource) { evtSource.close(); evtSource = null; }
  $("log").innerHTML = "";
  $("results").innerHTML = "";
  $("reports").classList.add("hidden");
  setProgress(0, "Starting…");

  const res = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg),
  });
  const data = await res.json();
  if (!res.ok) { showError(data.error || "Failed to start run."); return; }

  openStream();
  if (!dryRun) { applyState("running"); startStatusPolling(); }
}

async function stopRun() { await fetch("/api/stop", { method: "POST" }); }

// ---------------------------------------------------------------- stream
function openStream() {
  if (evtSource) evtSource.close();
  evtSource = new EventSource("/api/stream");
  evtSource.onmessage = (e) => { let evt; try { evt = JSON.parse(e.data); } catch (_) { return; } handleEvent(evt); };
  evtSource.onerror = () => {};
}

function handleEvent(evt) {
  switch (evt.type) {
    case "log": appendLog(evt.line, evt.t); break;
    case "progress": onProgress(evt); break;
    case "cases": renderCases(evt.cases); break;
    case "case": updateCaseRow(evt.case); break;
    case "plan": break;
    case "state": applyState(evt.state); if (evt.error) showError(evt.error); break;
    case "end":
      applyState(evt.state);
      if (evtSource) { evtSource.close(); evtSource = null; }
      stopStatusPolling(); refreshStatusOnce(); break;
  }
}

function onProgress(p) {
  const pct = Math.round((p.fraction || 0) * 100);
  if (p.total !== undefined) {           // suite progress
    setProgress(pct, `${p.done}/${p.total} test cases` + (p.label ? ` · ${p.label}` : ""));
  } else {                               // lesson-range progress
    const lesson = (p.lesson === null || p.lesson === undefined) ? "—" : p.lesson;
    setProgress(pct, `User ${p.user_index}/${p.user_total} (${p.username}) · lesson ${lesson} · ${p.lessons_done}/${p.lessons_total} lessons`);
  }
}

function setProgress(pct, text) { $("progress-bar").style.width = pct + "%"; if (text) $("progress-text").textContent = text; }

// ---------------------------------------------------------------- status / results
function startStatusPolling() { stopStatusPolling(); statusTimer = setInterval(refreshStatusOnce, 1500); }
function stopStatusPolling() { if (statusTimer) { clearInterval(statusTimer); statusTimer = null; } }
async function refreshStatusOnce() {
  try {
    const snap = await (await fetch("/api/status")).json();
    renderFromSnapshot(snap);
    if (snap.report_html || snap.report_txt) showReports();
    if (["done", "error", "stopped"].includes(snap.state)) { applyState(snap.state); stopStatusPolling(); }
  } catch (e) {}
}

function renderFromSnapshot(snap) {
  if (snap.cases && snap.cases.length) renderCases(snap.cases);
  else renderResults(snap.results);
}

function renderCases(cases) {
  const el = $("results");
  if (!cases || !cases.length) { el.innerHTML = ""; return; }
  const rows = cases.map((c) => caseRow(c)).join("");
  el.innerHTML = `<table>
    <thead><tr><th>TC ID</th><th>Test Case</th><th>User</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}
function caseRow(c) {
  const err = c.error ? `<details><summary>error</summary><pre>${escapeHtml(c.error)}</pre></details>` : "";
  return `<tr data-tc="${escapeAttr(c.tc_id)}">
    <td>${escapeHtml(c.tc_id || "")}</td><td>${escapeHtml(c.tc_name || "")}</td>
    <td>${escapeHtml(c.username || "")}</td>
    <td class="st-${escapeHtml(c.status || "")}">${escapeHtml(c.status || "")}</td>
    <td>${escapeHtml(c.duration || "")}</td><td>${err}</td></tr>`;
}
function updateCaseRow(c) {
  if (!c) return;
  const tr = document.querySelector(`#results tr[data-tc="${CSS.escape(c.tc_id)}"]`);
  if (tr) tr.outerHTML = caseRow(c); else refreshStatusOnce();
}

function renderResults(groups) {
  const el = $("results");
  if (!groups || !groups.length) { el.innerHTML = ""; return; }
  el.innerHTML = "";
  groups.forEach((g) => {
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "group-title";
    title.textContent = `${g.username} · class ${g.class_id} · lessons ${g.lesson_from}-${g.lesson_to}`;
    wrap.appendChild(title);
    const rows = (g.entries || []).map((e) => {
      const err = e.error ? `<details><summary>error</summary><pre>${escapeHtml(e.error)}</pre></details>` : "";
      return `<tr><td>${escapeHtml(e.activity || "")}</td>
        <td class="st-${escapeHtml(e.status || "")}">${escapeHtml(e.status || "")}</td>
        <td>${escapeHtml(e.duration || "")}</td><td>${err}</td></tr>`;
    }).join("");
    wrap.innerHTML += `<table>
      <thead><tr><th>Activity</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="muted">No activities yet…</td></tr>'}</tbody></table>`;
    el.appendChild(wrap);
  });
}

function showReports() {
  $("reports").classList.remove("hidden");
  $("link-html").href = "/api/report.html?t=" + Date.now();
  $("link-txt").href = "/api/report.txt?t=" + Date.now();
}

// ---------------------------------------------------------------- ui state
function applyState(state) {
  const badge = $("state-badge");
  badge.className = "badge " + state; badge.textContent = state;
  const running = state === "running";
  $("btn-run").disabled = running; $("btn-dry").disabled = running; $("btn-stop").disabled = !running;
}

function appendLog(line, ts) {
  const log = $("log");
  const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  const span = document.createElement("span");
  let cls = "";
  if (/\[(ERROR|FATAL|FAIL)\]|\bERROR\b/.test(line)) cls = "l-error";
  else if (/\[WARN|\[STOP|\bWARN\b/.test(line)) cls = "l-warn";
  else if (/\[(PASS|REPORT|INFO)\]|\bPASSED\b|Connected|complete/.test(line)) cls = "l-ok";
  span.className = cls;
  span.textContent = (ts ? `[${ts}] ` : "") + line + "\n";
  log.appendChild(span);
  while (log.childNodes.length > 700) log.removeChild(log.firstChild);
  if (atBottom) log.scrollTop = log.scrollHeight;
}

function showError(msg) { const e = $("error"); e.textContent = msg; e.classList.remove("hidden"); }
function hideError() { $("error").classList.add("hidden"); }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

// ---------------------------------------------------------------- Rally sync
function initRallyCard() {
  const rally = CONFIG.rally || {};
  // Always show the card + the Sync button. Connection state is reflected by
  // the dot colour and messaging — never by hiding the button (that was too
  // fragile and left users staring at an empty card).
  $("rally-card").classList.remove("hidden");
  $("rally-controls").classList.remove("hidden");

  if (rally.has_config) {
    $("rally-dot").classList.add("ok");
    $("rally-empty").classList.add("hidden");
    renderLastSync(rally.last_sync);
    loadRallyProjects();   // lazily fill the dropdown from Rally
  } else {
    $("rally-dot").classList.remove("ok");
    $("rally-last").textContent = "Not connected";
    $("rally-empty").classList.remove("hidden");
  }
}

function renderLastSync(info) {
  const el = $("rally-last");
  if (!info || !info.synced_at) { el.textContent = "Never synced"; return; }
  const when = formatRelativeTime(info.synced_at);
  const n = info.total_cases;
  el.textContent = `Last synced ${when}` + (n != null ? ` · ${n} case${n === 1 ? "" : "s"}` : "");
}

async function loadRallyProjects() {
  let data;
  try { data = await (await fetch("/api/rally/projects")).json(); } catch (e) { return; }
  if (!data || !data.configured || !Array.isArray(data.projects)) return;

  const sel = $("rally-project");
  const autoName = (data.projects.find((p) => p.id === data.auto_detected) || {}).name;
  sel.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "";
  auto.textContent = "⚡ Auto-detect" + (autoName ? ` (${autoName})` : "");
  sel.appendChild(auto);
  data.projects.forEach((p) => {
    const o = document.createElement("option");
    o.value = p.id; o.textContent = p.name;
    sel.appendChild(o);
  });

  // Restore remembered choice (only if it still exists).
  let saved = null;
  try { saved = localStorage.getItem(LS_RALLY_PROJECT); } catch (e) {}
  if (saved && data.projects.some((p) => p.id === saved)) sel.value = saved;
}

function toggleProjectPicker() {
  $("rally-project-row").classList.toggle("hidden");
}

async function testRally() {
  const statusEl = $("rally-status");
  const btn = $("btn-rally-test");
  statusEl.textContent = "Testing…";
  statusEl.className = "rally-status syncing";
  btn.disabled = true;
  try {
    const r = await (await fetch("/api/rally/test", { method: "POST" })).json();
    statusEl.textContent = (r.ok ? "✓ " : "✕ ") + r.message;
    statusEl.className = "rally-status " + (r.ok ? "success" : "error");
    $("rally-dot").classList.toggle("ok", !!r.ok);
  } catch (err) {
    statusEl.textContent = "✕ " + err.message;
    statusEl.className = "rally-status error";
  } finally {
    btn.disabled = false;
  }
}

async function syncRally() {
  const statusEl = $("rally-status");
  const syncBtn = $("btn-sync-rally");
  const projectId = $("rally-project") ? $("rally-project").value : "";

  statusEl.textContent = "Syncing…";
  statusEl.className = "rally-status syncing";
  syncBtn.disabled = true;

  try {
    const response = await fetch("/api/rally/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId }),
    });

    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Sync failed");

    statusEl.textContent = "✓ " + (result.message || "Synced");
    statusEl.className = "rally-status success";

    if (result.suite) { SUITE = result.suite; renderSuiteTree(); }
    // Surface the freshly imported tree: switch to the Test Folder view.
    if ($("run_type").value === "lesson_range") {
      $("run_type").value = "test_folder";
      onRunTypeChange();
      saveCfg();
    }
    if (result.synced_at) {
      renderLastSync({ synced_at: result.synced_at, total_cases: result.count });
    }
    hideError();

    setTimeout(() => {
      statusEl.textContent = "";
      statusEl.className = "rally-status";
      syncBtn.disabled = false;
    }, 4000);

  } catch (err) {
    statusEl.textContent = "✕ " + err.message;
    statusEl.className = "rally-status error";
    syncBtn.disabled = false;
  }
}

function formatRelativeTime(iso) {
  const then = Date.parse(iso);
  if (isNaN(then)) return "recently";
  const secs = Math.round((Date.now() - then) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? "" : "s"} ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(then).toLocaleDateString();
}

init().catch((err) => console.error("Init error:", err));
