"use strict";

const $ = (id) => document.getElementById(id);
const LS_KEY = "vt_runner_cfg";
const LS_USERS = "vt_runner_custom_users";

let MODES = [];
let evtSource = null;
let statusTimer = null;

// ---------------------------------------------------------------- init
async function init() {
  const cfg = await (await fetch("/api/config")).json();
  MODES = cfg.modes;

  // Users
  const usersEl = $("users");
  usersEl.innerHTML = "";
  if (!cfg.users.length) {
    usersEl.innerHTML = '<span class="muted">No users in data/test_users.py</span>';
  }
  cfg.users.forEach((u, i) => {
    const lbl = document.createElement("label");
    lbl.innerHTML = `<input type="checkbox" value="${u.username}" ${i === 0 ? "checked" : ""}>
      ${u.username} <span class="muted">· class ${u.class_id}</span>`;
    usersEl.appendChild(lbl);
  });

  // Modes
  const modeEl = $("mode");
  modeEl.innerHTML = "";
  MODES.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.key; o.textContent = m.label;
    modeEl.appendChild(o);
  });
  modeEl.value = cfg.defaults.mode;
  modeEl.addEventListener("change", updateModeDesc);

  // Defaults
  $("lesson_from").value = cfg.defaults.lesson_from;
  $("lesson_to").value = cfg.defaults.lesson_to;
  $("platform").value = cfg.defaults.platform;
  $("host").value = cfg.defaults.host;
  $("port").value = cfg.defaults.port;

  $("btn-add-user").addEventListener("click", () => { addCustomUserRow(); saveCustomRows(); });
  $("custom-users").addEventListener("input", saveCustomRows);
  $("custom-users").addEventListener("change", saveCustomRows);
  $("custom-users").addEventListener("click", (e) => {
    if (e.target.classList && e.target.classList.contains("cu-remove")) saveCustomRows();
  });

  restoreConfig();
  restoreCustomUsers();
  updateModeDesc();

  $("btn-run").addEventListener("click", () => startRun(false));
  $("btn-dry").addEventListener("click", () => startRun(true));
  $("btn-stop").addEventListener("click", stopRun);

  // Reconnect if a run is already in progress (e.g. after a page refresh).
  const snap = await (await fetch("/api/status")).json();
  applyState(snap.state);
  if (snap.state === "running") openStream(false);
  renderResults(snap.results);
  if (snap.report_html || snap.report_txt) showReports();
}

function updateModeDesc() {
  const m = MODES.find((x) => x.key === $("mode").value);
  $("mode-desc").textContent = m ? m.description : "";
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

// All custom rows (for persistence), including their enabled state.
function getCustomRows() {
  return [...document.querySelectorAll("#custom-users .custom-user")].map((r) => ({
    enabled: r.querySelector(".cu-enabled").checked,
    username: r.querySelector(".cu-username").value.trim(),
    password: r.querySelector(".cu-password").value,
    class_id: r.querySelector(".cu-class").value.trim(),
  }));
}

// Only the checked custom rows that have a username — these actually run.
function getCustomUsersForRun() {
  return getCustomRows()
    .filter((r) => r.enabled && (r.username || r.password))
    .map((r) => ({ username: r.username, password: r.password, class_id: r.class_id }));
}

// ---------------------------------------------------------------- config
function gatherConfig(dryRun) {
  // Predefined picks are sent as plain usernames (resolved server-side);
  // custom users are sent as full objects with their password.
  const picked = [...document.querySelectorAll("#users input:checked")].map((c) => c.value);
  const custom = getCustomUsersForRun();
  const users = [...picked, ...custom];
  return {
    users,
    class_id_override: $("class_id_override").value.trim(),
    lesson_from: parseInt($("lesson_from").value, 10),
    lesson_to: parseInt($("lesson_to").value, 10),
    mode: $("mode").value,
    platform: $("platform").value.trim(),
    host: $("host").value.trim(),
    port: parseInt($("port").value, 10),
    app_id: $("app_id").value.trim(),
    device_instance_id: $("device_instance_id").value.trim(),
    dry_run: dryRun,
  };
}

function saveConfig(cfg) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(cfg)); } catch (e) {}
}

function restoreConfig() {
  let saved;
  try { saved = JSON.parse(localStorage.getItem(LS_KEY)); } catch (e) { return; }
  if (!saved) return;
  const set = (id, v) => { if (v !== undefined && v !== null && $(id)) $(id).value = v; };
  set("lesson_from", saved.lesson_from);
  set("lesson_to", saved.lesson_to);
  set("class_id_override", saved.class_id_override);
  set("platform", saved.platform);
  set("host", saved.host);
  set("port", saved.port);
  set("app_id", saved.app_id);
  set("device_instance_id", saved.device_instance_id);
  if (saved.mode && MODES.some((m) => m.key === saved.mode)) $("mode").value = saved.mode;
  if (Array.isArray(saved.users)) {
    const names = saved.users.filter((u) => typeof u === "string");
    document.querySelectorAll("#users input").forEach((c) => { c.checked = names.includes(c.value); });
  }
}

function saveCustomRows() {
  try { localStorage.setItem(LS_USERS, JSON.stringify(getCustomRows())); } catch (e) {}
}

