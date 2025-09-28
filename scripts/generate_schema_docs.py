#!/usr/bin/env python3
"""
Database Schema Documentation Generator

This script generates comprehensive documentation about the SQLite database schema,
including table structures, indexes, views, and sample data.

Usage:
    python scripts/generate_schema_docs.py --db output/kanjidic2.sqlite --output docs/
"""
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any


def get_table_info(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Get detailed information about all tables."""
    tables = {}

    # Get all table names
    table_names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]

    for table_name in table_names:
        # Get column information
        columns = []
        for row in conn.execute(f"PRAGMA table_info({table_name})"):
            cid, name, type_, notnull, default, pk = row
            columns.append(
                {
                    "name": name,
                    "type": type_,
                    "not_null": bool(notnull),
                    "default": default,
                    "primary_key": bool(pk),
                }
            )

        # Get row count
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # Get sample data (first 3 rows)
        sample_data = []
        for row in conn.execute(f"SELECT * FROM {table_name} LIMIT 3"):
            sample_data.append(list(row))

        tables[table_name] = {
            "columns": columns,
            "row_count": row_count,
            "sample_data": sample_data,
        }

    return tables


def get_view_info(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Get information about database views."""
    views = {}

    # Get all view names and SQL
    for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
    ):
        view_name, view_sql = row

        # Get row count
        row_count = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]

        # Get column names
        cursor = conn.execute(f"SELECT * FROM {view_name} LIMIT 1")
        column_names = [description[0] for description in cursor.description]

        # Get sample data
        sample_data = []
        for row in conn.execute(f"SELECT * FROM {view_name} LIMIT 3"):
            sample_data.append(list(row))

        views[view_name] = {
            "sql": view_sql,
            "columns": column_names,
            "row_count": row_count,
            "sample_data": sample_data,
        }

    return views


