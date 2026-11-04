import { api } from "./api.js";
import { badge, el, errorBox, formatDate, loading } from "./app.js";

export async function showRun(render, runId) {
  render(loading("Loading report..."));
  try {
    const run = await api.getRun(runId);
    render(buildReport(run));
  } catch (err) {
    render(el("h1", { text: "Quality report" }), errorBox(err.message));
  }
}

function stat(value, label, extraClass = "") {
  return el("div", { class: `stat ${extraClass}`.trim() },
    el("div", { class: "num", text: value }),
    el("div", { class: "muted", text: label }));
}

/** Row accounting cards. Shown only when the run measured them (older runs and failed runs did not). */
function rowCards(run) {
  if (run.source_rows === null || run.source_rows === undefined) return null;
  return el("div", { class: "stats" },
    stat(run.source_rows, "Rows read"),
    stat(run.valid_rows, "Valid rows", "pass"),
    stat(run.rejected_rows, "Rejected rows", run.rejected_rows > 0 ? "fail" : "pass"),
    run.duration_ms === null || run.duration_ms === undefined ? null : stat(`${run.duration_ms} ms`, "Processing time"),
  );
}

function buildReport(run) {
  const headers = ["Rule", "Status", "Severity", "Kind", "Failed / evaluated", "Rejected rows", "Message"];

  const rows = run.results.map((r) =>
    el("tr", {},
      el("td", { text: r.rule_name }),
      el("td", {}, badge(r.status)),
      el("td", {}, badge(r.severity)),
      el("td", {}, badge(r.category)),
      el("td", { text: `${r.rows_failed} / ${r.rows_evaluated}` }),
      el("td", { text: r.rows_rejected === null || r.rows_rejected === undefined ? "n/a" : r.rows_rejected }),
      el("td", { text: r.message }),
    ),
  );

  const table = run.results.length
    ? el("div", { class: "table-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", { text: h })))),
        el("tbody", {}, rows)))
    : el("p", { class: "muted", text: "No rules were run. Add rules, then run again." });

  const notLoadable = run.loadable === false
    ? el("div", { class: "alert error", role: "alert",
        text: "A schema check failed, so this file is not considered loadable." })
    : null;

  return el("div", {},
    el("a", { class: "back-link", href: "#/runs", text: "← My runs" }),
    el("h1", { text: `Quality report: run #${run.id}` }),
    el("div", { class: "stats" },
      el("div", { class: "stat" }, el("div", { class: "muted", text: "Status" }), badge(run.status)),
      stat(run.checks_passed, "Checks passed", "pass"),
      stat(run.checks_failed, "Checks failed", "fail"),
    ),
    rowCards(run),
    el("div", { class: "row meta" },
      el("span", { class: "muted", text: `Started ${formatDate(run.started_at)}` }),
      el("a", { class: "btn secondary small", href: `#/datasets/${run.dataset_id}`, text: "View dataset" }),
      el("a", { class: "btn secondary small", href: `#/datasets/${run.dataset_id}/runs`, text: "Run history" }),
    ),
    notLoadable,
    run.error_message ? errorBox(run.error_message) : null,
    el("div", { class: "card" }, table),
  );
}
