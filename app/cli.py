"""Command-line entry point: run the pipeline on a CSV file without the web app.

    python -m app.cli run data.csv --rules rules.json
    python -m app.cli run data.csv --rules rules.json --json
    python -m app.cli run data.csv --output report.json

Exit codes (so scripts and CI can react):
    0  SUCCESS                 every check passed
    1  COMPLETED_WITH_ISSUES   the run finished and at least one check failed
    2  FAILED                  the run could not complete (bad file, bad rules, error)

The command needs no database. It reads and checks the file and prints a report.
"""
import argparse
import json
import sys
from pathlib import Path

from app.processing.report import PipelineReport
from app.processing.runner import DEFAULT_MAX_REJECTED_LISTED, run_pipeline

EXIT_CODES = {"SUCCESS": 0, "COMPLETED_WITH_ISSUES": 1, "FAILED": 2}


class CliError(Exception):
    """A problem with the command line itself (not with the data)."""


def load_rules(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        raise CliError(f"The rules file '{path.name}' could not be read.") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise CliError(f"The rules file '{path.name}' is not valid JSON.") from None
    if not isinstance(data, list):
        raise CliError("The rules file must contain a JSON list of rule objects.")
    return data


def format_report(report: PipelineReport, show_rejected: int) -> str:
    lines = [
        "DataGuard pipeline report",
        f"  run id   : {report.run_id}",
        f"  file     : {report.source_file}",
        f"  status   : {report.status}",
    ]
    if report.error:
        lines.append(f"  error    : [{report.error['code']}] {report.error['message']}")
        lines.append(f"  duration : {report.duration_ms} ms")
        return "\n".join(lines)

    timings = ", ".join(f"{name} {value}" for name, value in report.timings_ms.items())
    lines += [
        f"  rows     : {report.source_rows} read, {report.valid_rows} valid, "
        f"{report.rejected_rows} rejected",
        f"             (duplicate extra copies {report.duplicate_rows}, rows failing several rules counted once: {report.overlap_rows})",
        f"  rules    : {report.rules_executed} run, {report.rules_passed} passed, "
        f"{report.rules_failed} failed (schema {report.schema_failures}, quality {report.quality_failures})",
        f"  loadable : {'yes' if report.loadable else 'no (a schema check failed)'}",
        f"  duration : {report.duration_ms} ms ({timings})",
        "",
        "Rules",
    ]
    for rule in report.rules:
        lines.append(
            f"  {rule.status:<4} {rule.severity:<6} {rule.category:<7} {rule.name}: {rule.message}"
        )
    if report.rejected_sample and show_rejected > 0:
        shown = report.rejected_sample[:show_rejected]
        lines += ["", f"Rejected rows (first {len(shown)}; data row 1 is the first row after the header)"]
        for row in shown:
            columns = ", ".join(row.columns) or "all columns"
            lines.append(f"  data row {row.data_row}: {row.rule} - {row.reason} [{columns}]")
        if report.rejected_sample_truncated or len(report.rejected_sample) > len(shown):
            lines.append("  ... more rejections exist; use --json or --output for the full sample")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Run the DataGuard pipeline on a CSV file (no database needed).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="profile and validate a CSV file")
    run.add_argument("csv_file", help="path to the CSV file")
    run.add_argument("--rules", metavar="FILE", help="JSON file with a list of rules")
    run.add_argument("--json", action="store_true", help="print the full report as JSON")
    run.add_argument("--output", metavar="FILE", help="also write the full JSON report to FILE")
    run.add_argument(
        "--show-rejected", type=int, default=10, metavar="N",
        help="rejected rows to print in the text report (default 10)",
    )
    run.add_argument(
        "--max-rejected", type=int, default=DEFAULT_MAX_REJECTED_LISTED, metavar="N",
        help="rejected rows kept in the report sample (default %(default)s)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # never crash on an odd character in a name

    try:
        rules = load_rules(Path(args.rules)) if args.rules else []
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_CODES["FAILED"]

    report = run_pipeline(args.csv_file, rules, max_rejected_listed=max(args.max_rejected, 0))

    if args.output:
        try:
            Path(args.output).write_text(
                json.dumps(report.to_dict(), indent=2, allow_nan=False), encoding="utf-8"
            )
        except OSError:
            print("Error: the output file could not be written.", file=sys.stderr)
            return EXIT_CODES["FAILED"]

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, allow_nan=False))
    else:
        print(format_report(report, max(args.show_rejected, 0)))
    return EXIT_CODES[report.status]


if __name__ == "__main__":
    sys.exit(main())
