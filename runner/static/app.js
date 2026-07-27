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
  rtEl.addEventListener("change", () => { onRunTypeChange(); saveCfg(); renderRunTypeSeg(); });
  renderRunTypeSeg();

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
  const liveBtn = $("btn-live-skeleton");
  if (liveBtn) liveBtn.addEventListener("click", generateFromLiveApp);

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
  const clearRunsBtn = $("btn-clear-runs");
  if (clearRunsBtn) clearRunsBtn.addEventListener("click", clearRuns);

  // Tabs (Results / Last runs)
  $("tab-results").addEventListener("click", () => showPane("results"));
  $("tab-runs").addEventListener("click", () => showPane("runs"));

  // Live-log level filters + follow toggle
  document.querySelectorAll(".fchip[data-f]").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".fchip[data-f]").forEach((c) => c.classList.remove("on"));
      chip.classList.add("on");
      const log = $("log");
      log.classList.toggle("f-warn", chip.dataset.f === "warn");
      log.classList.toggle("f-err", chip.dataset.f === "err");
    });
  });
  $("chip-follow").addEventListener("click", () => {
    FOLLOW = !FOLLOW;
    $("chip-follow").classList.toggle("on", FOLLOW);
    if (FOLLOW) { const log = $("log"); log.scrollTop = log.scrollHeight; }
  });

  // Post-to-Rally modal + bulk
  $("rm-close").addEventListener("click", closeRallyPost);
  $("rm-cancel").addEventListener("click", closeRallyPost);
  $("rm-post").addEventListener("click", submitRallyPost);
  $("rally-modal").addEventListener("click", (e) => { if (e.target.id === "rally-modal") closeRallyPost(); });
  const postAllBtn = $("btn-post-all");
  if (postAllBtn) postAllBtn.addEventListener("click", postAllToRally);
  // Delegated: "→ Rally" buttons survive single-row re-renders
  $("results").addEventListener("click", (e) => {
    const b = e.target.closest(".post-rally");
    if (!b) return;
    const c = (LAST_CASES || []).find((x) => x.tc_id === b.dataset.tc);
    if (c) openRallyPost(c);
  });

  pollAltTester();
  setInterval(pollAltTester, 20000);

  const snap = await (await fetch("/api/status")).json();
  applyState(snap.state);
  if (snap.state === "running") openStream();
  renderFromSnapshot(snap);
  if (snap.report_html || snap.report_txt) showReports();
  loadRuns();
}

let FOLLOW = true;

function renderRunTypeSeg() {
  const seg = $("run-type-seg");
  if (!seg || !CONFIG) return;
  seg.innerHTML = "";
  (CONFIG.run_types || []).forEach((r) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = r.label;
    b.classList.toggle("on", $("run_type").value === r.key);
    b.addEventListener("click", () => {
      const rt = $("run_type");
      if (rt.value === r.key) return;
      rt.value = r.key;
      rt.dispatchEvent(new Event("change"));   // reuses the existing handler
    });
    seg.appendChild(b);
  });
}

async function pollAltTester() {
  const dot = $("alt-dot"), label = $("alt-conn-label");
  if (!dot) return;
  const host = $("host").value || "127.0.0.1";
  const port = $("port").value || "13000";
  label.textContent = `AltTester ${host}:${port}`;
  try {
    const r = await (await fetch(`/api/preflight?host=${encodeURIComponent(host)}&port=${encodeURIComponent(port)}`)).json();
    dot.className = "dot " + (r.ok ? "on" : "off");
    $("alt-conn").title = r.ok ? "AltTester server reachable" : "AltTester server NOT reachable — start the app";
  } catch (e) {
    dot.className = "dot";
  }
}

