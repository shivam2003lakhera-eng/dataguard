# Security notes

What the authentication does, and what it does not.

## What is implemented

| Area | Design |
|---|---|
| Passwords | Salted `scrypt` (N=2^14, r=8, p=1) from Python's standard library. Only the hash is stored. Verification uses a constant-time comparison. |
| Sessions | A random token is sent in a cookie. Only its SHA-256 hash is stored in `user_sessions`, so a database leak cannot be replayed as logins. Logout deletes the row on the server, so a copied cookie stops working. |
| Cookie | `HttpOnly` (JavaScript cannot read it), `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`, expires after `SESSION_DAYS`. |
| Login errors | One generic message for an unknown email and a wrong password. A dummy hash check keeps response time similar. |
| Brute force | 5 failed logins per IP and email within 15 minutes returns 429. A success resets the count. |
| Data isolation | Every dataset belongs to a user. Rules, runs and results are reached only through their dataset. Another user's data returns the same 404 as data that does not exist, so ids cannot be probed. |
| Rendering | All server data is inserted with `textContent`, never `innerHTML`, so an uploaded CSV cannot inject script. |
| Errors | A single JSON error format. Unexpected errors return a generic 500 with no traceback or paths. |
| Secrets | `.env` is git-ignored. Logs redact lines that look like secrets. |

## Known limitations

- The login limiter is in memory: it works for one server process and resets on restart.
- No email verification, password reset, or account deletion.
- No CSRF tokens. Protection relies on `SameSite=Lax` cookies and a same-origin app.
- Uploads are parsed before the login check runs, so a public deployment should cap request size at the proxy.
- Registration is open unless `ALLOW_REGISTRATION=false`.
- Tests keep the database dependency overridden, so they never touch the development database.

## Reporting

This is a portfolio project. Do not store sensitive data in it.