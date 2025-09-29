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


def generate_manifest(output_dir: Path, version: str = None):
    """Generate manifest.json with file checksums."""
    artifact_files = [
        "kanji_seed.csv",
        "kanji_seed.json",
        "map_char_to_meaning.json",
        "map_char_to_readings.json",
        "kanjidic2.sqlite",
    ]

    def sha256_file(filepath):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    manifest = {"version": version or "local-build", "files": []}

    for filename in artifact_files:
        filepath = output_dir / filename
        if filepath.exists():
            manifest["files"].append(
                {
                    "name": filename,
                    "bytes": filepath.stat().st_size,
                    "sha256": sha256_file(filepath),
                }
            )

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated manifest.json with {len(manifest['files'])} files")


def generate_artifacts(
    db_path: Path, output_dir: Path, seed_limit: int = 200, version: str = None
):
    """Generate all production artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating artifacts in {output_dir}")

    # Copy database to output dir
    import shutil

    db_dest = output_dir / "kanjidic2.sqlite"
    shutil.copy2(db_path, db_dest)
    print(f"Copied database to {db_dest}")

    # Generate seed files
    seed_csv = output_dir / "kanji_seed.csv"
    seed_json = output_dir / "kanji_seed.json"

    export_data(db_path, "kanji_seed", "csv", seed_csv, seed_limit)
    export_data(db_path, "kanji_seed", "json", seed_json, seed_limit)

    # Generate lookup maps
    generate_lookup_maps(db_path, output_dir)

    # Generate MCQ files
    generate_mcq_samples(db_path, output_dir, seed_limit)

    # Generate manifest
    generate_manifest(output_dir, version)

    print(f"✅ All artifacts generated in {output_dir}")
    print(f"📊 Seed files contain {seed_limit} top kanji")


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
