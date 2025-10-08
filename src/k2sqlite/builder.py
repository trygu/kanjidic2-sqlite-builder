from __future__ import annotations
import sqlite3
from xml.etree import ElementTree as ET
from pathlib import Path


def text(el):
    return el.text.strip() if el is not None and el.text else ""


def _dedup_preserve(items):
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA temp_store=MEMORY;
        PRAGMA foreign_keys=OFF;

        CREATE TABLE IF NOT EXISTS kanji(
            literal TEXT PRIMARY KEY,
            grade INTEGER,
            stroke_count INTEGER,
            freq INTEGER,
            jlpt INTEGER  -- Modern JLPT levels: 1=N1, 2=N2, 3=N3, 4=N4, 5=N5
        );

        CREATE TABLE IF NOT EXISTS kanji_radical(
            literal TEXT NOT NULL,
            rad_value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kanji_reading(
            literal TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('on','kun')),
            reading TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kanji_meaning(
            literal TEXT NOT NULL,
            lang TEXT NOT NULL DEFAULT 'en',
            meaning TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kanji_variant(
            literal TEXT NOT NULL,
            var_type TEXT NOT NULL,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_kanji_freq ON kanji(freq);
        CREATE INDEX IF NOT EXISTS idx_reading ON kanji_reading(reading);
        CREATE INDEX IF NOT EXISTS idx_meaning ON kanji_meaning(meaning);

        -- Unique indexes to prevent duplicates
        CREATE UNIQUE INDEX IF NOT EXISTS ux_reading ON kanji_reading(literal, type, reading);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_meaning ON kanji_meaning(literal, meaning);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_radical ON kanji_radical(literal, rad_value);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_variant ON kanji_variant(literal, var_type, value);

        -- Priority view: sorted by frequency -> grade -> jlpt with aggregated data
        CREATE VIEW IF NOT EXISTS kanji_priority AS
        SELECT
            k.literal,
            k.grade,
            k.stroke_count,
            k.freq,
            k.jlpt,
            (SELECT m.meaning
             FROM kanji_meaning m
             WHERE m.literal = k.literal AND m.lang = 'en'
             LIMIT 1) as main_meaning,
            COALESCE((SELECT GROUP_CONCAT(r.reading, '・')
                     FROM kanji_reading r
                     WHERE r.literal = k.literal AND r.type = 'on'), '') as on_prime,
            COALESCE((SELECT GROUP_CONCAT(r.reading, '・')
                     FROM kanji_reading r
                     WHERE r.literal = k.literal AND r.type = 'kun'), '') as kun_prime,
            -- Priority score: freq (lower=better), then grade, then jlpt
            CASE
                WHEN k.freq IS NOT NULL THEN k.freq
                WHEN k.grade IS NOT NULL THEN 3000 + k.grade
                WHEN k.jlpt IS NOT NULL THEN 4000 + k.jlpt
                ELSE 9999
            END as priority_score
        FROM kanji k
        ORDER BY priority_score, k.literal;

        -- App contract: kanji_seed view for quiz generation
        CREATE VIEW kanji_seed AS
        SELECT
            k.literal,
            k.jlpt as lvl,  -- N5=5, N4=4, N3=3, N2=2, N1=1
            k.freq,
            k.grade,
            (SELECT m.meaning
             FROM kanji_meaning m
             WHERE m.literal = k.literal AND m.lang = 'en'
             LIMIT 1) as main_meaning,
            COALESCE((SELECT GROUP_CONCAT(r.reading, '・')
                     FROM kanji_reading r
                     WHERE r.literal = k.literal AND r.type = 'on'), '') as on_prime,
            COALESCE((SELECT GROUP_CONCAT(r.reading, '・')
                     FROM kanji_reading r
                     WHERE r.literal = k.literal AND r.type = 'kun'), '') as kun_prime
        FROM kanji k
        WHERE k.jlpt IS NOT NULL
        AND EXISTS (SELECT 1 FROM kanji_meaning m WHERE m.literal = k.literal AND m.lang = 'en');

        -- App contract: distractor pool for quiz generation
        CREATE VIEW distractor_pool AS
        SELECT
            k.jlpt as lvl,  -- N5=5, N4=4, N3=3, N2=2, N1=1
            m.meaning
        FROM kanji k
        JOIN kanji_meaning m ON k.literal = m.literal
        WHERE k.jlpt IS NOT NULL AND m.lang = 'en';

        -- Performance indexes for app queries
        CREATE INDEX IF NOT EXISTS idx_kanji_seed_lvl ON kanji(jlpt) WHERE jlpt IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_kanji_seed_literal ON kanji(literal);
        CREATE INDEX IF NOT EXISTS idx_meaning_for_distractor ON kanji_meaning(meaning) WHERE lang = 'en';
        CREATE INDEX IF NOT EXISTS idx_seed_lvl ON kanji_seed(lvl);
        CREATE INDEX IF NOT EXISTS idx_seed_lit ON kanji_seed(literal);
        CREATE INDEX IF NOT EXISTS idx_pool_lvl ON distractor_pool(lvl);

        -- Finalize database with PRAGMA and ANALYZE
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        VACUUM;
        ANALYZE;
        """
    )
    conn.commit()


def _create_empty_record():
    """Create an empty kanji record structure."""
    return {
        "literal": "",
        "grade": None,
        "stroke_count": None,
        "freq": None,
        "jlpt": None,
        "radicals": [],
        "readings_on": [],
        "readings_kun": [],
        "meanings_en": [],
        "variants": [],
    }


def _parse_integer_field(elem, current_value=None):
    """Parse integer field from XML element, with optional max comparison."""
    if elem.text is None:
        return current_value
    text = elem.text.strip()
    if not text.isdigit():
        return current_value

    value = int(text)
    if current_value is None:
        return value
    return max(current_value, value)


def _process_start_element(tag, rec):
    """Process XML start elements."""
    if tag == "character":
        return _create_empty_record()
    return rec


def _process_end_element(tag, elem, rec):
    """Process XML end elements and update record."""
    if rec is None:
        return rec

    if tag == "literal":
        rec["literal"] = text(elem)
    elif tag == "grade":
        rec["grade"] = _parse_integer_field(elem)
    elif tag == "stroke_count":
        rec["stroke_count"] = _parse_integer_field(elem, rec["stroke_count"])
    elif tag == "freq":
        rec["freq"] = _parse_integer_field(elem)
    elif tag == "jlpt":
        rec["jlpt"] = _parse_integer_field(elem)
    elif tag == "rad_value":
        _process_radical(elem, rec)
    elif tag == "reading":
        _process_reading(elem, rec)
    elif tag == "meaning":
        _process_meaning(elem, rec)
    elif tag == "variant":
        _process_variant(elem, rec)

    return rec


def _process_radical(elem, rec):
    """Process radical element."""
    if elem.get("rad_type") == "classical":
        value = text(elem)
        if value:
            rec["radicals"].append(value)


def _process_reading(elem, rec):
    """Process reading element."""
    rtype = elem.get("r_type")
    value = text(elem)
    if not value:
        return

    if rtype == "ja_on":
        rec["readings_on"].append(value)
    elif rtype == "ja_kun":
        rec["readings_kun"].append(value)


def _process_meaning(elem, rec):
    """Process meaning element."""
    lang = elem.get("m_lang")
    value = text(elem)
    if value and (lang is None or lang == "en"):
        rec["meanings_en"].append(value)


def _process_variant(elem, rec):
    """Process variant element."""
    vtype = elem.get("var_type") or "unknown"
    value = text(elem)
    if value:
        rec["variants"].append((vtype, value))


def _calculate_modern_jlpt(grade, freq, old_jlpt):
    """
    Calculate modern JLPT level (1=N1, 2=N2, 3=N3, 4=N4, 5=N5) based on:
    - grade: School grade level (1-6)
    - freq: Frequency rank (lower numbers = more common)
    - old_jlpt: Old JLPT system from XML (1-4, where 1=hardest)
    """
    # Primary: Use old JLPT data if available
    if old_jlpt == 4:
        return 5  # N5 (easiest)
    elif old_jlpt == 3:
        return 4  # N4
    elif old_jlpt == 2:
        return 3  # N3
    elif old_jlpt == 1:
        return 2  # N2

    # Secondary: Very high frequency + low grade = N5
    if freq is not None and freq <= 200 and grade in (1, 2):
        return 5

    # Secondary: Common kanji in elementary grades = N4
    if freq is not None and freq <= 500 and grade in (3, 4):
        return 4

    # Secondary: Less common but still jouyou = N3
    if freq is not None and freq <= 1000 and grade in (5, 6):
        return 3

    # Everything else = N1 (hardest)
    return 1


def _insert_character_data(cur, rec):
    """Insert character data into database tables."""
    literal = rec["literal"]

    # Calculate modern JLPT level from old JLPT data
    jlpt = _calculate_modern_jlpt(rec["grade"], rec["freq"], rec["jlpt"])

    # Insert main kanji record
    cur.execute(
        "INSERT OR REPLACE INTO kanji(literal, grade, stroke_count, freq, jlpt) VALUES (?,?,?,?,?)",
        (
            literal,
            rec["grade"],
            rec["stroke_count"],
            rec["freq"],
            jlpt,
        ),
    )

    # Dedup and insert related data
    for radical in _dedup_preserve(rec["radicals"]):
        cur.execute(
            "INSERT OR IGNORE INTO kanji_radical(literal, rad_value) VALUES (?,?)",
            (literal, radical),
        )

    for reading in _dedup_preserve(rec["readings_on"]):
        cur.execute(
            "INSERT OR IGNORE INTO kanji_reading(literal, type, reading) VALUES (?,?,?)",
            (literal, "on", reading),
        )

    for reading in _dedup_preserve(rec["readings_kun"]):
        cur.execute(
            "INSERT OR IGNORE INTO kanji_reading(literal, type, reading) VALUES (?,?,?)",
            (literal, "kun", reading),
        )

    for meaning in _dedup_preserve(rec["meanings_en"]):
        cur.execute(
            "INSERT OR IGNORE INTO kanji_meaning(literal, lang, meaning) VALUES (?,?,?)",
            (literal, "en", meaning),
        )

    for vtype, value in _dedup_preserve(rec["variants"]):
        cur.execute(
            "INSERT OR IGNORE INTO kanji_variant(literal, var_type, value) VALUES (?,?,?)",
            (literal, vtype, value),
        )


def build_sqlite(xml_path: Path, db_path: Path, batch_size: int = 500) -> int:
    """Build SQLite database from KANJIDIC2 XML file."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    ensure_schema(conn)
    cur = conn.cursor()

    context = ET.iterparse(str(xml_path), events=("start", "end"))
    _, root = next(context)

    count = 0
    batch = 0
    rec = None

    for event, elem in context:
        tag = elem.tag

        if event == "start":
            rec = _process_start_element(tag, rec)
        elif event == "end":
            if tag == "character" and rec is not None and rec["literal"]:
                _insert_character_data(cur, rec)

                batch += 1
                count += 1
                if batch >= batch_size:
                    conn.commit()
                    batch = 0

                root.clear()
                rec = None
            else:
                rec = _process_end_element(tag, elem, rec)

    if batch:
        conn.commit()
    conn.close()
    return count
