#!/usr/bin/env python3
"""
Specialized Lookup Generator for Kanji Applications

Generates optimized lookup files for specific use cases like:
- Grade-level kanji sets
- JLPT-level kanji sets
- Frequency-based kanji sets
- Reading pattern lookups

Usage:
    python scripts/generate_lookups.py --db output/kanjidic2.sqlite --output lookups/
"""
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List


def generate_grade_lookups(conn: sqlite3.Connection, output_dir: Path):
    """Generate kanji sets by school grade level."""
    grades_dir = output_dir / "grades"
    grades_dir.mkdir(parents=True, exist_ok=True)

    # Get kanji by grade
    grade_query = """
    SELECT k.literal, k.freq,
           GROUP_CONCAT(DISTINCT km.meaning, ';') as meanings,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun_readings,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on_readings
    FROM kanji k
    LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
    LEFT JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE k.grade = ?
    GROUP BY k.literal
    ORDER BY k.freq
    """

    all_grades = {}
    for grade in range(1, 7):
        kanji_list = []
        for row in conn.execute(grade_query, (grade,)):
            literal, freq, meanings, kun_readings, on_readings = row
            kanji_list.append(
                {
                    "kanji": literal,
                    "freq": freq,
                    "meanings": [
                        m.strip() for m in (meanings or "").split(";") if m.strip()
                    ],
                    "kun_readings": [
                        r.strip() for r in (kun_readings or "").split(";") if r.strip()
                    ],
                    "on_readings": [
                        r.strip() for r in (on_readings or "").split(";") if r.strip()
                    ],
                }
            )

        # Save individual grade file
        with open(grades_dir / f"grade_{grade}.json", "w", encoding="utf-8") as f:
            json.dump(
                {"grade": grade, "count": len(kanji_list), "kanji": kanji_list},
                f,
                ensure_ascii=False,
                indent=2,
            )

        all_grades[f"grade_{grade}"] = kanji_list
        print(f"Grade {grade}: {len(kanji_list)} kanji")

    # Save combined grades file
    with open(grades_dir / "all_grades.json", "w", encoding="utf-8") as f:
        json.dump(all_grades, f, ensure_ascii=False, indent=2)