def get_index_info(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Get information about database indexes."""
    indexes = {}

    # Get all indexes
    for row in conn.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name, name"
    ):
        index_name, table_name, index_sql = row

        if table_name not in indexes:
            indexes[table_name] = []

        indexes[table_name].append({"name": index_name, "sql": index_sql})

    return indexes


def generate_markdown_docs(tables: Dict, views: Dict, indexes: Dict, output_dir: Path):
    """Generate comprehensive Markdown documentation."""

    # Main schema documentation
    schema_doc = output_dir / "DATABASE_SCHEMA.md"
    with open(schema_doc, "w", encoding="utf-8") as f:
        f.write("# KANJIDIC2 SQLite Database Schema\n\n")
        f.write(
            "This document provides comprehensive documentation of the database structure.\n\n"
        )

        # Tables section
        f.write("## Tables\n\n")
        for table_name, table_info in tables.items():
            f.write(f"### {table_name}\n\n")
            f.write(f"**Row Count**: {table_info['row_count']:,}\n\n")

            # Columns table
            f.write("| Column | Type | Not Null | Default | Primary Key |\n")
            f.write("|--------|------|----------|---------|-------------|\n")
            for col in table_info["columns"]:
                f.write(
                    f"| {col['name']} | {col['type']} | {col['not_null']} | {col['default'] or 'NULL'} | {col['primary_key']} |\n"
                )

            f.write("\n")

            # Sample data
            if table_info["sample_data"]:
                f.write("**Sample Data**:\n```\n")
                col_names = [col["name"] for col in table_info["columns"]]
                f.write(" | ".join(col_names) + "\n")
                f.write("-" * (len(" | ".join(col_names)) + 10) + "\n")
                for row in table_info["sample_data"]:
                    row_str = " | ".join(
                        str(cell)[:50] if cell else "NULL" for cell in row
                    )
                    f.write(row_str + "\n")
                f.write("```\n\n")

        # Views section
        if views:
            f.write("## Views\n\n")
            for view_name, view_info in views.items():
                f.write(f"### {view_name}\n\n")
                f.write(f"**Row Count**: {view_info['row_count']:,}\n\n")
                f.write(f"**Columns**: {', '.join(view_info['columns'])}\n\n")
                f.write("**SQL Definition**:\n```sql\n")
                f.write(view_info["sql"] + "\n")
                f.write("```\n\n")

                # Sample data
                if view_info["sample_data"]:
                    f.write("**Sample Data**:\n```\n")
                    f.write(" | ".join(view_info["columns"]) + "\n")
                    f.write("-" * (len(" | ".join(view_info["columns"])) + 10) + "\n")
                    for row in view_info["sample_data"]:
                        row_str = " | ".join(
                            str(cell)[:50] if cell else "NULL" for cell in row
                        )
                        f.write(row_str + "\n")
                    f.write("```\n\n")

        # Indexes section
        if indexes:
            f.write("## Indexes\n\n")
            for table_name, table_indexes in indexes.items():
                f.write(f"### {table_name}\n\n")
                for idx in table_indexes:
                    f.write(f"**{idx['name']}**:\n```sql\n{idx['sql']}\n```\n\n")


def generate_json_schema(tables: Dict, views: Dict, output_dir: Path):
    """Generate machine-readable JSON schema."""
    schema = {
        "database": "kanjidic2.sqlite",
        "generated": "Auto-generated schema documentation",
        "tables": tables,
        "views": views,
    }

    schema_file = output_dir / "schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)


def generate_sql_examples(conn: sqlite3.Connection, output_dir: Path):
    """Generate practical SQL examples file."""
    examples_file = output_dir / "SQL_EXAMPLES.md"

    with open(examples_file, "w", encoding="utf-8") as f:
        f.write("# KANJIDIC2 Database SQL Examples\n\n")
        f.write("Practical SQL queries for common kanji database operations.\n\n")

        examples = [
            {
                "title": "Basic Kanji Lookup",
                "description": "Find kanji with meanings and readings",
                "sql": """-- Find kanji with English meanings containing 'water'
SELECT DISTINCT k.literal, k.freq, k.grade
FROM kanji k
JOIN kanji_meaning km ON k.literal = km.literal
WHERE km.lang = 'en' AND km.meaning LIKE '%water%'
ORDER BY k.freq;""",
            },
            {
                "title": "Frequency Analysis",
                "description": "Most common kanji by frequency rank",
                "sql": """-- Top 20 most frequent kanji with meanings
SELECT k.literal, k.freq,
       GROUP_CONCAT(DISTINCT km.meaning, '; ') as meanings
FROM kanji k
LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
WHERE k.freq IS NOT NULL
GROUP BY k.literal
ORDER BY k.freq
LIMIT 20;""",
            },
            {
                "title": "Reading Patterns",
                "description": "Find kanji by reading patterns",
                "sql": """-- Find kanji with kun reading containing 'mizu'
SELECT DISTINCT k.literal, kr.reading, k.freq
FROM kanji k
JOIN kanji_reading kr ON k.literal = kr.literal
WHERE kr.type = 'kun' AND kr.reading LIKE '%みず%'
ORDER BY k.freq;""",
            },
            {
                "title": "Educational Levels",
                "description": "Kanji by school grade levels",
                "sql": """-- Count kanji by grade level
SELECT
    CASE
        WHEN grade IS NULL THEN 'Not in school curriculum'
        ELSE 'Grade ' || grade
    END as level,
    COUNT(*) as kanji_count
FROM kanji
GROUP BY grade
ORDER BY grade;""",
            },
            {
                "title": "JLPT Levels",
                "description": "Kanji by JLPT difficulty levels",
                "sql": """-- Kanji distribution by JLPT level
SELECT
    CASE
        WHEN jlpt IS NULL THEN 'Not in JLPT'
        ELSE 'N' || jlpt
    END as jlpt_level,
    COUNT(*) as kanji_count
FROM kanji
GROUP BY jlpt
ORDER BY jlpt;""",
            },
        ]

        for example in examples:
            f.write(f"## {example['title']}\n\n")
            f.write(f"{example['description']}\n\n")
            f.write("```sql\n")
            f.write(example["sql"])
            f.write("\n```\n\n")

            # Execute and show sample results
            try:
                cursor = conn.execute(example["sql"])
                rows = cursor.fetchmany(5)  # Show first 5 results
                if rows:
                    f.write("**Sample Results**:\n```\n")
                    # Get column names
                    col_names = [description[0] for description in cursor.description]
                    f.write(" | ".join(col_names) + "\n")
                    f.write("-" * (len(" | ".join(col_names)) + 10) + "\n")
                    for row in rows:
                        row_str = " | ".join(
                            str(cell) if cell is not None else "NULL" for cell in row
                        )
                        f.write(row_str + "\n")
                    f.write("```\n\n")
            except Exception as e:
                f.write(f"_Error executing example: {e}_\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate database schema documentation"
    )
    parser.add_argument("--db", "-d", required=True, help="SQLite database path")
    parser.add_argument("--output", "-o", default="docs", help="Output directory")

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)

    print("Analyzing database schema...")
    tables = get_table_info(conn)
    views = get_view_info(conn)
    indexes = get_index_info(conn)

    print("Generating documentation...")
    generate_markdown_docs(tables, views, indexes, output_dir)
    generate_json_schema(tables, views, output_dir)
    generate_sql_examples(conn, output_dir)

    conn.close()

    print(f"✅ Documentation generated in {output_dir}/")
    print("Generated files:")
    print("  - DATABASE_SCHEMA.md - Comprehensive schema documentation")
    print("  - SQL_EXAMPLES.md - Practical SQL query examples")
    print("  - schema.json - Machine-readable schema definition")


if __name__ == "__main__":
    main()
