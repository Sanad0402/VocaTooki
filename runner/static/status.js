/* Release status rendering — shared by the panel tab and the public /status
   page, so the two can never drift apart. The panel passes editable=true and
   gets the scope editor and the per-case verdict controls; the shared page is
   read-only.

   Form: progress toward 100% per platform. That is a magnitude question, so it
   is a bar per platform, not a donut — a bar reads exactly against a 100% end
   and stacks the four states in place.

   Colour: the four states are a STATUS palette (passed / failed / blocked /
   not run), never reused for anything else. The steps were run through the
   palette validator; the dark set sits in the 6-8 CVD floor band, which is only
   legal with secondary encoding, so every segment carries a direct label and a
   2px gap, a legend is always present, and the tables below repeat the same
   numbers without colour. */

const RS_STATES = [
  { key: "passed",  label: "Passed"  },
  { key: "failed",  label: "Failed"  },
  { key: "blocked", label: "Blocked" },
  { key: "not_run", label: "Not run" },
];

const RS_PLATFORM_LABEL = { ios: "iOS", android: "Android", web: "Web" };
const RS_VERDICT_LABEL = { passed: "Passed", failed: "Failed", blocked: "Blocked", "": "Not run" };

function rsEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function rsPlatformCard(platform, t) {
  const segs = RS_STATES.map((s) => ({ ...s, n: t[s.key] || 0 })).filter((s) => s.n > 0);
  const total = Math.max(1, t.total || 0);
  const bar = segs.map((s) => {
    const pct = (100 * s.n) / total;
    // Direct label only where the segment is wide enough to hold one.
    const label = pct >= 9 ? `<span class="rs-seg-n">${s.n}</span>` : "";
    return `<div class="rs-seg rs-${s.key}" style="width:${pct}%"
                 title="${rsEsc(s.label)}: ${s.n} of ${t.total}">${label}</div>`;
  }).join("");
  return `
    <section class="rs-card">
      <header class="rs-card-head">
        <h3>${rsEsc(RS_PLATFORM_LABEL[platform] || platform)}</h3>
        <p class="rs-hero"><strong>${t.percent || 0}%</strong><span>tested</span></p>
      </header>
      <div class="rs-bar" role="img"
           aria-label="${rsEsc(RS_PLATFORM_LABEL[platform] || platform)}: ${t.passed} passed, ${t.failed} failed, ${t.blocked} blocked, ${t.not_run} not run of ${t.total}">
        ${bar || '<div class="rs-seg rs-not_run" style="width:100%"></div>'}
      </div>
      <p class="rs-sub">${t.tested || 0}/${t.total || 0} tested · ${t.passed || 0} passed · ${t.failed || 0} failed${t.blocked ? ` · ${t.blocked} blocked` : ""}</p>
    </section>`;
}

function rsLegend() {
  return `<ul class="rs-legend">` + RS_STATES.map((s) =>
    `<li><span class="rs-key rs-${s.key}"></span>${s.label}</li>`).join("") + `</ul>`;
}

