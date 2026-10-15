import { showUpload } from "./upload.js";
import { showRun } from "./reports.js";

const view = document.getElementById("view");

/** Build an element safely. Text always goes through textContent. */
export function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
        if (child == null) continue;
        node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
}

export const badge = (value) => el("span", { class: `badge ${value}`, text: String(value).replaceAll("_", " ") });
export const errorBox = (message) => el("div", { class: "alert error", role: "alert", text: message });
export const formatDate = (iso) => (iso ? new Date(iso).toLocaleString() : "");

function render(...nodes) {
    view.replaceChildren(...nodes);
}

const routes = [
    { pattern: /^#\/upload$/, handler: () => showUpload(render) },
    { pattern: /^#\/runs\/(\d+)$/, handler: (m) => showRun(render, Number(m[1])) },
    { pattern: /^#\/?$/, handler: () => showHome() },
];

function showHome() {
    render(
        el("h1", { text: "DataGuard" }),
        el("div", { class: "card" },
            el("p", { text: "Upload a CSV file to profile it and check its quality." }),
            el("a", { class: "btn", href: "#/upload", text: "Upload a dataset" }),
        ),
    );
}

function route() {
    const hash = location.hash || "#/";
    for (const { pattern, handler } of routes) {
        const match = hash.match(pattern);
        if (match) return handler(match);
    }
    render(el("h1", { text: "Page not found" }), el("a", { href: "#/", text: "Back to start" }));
}

window.addEventListener("hashchange", route);
route();