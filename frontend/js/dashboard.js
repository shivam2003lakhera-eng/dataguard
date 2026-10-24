import { api } from "./api.js";
import { badge, el, emptyState, errorBox, formatDate, loading } from "./app.js";

const DATASET_LIMIT = 10;
const RUNS_PER_DATASET = 5;
const REPORTS_TO_SUMMARIZE = 10;

export async function showDashboard(render) {
    render(el("h1", { text: "Dashboard" }), loading());
    try {
        const datasets = await api.listDatasets(DATASET_LIMIT, 0);
        const perDataset = await Promise.all(
            datasets.items.map((d) => api.listRuns(d.id, RUNS_PER_DATASET, 0)),
        );

        const names = new Map(datasets.items.map((d) => [d.id, d.name]));
        const totalRuns = perDataset.reduce((sum, page) => sum + page.total, 0);
        const recentRuns = perDataset
            .flatMap((page) => page.items)
            .sort((a, b) => b.id - a.id)
            .slice(0, 10);

        const failingRuns = recentRuns.filter((r) => r.checks_failed > 0).slice(0, REPORTS_TO_SUMMARIZE);
        const reports = await Promise.all(failingRuns.map((r) => api.getRun(r.id)));

        render(
            el("h1", { text: "Dashboard" }),
            statCards(datasets, totalRuns),
            recentRunsCard(recentRuns, names),
            failedChecksCard(reports, failingRuns.length),
        );
    } catch (err) {
        render(el("h1", { text: "Dashboard" }), errorBox(err.message));
    }
}

function statCards(datasets, totalRuns) {
    const partial = datasets.total > DATASET_LIMIT;
    const runLabel = partial ? `Quality runs (latest ${DATASET_LIMIT} datasets)` : "Quality runs";
    return el("div", { class: "stats" },
        el("div", { class: "stat" }, el("div", { class: "num", text: datasets.total }), el("div", { class: "muted", text: "Datasets uploaded" })),
        el("div", { class: "stat" }, el("div", { class: "num", text: totalRuns }), el("div", { class: "muted", text: runLabel })),
    );
}

function recentRunsCard(runs, names) {
    if (!runs.length) {
        return el("div", { class: "card" },
            el("h2", { text: "Recent runs" }),
            emptyState(
                "No runs yet",
                "Upload a CSV file to profile it and see its quality report here.",
                "#/upload",
                "Upload a dataset",
            ),
        );
    }
    const rows = runs.map((r) =>
        el("tr", {},
            el("td", {}, el("a", { class: "run-link", href: `#/runs/${r.id}`, text: `#${r.id}` })),
            el("td", {}, el("a", { class: "name-link", href: `#/datasets/${r.dataset_id}`, text: names.get(r.dataset_id) || `Dataset ${r.dataset_id}` })),
            el("td", {}, badge(r.status)),
            el("td", { text: `${r.checks_passed} passed, ${r.checks_failed} failed` }),
            el("td", { text: formatDate(r.started_at) }),
        ),
    );
    return el("div", { class: "card" },
        el("h2", { text: "Recent runs" }),
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
        return el("div", { class: "card" }, heading, el("p", { class: "muted", text: "No failed checks. 🎉".replace(" 🎉", "") }));
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