/* What counts toward the percentage, and how to change it. */
function rsScope(data, editable) {
  const chips = [];
  (data.scope.folders || []).forEach((fid) => {
    const row = (data.folders || []).find((f) => f.id === fid) || {};
    const missing = row.in_suite === false;
    chips.push(`<span class="rs-chip${missing ? " rs-chip-missing" : ""}">
        ${rsEsc(row.name || fid)} <span class="rs-fid">${rsEsc(fid)}</span>
        <span class="rs-chip-n">${missing ? "not synced" : (row.total || 0) + " cases"}</span>
        ${editable ? `<button type="button" class="rs-x" data-kind="folder" data-id="${rsEsc(fid)}" title="Remove from scope">×</button>` : ""}
      </span>`);
  });
  (data.scope.cases || []).forEach((cid) => {
    chips.push(`<span class="rs-chip">${rsEsc(cid)}
        ${editable ? `<button type="button" class="rs-x" data-kind="case" data-id="${rsEsc(cid)}" title="Remove from scope">×</button>` : ""}
      </span>`);
  });

  const picker = editable ? `
      <div class="rs-add">
        <select id="rs-add-folder">
          <option value="">Add a test folder…</option>
          ${(data.available_folders || []).map((f) =>
            `<option value="${rsEsc(f.id)}">${rsEsc(f.id)} — ${rsEsc(f.name)}${f.cases ? ` (${f.cases})` : ""}</option>`).join("")}
        </select>
        <select id="rs-add-case">
          <option value="">Add a single test case…</option>
          ${(data.available_cases || []).map((c) =>
            `<option value="${rsEsc(c.id)}">${rsEsc(c.id)} — ${rsEsc(c.name)}</option>`).join("")}
        </select>
        <input id="rs-add-other" placeholder="or type an id (e.g. TF295)" size="18">
        <button type="button" class="small" id="rs-add-btn">Add to scope</button>
      </div>` : "";

  return `<div class="rs-scope">
      <h3 class="rs-th">Regression scope</h3>
      <div class="rs-chips">${chips.join("") ||
        '<span class="muted">Nothing chosen — showing the whole suite.</span>'}</div>
      ${picker}
    </div>`;
}

/* Case-level table: every case the percentage counts, and its state per
   platform. This is also the table view that keeps identity off colour alone. */
function rsCases(data, editable) {
  const plats = data.platforms || [];
  const head = plats.map((p) => `<th>${rsEsc(RS_PLATFORM_LABEL[p] || p)}</th>`).join("");
  const rows = (data.cases_detail || []).map((c) => {
    const cells = plats.map((p) => {
      const st = c.platforms[p] || {};
      const v = st.verdict || "";
      if (!editable) {
        return `<td><span class="rs-pill rs-${v || "not_run"}">${RS_VERDICT_LABEL[v]}</span></td>`;
      }
      const opts = ["", "passed", "failed", "blocked"].map((o) =>
        `<option value="${o}"${o === v ? " selected" : ""}>${RS_VERDICT_LABEL[o]}</option>`).join("");
      const src = st.source === "run" ? ' title="recorded by an automated run"' : "";
      return `<td><select class="rs-set rs-${v || "not_run"}" data-case="${rsEsc(c.id)}"
                   data-platform="${p}"${src}>${opts}</select></td>`;
    }).join("");
    return `<tr>
        <th scope="row"><span class="rs-tc">${rsEsc(c.id)}</span> ${rsEsc(c.name)}
          <span class="rs-fid">${rsEsc(c.folder_name || "")}</span></th>${cells}
      </tr>`;
  }).join("");
  return `<h3 class="rs-th">Test cases in scope (${(data.cases_detail || []).length})</h3>
    <table class="rs-table rs-cases">
      <thead><tr><th scope="col">Test case</th>${head}</tr></thead>
      <tbody>${rows || `<tr><td colspan="${plats.length + 1}" class="rs-empty">No cases in scope yet — add a folder or a case above. TF295 appears here once it holds cases and you re-sync from Rally.</td></tr>`}</tbody>
    </table>`;
}

function renderReleaseStatus(el, data, editable) {
  if (!el) return;
  const plats = data.platforms || [];
  const title = data.release ? `Release ${rsEsc(data.release)}` : "Release status";
  el.innerHTML = `
    <div class="rs-head">
      <h2>${title}</h2>
      <p class="rs-meta">${data.total_cases} case(s) in scope · runner is testing
        <strong>${rsEsc(RS_PLATFORM_LABEL[data.platform] || data.platform)}</strong></p>
    </div>
    ${rsLegend()}
    <div class="rs-cards">${plats.map((p) => rsPlatformCard(p, data.overall[p] || {})).join("")}</div>
    ${rsScope(data, editable)}
    ${rsCases(data, editable)}`;
}

if (typeof window !== "undefined") window.renderReleaseStatus = renderReleaseStatus;
