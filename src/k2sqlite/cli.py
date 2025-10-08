import argparse
import json
import random
import sqlite3
import hashlib
import os
from pathlib import Path
from .builder import build_sqlite


def export_data(
    db_path: Path, view: str, format: str, output_path: Path | None, limit: int | None
):
    """Export     # Copy database to output dir if different locations
    import shutil

    db_dest = output_dir / "kanjidic2.sqlite"
    if db_path.resolve() != db_dest.resolve():
        shutil.copy2(db_path, db_dest)
        print(f"Copied database to {db_dest}")
    else:
        print(f"Database already in place: {db_dest}")

    # Generate manifest with quality metrics
    manifest = generate_manifest(output_dir, db_path, version)

    print("✅ Quiz artifacts generated:")
    print(f"📁 Database: {db_dest}")
    print(f"📊 Quality checks passed: {all(v == 0 for v in manifest['quality_checks'].values())}")
    print(f"🎯 JLPT levels available: {list(manifest['jlpt_levels'].keys())}")
    print("🛠️ App contract SQL queries included in manifest.json")ase view to CSV or JSON."""
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


def generate_lookup_maps(db_path: Path, output_dir: Path):
    """Generate char-to-meaning and char-to-reading lookup maps."""
    conn = sqlite3.connect(db_path)

    # Char to meaning map
    meanings_map = {}
    for (literal,) in conn.execute("SELECT literal FROM kanji"):
        meanings = [
            row[0]
            for row in conn.execute(
                "SELECT meaning FROM kanji_meaning WHERE literal=? AND lang='en'",
                (literal,),
            )
        ]
        meanings_map[literal] = meanings

    with open(output_dir / "map_char_to_meaning.json", "w", encoding="utf-8") as f:
        json.dump(meanings_map, f, ensure_ascii=False, indent=2)

    # Char to readings map
    readings_map = {}
    for (literal,) in conn.execute("SELECT literal FROM kanji"):
        on_readings = [
            row[0]
            for row in conn.execute(
                "SELECT reading FROM kanji_reading WHERE literal=? AND type='on'",
                (literal,),
            )
        ]
        kun_readings = [
            row[0]
            for row in conn.execute(
                "SELECT reading FROM kanji_reading WHERE literal=? AND type='kun'",
                (literal,),
            )
        ]
        readings_map[literal] = {"on": on_readings, "kun": kun_readings}

    with open(output_dir / "map_char_to_readings.json", "w", encoding="utf-8") as f:
        json.dump(readings_map, f, ensure_ascii=False, indent=2)

    conn.close()
    print("Generated lookup maps")


