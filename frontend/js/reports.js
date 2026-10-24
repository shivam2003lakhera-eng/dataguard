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

function buildReport(run) {
    const rows = run.results.map((r) =>
        el("div", { class: "stats" },
            el("div", { class: "stat" }, el("div", { class: "muted", text: "Status" }), badge(run.status)),
            el("div", { class: "stat pass" }, el("div", { class: "num", text: run.checks_passed }), el("div", { class: "muted", text: "Checks passed" })),
            el("div", { class: "stat fail" }, el("div", { class: "num", text: run.checks_failed }), el("div", { class: "muted", text: "Checks failed" })),
        ),
    );

    const table = run.results.length
        ? el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {},
                ...["Rule", "Status", "Severity", "Failed / evaluated", "Message"].map((h) => el("th", { text: h })))),
            el("tbody", {}, rows)))
        : el("p", { class: "muted", text: "No rules were run. Add rules, then run again." });

    return el("div", {},
        el("h1", { text: `Quality report: run #${run.id}` }),
        el("div", { class: "stats" },
            el("div", { class: "stat" }, el("div", { class: "muted", text: "Status" }), badge(run.status)),
            el("div", { class: "stat" }, el("div", { class: "num", text: run.checks_passed }), el("div", { class: "muted", text: "Checks passed" })),
            el("div", { class: "stat" }, el("div", { class: "num", text: run.checks_failed }), el("div", { class: "muted", text: "Checks failed" })),
        ),
        el("div", { class: "row meta" },
            el("span", { class: "muted", text: `Started ${formatDate(run.started_at)}` }),
            el("a", { class: "btn secondary small", href: `#/datasets/${run.dataset_id}`, text: "View dataset" }),
            el("a", { class: "btn secondary small", href: `#/datasets/${run.dataset_id}/runs`, text: "Run history" }),
        ),
        run.error_message ? errorBox(run.error_message) : null,
        el("div", { class: "card" }, table),
    );
}