function showPane(which) {
  $("pane-results").classList.toggle("hidden", which !== "results");
  $("pane-runs").classList.toggle("hidden", which !== "runs");
  $("tab-results").classList.toggle("on", which === "results");
  $("tab-runs").classList.toggle("on", which === "runs");
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
  updateSelCount();
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

// Implementation-status badge for a test case: real / stub / unlinked.
// Makes it obvious which cases actually test something vs. auto-generated
// stubs (which skip) vs. cases with no pytest linked yet.
function implBadge(impl) {
  const map = {
    real:     { cls: "impl-real",     txt: "generated ✓",   title: "Test generated in the framework — runs against the app" },
    stub:     { cls: "impl-stub",     txt: "not generated", title: "Only an auto-stub exists (skips). Select the case and click “Generate from live app”, or add the missing data in Rally and re-sync." },
    unlinked: { cls: "impl-unlinked", txt: "no test",       title: "No pytest test linked — runs as SKIPPED" },
  };
  const b = map[impl] || map.unlinked;
  return `<span class="impl-badge ${b.cls}" title="${b.title}">${b.txt}</span>`;
}

async function generateCase(c, btn) {
  const msg = $("skeleton-msg");
  btn.disabled = true; btn.textContent = "generating…";
  try {
    const res = await fetch(`/api/suite/case/${encodeURIComponent(c.id)}/generate`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) { msg.textContent = data.error || "Generation failed."; return; }
    msg.textContent = data.message || `${c.id}: generated.`;
    if (data.suite) setSuite(data.suite);
  } catch (e) {
    msg.textContent = "Generation failed: " + e;
  } finally {
    btn.disabled = false; btn.textContent = "generate";
  }
}

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
    row.style.paddingLeft = (depth * 18 + 6) + "px";
    row.innerHTML = `
      <span class="twisty"></span>
      <input type="checkbox" class="sel-c" value="${escapeAttr(c.id)}" ${SEL_CASES.has(c.id) ? "checked" : ""}>
      <span class="idchip">${escapeHtml(c.id)}</span>
      <span class="nm" title="${escapeAttr(c.name)}">${escapeHtml(c.name)}</span>
      ${implBadge(c.impl)}
      <span class="row-actions">
        ${c.impl === "real" ? "" :
          `<button type="button" class="link c-gen" title="Write this case's test code into the project">generate</button>`}
        ${c.impl === "unlinked" ? "" :
          `<button type="button" class="link c-impl">${c.impl === "stub" ? "make real" : "make stub"}</button>`}
        <button type="button" class="link c-edit">edit</button>
        <button type="button" class="link danger c-del">delete</button>
      </span>`;
    row.querySelector(".sel-c").addEventListener("change", (e) => {
      e.target.checked ? SEL_CASES.add(c.id) : SEL_CASES.delete(c.id); saveCfg(); updateSelCount();
    });
    // Full test-case name: shown on hover via title, and click toggles the
    // row into wrapped (multi-line) mode for long names.
    row.querySelector(".nm").addEventListener("click", () => row.classList.toggle("nm-open"));
    const genBtn = row.querySelector(".c-gen");
    if (genBtn) genBtn.addEventListener("click", () => generateCase(c, genBtn));
    const implBtn = row.querySelector(".c-impl");
    if (implBtn) implBtn.addEventListener("click", () => toggleImpl(c));
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
    row.style.paddingLeft = (depth * 18 + 6) + "px";
    row.innerHTML = `
      <span class="twisty">${hasChildren ? (expanded ? "▾" : "▸") : ""}</span>
      <input type="checkbox" class="sel-f" value="${escapeAttr(f.id)}" ${SEL_FOLDERS.has(f.id) ? "checked" : ""}>
      <span class="idchip">${escapeHtml(f.id)}</span>
      <span class="nm" title="${escapeAttr(f.name)}">${escapeHtml(f.name)}</span>
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
      e.target.checked ? SEL_FOLDERS.add(f.id) : SEL_FOLDERS.delete(f.id); saveCfg(); updateSelCount();
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
  updateSelCount();
}

function updateSelCount() {
  const el = $("sel-count");
  if (!el) return;
  const rt = currentRunType();
  const n = rt === "test_folder" ? SEL_FOLDERS.size : SEL_CASES.size;
  el.textContent = n ? `${n} selected` : "";
  const runBtn = $("btn-run");
  if (runBtn && (rt === "test_folder" || rt === "test_case")) {
    runBtn.textContent = n ? `▶ Run ${n} selected` : "▶ Run";
  } else if (runBtn) {
    runBtn.textContent = "▶ Run";
  }
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

function setSkeletonMsg(text, isErr) {
  const el = $("skeleton-msg");
  if (!el) return;
  el.textContent = text || "";
  el.style.color = isErr ? "#b91c1c" : "#475569";
}

// Manually flip a case between 'real' and 'stub' (edits the test file's markers,
// locks MANUAL_EDIT=True so a re-sync keeps the choice).
async function toggleImpl(c) {
  const target = c.impl === "stub" ? "real" : "stub";
  if (target === "real" && !confirm(
    `Mark ${c.id} as REAL? It will run instead of skipping. If it isn't implemented yet it may pass without testing anything.`)) return;
  try {
    const res = await fetch("/api/suite/case/impl", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: c.id, impl: target }),
    });
    const data = await res.json();
    if (!res.ok) { setSkeletonMsg(data.error || "Could not change status.", true); return; }
    if (data.suite) { SUITE = data.suite; renderSuiteTree(); }
    setSkeletonMsg(`${c.id} → ${data.impl}` + (data.warning ? " · " + data.warning : ""), !!data.warning);
  } catch (e) {
    setSkeletonMsg("Request failed: " + e.message, true);
  }
}

