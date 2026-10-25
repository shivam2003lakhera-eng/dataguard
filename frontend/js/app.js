import { api, onUnauthorized } from "./api.js";
import { showLogin, showRegister } from "./auth.js";
import { showUpload } from "./upload.js";
import { showRun } from "./reports.js";
import { showDashboard } from "./dashboard.js";
import { showDataset } from "./datasets.js";
import { showRules } from "./rules.js";
import { showRunHistory } from "./runs.js";
import { showMyRuns } from "./myruns.js";

const view = document.getElementById("view");
const nav = document.getElementById("nav");
const userBox = document.getElementById("userbox");

let currentUser = null;
let returnTo = null; // where the visitor was heading before we sent them to log in
let flash = null;    // a one-time message for the login screen

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

export function loading(text = "Loading...") {
    return el("div", { class: "loading", role: "status" },
        el("span", { class: "spinner", "aria-hidden": "true" }), text);
}

export function emptyState(title, text, href, actionText) {
    return el("div", { class: "empty-state" },
        el("div", { class: "empty-icon", "aria-hidden": "true", text: "↑" }),
        el("h2", { text: title }),
        el("p", { class: "muted", text }),
        href ? el("a", { class: "btn", href, text: actionText }) : null,
    );
}

export function takeFlash() {
    const message = flash;
    flash = null;
    return message;
}

function setFlash(text, kind = "info") {
    flash = { text, kind };
}

/** Called by the login and register screens once the server accepted them. */
export function loginSucceeded(user) {
    currentUser = user;
    const target = returnTo || "#/";
    returnTo = null;
    location.hash = target;
}

function render(...nodes) {
    view.replaceChildren(...nodes);
}

// ---------- Top bar ----------

const NAV = [
    { href: "#/", label: "Dashboard", active: (h) => h === "#/" || h === "#" },
    { href: "#/upload", label: "Upload", active: (h) => h === "#/upload" },
    { href: "#/runs", label: "My runs", active: (h) => h === "#/runs" },
];

function renderChrome(hash) {
    nav.replaceChildren();
    userBox.replaceChildren();
    if (!currentUser) return;

    nav.append(...NAV.map((item) =>
        el("a", { href: item.href, class: item.active(hash) ? "active" : "", text: item.label })));

    const logoutButton = el("button", { type: "button", class: "secondary small", text: "Log out" });
    logoutButton.addEventListener("click", logout);
    userBox.append(
        el("span", { class: "user-email", title: currentUser.email, text: currentUser.email }),
        logoutButton,
    );
}

async function logout() {
    try {
        await api.logout();
    } catch {
        /* we leave the session either way */
    }
    currentUser = null;
    returnTo = null;
    setFlash("You have been logged out.", "success");
    location.hash = "#/login";
}

// ---------- Routing ----------

const routes = [
    { pattern: /^#\/login$/, handler: () => showLogin(render) },
    { pattern: /^#\/register$/, handler: () => showRegister(render) },
    { pattern: /^#\/upload$/, handler: () => showUpload(render) },
    { pattern: /^#\/runs$/, handler: () => showMyRuns(render) },
    { pattern: /^#\/runs\/(\d+)$/, handler: (m) => showRun(render, Number(m[1])) },
    { pattern: /^#\/datasets\/(\d+)$/, handler: (m) => showDataset(render, Number(m[1])) },
    { pattern: /^#\/datasets\/(\d+)\/rules$/, handler: (m) => showRules(render, Number(m[1])) },
    { pattern: /^#\/datasets\/(\d+)\/runs$/, handler: (m) => showRunHistory(render, Number(m[1])) },
    { pattern: /^#\/?$/, handler: () => showDashboard(render) },
];

const AUTH_PAGES = [/^#\/login$/, /^#\/register$/];

function route() {
    const hash = location.hash || "#/";
    const isAuthPage = AUTH_PAGES.some((pattern) => pattern.test(hash));

    if (!currentUser && !isAuthPage) {
        returnTo = hash;
        location.hash = "#/login";
        return;
    }
    if (currentUser && isAuthPage) {
        location.hash = "#/";
        return;
    }

    renderChrome(hash);
    window.scrollTo(0, 0);
    for (const { pattern, handler } of routes) {
        const match = hash.match(pattern);
        if (match) return handler(match);
    }
    render(el("h1", { text: "Page not found" }), el("a", { class: "btn", href: "#/", text: "Back to start" }));
}

// The server said 401 on a data call: the session ended (expired, or logged out elsewhere).
onUnauthorized(() => {
    if (!currentUser) return;
    currentUser = null;
    returnTo = location.hash || "#/";
    setFlash("Your session has expired. Please log in again.");
    location.hash = "#/login";
});

async function start() {
    render(loading());
    try {
        currentUser = await api.me();
    } catch {
        currentUser = null; // not logged in, or the server is unreachable
    }
    window.addEventListener("hashchange", route);
    route();
}

start();