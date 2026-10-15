import { api } from "./api.js";
import { badge, el, errorBox, formatDate } from "./app.js";

export async function showRunHistory(render, datasetId) {
    render(el("p", { class: "muted", text: "Loading run history..." }));
    try {
        const [dataset, runs] = await Promise.all([api.getDataset(datasetId), api.listRuns(datasetId, 100, 0)]);
        render(buildHistory(dataset, runs));
    } catch (err) {
        render(el("h1", { text: "Run history" }), errorBox(err.message));
    }
}

function buildHistory(dataset, page) {
    const rows = page.items.map((r) =>
        el("tr", {},
            el("td", {}, el("a", { href: `#/runs/${r.id}`, text: `#${r.id}` })),
            el("td", {}, badge(r.status)),
            el("td", { text: `${r.checks_passed} passed, ${r.checks_failed} failed` }),
            el("td", { text: formatDate(r.started_at) }),
            el("td", { text: formatDate(r.completed_at) }),
        ),
    );

    const table = page.items.length
        ? el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {}, ...["Run", "Status", "Checks", "Started", "Completed"].map((h) => el("th", { text: h })))),
            el("tbody", {}, rows)))
        : el("p", { class: "muted", text: "No runs yet." });

    const more = page.total > page.items.length
        ? el("p", { class: "muted", text: `Showing the newest ${page.items.length} of ${page.total} runs.` })
        : null;

    return el("div", {},
        el("p", {}, el("a", { href: `#/datasets/${dataset.id}`, text: "← Back to dataset" })),
        el("h1", { text: `Run history: ${dataset.name}` }),
        el("div", { class: "card" }, table, more),
        rerunCard(dataset.id),
    );
}

function rerunCard(datasetId) {
    const message = el("div");
    const fileInput = el("input", { type: "file", accept: ".csv" });
    const button = el("button", { type: "button", text: "Run checks" });

    button.addEventListener("click", async () => {
        message.replaceChildren();
        const file = fileInput.files[0];
        if (!file) return message.append(errorBox("Please choose a CSV file."));
        if (!file.name.toLowerCase().endsWith(".csv")) return message.append(errorBox("Only .csv files are supported."));

        const form = new FormData();
        form.append("file", file);
        button.disabled = true;
        button.textContent = "Running...";
        try {
            const run = await api.createRun(datasetId, form);
            location.hash = `#/runs/${run.id}`;
        } catch (err) {
            message.replaceChildren(errorBox(err.message));
            button.disabled = false;
            button.textContent = "Run checks";
        }
    });

    return el("div", { class: "card" },
        el("h2", { text: "Run again with a new file" }),
        el("p", { class: "muted", text: "V1 does not keep CSV rows, so each run needs a file. It is checked against this dataset's enabled rules." }),
        fileInput,
        el("div", { class: "row", style: "margin-top:12px" }, button),
        message,
    );
}