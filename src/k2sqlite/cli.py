from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from .builder import build_sqlite


def export_data(
    db_path: Path, view: str, format: str, output_path: Path | None, limit: int | None
):
    """Export data from database view to CSV or JSON."""
    import sys

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = f"SELECT * FROM {view}"
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query)
    rows = cursor.fetchall()

    if format == "csv":
        import csv

        output = (
            sys.stdout
            if output_path is None
            else open(output_path, "w", newline="", encoding="utf-8")
        )

        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

        if output_path:
            output.close()
            print(f"Exported {len(rows)} records to {output_path}")

    elif format == "json":
        data = [dict(row) for row in rows]
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        if output_path:
            output_path.write_text(json_str, encoding="utf-8")
            print(f"Exported {len(rows)} records to {output_path}")
        else:
            print(json_str)

    conn.close()


def app():
    ap = argparse.ArgumentParser(prog="k2sqlite")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_build = sub.add_parser("build", help="Build SQLite from KANJIDIC2.xml")
    ap_build.add_argument("--input", "-i", type=Path, required=True)
    ap_build.add_argument("--db", "-o", type=Path, required=True)
    ap_build.add_argument("--batch", "-b", type=int, default=500)

    ap_export = sub.add_parser("export", help="Export data from SQLite to CSV/JSON")
    ap_export.add_argument(
        "--db", "-d", type=Path, required=True, help="SQLite database path"
    )
    ap_export.add_argument(
        "--view",
        "-v",
        choices=["kanji_seed", "kanji_priority"],
        default="kanji_seed",
        help="View to export",
    )
    ap_export.add_argument(
        "--format", "-f", choices=["csv", "json"], default="csv", help="Export format"
    )
    ap_export.add_argument(
        "--output", "-o", type=Path, help="Output file (default: stdout)"
    )
    ap_export.add_argument("--limit", "-l", type=int, help="Limit number of records")

    args = ap.parse_args()
    if args.cmd == "build":
        total = build_sqlite(args.input, args.db, batch_size=args.batch)
        print(f"Inserted {total} characters into {args.db}")
    elif args.cmd == "export":
        export_data(args.db, args.view, args.format, args.output, args.limit)