def generate_mcq_samples(db_path: Path, output_dir: Path, kanji_limit: int = 200):
    """Generate sample MCQ files for artifacts."""
    conn = sqlite3.connect(db_path)

    # Get kanji data for MCQ generation (similar to generate_mcq.py logic)
    query = """
    SELECT k.literal, k.freq,
           GROUP_CONCAT(km.meaning, ';') as meanings,
           GROUP_CONCAT(CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun_readings,
           GROUP_CONCAT(CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on_readings
    FROM kanji k
    LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
    LEFT JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE k.freq IS NOT NULL
    GROUP BY k.literal
    ORDER BY k.freq
    LIMIT ?
    """

    kanji_data = []
    for row in conn.execute(query, (kanji_limit,)):
        literal, freq, meanings, _, _ = row
        meanings_list = [m.strip() for m in (meanings or "").split(";") if m.strip()]

        if meanings_list:  # Only include kanji with meanings
            kanji_data.append(
                {"literal": literal, "meanings": meanings_list, "freq": freq}
            )

    # Generate sample questions (simplified version)
    sample_questions = []
    used_meanings = set()

    for i, kanji in enumerate(kanji_data[:50]):  # Generate 50 sample questions
        if not kanji["meanings"]:
            continue

        meaning = kanji["meanings"][0]
        if meaning in used_meanings:
            continue
        used_meanings.add(meaning)

        # Generate distractors
        distractors = []
        attempts = 0
        while len(distractors) < 3 and attempts < 10:
            distractor_kanji = random.choice(kanji_data)
            if (
                distractor_kanji["literal"] != kanji["literal"]
                and distractor_kanji["meanings"]
                and distractor_kanji["meanings"][0] not in distractors
                and distractor_kanji["meanings"][0] != meaning
            ):
                distractors.append(distractor_kanji["meanings"][0])
            attempts += 1

        if len(distractors) >= 3:
            choices = [meaning] + distractors[:3]
            random.shuffle(choices)

            sample_questions.append(
                {
                    "type": "char_to_meaning",
                    "question": f"What does {kanji['literal']} mean?",
                    "choices": choices,
                    "correct": meaning,
                    "explanation": f"The kanji {kanji['literal']} means '{meaning}'",
                }
            )

    # Save sample MCQ file
    mcq_file = output_dir / "sample_mcq.json"
    with open(mcq_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "description": "Sample MCQ questions from top frequent kanji",
                "count": len(sample_questions),
                "questions": sample_questions,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    conn.close()
    print(f"Generated {len(sample_questions)} sample MCQ questions")


def generate_manifest(output_dir: Path, db_path: Path, version: str = None):
    """Generate manifest.json with database quality metrics."""
    import sqlite3

    # Get database statistics
    conn = sqlite3.connect(db_path)

    # Level distribution
    level_stats = {}
    for row in conn.execute("""
        SELECT lvl, COUNT(*) as total,
               COUNT(CASE WHEN freq IS NOT NULL THEN 1 END) as with_freq
        FROM kanji_seed GROUP BY lvl ORDER BY lvl DESC
    """):
        level_name = {5: 'N5', 4: 'N4', 3: 'N3', 2: 'N2', 1: 'N1'}[row[0]]
        level_stats[level_name] = {"total": row[1], "with_frequency": row[2]}

    # Quality checks
    quality_checks = {}

    # Check for missing meanings
    no_meaning = conn.execute("SELECT COUNT(*) FROM kanji_seed WHERE main_meaning IS NULL OR main_meaning = ''").fetchone()[0]
    quality_checks["kanji_without_meaning"] = no_meaning

    # Check for duplicates
    duplicates = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT literal, COUNT(*) FROM kanji_seed GROUP BY literal HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    quality_checks["duplicate_literals"] = duplicates

    conn.close()

    def sha256_file(filepath):
        import hashlib
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    manifest = {
        "version": version or "local-build",
        "database": {
            "file": "kanjidic2.sqlite",
            "bytes": db_path.stat().st_size,
            "sha256": sha256_file(db_path)
        },
        "jlpt_levels": level_stats,
        "quality_checks": quality_checks,
        "views": ["kanji_seed", "distractor_pool", "kanji_priority"],
        "app_contract": {
            "pick_random_kanji": "SELECT * FROM kanji_seed WHERE lvl=? ORDER BY RANDOM() LIMIT 1",
            "get_distractors": "SELECT meaning FROM distractor_pool WHERE lvl=? AND meaning<>? ORDER BY RANDOM() LIMIT 3"
        }
    }

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated manifest.json with quality metrics")
    return manifest


def generate_artifacts(
    db_path: Path, output_dir: Path, seed_limit: int = 200, version: str = None
):
    """Generate quiz-focused production artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating quiz-focused artifacts in {output_dir}")

    # Copy database to output dir if different locations
    import shutil

    db_dest = output_dir / "kanjidic2.sqlite"
    if db_path.resolve() != db_dest.resolve():
        shutil.copy2(db_path, db_dest)
        print(f"Copied database to {db_dest}")
    else:
        print(f"Database already in place: {db_dest}")

    # Generate manifest with quality metrics
    manifest = generate_manifest(output_dir, db_path, version)

    print("✅ Quiz artifacts generated:")
    print(f"📁 Database: {db_dest}")
    print(f"📊 Quality checks passed: {all(v == 0 for v in manifest['quality_checks'].values())}")
    print(f"🎯 JLPT levels available: {list(manifest['jlpt_levels'].keys())}")
    print("� App contract SQL queries included in manifest.json")


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

    ap_artifacts = sub.add_parser("artifacts", help="Generate all production artifacts")
    ap_artifacts.add_argument(
        "--db", "-d", type=Path, required=True, help="SQLite database path"
    )
    ap_artifacts.add_argument(
        "--output-dir", "-o", type=Path, default=Path("output"), help="Output directory"
    )
    ap_artifacts.add_argument(
        "--seed-limit",
        "-l",
        type=int,
        default=200,
        help="Number of kanji in seed files",
    )
    ap_artifacts.add_argument(
        "--version", "-v", type=str, help="Version string for manifest"
    )

    args = ap.parse_args()
    if args.cmd == "build":
        total = build_sqlite(args.input, args.db, batch_size=args.batch)
        print(f"Inserted {total} characters into {args.db}")
    elif args.cmd == "export":
        export_data(args.db, args.view, args.format, args.output, args.limit)
    elif args.cmd == "artifacts":
        generate_artifacts(args.db, args.output_dir, args.seed_limit, args.version)