// #4 — discover elements on the LIVE app and turn selected stub cases into real
// skeletons. Needs the game + AltTester running (uses the Connection settings).
async function generateFromLiveApp() {
  const ids = [...SEL_CASES];
  if (!ids.length) {
    setSkeletonMsg("Tick at least one test case (checkbox) first — this reads the running app's current scene.", true);
    return;
  }
  const cfg = gatherConfig(false);
  const btn = $("btn-live-skeleton");
  btn.disabled = true;
  setSkeletonMsg(`Connecting to ${cfg.host}:${cfg.port} and discovering elements…`, false);
  try {
    const res = await fetch("/api/suite/skeleton", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        test_cases: ids, host: cfg.host, port: cfg.port, platform: cfg.platform,
        app_id: cfg.app_id, device_instance_id: cfg.device_instance_id,
      }),
    });
    const data = await res.json();
    if (!res.ok) { setSkeletonMsg(data.error || "Generation failed.", true); return; }
    if (data.suite) { SUITE = data.suite; renderSuiteTree(); }
    const failed = (data.results || []).filter((r) => !r.ok);
    let msg = data.message || "Done.";
    if (failed.length) msg += " · Failed: " + failed.map((r) => `${r.id} (${r.error})`).join(", ");
    setSkeletonMsg(msg, failed.length > 0);
  } catch (e) {
    setSkeletonMsg("Request failed: " + e.message, true);
  } finally {
    btn.disabled = false;
  }
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
  updateFailFlag([]);
  showPane("results");
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
      stopStatusPolling(); refreshStatusOnce(); loadRuns(); break;
  }
}

// ---------------------------------------------------------------- last runs
async function loadRuns() {
  const el = $("runs");
  if (!el) return;
  let runs = [];
  try { runs = (await (await fetch("/api/runs")).json()).runs || []; } catch (_) { return; }
  const cnt = $("runs-count");
  if (cnt) cnt.textContent = runs.length ? `· ${runs.length}` : "";
  if (!runs.length) {
    el.innerHTML = '<span class="muted" style="padding:12px;display:block">No runs recorded yet.</span>';
    return;
  }
  const stateCls = (s) => s === "done" ? "l-ok" : (s === "error" ? "l-error" : "l-warn");
  const rows = runs.map((r) => {
    const t = r.totals || {};
    const counts = ["PASSED", "FAILED", "SKIPPED", "CANCELLED"]
      .filter((k) => t[k]) .map((k) => `${t[k]} ${k.toLowerCase()}`).join(" · ");
    const links = [
      r.report_html ? `<a href="/api/runs/${escapeAttr(r.id)}/report.html" target="_blank">html</a>` : "",
      r.report_txt ? `<a href="/api/runs/${escapeAttr(r.id)}/report.txt">txt</a>` : "",
    ].filter(Boolean).join(" ");
    return `<tr>
      <td>${escapeHtml(r.finished_at || r.id)}</td>
      <td>${escapeHtml(r.kind || "")}</td>
      <td class="${stateCls(r.state)}">${escapeHtml(r.state || "")}</td>
      <td>${escapeHtml(counts || "—")}</td>
      <td>${links || '<span class="muted">no report</span>'}</td>
    </tr>`;
  }).join("");
  el.innerHTML = `<table>
    <thead><tr><th>Finished</th><th>Type</th><th>State</th><th>Results</th><th>Report</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

async function clearRuns() {
  if (!confirm("Clear the recorded run history? (Report files on disk are kept.)")) return;
  try { await fetch("/api/runs/clear", { method: "POST" }); } catch (_) {}
  loadRuns();
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

let LAST_CASES = [];

function renderCases(cases) {
  const el = $("results");
  updateFailFlag(cases);
  LAST_CASES = cases || [];
  const done = (cases || []).filter((c) => ["PASSED", "FAILED", "SKIPPED"].includes(c.status));
  const tb = $("results-toolbar");
  if (tb) tb.classList.toggle("hidden", done.length === 0);
  if (!cases || !cases.length) { el.innerHTML = ""; return; }
  const rows = cases.map((c) => caseRow(c)).join("");
  el.innerHTML = `<table>
    <thead><tr><th>TC ID</th><th>Test Case</th><th>User</th><th>Status</th><th>Duration</th><th>Details</th><th>Rally</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  // delegation set up once in init(); rows replaced later still work
}

