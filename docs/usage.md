# Usage

## Account

Open the app and choose **Create one** on the login screen. Enter an email and a password of 8 to 128 characters. Logging out ends the session on the server.

## Upload

Choose **Upload**, enter a name, pick a CSV, and optionally paste rules as JSON:

```json
[{"name":"id required","rule_type":"required_values","configuration":{"columns":["policy_id"]},"severity":"HIGH"}]
```

You land on the quality report.

## Rule types and configuration

| rule_type | configuration |
|---|---|
| `required_columns` | `{"columns": ["a", "b"]}` |
| `required_values` | `{"columns": ["a"]}` |
| `duplicates` | `{}` for whole rows, or `{"columns": ["id"]}` |
| `numeric_range` | `{"column": "age", "min": 0, "max": 120}` (min or max may be omitted, not both) |
| `allowed_values` | `{"column": "status", "allowed": ["Active"], "case_sensitive": true}` |
| `data_type` | `{"column": "n", "data_type": "integer"}` (also `float`, `date`) |

Rules can also be created in the **Manage rules** screen. Invalid configuration is rejected with a clear message.

## Running again and history

Open a dataset, then **Run history**, and upload a CSV. It is checked against the dataset's enabled rules. **My runs** in the top bar lists every run of every dataset you own, newest first, with a status filter.

**Input strategy:** DataGuard does not store CSV rows, so `POST /api/v1/datasets/{id}/runs` always needs a newly uploaded file.

## API

All endpoints are under `/api/v1` and, except `health` and `auth`, need a login cookie. Interactive docs are at `/docs`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check (public) |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Accounts and sessions |
| `POST /datasets/upload`, `GET /datasets`, `GET /datasets/{id}`, `GET /datasets/{id}/profile` | Datasets |
| `GET`/`POST /datasets/{id}/rules`, `PATCH`/`DELETE /rules/{id}` | Rules |
| `POST`/`GET /datasets/{id}/runs`, `GET /runs`, `GET /runs/{id}` | Runs; `GET /runs` is all my runs, with `?status=` |

## Notes on behavior

- A numeric range ignores text such as `abc`; use a `data_type` rule to catch it.
- Dates are recognised only in strict ISO form (`2025-01-31` or `2025-01-31T10:00:00`).
- Uploads over `MAX_FILE_SIZE_MB` (default 50) are rejected.
- Another user's data always looks like it does not exist (404).

## Demo workflow

1. Register an account and log in.
2. Upload `sample_data/insurance/policies_bad.csv` with no rules.
3. Open **Manage rules** and add: no missing values on `policy_id` (HIGH), numeric range on `premium` minimum 0, allowed values on `policy_status` (`ACTIVE, EXPIRED, PENDING`).
4. Open **Run history**, upload the same file, and read the report (3 failures).
5. Check the Dashboard and **My runs**.