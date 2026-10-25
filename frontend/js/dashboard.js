import { api } from "./api.js";
import { badge, el, emptyState, errorBox, formatDate, loading } from "./app.js";

const RECENT_RUNS = 10;
const REPORTS_TO_SUMMARIZE = 10;

export async function showDashboard(render) {
    render(el("h1", { text: "Dashboard" }), loading());
    try {
        const [datasets, runs] = await Promise.all([api.listDatasets(1, 0), api.listMyRuns(RECENT_RUNS, 0)]);

        const failingRuns = runs.items.filter((r) => r.checks_failed > 0).slice(0, REPORTS_TO_SUMMARIZE);
        const reports = await Promise.all(failingRuns.map((r) => api.getRun(r.id)));

        render(
            el("h1", { text: "Dashboard" }),
            statCards(datasets.total, runs.total),
            recentRunsCard(runs.items),
            failedChecksCard(reports, failingRuns.length),
        );
    } catch (err) {
        render(el("h1", { text: "Dashboard" }), errorBox(err.message));
    }
}

function statCards(datasetCount, runCount) {
    return el("div", { class: "stats" },
        el("div", { class: "stat" }, el("div", { class: "num", text: datasetCount }), el("div", { class: "muted", text: "Datasets uploaded" })),
        el("div", { class: "stat" }, el("div", { class: "num", text: runCount }), el("div", { class: "muted", text: "Quality runs" })),
    );
}

function recentRunsCard(runs) {
    const header = el("div", { class: "row spread" },
        el("h2", { text: "Recent runs" }),
        runs.length ? el("a", { class: "btn secondary small", href: "#/runs", text: "View all runs" }) : null,
    );

    if (!runs.length) {
        return el("div", { class: "card" }, header,
            emptyState("No runs yet", "Upload a CSV file to profile it and see its quality report here.", "#/upload", "Upload a dataset"));
    }

    const rows = runs.map((r) =>
        el("tr", {},
            el("td", {}, el("a", { class: "run-link", href: `#/runs/${r.id}`, text: `#${r.id}` })),
            el("td", {}, el("a", { class: "name-link", href: `#/datasets/${r.dataset_id}`, text: r.dataset_name })),
            el("td", {}, badge(r.status)),
            el("td", { text: `${r.checks_passed} passed, ${r.checks_failed} failed` }),
            el("td", { text: formatDate(r.started_at) }),
        ),
    );
    return el("div", { class: "card" }, header,
        el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {}, ...["Run", "Dataset", "Status", "Checks", "Started"].map((h) => el("th", { text: h })))),
            el("tbody", {}, rows))),
    );
}

function failedChecksCard(reports, runCount) {
    const failures = new Map(); // "rule name|severity" -> count
    for (const report of reports) {
        for (const result of report.results) {
            if (result.status !== "FAIL") continue;
            const key = `${result.rule_name}|${result.severity}`;
            failures.set(key, (failures.get(key) || 0) + 1);
        }
    }

    const heading = el("h2", { text: "Failed checks in recent runs" });
    if (!failures.size) {
        return el("div", { class: "card" }, heading, el("p", { class: "muted", text: "No failed checks." }));
    }

    const rows = [...failures.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([key, count]) => {
            const [name, severity] = key.split("|");
            return el("tr", {}, el("td", { text: name }), el("td", {}, badge(severity)), el("td", { text: count }));
        });
    return el("div", { class: "card" },
        heading,
        el("p", { class: "muted", text: `Counted across the ${runCount} most recent run(s) that had failures.` }),
        el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {}, ...["Rule", "Severity", "Times failed"].map((h) => el("th", { text: h })))),
            el("tbody", {}, rows))),
    );
}