"""
Phase 2 - Profiling: scan every raw.* table and report nulls, duplicates, and
dtype issues BEFORE any cleaning happens. This is a read-only diagnostic step —
it writes a markdown report to /docs/data_quality_notes.md and touches nothing
in the database.

Usage:
    python transform/profile_raw_tables.py
"""
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from sqlalchemy import inspect

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "data_quality_notes.md"


def profile_table(engine, table_name: str) -> dict:
    df = pd.read_sql_table(table_name, engine, schema="raw")

    n_rows = len(df)
    n_dupes = df.duplicated().sum()

    null_counts = df.isnull().sum()
    null_pct = (null_counts / n_rows * 100).round(2) if n_rows else null_counts

    null_summary = pd.DataFrame({
        "null_count": null_counts,
        "null_pct": null_pct,
        "dtype": df.dtypes.astype(str),
    })
    null_summary = null_summary[null_summary["null_count"] > 0].sort_values(
        "null_count", ascending=False
    )

    return {
        "table": table_name,
        "n_rows": n_rows,
        "n_cols": df.shape[1],
        "n_duplicate_rows": int(n_dupes),
        "null_summary": null_summary,
        "dtypes": df.dtypes.astype(str),
    }


def render_report(profiles: list[dict]) -> str:
    lines = [
        "# Data Quality Notes — Raw Tables",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Profiling run against `raw.*` staging tables, before any cleaning or "
        "transformation. Purpose: surface nulls, duplicates, and dtype issues "
        "that Phase 2's cleaning scripts need to handle.",
        "",
        "## Summary",
        "",
        "| Table | Rows | Cols | Duplicate Rows | Columns with Nulls |",
        "|---|---|---|---|---|",
    ]
    for p in profiles:
        lines.append(
            f"| raw.{p['table']} | {p['n_rows']:,} | {p['n_cols']} | "
            f"{p['n_duplicate_rows']:,} | {len(p['null_summary'])} |"
        )

    lines.append("")
    lines.append("## Detail by table")

    for p in profiles:
        lines.append("")
        lines.append(f"### raw.{p['table']}")
        lines.append("")
        lines.append(f"- Rows: {p['n_rows']:,} | Columns: {p['n_cols']} | Duplicate rows: {p['n_duplicate_rows']:,}")

        if p["null_summary"].empty:
            lines.append("- No nulls found in any column.")
        else:
            lines.append("")
            lines.append("| Column | Null Count | Null % | Dtype |")
            lines.append("|---|---|---|---|")
            for col, row in p["null_summary"].iterrows():
                lines.append(
                    f"| {col} | {int(row['null_count']):,} | {row['null_pct']}% | {row['dtype']} |"
                )

    lines.append("")
    lines.append("## Notes for Phase 2 cleaning")
    lines.append("")
    lines.append("- (fill in manually after reviewing the tables above — e.g. which "
                  "nulls are expected/acceptable vs. which need imputation or filtering, "
                  "any dtype casts needed before joining, dedupe strategy per table)")

    return "\n".join(lines)


def main() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names(schema="raw"))

    if not table_names:
        print("No tables found in 'raw' schema. Run the ingestion scripts first.")
        return

    print(f"Profiling {len(table_names)} tables in 'raw' schema...\n")

    profiles = []
    for table_name in table_names:
        print(f"  Profiling raw.{table_name} ...")
        profiles.append(profile_table(engine, table_name))

    report = render_report(profiles)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report)

    print(f"\nDone. Report written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