function updateFailFlag(cases) {
  const flag = $("fail-flag");
  if (!flag) return;
  const n = (cases || []).filter((c) => c.status === "FAILED").length;
  flag.textContent = n ? `${n} failed` : "";
}
function caseRow(c) {
  let err = c.error ? `<details><summary>error</summary><pre>${escapeHtml(c.error)}</pre></details>` : "";
  if (c.screenshot) {
    const url = `/api/screenshots/${encodeURIComponent(c.screenshot)}`;
    err += `<details><summary>📷 screenshot (where it got stuck)</summary>
      <a href="${url}" target="_blank"><img src="${url}" style="max-width:420px"></a></details>`;
  }
  const ran = ["PASSED", "FAILED", "SKIPPED"].includes(c.status);
  const rally = ran
    ? `<button type="button" class="link post-rally" data-tc="${escapeAttr(c.tc_id)}"
         title="Create a TestCaseResult in Rally for this run">→ Rally</button>`
    : "";
  return `<tr data-tc="${escapeAttr(c.tc_id)}">
    <td>${escapeHtml(c.tc_id || "")}</td><td>${escapeHtml(c.tc_name || "")}</td>
    <td>${escapeHtml(c.username || "")}</td>
    <td class="st-${escapeHtml(c.status || "")}">${escapeHtml(c.status || "")}</td>
    <td>${escapeHtml(c.duration || "")}</td><td>${err}</td><td>${rally}</td></tr>`;
}

// -------------------------------------------------- post results to Rally
function verdictFor(status) {
  return status === "PASSED" ? "Pass" : (status === "SKIPPED" ? "Inconclusive" : "Fail");
}
function defaultBuild() {
  const p = ($("platform") && $("platform").value) || "WindowsEditor";
  const d = new Date();
  const s = d.getFullYear() + String(d.getMonth() + 1).padStart(2, "0") + String(d.getDate()).padStart(2, "0");
  return `${p}-${s}`;
}
let POST_TARGET = null;
function openRallyPost(c) {
  POST_TARGET = c;
  $("rm-tc").value = `${c.tc_id} — ${c.tc_name || ""}`;
  $("rm-verdict").value = verdictFor(c.status);
  $("rm-build").value = defaultBuild();
  const noteLines = [`Automated run: ${c.status}`];
  if (c.duration) noteLines.push(`Duration: ${c.duration}`);
  if (c.error) noteLines.push("", c.error);
  $("rm-notes").value = noteLines.join("\n");
  const shotRow = $("rm-shot-row");
  shotRow.style.display = c.screenshot ? "flex" : "none";
  $("rm-attach").checked = !!c.screenshot;
  $("rm-msg").textContent = "";
  $("rally-modal").classList.remove("hidden");
}
function closeRallyPost() { $("rally-modal").classList.add("hidden"); POST_TARGET = null; }

