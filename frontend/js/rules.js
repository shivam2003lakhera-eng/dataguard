import { api } from "./api.js";
import { badge, el, emptyState, errorBox } from "./app.js";

const splitList = (text) => text.split(",").map((s) => s.trim()).filter(Boolean);

function parseNumber(text, label) {
    if (text.trim() === "") return { value: null };
    const n = Number(text);
    if (!Number.isFinite(n)) return { error: `${label} must be a number.` };
    return { value: n };
}

/** One entry per rule type: the fields to show, and how to build/validate the configuration. */
const RULE_FORMS = {
    required_columns: {
        label: "Required columns exist",
        fields: [{ key: "columns", label: "Column names (comma-separated)", kind: "list" }],
        build: (v) => (v.columns.length ? { config: { columns: v.columns } } : { error: "Enter at least one column name." }),
        read: (c) => ({ columns: (c.columns || []).join(", ") }),
    },
    required_values: {
        label: "No missing values",
        fields: [{ key: "columns", label: "Column names (comma-separated)", kind: "list" }],
        build: (v) => (v.columns.length ? { config: { columns: v.columns } } : { error: "Enter at least one column name." }),
        read: (c) => ({ columns: (c.columns || []).join(", ") }),
    },
    duplicates: {
        label: "No duplicate rows",
        fields: [{ key: "columns", label: "Key columns (comma-separated, leave empty for the whole row)", kind: "list" }],
        build: (v) => ({ config: v.columns.length ? { columns: v.columns } : {} }),
        read: (c) => ({ columns: (c.columns || []).join(", ") }),
    },
    numeric_range: {
        label: "Numeric range",
        fields: [
            { key: "column", label: "Column name", kind: "text" },
            { key: "min", label: "Minimum (optional)", kind: "text" },
            { key: "max", label: "Maximum (optional)", kind: "text" },
        ],
        build: (v) => {
            if (!v.column) return { error: "Enter a column name." };
            const low = parseNumber(v.min, "Minimum");
            const high = parseNumber(v.max, "Maximum");
            if (low.error) return { error: low.error };
            if (high.error) return { error: high.error };
            if (low.value === null && high.value === null) return { error: "Enter a minimum, a maximum, or both." };
            if (low.value !== null && high.value !== null && low.value > high.value) {
                return { error: "Minimum cannot be greater than maximum." };
            }
            const config = { column: v.column };
            if (low.value !== null) config.min = low.value;
            if (high.value !== null) config.max = high.value;
            return { config };
        },
        read: (c) => ({ column: c.column || "", min: c.min ?? "", max: c.max ?? "" }),
    },
    allowed_values: {
        label: "Allowed values",
        fields: [
            { key: "column", label: "Column name", kind: "text" },
            { key: "allowed", label: "Allowed values (comma-separated)", kind: "list" },
            { key: "case_sensitive", label: "Case sensitive", kind: "checkbox" },
        ],
        build: (v) => {
            if (!v.column) return { error: "Enter a column name." };
            if (!v.allowed.length) return { error: "Enter at least one allowed value." };
            return { config: { column: v.column, allowed: v.allowed, case_sensitive: v.case_sensitive } };
        },
        read: (c) => ({ column: c.column || "", allowed: (c.allowed || []).join(", "), case_sensitive: c.case_sensitive !== false }),
    },
    data_type: {
        label: "Data type",
        fields: [
            { key: "column", label: "Column name", kind: "text" },
            { key: "data_type", label: "Must be convertible to", kind: "select", options: ["integer", "float", "date"] },
        ],
        build: (v) => (v.column ? { config: { column: v.column, data_type: v.data_type } } : { error: "Enter a column name." }),
        read: (c) => ({ column: c.column || "", data_type: c.data_type || "integer" }),
    },
};

function makeInput(field, value) {
    if (field.kind === "checkbox") {
        const box = el("input", { type: "checkbox" });
        box.checked = value !== false;
        return box;
    }
    if (field.kind === "select") {
        const select = el("select", {}, field.options.map((o) => el("option", { value: o, text: o })));
        select.value = value || field.options[0];
        return select;
    }
    const input = el("input", { type: "text" });
    input.value = value ?? "";
    return input;
}

function readInput(field, input) {
    if (field.kind === "checkbox") return input.checked;
    if (field.kind === "list") return splitList(input.value);
    return input.value.trim();
}

