# Architecture

```
Browser (HTML/CSS/JS)
   |  fetch()
FastAPI routes (app/api)        thin: validate input, call a service, shape output
   |
Pipeline service (app/services/pipeline.py)
   |-- read_csv_bytes   (app/ingestion)   validate and parse in memory
   |-- profile_dataframe (app/profiling)  profile
   |-- run_rules        (app/quality)     rule engine + registry
   '-- SQLAlchemy models (app/models)  -> PostgreSQL
```

## Pipeline

1. Read and validate the uploaded bytes. Failure here saves nothing.
2. Validate any rule configs. Failure here saves nothing.
3. Save dataset, profile and rules in one commit.
4. Create a run row that starts as `FAILED`, so an interrupted run never looks successful.
5. Run enabled rules, then save all results and the final status in one commit.

Run statuses: `SUCCESS` (all checks passed), `COMPLETED_WITH_ISSUES` (at least one check failed), `FAILED` (an exception stopped the run; the stored message is generic, details go to the server log). A failed check is not a failed run.

## Rule engine

Each rule is a class with `validate_config()` and `evaluate(df)`. `registry.py` maps a stored `rule_type` to its class. Invalid configs raise `ConfigurationError` when the rule is built. A problem found only at run time (for example a missing column) becomes a visible FAIL starting with "Configuration error:". To add a rule type: write one class and add it to `RULE_TYPES`.

## Errors

Every API error uses `{"error": {"code", "message", "details"}}`. Unexpected exceptions return a generic 500 with no traceback or paths.

## Design choices

- CSV rows are processed in memory and discarded. Only metadata, profiles, rules and results are stored.
- Because rows are not kept, **every new run needs a freshly uploaded file**.
- The dashboard builds its summary from existing endpoints (no stats endpoint), so it looks at the 10 most recent datasets.
- Tests override the database dependency with `dataguard_test`.