import { api } from "./api.js";
import { badge, el, emptyState, errorBox, formatDate, loading } from "./app.js";

const PAGE_SIZE = 15;
const FILTERS = [
    ["", "All statuses"],
    ["SUCCESS", "Success"],
    ["COMPLETED_WITH_ISSUES", "Completed with issues"],
    ["FAILED", "Failed"],
];

export async function showMyRuns(render) {
    const state = { status: "", offset: 0 };
    const results = el("div");

    const filter = el("select", { "aria-label": "Filter runs by status" },
        FILTERS.map(([value, label]) => el("option", { value, text: label })));
    filter.addEventListener("change", () => {
        state.status = filter.value;
        state.offset = 0;
        load();
    });

    async function load() {
        results.replaceChildren(loading());
        try {
            results.replaceChildren(buildResults(await api.listMyRuns(PAGE_SIZE, state.offset, state.status)));
        } catch (err) {
            results.replaceChildren(errorBox(err.message));
        }
    }

    function go(offset) {
        state.offset = Math.max(0, offset);
        load();
    }

    function buildResults(page) {
        if (page.total === 0) {
            return state.status
                ? el("p", { class: "muted", text: "No runs match this filter." })
                : emptyState("No runs yet", "Upload a CSV file to see its quality report here.", "#/upload", "Upload a dataset");
        }

        const rows = page.items.map((r) =>
            el("tr", {},
                el("td", {}, el("a", { class: "run-link", href: `#/runs/${r.id}`, text: `#${r.id}` })),
                el("td", {}, el("a", { class: "name-link", href: `#/datasets/${r.dataset_id}`, text: r.dataset_name })),
                el("td", {}, badge(r.status)),
                el("td", { text: `${r.checks_passed} passed, ${r.checks_failed} failed` }),
                el("td", { text: formatDate(r.started_at) }),
            ),
        );

        const previous = el("button", { type: "button", class: "secondary small", text: "← Previous" });
        const next = el("button", { type: "button", class: "secondary small", text: "Next →" });
        previous.disabled = state.offset === 0;
        next.disabled = state.offset + page.items.length >= page.total;
        previous.addEventListener("click", () => go(state.offset - PAGE_SIZE));
        next.addEventListener("click", () => go(state.offset + PAGE_SIZE));

        return el("div", {},
            el("div", { class: "table-wrap" }, el("table", {},
                el("thead", {}, el("tr", {},
                    ...["Run", "Dataset", "Status", "Checks", "Started"].map((h) => el("th", { text: h })))),
                el("tbody", {}, rows))),
            el("div", { class: "pager" },
                el("span", { class: "muted", text: `Showing ${state.offset + 1}–${state.offset + page.items.length} of ${page.total}` }),
                el("div", { class: "row" }, previous, next)),
        );
    }

    render(
        el("h1", { text: "My runs" }),
        el("div", { class: "row filter-row" }, filter),
        el("div", { class: "card" }, results),
    );
    await load();
}