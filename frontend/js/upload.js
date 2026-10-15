import { api } from "./api.js";
import { el, errorBox } from "./app.js";

export function showUpload(render) {
    const message = el("div");
    const nameInput = el("input", { type: "text", id: "name", maxlength: "200", required: "" });
    const fileInput = el("input", { type: "file", id: "file", accept: ".csv" });
    const rulesInput = el("textarea", {
        id: "rules",
        placeholder: '[{"name":"id required","rule_type":"required_values","configuration":{"columns":["id"]},"severity":"HIGH"}]',
    });
    const button = el("button", { type: "button", text: "Upload and validate" });

    button.addEventListener("click", async () => {
        message.replaceChildren();
        const name = nameInput.value.trim();
        const file = fileInput.files[0];

        if (!name) return message.append(errorBox("Please enter a dataset name."));
        if (!file) return message.append(errorBox("Please choose a CSV file."));
        if (!file.name.toLowerCase().endsWith(".csv")) {
            return message.append(errorBox("Only .csv files are supported."));
        }
        const rulesText = rulesInput.value.trim();
        if (rulesText) {
            try {
                if (!Array.isArray(JSON.parse(rulesText))) throw new Error();
            } catch {
                return message.append(errorBox("Rules must be a valid JSON list, or leave the box empty."));
            }
        }

        const form = new FormData();
        form.append("file", file);
        form.append("name", name);
        if (rulesText) form.append("rules", rulesText);

        button.disabled = true;
        button.textContent = "Uploading...";
        message.append(el("div", { class: "alert info", text: "Uploading and validating..." }));
        try {
            const run = await api.uploadDataset(form);
            location.hash = `#/runs/${run.id}`;
        } catch (err) {
            message.replaceChildren(errorBox(err.message));
            button.disabled = false;
            button.textContent = "Upload and validate";
        }
    });

    render(
        el("h1", { text: "Upload dataset" }),
        el("div", { class: "card" },
            el("label", { for: "name", text: "Dataset name" }), nameInput,
            el("label", { for: "file", text: "CSV file" }), fileInput,
            el("label", { for: "rules", text: "Rules (optional, JSON list)" }), rulesInput,
            el("p", { class: "muted", text: "The rule editor comes in a later step. You can also add rules after uploading." }),
            el("div", { class: "row" }, button),
            message,
        ),
    );
}