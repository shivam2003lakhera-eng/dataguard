# Security notes

What the authentication and the data handling do, and what they do not.

## What is implemented

| Area | Design |
|---|---|
| Passwords | Salted `scrypt` (N=2^14, r=8, p=1) from Python's standard library. Only the hash is stored. Verification uses a constant-time comparison. |
| Sessions | A random token is sent in a cookie. Only its SHA-256 hash is stored in `user_sessions`, so a database leak cannot be replayed as logins. Logout deletes the row on the server, so a copied cookie stops working. |
| Cookie | `HttpOnly` (JavaScript cannot read it), `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`, expires after `SESSION_DAYS`. |
| Login errors | One generic message for an unknown email and a wrong password. A dummy hash check keeps response time similar. |
| Brute force | 5 failed logins per IP and email within 15 minutes returns 429. A success resets the count. |
| Data isolation | Every dataset belongs to a user. Rules, runs, results and loaded records are reached only through their dataset. Another user's data returns the same 404 as data that does not exist, so ids cannot be probed. Tests cover reading, changing and deleting. |
| Rendering | All server data is inserted with `textContent`, never `innerHTML`, so an uploaded CSV cannot inject script. |
| Errors | A single JSON error format. Unexpected errors return a generic 500 with no traceback or paths, and a failed pipeline run stores a generic message. |
| Secrets | `.env` is git-ignored. Logs redact lines that look like secrets. The settings object hides the database URLs in its `repr`, and pytest prints short tracebacks, so a failure does not print a password. |

## What the app stores about your data

| Data | Stored? |
|---|---|
| The uploaded file | **No.** Only its SHA-256 hash, to recognise a re-upload. |
| Rows | **No, unless the dataset has key columns.** Then the valid rows are stored in `dataset_records`. |
| Cell values in reports | **No by default.** Failing rows are stored as positions (at most 5 per rule). `STORE_SAMPLE_VALUES=true` also stores up to 5 offending values per rule. |
| The profile | Yes: counts, types, and the minimum and maximum of numeric and date columns. |

A user can turn loading off with `PATCH /datasets/{dataset_id}` and delete everything loaded with `DELETE /datasets/{dataset_id}/records`.

## Known limitations

- Loaded rows are stored unencrypted in PostgreSQL. Anyone with database access can read them.
- The login limiter is in memory: it works for one server process and resets on restart. Behind a proxy it may see only the proxy's address.
- No email verification, password reset, account deletion, or CSRF tokens. Protection relies on `SameSite=Lax` cookies and a same-origin app.
- Uploads are parsed before the login check runs, so a public deployment should cap request size at the proxy.
- Registration is open unless `ALLOW_REGISTRATION=false`.
- No per-user quota on stored rows or runs.

## Reporting

This is a portfolio project. Do not store sensitive data in it.
