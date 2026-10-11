import json

from app.connectors.csv_connector import CsvConnector
from app.profiling.profiler import profile_dataframe

for rel in ["insurance/policies_bad.csv", "weather/weather_bad.csv"]:
    df = CsvConnector(rel).read()
    snapshot = df.copy()
    profile = profile_dataframe(df)
    print("\n==", rel)
    print("rows:", profile["row_count"], "cols:", profile["column_count"],
          "duplicates:", profile["duplicate_row_count"])
    print("input unchanged:", df.equals(snapshot))
    for c in profile["columns"]:
        print(f'{c["name"]:<18} {c["inferred_type"]:<8} '
              f'nulls={c["null_count"]} distinct={c["distinct_count"]} '
              f'min={c["min"]} max={c["max"]}')
    json.dumps(profile, allow_nan=False)
    print("JSON-safe: yes")