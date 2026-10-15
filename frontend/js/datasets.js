import { api } from "./api.js";
import { badge, el, errorBox, formatDate } from "./app.js";

export async function showDataset(render, datasetId) {
    render(el("p", { class: "muted", text: "Loading dataset..." }));
    try {
        const [dataset, profile] = await Promise.all([api.getDataset(datasetId), api.getProfile(datasetId)]);
        render(buildDetails(dataset, profile.profile_data));
    } catch (err) {
        render(el("h1", { text: "Dataset" }), errorBox(err.message));
    }
}

function buildDetails(dataset, profile) {
    const meta = [
        ["File", dataset.original_filename],
        ["Rows", dataset.row_count],
        ["Columns", dataset.column_count],
        ["Duplicate rows", profile.duplicate_row_count],
        ["Uploaded", formatDate(dataset.created_at)],
    ];

    return el("div", {},
        el("h1", { text: dataset.name }),
        dataset.description ? el("p", { class: "muted", text: dataset.description }) : null,
        el("div", { class: "stats" },
            meta.map(([label, value]) =>
                el("div", { class: "stat" }, el("div", { class: "num", text: value }), el("div", { class: "muted", text: label }))),
        ),
        el("div", { class: "card" },
            el("h2", { text: "Column statistics" }),
            columnTable(profile.columns),
        ),
        el("div", { class: "row" },
            el("a", { class: "btn", href: `#/datasets/${dataset.id}/rules`, text: "Manage rules" }),
            el("a", { class: "btn", href: `#/datasets/${dataset.id}/runs`, text: "Run history" }),
        ),
    );
}

const fmt = (value) => (value === null || value === undefined ? "" : String(value));

function columnTable(columns) {
    const headers = ["Column", "Type", "Missing", "Missing %", "Distinct", "Min", "Max"];
    const rows = columns.map((c) =>
        el("tr", {},
            el("td", { text: c.name }),
            el("td", {}, badge(c.inferred_type)),
            el("td", { text: c.null_count }),
            el("td", { text: `${c.null_percent}%` }),
            el("td", { text: c.distinct_count }),
            el("td", { text: fmt(c.min) }),
            el("td", { text: fmt(c.max) }),
        ),
    );
    return el("div", { class: "table-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", { text: h })))),
        el("tbody", {}, rows)));
}