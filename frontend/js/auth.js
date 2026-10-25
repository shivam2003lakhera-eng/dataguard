import { api } from "./api.js";
import { el, errorBox, loginSucceeded, takeFlash } from "./app.js";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function labelled(text, id, input) {
    return [el("label", { for: id, text }), input];
}

function authCard(title, flash, form, message, switchText, switchHref, switchLabel) {
    return el("div", { class: "card auth-card" },
        el("h1", { text: title }),
        flash ? el("div", { class: `alert ${flash.kind}`, text: flash.text }) : null,
        form,
        message,
        el("p", { class: "auth-switch muted" }, `${switchText} `, el("a", { href: switchHref, text: switchLabel })),
    );
}

export function showLogin(render) {
    const message = el("div");
    const email = el("input", { type: "email", id: "email", autocomplete: "username", maxlength: "254" });
    const password = el("input", { type: "password", id: "password", autocomplete: "current-password" });
    const button = el("button", { type: "submit", text: "Log in" });

    const form = el("form", { novalidate: "" },
        labelled("Email", "email", email), labelled("Password", "password", password), button);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        message.replaceChildren();
        if (!email.value.trim() || !password.value) {
            return message.append(errorBox("Enter your email and password."));
        }
        button.disabled = true;
        button.textContent = "Logging in...";
        try {
            loginSucceeded(await api.login(email.value.trim(), password.value));
        } catch (err) {
            message.replaceChildren(errorBox(err.message));
            button.disabled = false;
            button.textContent = "Log in";
        }
    });

    render(authCard("Log in", takeFlash(), form, message, "No account yet?", "#/register", "Create one"));
    email.focus();
}

export function showRegister(render) {
    const message = el("div");
    const email = el("input", { type: "email", id: "email", autocomplete: "username", maxlength: "254" });
    const password = el("input", { type: "password", id: "password", autocomplete: "new-password" });
    const confirm = el("input", { type: "password", id: "confirm", autocomplete: "new-password" });
    const button = el("button", { type: "submit", text: "Create account" });

    const form = el("form", { novalidate: "" },
        labelled("Email", "email", email),
        labelled("Password (8 to 128 characters)", "password", password),
        labelled("Confirm password", "confirm", confirm),
        button);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        message.replaceChildren();
        const problem =
            !EMAIL_PATTERN.test(email.value.trim()) ? "Enter a valid email address." :
                password.value.length < 8 ? "The password must be at least 8 characters." :
                    password.value.length > 128 ? "The password must be at most 128 characters." :
                        password.value !== confirm.value ? "The two passwords do not match." : null;
        if (problem) return message.append(errorBox(problem));

        button.disabled = true;
        button.textContent = "Creating account...";
        try {
            loginSucceeded(await api.register(email.value.trim(), password.value));
        } catch (err) {
            message.replaceChildren(errorBox(err.message));
            button.disabled = false;
            button.textContent = "Create account";
        }
    });

    render(authCard("Create an account", takeFlash(), form, message, "Already registered?", "#/login", "Log in"));
    email.focus();
}