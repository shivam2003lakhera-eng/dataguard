# Usage

## Upload

Open the app, choose **Upload**, enter a name, pick a CSV, and optionally paste rules as JSON:

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

## Running again

Open **Run history** and upload a CSV. It is checked against the dataset's enabled rules.

**Input strategy:** V1 does not store CSV rows, so `POST /api/v1/datasets/{id}/runs` always needs a newly uploaded file.

## Notes on behavior

- A numeric range ignores text such as `abc`; use a `data_type` rule to catch it.
- Dates are recognised only in strict ISO form (`2025-01-31` or `2025-01-31T10:00:00`).
- Uploads over `MAX_FILE_SIZE_MB` (default 50) are rejected.

## Demo workflow

1. Upload `sample_data/insurance/policies_bad.csv` with no rules.
2. Open **Manage rules** and add: no missing values on `policy_id` (HIGH), numeric range on `premium` minimum 0, allowed values on `policy_status` (`ACTIVE, EXPIRED, PENDING`).
3. Open **Run history**, upload the same file, and read the report (3 failures).
4. Check the Dashboard.