function restoreCustomUsers() {
  let rows;
  try { rows = JSON.parse(localStorage.getItem(LS_USERS)); } catch (e) {}
  $("custom-users").innerHTML = "";
  if (Array.isArray(rows) && rows.length) {
    rows.forEach((r) => addCustomUserRow(r));
  } else {
    addCustomUserRow(); // start with one empty row for convenience
  }
}

// ---------------------------------------------------------------- run
async function startRun(dryRun) {
  hideError();
  const cfg = gatherConfig(dryRun);
  saveConfig(cfg);

  if (evtSource) { evtSource.close(); evtSource = null; }
  $("log").innerHTML = "";
  $("results").innerHTML = "";
  $("reports").classList.add("hidden");
  setProgress(0, "Starting…");

  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  const data = await res.json();
  if (!res.ok) { showError(data.error || "Failed to start run."); return; }

  openStream(true);
  if (!dryRun) {
    applyState("running");
    startStatusPolling();
  }
}

async function stopRun() {
  await fetch("/api/stop", { method: "POST" });
}

// ---------------------------------------------------------------- stream
function openStream(clear) {
  if (evtSource) evtSource.close();
  evtSource = new EventSource("/api/stream");
  evtSource.onmessage = (e) => {
    let evt;
    try { evt = JSON.parse(e.data); } catch (_) { return; }
    handleEvent(evt);
  };
  evtSource.onerror = () => { /* browser auto-retries unless we close on 'end' */ };
}

function handleEvent(evt) {
  switch (evt.type) {
    case "log": appendLog(evt.line, evt.t); break;
    case "progress": onProgress(evt); break;
    case "plan":
      appendLog(`Plan: ${evt.steps.length} step(s)` + (evt.dry_run ? " (dry-run)" : ""));
      break;
    case "state": applyState(evt.state); if (evt.error) showError(evt.error); break;
    case "end":
      applyState(evt.state);
      if (evtSource) { evtSource.close(); evtSource = null; }
      stopStatusPolling();
      refreshStatusOnce();
      break;
  }
}

function onProgress(p) {
  const pct = Math.round((p.fraction || 0) * 100);
  const lesson = (p.lesson === null || p.lesson === undefined) ? "—" : p.lesson;
  setProgress(pct,
    `User ${p.user_index}/${p.user_total} (${p.username}) · lesson ${lesson} · ` +
    `${p.lessons_done}/${p.lessons_total} lessons`);
}

function setProgress(pct, text) {
  $("progress-bar").style.width = pct + "%";
  if (text) $("progress-text").textContent = text;
}

// ---------------------------------------------------------------- status / results
function startStatusPolling() {
  stopStatusPolling();
  statusTimer = setInterval(refreshStatusOnce, 1500);
}
function stopStatusPolling() {
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
}
async function refreshStatusOnce() {
  try {
    const snap = await (await fetch("/api/status")).json();
    renderResults(snap.results);
    if (snap.report_html || snap.report_txt) showReports();
    if (["done", "error", "stopped"].includes(snap.state)) {
      applyState(snap.state);
      stopStatusPolling();
    }
  } catch (e) {}
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
      return `<tr>
        <td>${escapeHtml(e.activity || "")}</td>
        <td class="st-${escapeHtml(e.status || "")}">${escapeHtml(e.status || "")}</td>
        <td>${escapeHtml(e.duration || "")}</td>
        <td>${err}</td></tr>`;
    }).join("");

    wrap.innerHTML += `<table>
      <thead><tr><th>Activity</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="muted">No activities yet…</td></tr>'}</tbody></table>`;
    el.appendChild(wrap);
  });
}

function showReports() {
  $("reports").classList.remove("hidden");
  // cache-bust so links always point at the latest run's report
  $("link-html").href = "/api/report.html?t=" + Date.now();
  $("link-txt").href = "/api/report.txt?t=" + Date.now();
}

// ---------------------------------------------------------------- ui state
function applyState(state) {
  const badge = $("state-badge");
  badge.className = "badge " + state;
  badge.textContent = state;
  const running = state === "running";
  $("btn-run").disabled = running;
  $("btn-dry").disabled = running;
  $("btn-stop").disabled = !running;
}

function appendLog(line, ts) {
  const log = $("log");
  const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  const span = document.createElement("span");
  let cls = "";
  if (/\b(ERROR|FATAL|FAIL)\b/.test(line)) cls = "l-error";
  else if (/\bWARN\b/.test(line)) cls = "l-warn";
  else if (/\b(PASSED|Connected|complete|REPORT)\b/.test(line)) cls = "l-ok";
  span.className = cls;
  span.textContent = (ts ? `[${ts}] ` : "") + line + "\n";
  log.appendChild(span);
  // Keep the DOM bounded so long runs don't make the page sluggish.
  while (log.childNodes.length > 600) log.removeChild(log.firstChild);
  if (atBottom) log.scrollTop = log.scrollHeight;
}

function showError(msg) { const e = $("error"); e.textContent = msg; e.classList.remove("hidden"); }
function hideError() { $("error").classList.add("hidden"); }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

init();