async function submitRallyPost() {
  if (!POST_TARGET) return;
  const btn = $("rm-post");
  btn.disabled = true; $("rm-msg").textContent = "Posting…";
  try {
    const res = await fetch("/api/rally/post-result", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tc_id: POST_TARGET.tc_id,
        verdict: $("rm-verdict").value,
        build: $("rm-build").value,
        notes: $("rm-notes").value,
        screenshot: $("rm-attach").checked ? (POST_TARGET.screenshot || "") : "",
      }),
    });
    const data = await res.json();
    if (!res.ok) { $("rm-msg").textContent = data.error || "Failed to post."; return; }
    $("rm-msg").textContent = data.message || "Posted.";
    setTimeout(closeRallyPost, 900);
  } catch (e) {
    $("rm-msg").textContent = "Failed to post: " + e;
  } finally {
    btn.disabled = false;
  }
}

async function postAllToRally() {
  const cases = (LAST_CASES || []).filter((c) => ["PASSED", "FAILED", "SKIPPED"].includes(c.status));
  if (!cases.length) return;
  const msg = $("post-all-msg");
  if (!confirm(`Post ${cases.length} result(s) to Rally?`)) return;
  let ok = 0, fail = 0;
  for (const c of cases) {
    msg.textContent = `Posting ${c.tc_id}… (${ok + fail}/${cases.length})`;
    try {
      const res = await fetch("/api/rally/post-result", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tc_id: c.tc_id, verdict: verdictFor(c.status), build: defaultBuild(),
          notes: `Automated run: ${c.status}` + (c.error ? "\n\n" + c.error : ""),
          screenshot: c.screenshot || "",
        }),
      });
      (res.ok ? ok++ : fail++);
    } catch (e) { fail++; }
  }
  msg.textContent = `Posted ${ok} result(s) to Rally` + (fail ? `, ${fail} failed` : "");
}
function updateCaseRow(c) {
  if (!c) return;
  const tr = document.querySelector(`#results tr[data-tc="${CSS.escape(c.tc_id)}"]`);
  if (tr) tr.outerHTML = caseRow(c); else refreshStatusOnce();
}

function renderResults(groups) {
  const el = $("results");
  if (!groups || !groups.length) { el.innerHTML = ""; updateFailFlagEntries(0); return; }
  el.innerHTML = "";
  let fails = 0;
  groups.forEach((g) => {
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "group-title";
    title.textContent = `${g.username} · class ${g.class_id} · lessons ${g.lesson_from}-${g.lesson_to}`;
    wrap.appendChild(title);
    const rows = (g.entries || []).map((e) => {
      if (e.status === "FAILED") fails++;
      let err = e.error ? `<details${e.status === "FAILED" ? " open" : ""}><summary>error</summary><pre>${escapeHtml(e.error)}</pre></details>` : "";
      if (e.screenshot) {
        const url = `/api/screenshots/${encodeURIComponent(e.screenshot)}`;
        err += `<details><summary>📷 screenshot (where it got stuck)</summary>
          <a href="${url}" target="_blank"><img src="${url}" style="max-width:420px"></a></details>`;
      }
      return `<tr><td>${escapeHtml(e.activity || "")}</td>
        <td class="st-${escapeHtml(e.status || "")}">${escapeHtml(e.status || "")}</td>
        <td>${escapeHtml(e.duration || "")}</td><td>${err}</td></tr>`;
    }).join("");
    wrap.innerHTML += `<table>
      <thead><tr><th>Activity</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="muted">No activities yet…</td></tr>'}</tbody></table>`;
    el.appendChild(wrap);
  });
  updateFailFlagEntries(fails);
}

function updateFailFlagEntries(n) {
  const flag = $("fail-flag");
  if (flag) flag.textContent = n ? `${n} failed` : "";
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
  if (!running) { const nl = $("now-line"); if (nl) nl.classList.add("hidden"); }
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
  if (FOLLOW || atBottom) log.scrollTop = log.scrollHeight;
  updateNowLine(line);
}

// Promote the latest meaningful event out of the log into the "Now:" line
// under the progress bar, so the current step is visible without reading
// the console.
function updateNowLine(line) {
  if (!/\[act\]|\[info\]|\[Activity\]|\[Map Navigation\]|\[Login\]|\[START\]|\[PASS\]|\[FAIL\]|progress /.test(line)) return;
  const el = $("now-line");
  if (!el) return;
  el.classList.remove("hidden");
  $("now-text").textContent = line.replace(/^\s*\[[0-9:]+\]\s*/, "").slice(0, 160);
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
