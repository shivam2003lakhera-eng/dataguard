# Architecture

```
Browser (HTML/CSS/JS, hash routing)
   |  fetch() with a session cookie
FastAPI routes (app/api)          thin: check login, validate input, call a service
   |-- auth routes -> app/services/auth.py -> users, user_sessions
   |
Services (app/services)           the database-backed layer
   |-- pipeline.py   a run: read, save, validate, account, load, record the result
   |-- loading.py    the idempotent upsert into dataset_records
   |
Processing core (app/processing)  NO FastAPI, NO database: also used by the CLI and the tests
   |-- runner.py     run_pipeline, process_dataframe, row accounting
   |-- loading.py    prepare the valid rows for loading
   |-- report.py     the structured PipelineReport
   |
   |-- app/ingestion/csv_reader.py   extraction and file validation
   |-- app/profiling/                profile
   |-- app/quality/                  rule engine and the six rules
   '-- app/models  -> PostgreSQL     (schema versioned in migrations/)

Command line (app/cli.py) -> app/processing   (no web app, no database)
```

## Why the processing core is separate

The same code answers three callers: the web app (through the services), the command line, and the unit tests. Because it has no web or database dependency, it can be tested in milliseconds and run anywhere. The services add only what needs a database: ownership, saving, and loading.

## Request flow

1. The browser sends the session cookie with every call.
2. `get_current_user` hashes the cookie token and looks up an unexpired session. No match means 401.
3. Routes look up data through the logged-in user (`get_dataset_or_404(db, dataset_id, user)`), so another user's id is a 404.
4. The frontend turns any 401 on a data call into a redirect to the login screen.

## A run, step by step

1. **Extract:** read and validate the uploaded bytes. Failure here saves nothing.
2. **Check the configuration:** rules and key columns are validated before any data is saved. Failure here saves nothing.
3. **Save** the dataset (with its owner), profile and rules in one commit.
4. **Start the run** as `FAILED`, so an interrupted run never looks successful.
5. **Validate:** run the enabled rules. Each rule reports which rows it rejects.
6. **Account:** valid and rejected rows are counted once per row, from one shared function.
7. **Load** (only if the dataset has key columns and no schema check failed): upsert the valid rows.
8. **Record** the results, the metrics and the final status in one commit. Steps 5 to 8 are one transaction, so a failure in any of them, including the load, rolls all of it back.

Run statuses: `SUCCESS` (all checks passed), `COMPLETED_WITH_ISSUES` (the run finished and at least one check failed), `FAILED` (an exception stopped the run; the stored message is generic, details go to the server log). A failed check is not a failed run. A `FAILED` run stores `NULL` for every number it never measured.

## Rule engine

Each rule is a class with `validate_config()` and `evaluate(df)`. `registry.py` maps a stored `rule_type` to its class. Invalid configs raise `ConfigurationError` when the rule is built. A problem found only at run time (for example a missing column) becomes a visible schema FAIL starting with "Configuration error:". A rule that crashes becomes a failed check, never a silent skip. To add a rule type: write one class and add it to `RULE_TYPES`.

## Errors

Every API error uses `{"error": {"code", "message", "details"}}`. Unexpected exceptions return a generic 500 with no traceback or paths.

## Design choices

- **Rows are not stored by default.** They are processed in memory and discarded. Loading is opt-in per dataset, with explicit key columns.
- Because the file is not kept, **every new run needs a freshly uploaded file**. Its SHA-256 is stored so a re-upload of the same file can be recognised.
- The first duplicate of a key wins, both in the `duplicates` rule and when loading.
- The database enforces the invariants too (constraints), so a bug in the code cannot quietly store inconsistent numbers.
- The dashboard uses `GET /runs` plus the failing runs' reports, so it makes a small, fixed number of requests.
- Tests override the database dependency with `dataguard_test`.