/** Build a rule form. `existing` is a stored rule when editing, or null when creating. */
function ruleForm(existing, onSave, onCancel) {
    const message = el("div");
    const nameInput = el("input", { type: "text", maxlength: "200" });
    nameInput.value = existing ? existing.name : "";
    const severity = el("select", {}, ["LOW", "MEDIUM", "HIGH"].map((s) => el("option", { value: s, text: s })));
    severity.value = existing ? existing.severity : "MEDIUM";

    const typeSelect = el("select", {}, Object.entries(RULE_FORMS).map(([k, f]) => el("option", { value: k, text: f.label })));
    if (existing) {
        typeSelect.value = existing.rule_type;
        typeSelect.disabled = true; // the server does not allow changing a rule's type
    }

    const fieldsBox = el("div");
    let inputs = {};

    function drawFields() {
        const spec = RULE_FORMS[typeSelect.value];
        const values = existing && existing.rule_type === typeSelect.value ? spec.read(existing.configuration) : {};
        inputs = {};
        fieldsBox.replaceChildren();
        for (const field of spec.fields) {
            inputs[field.key] = makeInput(field, values[field.key]);
            fieldsBox.append(el("label", { text: field.label }), inputs[field.key]);
        }
    }
    typeSelect.addEventListener("change", drawFields);
    drawFields();

    const save = el("button", { type: "button", text: existing ? "Save changes" : "Add rule" });
    save.addEventListener("click", async () => {
        message.replaceChildren();
        const spec = RULE_FORMS[typeSelect.value];
        const name = nameInput.value.trim();
        if (!name) return message.append(errorBox("Enter a rule name."));

        const values = {};
        for (const field of spec.fields) values[field.key] = readInput(field, inputs[field.key]);
        const built = spec.build(values);
        if (built.error) return message.append(errorBox(built.error));

        save.disabled = true;
        try {
            await onSave({ name, rule_type: typeSelect.value, configuration: built.config, severity: severity.value });
        } catch (err) {
            message.replaceChildren(errorBox(err.message));
            save.disabled = false;
        }
    });

    const cancel = el("button", { type: "button", class: "secondary", text: "Cancel" });
    cancel.addEventListener("click", onCancel);

    return el("div", { class: "card" },
        el("h2", { text: existing ? `Edit rule #${existing.id}` : "Add a rule" }),
        el("label", { text: "Rule name" }), nameInput,
        el("label", { text: "Rule type" }), typeSelect,
        fieldsBox,
        el("label", { text: "Severity" }), severity,
        el("div", { class: "row", style: "margin-top:12px" }, save, cancel),
        message,
    );
}

export async function showRules(render, datasetId) {
    const formSlot = el("div");
    const listSlot = el("div");
    const flash = el("div");

    async function refresh() {
        try {
            const rules = await api.listRules(datasetId);
            listSlot.replaceChildren(buildTable(rules));
        } catch (err) {
            listSlot.replaceChildren(errorBox(err.message));
        }
    }

    function closeForm() { formSlot.replaceChildren(); }

    function openForm(existing) {
        formSlot.replaceChildren(ruleForm(
            existing,
            async (payload) => {
                if (existing) await api.updateRule(existing.id, { name: payload.name, configuration: payload.configuration, severity: payload.severity });
                else await api.createRule(datasetId, payload);
                closeForm();
                await refresh();
            },
            closeForm,
        ));
    }

    async function act(promise) {
        flash.replaceChildren();
        try { await promise; await refresh(); } catch (err) { flash.replaceChildren(errorBox(err.message)); }
    }

    function buildTable(rules) {
        if (!rules.length) return emptyState("No rules yet", "Add a rule below to start checking this dataset."); const rows = rules.map((r) => {
            const toggle = el("button", { type: "button", class: "secondary", text: r.enabled ? "Disable" : "Enable" });
            toggle.addEventListener("click", () => act(api.updateRule(r.id, { enabled: !r.enabled })));
            const edit = el("button", { type: "button", class: "secondary", text: "Edit" });
            edit.addEventListener("click", () => openForm(r));
            const remove = el("button", { type: "button", class: "danger", text: "Delete" });
            remove.addEventListener("click", () => {
                if (confirm(`Delete rule "${r.name}"? Past results are kept.`)) act(api.deleteRule(r.id));
            });
            return el("tr", {},
                el("td", { text: r.name }),
                el("td", { text: RULE_FORMS[r.rule_type] ? RULE_FORMS[r.rule_type].label : r.rule_type }),
                el("td", { text: JSON.stringify(r.configuration) }),
                el("td", {}, badge(r.severity)),
                el("td", { text: r.enabled ? "Enabled" : "Disabled" }),
                el("td", {}, el("div", { class: "row" }, toggle, edit, remove)),
            );
        });
        return el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {}, ...["Name", "Type", "Configuration", "Severity", "State", ""].map((h) => el("th", { text: h })))),
            el("tbody", {}, rows)));
    }

    const addButton = el("button", { type: "button", text: "Add a rule" });
    addButton.addEventListener("click", () => openForm(null));

    render(
        el("p", {}, el("a", { href: `#/datasets/${datasetId}`, text: "← Back to dataset" })),
        el("h1", { text: "Quality rules" }),
        flash,
        el("div", { class: "card" }, listSlot),
        el("div", { class: "row" }, addButton),
        formSlot,
    );
    await refresh();
}