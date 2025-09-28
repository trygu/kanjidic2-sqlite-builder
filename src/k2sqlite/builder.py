from __future__ import annotations
import sqlite3
from xml.etree import ElementTree as ET
from pathlib import Path


def text(el):
    return el.text.strip() if el is not None and el.text else ""


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
            jlpt INTEGER
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


def _insert_character_data(cur, rec):
    """Insert character data into database tables."""
    literal = rec["literal"]

    # Insert main kanji record
    cur.execute(
        "INSERT OR REPLACE INTO kanji(literal, grade, stroke_count, freq, jlpt) VALUES (?,?,?,?,?)",
        (literal, rec["grade"], rec["stroke_count"], rec["freq"], rec["jlpt"]),
    )

    # Insert related data
    for radical in rec["radicals"]:
        cur.execute(
            "INSERT INTO kanji_radical(literal, rad_value) VALUES (?,?)",
            (literal, radical),
        )

    for reading in rec["readings_on"]:
        cur.execute(
            "INSERT INTO kanji_reading(literal, type, reading) VALUES (?,?,?)",
            (literal, "on", reading),
        )

    for reading in rec["readings_kun"]:
        cur.execute(
            "INSERT INTO kanji_reading(literal, type, reading) VALUES (?,?,?)",
            (literal, "kun", reading),
        )

    for meaning in rec["meanings_en"]:
        cur.execute(
            "INSERT INTO kanji_meaning(literal, lang, meaning) VALUES (?,?,?)",
            (literal, "en", meaning),
        )

    for vtype, value in rec["variants"]:
        cur.execute(
            "INSERT INTO kanji_variant(literal, var_type, value) VALUES (?,?,?)",
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