def generate_jlpt_lookups(conn: sqlite3.Connection, output_dir: Path):
    """Generate kanji sets by JLPT level."""
    jlpt_dir = output_dir / "jlpt"
    jlpt_dir.mkdir(parents=True, exist_ok=True)

    jlpt_query = """
    SELECT k.literal, k.freq,
           GROUP_CONCAT(DISTINCT km.meaning, ';') as meanings,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on
    FROM kanji k
    LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
    LEFT JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE k.jlpt = ?
    GROUP BY k.literal
    ORDER BY k.freq
    """

    all_jlpt = {}
    for level in [1, 2, 3, 4, 5]:  # N5 to N1
        kanji_list = []
        for row in conn.execute(jlpt_query, (level,)):
            literal, freq, meanings, kun, on = row
            kanji_list.append(
                {
                    "kanji": literal,
                    "freq": freq,
                    "meanings": [
                        m.strip() for m in (meanings or "").split(";") if m.strip()
                    ],
                    "kun_readings": [
                        r.strip() for r in (kun or "").split(";") if r.strip()
                    ],
                    "on_readings": [
                        r.strip() for r in (on or "").split(";") if r.strip()
                    ],
                }
            )

        # Save individual JLPT file
        with open(jlpt_dir / f"N{level}.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "jlpt_level": f"N{level}",
                    "count": len(kanji_list),
                    "kanji": kanji_list,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        all_jlpt[f"N{level}"] = kanji_list
        print(f"JLPT N{level}: {len(kanji_list)} kanji")

    # Save combined JLPT file
    with open(jlpt_dir / "all_jlpt.json", "w", encoding="utf-8") as f:
        json.dump(all_jlpt, f, ensure_ascii=False, indent=2)


def generate_frequency_lookups(conn: sqlite3.Connection, output_dir: Path):
    """Generate frequency-based kanji sets."""
    freq_dir = output_dir / "frequency"
    freq_dir.mkdir(parents=True, exist_ok=True)

    # Different frequency tiers
    tiers = [(100, "top_100"), (500, "top_500"), (1000, "top_1000"), (2000, "top_2000")]

    freq_query = """
    SELECT k.literal, k.freq, k.grade, k.jlpt, k.stroke_count,
           GROUP_CONCAT(DISTINCT km.meaning, ';') as meanings,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun,
           GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on
    FROM kanji k
    LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
    LEFT JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE k.freq IS NOT NULL AND k.freq <= ?
    GROUP BY k.literal
    ORDER BY k.freq
    """

    for limit, filename in tiers:
        kanji_list = []
        for row in conn.execute(freq_query, (limit,)):
            literal, freq, grade, jlpt, strokes, meanings, kun, on = row
            kanji_list.append(
                {
                    "kanji": literal,
                    "freq": freq,
                    "grade": grade,
                    "jlpt": jlpt,
                    "stroke_count": strokes,
                    "meanings": [
                        m.strip() for m in (meanings or "").split(";") if m.strip()
                    ],
                    "kun_readings": [
                        r.strip() for r in (kun or "").split(";") if r.strip()
                    ],
                    "on_readings": [
                        r.strip() for r in (on or "").split(";") if r.strip()
                    ],
                }
            )

        with open(freq_dir / f"{filename}.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "frequency_limit": limit,
                    "count": len(kanji_list),
                    "kanji": kanji_list,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"Frequency top {limit}: {len(kanji_list)} kanji")


def generate_reading_patterns(conn: sqlite3.Connection, output_dir: Path):
    """Generate reading pattern lookups."""
    reading_dir = output_dir / "readings"
    reading_dir.mkdir(parents=True, exist_ok=True)

    # Common reading patterns
    patterns = {
        "single_syllable_kun": "LENGTH(kr.reading) <= 3 AND kr.type = 'kun'",
        "long_kun_readings": "LENGTH(kr.reading) > 6 AND kr.type = 'kun'",
        "single_on_reading": "kr.type = 'on'",
        "multiple_readings": "1=1",  # Will filter this differently
    }

    base_query = """
    SELECT DISTINCT k.literal, kr.reading, kr.type, k.freq
    FROM kanji k
    JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE {}
    ORDER BY k.freq
    """

    for pattern_name, condition in patterns.items():
        if pattern_name == "multiple_readings":
            # Special case: kanji with multiple readings
            multi_query = """
            SELECT k.literal, k.freq,
                   GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun,
                   GROUP_CONCAT(DISTINCT CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on
            FROM kanji k
            JOIN kanji_reading kr ON k.literal = kr.literal
            GROUP BY k.literal
            HAVING COUNT(DISTINCT kr.reading) > 3
            ORDER BY k.freq
            LIMIT 200
            """

            results = []
            for row in conn.execute(multi_query):
                literal, freq, kun, on = row
                kun_list = [r.strip() for r in (kun or "").split(";") if r.strip()]
                on_list = [r.strip() for r in (on or "").split(";") if r.strip()]
                total_readings = len(kun_list) + len(on_list)

                results.append(
                    {
                        "kanji": literal,
                        "freq": freq,
                        "kun_readings": kun_list,
                        "on_readings": on_list,
                        "total_readings": total_readings,
                    }
                )
        else:
            results = []
            for row in conn.execute(base_query.format(condition)):
                literal, reading, reading_type, freq = row
                results.append(
                    {
                        "kanji": literal,
                        "reading": reading,
                        "type": reading_type,
                        "freq": freq,
                    }
                )

        with open(reading_dir / f"{pattern_name}.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "pattern": pattern_name,
                    "count": len(results),
                    "kanji": results[:200],  # Limit to 200 for file size
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"Reading pattern '{pattern_name}': {len(results)} matches")


def generate_manifest(output_dir: Path):
    """Generate manifest of all lookup files."""
    manifest = {
        "generated": "Kanji lookup files",
        "categories": {
            "grades": "Kanji by school grade levels (1-6)",
            "jlpt": "Kanji by JLPT levels (N5-N1)",
            "frequency": "Kanji by frequency rankings",
            "readings": "Kanji grouped by reading patterns",
        },
        "files": [],
    }

    # Find all generated JSON files
    for json_file in output_dir.rglob("*.json"):
        if json_file.name != "manifest.json":
            relative_path = json_file.relative_to(output_dir)
            manifest["files"].append(
                {"path": str(relative_path), "size_bytes": json_file.stat().st_size}
            )

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate specialized kanji lookup files"
    )
    parser.add_argument("--db", "-d", required=True, help="SQLite database path")
    parser.add_argument("--output", "-o", default="lookups", help="Output directory")
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["grades", "jlpt", "frequency", "readings", "all"],
        default=["all"],
        help="Categories to generate",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.Connection(args.db)

    categories = args.categories
    if "all" in categories:
        categories = ["grades", "jlpt", "frequency", "readings"]

    print(f"Generating lookup files in {output_dir}")

    if "grades" in categories:
        print("\n📚 Generating grade-level lookups...")
        generate_grade_lookups(conn, output_dir)

    if "jlpt" in categories:
        print("\n🎯 Generating JLPT-level lookups...")
        generate_jlpt_lookups(conn, output_dir)

    if "frequency" in categories:
        print("\n📊 Generating frequency-based lookups...")
        generate_frequency_lookups(conn, output_dir)

    if "readings" in categories:
        print("\n🔤 Generating reading pattern lookups...")
        generate_reading_patterns(conn, output_dir)

    print("\n📋 Generating manifest...")
    generate_manifest(output_dir)

    conn.close()

    print("\n✅ Lookup generation complete!")
    print(f"📁 Files saved to: {output_dir}")


if __name__ == "__main__":
    main()
