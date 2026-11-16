"""Measure the pipeline on generated CSV files of different sizes.

Usage (project root, venv active):
    python -m scripts.benchmark                  # 10k, 100k and 1M rows
    python -m scripts.benchmark --rows 50000     # one or more sizes
    python -m scripts.benchmark --json           # machine-readable output

Each size runs in a fresh child process, so peak memory is not polluted by the
previous size. The data is generated before the child starts and is not part of
the measurement. Numbers are from THIS machine only: they say how the pipeline
behaves here, not how it would behave in production.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_SIZES = (10_000, 100_000, 1_000_000)
ROOT = Path(__file__).resolve().parent.parent

RULES = [
    {"name": "columns", "rule_type": "required_columns", "severity": "HIGH",
     "configuration": {"columns": ["customer_id", "age", "status", "signup_date", "city", "balance"]}},
    {"name": "id filled", "rule_type": "required_values", "severity": "HIGH",
     "configuration": {"columns": ["customer_id"]}},
    {"name": "id unique", "rule_type": "duplicates", "severity": "HIGH",
     "configuration": {"columns": ["customer_id"]}},
    {"name": "age in range", "rule_type": "numeric_range", "severity": "MEDIUM",
     "configuration": {"column": "age", "min": 0, "max": 120}},
    {"name": "age is integer", "rule_type": "data_type", "severity": "MEDIUM",
     "configuration": {"column": "age", "data_type": "integer"}},
    {"name": "status allowed", "rule_type": "allowed_values", "severity": "LOW",
     "configuration": {"column": "status", "allowed": ["Active", "Inactive", "Pending"]}},
    {"name": "signup is a date", "rule_type": "data_type", "severity": "LOW",
     "configuration": {"column": "signup_date", "data_type": "date"}},
]


def generate_csv(path: Path, rows: int, seed: int = 42) -> None:
    """A synthetic customer file with problems planted at known rates."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)

    def chance(rate):
        return rng.random(rows) < rate

    ids = np.array([f"C{i:09d}" for i in range(rows)], dtype=object)
    duplicate = chance(0.005)
    ids[duplicate] = ids[np.maximum(np.nonzero(duplicate)[0] - 1, 0)]  # repeat the previous id
    ids[chance(0.01)] = ""                                              # 1% blank ids

    age = rng.integers(18, 90, rows).astype(str).astype(object)
    age[chance(0.005)] = "-5"
    age[chance(0.005)] = "abc"

    status = rng.choice(["Active", "Inactive", "Pending"], rows).astype(object)
    status[chance(0.005)] = "UNKNOWN"

    days = pd.to_timedelta(rng.integers(0, 1800, rows), unit="D")
    signup = np.asarray((pd.Timestamp("2020-01-01") + days).strftime("%Y-%m-%d"), dtype=object)
    signup[chance(0.005)] = "not-a-date"

    frame = pd.DataFrame({
        "customer_id": ids,
        "age": age,
        "status": status,
        "signup_date": signup,
        "city": rng.choice(["Bhopal", "Delhi", "Mumbai", "Chennai", "Pune"], rows),
        "balance": np.round(rng.random(rows) * 10000, 2).astype(str),
    })
    frame.to_csv(path, index=False)


def peak_memory_mb() -> float | None:
    """Peak resident memory of this process in MB, or None if it cannot be read."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
            return round(counters.PeakWorkingSetSize / 1e6, 1) if ok else None
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / 1e6 if sys.platform == "darwin" else peak / 1e3, 1)
    except Exception:
        return None


def run_child(path: Path) -> None:
    """Run the pipeline once on a file and print one JSON line."""
    from app.processing.runner import run_pipeline

    baseline = peak_memory_mb()  # the interpreter plus pandas, before any data is read
    report = run_pipeline(path, RULES, max_bytes=10**12)
    peak = peak_memory_mb()
    print(json.dumps({
        "status": report.status,
        "rows": report.source_rows,
        "columns": report.source_columns,
        "valid_rows": report.valid_rows,
        "rejected_rows": report.rejected_rows,
        "duplicate_rows": report.duplicate_rows,
        "file_mb": round(path.stat().st_size / 1e6, 1),
        "timings_ms": report.timings_ms,
        "duration_ms": report.duration_ms,
        "baseline_memory_mb": baseline,
        "peak_memory_mb": peak,
        "error": report.error,
    }))


def measure(rows: int) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"bench_{rows}.csv"
        generate_csv(path, rows)
        done = subprocess.run(
            [sys.executable, "-m", "scripts.benchmark", "--child", str(path)],
            cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True,
        )
    if done.returncode != 0 or not done.stdout.strip():
        raise SystemExit(f"Benchmark child failed for {rows} rows:\n{done.stderr[-800:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the DataGuard pipeline.")
    parser.add_argument("--rows", type=int, nargs="+", help="row counts to test")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument("--child", metavar="FILE", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.child:
        run_child(Path(args.child))
        return

    import pandas as pd

    results = [measure(n) for n in (args.rows or DEFAULT_SIZES)]
    environment = {
        "python": platform.python_version(), "pandas": pd.__version__,
        "system": f"{platform.system()} {platform.release()}", "cpu_count": os.cpu_count(),
    }
    if args.json:
        print(json.dumps({"environment": environment, "results": results}, indent=2))
        return

    print(f"Python {environment['python']}, pandas {environment['pandas']}, "
          f"{environment['system']}, {environment['cpu_count']} CPUs\n")
    print("| rows | file MB | extract s | profile s | validate s | total s | rows/s | peak MB | valid | rejected |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        if r["error"]:
            print(f"| {r['rows']} | pipeline FAILED: {r['error']['code']} |")
            continue
        t = r["timings_ms"]
        total = r["duration_ms"] / 1000
        print(f"| {r['rows']:,} | {r['file_mb']} | {t['extract'] / 1000:.2f} | {t['profile'] / 1000:.2f} | "
              f"{t['validate'] / 1000:.2f} | {total:.2f} | {r['rows'] / total:,.0f} | "
              f"{r['peak_memory_mb']} | {r['valid_rows']:,} | {r['rejected_rows']:,} |")
    print("\nPeak MB is the whole process (including the interpreter and pandas, about "
          f"{results[0]['baseline_memory_mb']} MB before reading any data).")


if __name__ == "__main__":
    main()
