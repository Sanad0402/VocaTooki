/* Release status rendering — shared by the panel tab and the public /status page,
   so the two can never drift apart.

   Form: progress toward 100% per platform. That is a magnitude question, so it
   is a bar per platform, not a donut — a bar reads exactly against a 100% end
   and stacks the four states in place.

   Colour: the four states are a STATUS palette (passed / failed / blocked /
   not run), never reused for anything else. The steps were run through the
   palette validator; the dark set sits in the 6-8 CVD floor band, which is only
   legal with secondary encoding, so every segment carries a direct label, a 2px
   gap and a legend, and the folder table below is the table view. Colour is
   never the only signal. */

const RS_STATES = [
  { key: "passed",  label: "Passed"  },
  { key: "failed",  label: "Failed"  },
  { key: "blocked", label: "Blocked" },
  { key: "not_run", label: "Not run" },
];

const RS_PLATFORM_LABEL = { ios: "iOS", android: "Android", web: "Web" };

function rsEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

/* One platform: a headline number, then the stacked bar it summarises. */
function rsPlatformCard(platform, t) {
  const segs = RS_STATES
    .map((s) => ({ ...s, n: t[s.key] || 0 }))
    .filter((s) => s.n > 0);
  const total = Math.max(1, t.total || 0);

  const bar = segs.map((s) => {
    const pct = (100 * s.n) / total;
    // Direct label inside the segment when it is wide enough to hold one —
    // never a number on every segment regardless of room.
    const label = pct >= 9 ? `<span class="rs-seg-n">${s.n}</span>` : "";
    return `<div class="rs-seg rs-${s.key}" style="width:${pct}%"
                 title="${rsEsc(s.label)}: ${s.n} of ${t.total}">${label}</div>`;
  }).join("");

  return `
    <section class="rs-card">
      <header class="rs-card-head">
        <h3>${rsEsc(RS_PLATFORM_LABEL[platform] || platform)}</h3>
        <p class="rs-hero"><strong>${t.percent}%</strong><span>tested</span></p>
      </header>
      <div class="rs-bar" role="img"
           aria-label="${rsEsc(RS_PLATFORM_LABEL[platform] || platform)}: ${t.passed} passed, ${t.failed} failed, ${t.blocked} blocked, ${t.not_run} not run of ${t.total}">
        ${bar || '<div class="rs-seg rs-not_run" style="width:100%"></div>'}
      </div>
      <p class="rs-sub">${t.tested}/${t.total} cases tested · ${t.passed} passed · ${t.failed} failed${t.blocked ? ` · ${t.blocked} blocked` : ""}</p>
    </section>`;
}

function rsLegend() {
  return `<ul class="rs-legend">` + RS_STATES.map((s) =>
    `<li><span class="rs-key rs-${s.key}"></span>${s.label}</li>`).join("") + `</ul>`;
}

/* The table view: identity never rests on colour alone. */
function rsTable(data) {
  const plats = data.platforms || [];
  const head = plats.map((p) => `<th>${rsEsc(RS_PLATFORM_LABEL[p] || p)}</th>`).join("");
  const rows = (data.folders || []).map((f) => {
    const cells = plats.map((p) => {
      const t = f.platforms[p] || {};
      return `<td><span class="rs-cell">${t.tested}/${t.total}</span>
                  <span class="rs-cell-sub">${t.percent}%</span></td>`;
    }).join("");
    return `<tr><th scope="row">${rsEsc(f.name)} <span class="rs-fid">${rsEsc(f.id)}</span></th>${cells}</tr>`;
  }).join("");
  return `<table class="rs-table">
      <thead><tr><th scope="col">Folder</th>${head}</tr></thead>
      <tbody>${rows || `<tr><td colspan="${plats.length + 1}" class="rs-empty">No test folders in scope.</td></tr>`}</tbody>
    </table>`;
}

function renderReleaseStatus(el, data) {
  if (!el) return;
  const plats = data.platforms || [];
  const title = data.release ? `Release ${rsEsc(data.release)}` : "Release status";
  el.innerHTML = `
    <div class="rs-head">
      <h2>${title}</h2>
      <p class="rs-meta">${data.total_cases} case(s) in scope${data.folder ? ` · folder ${rsEsc(data.folder)}` : ""}
        · runner is testing <strong>${rsEsc(RS_PLATFORM_LABEL[data.platform] || data.platform)}</strong></p>
    </div>
    ${rsLegend()}
    <div class="rs-cards">${plats.map((p) => rsPlatformCard(p, data.overall[p] || {})).join("")}</div>
    <h3 class="rs-th">By folder</h3>
    ${rsTable(data)}`;
}

if (typeof window !== "undefined") window.renderReleaseStatus = renderReleaseStatus;
